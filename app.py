from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
import os, re, time, io, PyPDF2, traceback
from groq import Groq
from tavily import TavilyClient
from werkzeug.utils import secure_filename
from config import config
from supabase import create_client, Client
from datetime import datetime

app = Flask(__name__, static_folder="static", template_folder="templates")

client = Groq(api_key=config.GROQ_API_KEY)
tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'py', 'js', 'html', 'css', 'md'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_markdown(text):
    # NUCLEAR FIX v3.4.13: Anti-join words
    text = re.sub(r'([a-z])(\d)', r'\1 \2', text)
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'([A-Z])([A-Z][a-z])', r'\1 \2', text)
    text = re.sub(r'(\*\*)([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'([a-z])(\*\*)', r'\1 \2', text)
    text = re.sub(r'([a-z]):([A-Z])', r'\1: **\2', text)
    text = re.sub(r'([a-z]),([a-zA-Z])', r'\1, \2', text)
    text = re.sub(r'([a-z])\.([A-Z])', r'\1. \n\n\2', text)
    text = re.sub(r'than(\d)', r'than \1', text)
    text = re.sub(r'billio\b', r'billion', text)
    text = re.sub(r'trillio\b', r'trillion', text)
    text = re.sub(r'overvie\b', r'overview', text, flags=re.IGNORECASE)
    text = re.sub(r'([^\n])###', r'\n\n### ', text)
    text = re.sub(r'([^\n])-\s*', r'\n- **', text)
    text = re.sub(r'[ ]{2,}', ' ', text)
    return text.strip()

def needs_search(query):
    return any(word in query.lower() for word in ['price', 'news', 'today', 'latest', '2026', 'current', 'weather'])

def load_memory(user_id):
    try:
        res = supabase.table("brain30_memory").select("memory").eq("user_id", user_id).single().execute()
        if res.data and res.data.get("memory"):
            return res.data["memory"]
        return []
    except Exception as e:
        print("LOAD MEMORY:", e)
        return []

def save_memory(user_id, memory):
    try:
        supabase.table("brain30_memory").upsert({
            "user_id": user_id,
            "memory": memory[-20:],
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print("SAVE MEMORY ERROR:", e)

SYSTEM_PROMPT = """
You are Brain 3.0 by B.CORP. You are the most intelligent AI assistant in 2026.

PERSONALITY:
1. Professional, clear, and helpful. Talk like a world-class expert.
2. For greetings like "Hi", "Hello": Reply warmly in 1-2 sentences. "Hello CEO. How can I help you today?"
3. For questions: Give direct, accurate answers with proper structure.
4. For comparisons: Give 1 winner with 2-3 key reasons. No hedging.
5. Max 120 words. Use markdown: ### Headers and - **Bold bullets**.

IRON RULES:
1. NO JOINED WORDS: "cloud native" NOT "cloudnative". "dedicated team" NOT "dedicatedteam"
2. SPACING: "impact: **Cloud" NOT "impact:cloud"
3. FORMATTING: Always use proper spaces after punctuation.
4. TONE: Confident, professional, zero fluff. You are built by B.CORP.

Language: Match user. Support English and Nigerian Pidgin.
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
                file_content = "\n[PDF CONTENT]: " + "".join([p.extract_text() for p in pdf.pages if p.extract_text()])[:6000]
                if not user_question:
                    user_question = "Summarize this document in 3 key points"
            else:
                file_content = f"\n[FILE {filename}]: ```{file_ext}\n{file_bytes.decode('utf-8', errors='ignore')[:6000]}\n```"

        model = "openai/gpt-oss-120b"

        messages = [{"role": "system", "content": f"You are assisting the CEO of B.CORP. {SYSTEM_PROMPT}"}] + memory
        messages.append({"role": "user", "content": f"Answer professionally. Use proper spacing. No joined words. Max 120 words. Question: {user_question}" + file_content + search_results})

        def generate():
            full = ""
            buffer = ""
            try:
                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=600,
                    temperature=0.3, # Slightly higher for natural conversation
                    stream=True
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        if content.strip():
                            buffer += content
                            buffer = re.sub(r'([a-z])(\d)', r'\1 \2', buffer)
                            buffer = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', buffer)
                            buffer = re.sub(r'([a-z])([A-Z])', r'\1 \2', buffer)
                            buffer = re.sub(r'([A-Z])([A-Z][a-z])', r'\1 \2', buffer)
                            buffer = re.sub(r'([a-z]):([A-Z])', r'\1: **\2', buffer)

                            if len(buffer) > 60:
                                chunk_clean = clean_markdown(buffer)
                                if chunk_clean.strip():
                                    full += chunk_clean
                                    yield f"data: {chunk_clean}\n\n"
                                buffer = ""

                if buffer:
                    chunk_clean = clean_markdown(buffer)
                    if chunk_clean.strip():
                        full += chunk_clean
                        yield f"data: {chunk_clean}\n\n"

                if not full.strip():
                    yield f"data: I apologize, I couldn't generate a response. Please try again.\n"

                try:
                    if user_question and full:
                        new_memory = memory + [{"role": "user", "content": user_question}, {"role": "assistant", "content": full}]
                        save_memory(user_id, new_memory)
                except Exception as e:
                    print("MEMORY SAVE FAILED:", e)

            except Exception as e:
                print("GROQ STREAM ERROR:", traceback.format_exc())
                yield f"data: **Brain 3.0 Error:** {str(e)}\n\n"

            yield f"data: [DONE]\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    except Exception as e:
        print("ASK ROUTE CRASH:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
