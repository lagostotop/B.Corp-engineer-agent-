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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_markdown(text):
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

# ===== DAY 2: NEW DB FUNCTIONS =====
def create_chat(user_id, first_message):
    title = first_message[:50] + "..." if len(first_message) > 50 else first_message
    res = supabase.table("chats").insert({"user_id": user_id, "title": title}).execute()
    return res.data[0]['id']

def load_chats(user_id):
    res = supabase.table("chats").select("*").eq("user_id", user_id).order("updated_at", desc=True).limit(20).execute()
    return res.data

def load_messages(chat_id):
    res = supabase.table("messages").select("*").eq("chat_id", chat_id).order("created_at").execute()
    return res.data

def save_message(chat_id, role, content):
    if not content.strip(): return # FIX: Don't save empty messages
    supabase.table("messages").insert({"chat_id": chat_id, "role": role, "content": content}).execute()
    supabase.table("chats").update({"updated_at": datetime.utcnow().isoformat()}).eq("id", chat_id).execute()

def delete_chat(chat_id):
    supabase.table("chats").delete().eq("id", chat_id).execute()

def rename_chat(chat_id, new_title):
    supabase.table("chats").update({"title": new_title}).eq("id", chat_id).execute()

@app.route('/')
def home(): return render_template('index.html')

@app.route('/static/<path:filename>')
def serve_static(filename): return send_from_directory(app.static_folder, filename)

@app.route("/config")
def get_config(): return jsonify({"supabase_url": config.SUPABASE_URL, "supabase_key": config.SUPABASE_KEY})

# ===== DAY 3: SIDEBAR ROUTES =====
@app.route("/chats", methods=["GET"])
def get_chats():
    user_id = request.args.get("user_id")
    if not user_id: return jsonify([])
    return jsonify(load_chats(user_id))

@app.route("/chat/<chat_id>", methods=["GET"])
def get_chat(chat_id):
    return jsonify(load_messages(chat_id))

@app.route("/chat/delete", methods=["POST"])
def delete():
    chat_id = request.json.get("chat_id")
    delete_chat(chat_id)
    return jsonify({"success": True})

@app.route("/chat/rename", methods=["POST"])
def rename():
    chat_id = request.json.get("chat_id")
    title = request.json.get("title")
    rename_chat(chat_id, title)
    return jsonify({"success": True})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        user_question = request.form.get("question", "").strip()
        user_id = request.form.get("user_id")
        chat_id = request.form.get("chat_id")
        file = request.files.get("file")
        print("CEO ASKED:", user_question)

        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        # Create new chat if none
        if not chat_id or chat_id == "null":
            chat_id = create_chat(user_id, user_question)

        messages_db = load_messages(chat_id)
        memory = [{"role": m['role'], "content": m['content']} for m in messages_db]

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
                file_content = "\n[PDF CONTENT]: " + "".join([p.extract_text() for p in pdf.pages if p.extract_text()])[:12000] # Increased to 12k
                if not user_question:
                    user_question = "Summarize this document in 3 key points"
            else:
                file_content = f"\n[FILE {filename}]: ```{file_ext}\n{file_bytes.decode('utf-8', errors='ignore')[:12000]}\n```"

        model = "openai/gpt-oss-120b"
        messages = [{"role": "system", "content": f"You are assisting the CEO of B.CORP. {SYSTEM_PROMPT}"}] + memory
        messages.append({"role": "user", "content": f"Answer professionally. Use proper spacing. No joined words. Max 120 words. Question: {user_question}" + file_content + search_results})

        save_message(chat_id, "user", user_question) # Save user message

        def generate():
            full = ""
            buffer = ""
            try:
                stream = client.chat.completions.create(model=model, messages=messages, max_tokens=600, temperature=0.3, stream=True)
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        if content.strip():
                            buffer += content
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

                save_message(chat_id, "assistant", full) # Save AI message
                yield f"data: [CHAT_ID]{chat_id}[/CHAT_ID]\n" # Send chat_id back to frontend
                yield f"data: [DONE]\n\n"

            except Exception as e:
                print("GROQ STREAM ERROR:", traceback.format_exc())
                yield f"data: **Brain 3.0 Error:** {str(e)}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    except Exception as e:
        print("ASK ROUTE CRASH:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
