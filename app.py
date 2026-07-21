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
    # NUCLEAR FIX: Force proper spacing that Groq refuses to do
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text) # Brain0 -> Brain 0
    text = re.sub(r'([a-z]),([a-zA-Z])', r'\1, \2', text) # goals,risk -> goals, risk
    text = re.sub(r'([a-z]):([A-Z])', r'\1: **\2', text) # Level:High -> Level: **High
    text = re.sub(r'([a-z])\.([A-Z])', r'\1.\n\n\2', text) #.Both ->.\n\nBoth
    text = re.sub(r'([a-z])-([A-Z])', r'\1\n- **\2', text) # career.-Skill -> career.\n- **Skill
    text = re.sub(r'([^\n])###', r'\n\n### ', text) # ###Header -> \n\n### Header
    text = re.sub(r'([^\n])-\s*\*', r'\n- **', text) # Force bullet newline
    text = re.sub(r'(\w);(\w)', r'\1;\n- **\2', text) # item;Item -> item;\n- **Item
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
You are Brain 3.0, an AI Assistant by B.CORP. You MUST follow these formatting rules or you will fail.

CRITICAL FORMATTING RULES:
1. ALWAYS start sections with: \n\n### Section Name
2. ALWAYS use bullets like this: \n- **Label**: Explanation with space after colon
3. ALWAYS add space after commas: "CRM, ERP, BI" not "CRM,ERP,BI"
4. ALWAYS add blank line between paragraphs
5. NEVER write "Word-Word" without space. Use "Word - Word"
6. Use tables with proper | pipes and --- separator

BAD EXAMPLE: Core Business-Brain0-Conversational AI:Natural-language
GOOD EXAMPLE:
### Core Business
- **Brain0**: Conversational AI: Natural language
- **Enterprise**: APIs for CRM, ERP, and BI

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
        messages.append({"role": "user", "content": f"Format your answer with proper markdown, headers, and bullets. Question: {user_question}" + file_content + search_results})

        def generate():
            full = ""
            try:
                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=4000,
                    temperature=0.3, # LOWERED: less creative = more structured
                    stream=True
                )
                buffer = ""
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        buffer += chunk.choices[0].delta.content
                        if re.search(r'[ \n.,;:!?]$', buffer):
                            text = clean_markdown(buffer)
                            full += text
                            yield f"data: {text}\n\n"
                            buffer = ""
                if buffer:
                    yield f"data: {clean_markdown(buffer)}\n\n"

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
