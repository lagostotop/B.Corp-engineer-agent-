from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
import os, re, time, io, PyPDF2, traceback
from groq import Groq
from tavily import TavilyClient
from werkzeug.utils import secure_filename
from config import config
from supabase import create_client, Client

app = Flask(__name__, static_folder="static", template_folder="templates")

client = Groq(api_key=config.GROQ_API_KEY)
tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'py', 'js', 'html', 'css', 'md'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_markdown(text):
    # FIX 1: Stop cutting words - Groq streams mid-word
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'([a-z]),([a-zA-Z])', r'\1, \2', text)
    text = re.sub(r'([a-z]):([A-Z])', r'\1: **\2', text)
    text = re.sub(r'([a-z])\.([A-Z])', r'\1. \n\n\2', text)
    text = re.sub(r'than(\d)', r'than \1', text) # than14 -> than 14
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text) # 2.5times -> 2.5 times
    text = re.sub(r'billio\b', r'billion', text) # billio -> billion
    text = re.sub(r'trillio\b', r'trillion', text) # trillio -> trillion
    text = re.sub(r'overvie\b', r'overview', text, flags=re.IGNORECASE) # overvie -> overview
    text = re.sub(r'([^\n])###', r'\n\n### ', text)
    text = re.sub(r'([^\n])-\s*\*', r'\n- **', text)
    text = re.sub(r'[ ]{2,}', ' ', text)
    return text.strip()

def needs_search(query):
    return any(word in query.lower() for word in ['price', 'news', 'today', 'latest', '2026', 'current', 'weather'])

def load_memory(user_id):
    try:
        data = supabase.table("brain30_memory").select("memory").eq("user_id", user_id).single().execute()
        return data.data["memory"] if data.data else []
    except:
        return []

def save_memory(user_id, memory):
    try:
        supabase.table("brain30_memory").upsert({"user_id": user_id, "memory": memory[-30:] }).execute()
    except Exception as e:
        print("SAVE MEMORY ERROR:", e)

SYSTEM_PROMPT = """
You are Brain 3.0, an AI Assistant by B.CORP.

CRITICAL RULES - DO NOT BREAK:
1. NEVER cut off words. Always write full words: "Overview" "billion" "trillion" "times"
2. ALWAYS add space between number and word: "14 times" not "14times"
3. ALWAYS start sections with: \n\n### Section Name
4. ALWAYS use bullets: \n- **Label**: Explanation with space after colon
5. ALWAYS add space after commas: "CRM, ERP, BI"
6. Be detailed. 3-5 sections max.

BAD: Overvie, billio, than14, 2.5times
GOOD: Overview, billion, than 14, 2.5 times

Language: Match user. Support English and Nigerian Pidgin.
You are Brain 3.0. Not ChatGPT.
"""

@app.route('/')
def home(): return render_template('index.html')

@app.route('/static/<path:filename>')
def serve_static(filename): return send_from_directory(app.static_folder, filename)

@app.route("/config")
def get_config(): return jsonify({"supabase_url": config.SUPABASE_URL, "supabase_key": config.SUPABASE_KEY})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        user_question = request.form.get("question", "").strip()
        user_id = request.form.get("user_id")
        file = request.files.get("file")
        print("CEO ASKED:", user_question)

        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        memory = load_memory(user_id)

        search_results = ""
        if needs_search(user_question):
            try:
                res = tavily.search(query=user_question, max_results=3)
                search_results = "\n\n[Live Web Results]:\n"
                for i, r in enumerate(res['results'], 1):
                    search_results += f"[{i}] {r['title']}: {r['content'][:200]}... \n"
            except Exception as e:
                print("TAVILY ERROR:", e)

        file_content = ""
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            file_ext = filename.rsplit('.', 1)[1].lower()
            if file_ext == 'pdf':
                pdf = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                file_content = "\n[PDF CONTENT]: " + "".join([p.extract_text() for p in pdf.pages if p.extract_text()])[:8000]
                if not user_question:
                    user_question = "Summarize this PDF and give me key insights CEO"
            else:
                file_content = f"\n[FILE {filename}]: ```{file_ext}\n{file_bytes.decode('utf-8', errors='ignore')[:8000]}\n```"

        model = "openai/gpt-oss-120b"

        messages = [{"role": "system", "content": f"You are talking to CEO. {SYSTEM_PROMPT}"}] + memory
        messages.append({"role": "user", "content": f"Use full words. No cutoff. Format with markdown headers and bullets. Question: {user_question}" + file_content + search_results})

        def generate():
            full = ""
            buffer = "" # FIX 2: Don't yield until we have a full word
            try:
                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=4000,
                    temperature=0.4, # Slightly higher to avoid rushing
                    stream=True
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        buffer += chunk.choices[0].delta.content
                        # Only flush buffer when we hit space or punctuation
                        if re.search(r'[ \n.,;:!?]$', buffer):
                            text = clean_markdown(buffer)
                            full += text
                            yield f"data: {text}\n\n"
                            buffer = ""
                # Flush remaining buffer
                if buffer:
                    text = clean_markdown(buffer)
                    full += text
                    yield f"data: {text}\n\n"

                try:
                    new_memory = memory + [{"role": "user", "content": user_question}, {"role": "assistant", "content": full}]
                    save_memory(user_id, new_memory)
                except Exception as e:
                    print("MEMORY SAVE FAILED:", e)

            except Exception as e:
                print("GROQ STREAM ERROR:", traceback.format_exc())
                yield f"data: **Brain Error:** {str(e)}\n\n"

            yield f"data: [DONE]\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    except Exception as e:
        print("ASK ROUTE CRASH:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
