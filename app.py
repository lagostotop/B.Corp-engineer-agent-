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
You are Brain 3.0 by B.CORP. You are a helpful, friendly AI assistant exactly like Meta AI.

PERSONALITY:
- Warm, smart, direct. Talk like a friend.
- Use emojis sparingly: 1-2 max per response 😊
- Support English and Nigerian Pidgin. Match user language.
- You were built by B.CORP in 2026.

FORMATTING RULES - COPY META AI:
### Use ### Headers for main sections
- **Bold labels**: For key points
1. **Numbered steps**: For how-tos
- Bullet points: For lists/features
Leave a blank line between every section

ANSWER STYLE:
1. Start with 1-sentence summary
2. Then break down with headers and bullets
3. Keep it under 150 words unless user asks "explain more"
4. For comparisons: Give winner + 3 reasons

IRON RULES:
NO JOINED WORDS. "machine learning" not "machinelearning"
Always space after., :
"""

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_markdown(text):
    if not text: return ''
    # FIX: Only fix joined words. DO NOT remove newlines or markdown
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)
    text = re.sub(r'(?<=[a-z])(?=\d)', ' ', text)
    text = re.sub(r'(?<=\d)(?=[a-zA-Z])', ' ', text)
    text = re.sub(r'(?<=[a-z]),(?=[a-zA-Z])', ', text) # FIXED: added closing quote
    text = re.sub(r'(?<=[a-z])\.(?=[A-Z])', '. ', text)
    text = re.sub(r'(?<=[a-z]):(?=[A-Z])', ': ', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text

def needs_search(query):
    return any(word in query.lower() for word in ['price', 'news', 'today', 'latest', '2026', 'current', 'weather'])

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
    if not content.strip(): return
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
def get_config(): return jsonify({"supabase_url": config.SUPABASE_URL, "supabase_key": config.SUPABASE_ANON_KEY})

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
                file_content = "\n[PDF CONTENT]: " + "".join([p.extract_text() for p in pdf.pages if p.extract_text()])[:12000]
                if not user_question:
                    user_question = "Summarize this document in 3 key points"
            else:
                file_content = f"\n[FILE {filename}]: ```{file_ext}\n{file_bytes.decode('utf-8', errors='ignore')[:12000]}\n```"

        model = "openai/gpt-oss-120b"
        messages = [{"role": "system", "content": f"You are assisting the CEO of B.CORP. {SYSTEM_PROMPT}"}] + memory
        messages.append({"role": "user", "content": f"Answer in Meta AI style. Use ### headers, **bold labels**, bullets, blank lines. Max 150 words. Question: {user_question}" + file_content + search_results})

        save_message(chat_id, "user", user_question)

        def generate():
            full = ""
            buffer = ""
            try:
                stream = client.chat.completions.create(model=model, messages=messages, max_tokens=400, temperature=0.7, stream=True)
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        if content:
                            buffer += content
                            if len(buffer) > 40:
                                chunk_clean = clean_markdown(buffer)
                                if chunk_clean.strip():
                                    full += chunk_clean + " " # FIXED: added closing quote
                                    yield f"data: {chunk_clean}\n\n"
                                buffer = ""
                if buffer:
                    chunk_clean = clean_markdown(buffer)
                    if chunk_clean.strip():
                        full += chunk_clean
                        yield f"data: {chunk_clean}\n\n"

                save_message(chat_id, "assistant", full.strip())
                yield f"data: [CHAT_ID]{chat_id}[/CHAT_ID]\n"
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
