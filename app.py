from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
import os, re, time, io, PyPDF2, traceback
from groq import Groq
from tavily import TavilyClient
from werkzeug.utils import secure_filename
from config import config
from supabase import create_client, Client
from datetime import datetime

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 # 10MB

print("=== BRAIN 3.0 WORLD CLASS STARTING ===")
print("SUPABASE_URL:", config.SUPABASE_URL[:30] + "..." if config.SUPABASE_URL else "MISSING")
print("GROQ:", bool(config.GROQ_API_KEY))
print("TAVILY:", bool(config.TAVILY_API_KEY))

client = Groq(api_key=config.GROQ_API_KEY)
tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'py', 'js', 'html', 'css', 'md', 'csv', 'json'}

# UPGRADE 1: CEO-LEVEL SYSTEM PROMPT
SYSTEM_PROMPT = """
You are Brain 3.0 by B.CORP. You are the world's most capable AI engineer and strategist.
MISSION: Help the CEO of B.CORP build, decide, and execute 10x faster.
PERSONALITY: Direct, elite, warm, zero fluff. Like Meta AI + Claude + Senior CTO combined.
TONE: Confident. Use 1 emoji max per message 😊
FORMATTING RULES - ALWAYS FOLLOW:
### 1. Headers for sections
- **Bold labels** for key points
- Bullet lists for steps
- `code blocks` for code
- Blank lines between sections
ANTI-JOIN RULE: Never output "machinelearning". Always "machine learning".

CORE ABILITIES:
1. **Build**: Write full, production-ready code. No placeholders.
2. **Decide**: Give 1 clear recommendation with "why".
3. **Explain**: Break complex topics into 3 steps.
4. **Search**: Use live web data when user asks "latest, news, price, today".
"""

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# UPGRADE 2: BETTER CLEANER - NO MORE JOINED WORDS
def clean_markdown(text):
    if not text: return ''
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text) # camelCase
    text = re.sub(r'([a-z])(\d)', r'\1 \2', text) # word1
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text) # 1word
    text = re.sub(r'([a-z])\.([A-Z])', r'\1. \2', text) # sentence.Start
    text = re.sub(r'([a-z]),([A-Z])', r'\1, \2', text) # comma,Word
    text = re.sub(r'([a-z]):([A-Z])', r'\1: \2', text) # key:Value
    text = re.sub(r'\s{2,}', ' ', text) # multiple spaces
    return text.strip()

def needs_search(query):
    triggers = ['price', 'news', 'today', 'latest', '2026', 'current', 'weather', 'stock', 'crypto']
    return any(word in query.lower() for word in triggers)

def create_chat(user_id, first_message):
    title = first_message[:60] + "..." if len(first_message) > 60 else first_message
    res = supabase.table("chats").insert({"user_id": user_id, "title": title}).execute()
    return res.data[0]['id']

def load_chats(user_id):
    res = supabase.table("chats").select("*").eq("user_id", user_id).order("updated_at", desc=True).limit(50).execute()
    return res.data

def load_messages(chat_id):
    res = supabase.table("messages").select("*").eq("chat_id", chat_id).order("created_at").execute()
    return res.data

def save_message(chat_id, role, content):
    if not content.strip(): return
    supabase.table("messages").insert({"chat_id": chat_id, "role": role, "content": content}).execute()
    supabase.table("chats").update({"updated_at": datetime.utcnow().isoformat()}).eq("id", chat_id).execute()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route("/config")
def get_config():
    return jsonify({
        "supabase_url": config.SUPABASE_URL,
        "supabase_anon_key": config.SUPABASE_ANON_KEY # SECURE FOR BROWSER
    })

@app.route("/chats", methods=["GET"])
def get_chats():
    user_id = request.args.get("user_id")
    if not user_id: return jsonify([])
    return jsonify(load_chats(user_id))

@app.route("/chat/<chat_id>", methods=["GET"])
def get_chat(chat_id):
    return jsonify(load_messages(chat_id))

@app.route("/chat/delete", methods=["POST"]) # UPGRADE 3: DELETE CHAT
def delete_chat():
    data = request.get_json()
    chat_id = data.get("chat_id")
    supabase.table("messages").delete().eq("chat_id", chat_id).execute()
    supabase.table("chats").delete().eq("id", chat_id).execute()
    return jsonify({"success": True})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        user_question = request.form.get("question", "").strip()
        user_id = request.form.get("user_id")
        chat_id = request.form.get("chat_id")
        file = request.files.get("file")

        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        if not chat_id or chat_id == "null":
            chat_id = create_chat(user_id, user_question or "New Chat")

        messages_db = load_messages(chat_id)
        memory = [{"role": m['role'], "content": m['content']} for m in messages_db[-10:]] # Last 10 for context

        # UPGRADE 4: BETTER WEB SEARCH
        search_results = ""
        if needs_search(user_question):
            try:
                res = tavily.search(query=user_question, max_results=5, search_depth="advanced")
                search_results = "\n\n[Live Web Results " + datetime.now().strftime("%Y-%m-%d") + "]:\n"
                for i, r in enumerate(res['results'], 1):
                    search_results += f"[{i}] **{r['title']}**: {r['content'][:300]}... Source: {r['url']}\n"
            except: pass

        # UPGRADE 5: BETTER FILE HANDLING
        file_content = ""
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            file_ext = filename.rsplit('.', 1)[1].lower()
            if file_ext == 'pdf':
                pdf = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                file_content = "\n\n[PDF CONTENT: " + filename + "]\n" + "".join([p.extract_text() for p in pdf.pages if p.extract_text()])[:15000]
                if not user_question: user_question = "Summarize this PDF in 5 bullet points with key takeaways"
            else:
                decoded = file_bytes.decode('utf-8', errors='ignore')[:15000]
                file_content = f"\n\n[FILE: {filename}]\n```{file_ext}\n{decoded}\n```"

        # UPGRADE 6: BEST GROQ MODEL + BIGGER CONTEXT
        model = "openai/gpt-oss-120b" # Fastest + Smartest on Groq
        messages = [{"role": "system", "content": f"You are assisting the CEO of B.CORP. {SYSTEM_PROMPT}"}] + memory
        messages.append({"role": "user", "content": f"Question: {user_question}" + file_content + search_results})

        save_message(chat_id, "user", user_question)

        def generate():
            full = ""
            buffer = ""
            try:
                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=2048, # UPGRADE: 5x longer answers
                    temperature=0.6,
                    top_p=0.9,
                    stream=True
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        buffer += content
                        if len(buffer) > 60: # Send in bigger chunks
                            chunk_clean = clean_markdown(buffer)
                            if chunk_clean.strip():
                                full += chunk_clean + " "
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
                print("STREAM ERROR:", traceback.format_exc())
                yield f"data: **Brain 3.0 Error:** {str(e)}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    except Exception as e:
        print("ASK ERROR:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
