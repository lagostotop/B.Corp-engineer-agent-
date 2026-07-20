from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
import os, re, time, io, PyPDF2, traceback
from groq import Groq
from tavily import TavilyClient
from werkzeug.utils import secure_filename
from config import config
from supabase import create_client, Client

app = Flask(__name__, static_folder="static", template_folder="templates")

client = Groq(api_key=config.GROQ_API_KEY) # Use your newest key on Render
tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'py', 'js', 'html', 'css', 'md'} # NO IMAGES
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_markdown(text):
    # AGGRESSIVE FIX FOR GLUED WORDS
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text) # iAm -> i Am
    text = re.sub(r'([a-z])\.([A-Z])', r'\1. \2', text) # CEO.How -> CEO. How
    text = re.sub(r'([a-z])(\d)', r'\1 \2', text) # Brain3 -> Brain 3
    text = re.sub(r'(\d)([a-z])', r'\1 \2', text) # 3Brain -> 3 Brain
    text = re.sub(r'(\w):(\w)', r'\1: \2', text)
    text = re.sub(r'(\w),(\w)', r'\1, \2', text)
    text = re.sub(r'([^\n])###', r'\n\n###', text)
    text = re.sub(r'([^\n])- \*\*', r'\n- **', text)
    text = re.sub(r'([^\n])(\d+\.)', r'\n\2', text)
    text = re.sub(r'[ ]{2,}', ' ', text)
    return text.strip()

def needs_search(query):
    return any(word in query.lower() for word in ['price', 'news', 'today', 'latest', '2026', 'current', 'weather'])

def load_memory(user_id):
    try: 
        data = supabase.table("brain30_memory").select("memory").eq("user_id", user_id).single().execute()
        return data.data["memory"] if data.data else []
    except: return []

def save_memory(user_id, memory):
    try: supabase.table("brain30_memory").upsert({"user_id": user_id, "memory": memory[-30:] }).execute()
    except: pass

SYSTEM_PROMPT = """You are Brain 3.0 by B.CORP. Current date: July 19 2026. You are CEO's personal AI assistant.
Act professional, smart, and helpful.
CRITICAL RULES:
1. Always add space between words. Never write "Iam" or "CEO". Write "I am" and "CEO".
2. Add 2 blank lines before ### Headings
3. Add 1 blank line before lists
4. Address user as "CEO".
5. Keep answers 5-8 sentences. End with "What else can I do for you CEO?" """

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
        user_name = request.form.get("user_name", "CEO")
        user_id = request.form.get("user_id")
        file = request.files.get("file")
        if not user_id: return jsonify({"error": "Not logged in"}), 401

        memory = load_memory(user_id)
        search_results = ""
        if needs_search(user_question):
            try:
                res = tavily.search(query=user_question, max_results=3)
                search_results = "\n\n[Live Web Results]:\n"
                for i, r in enumerate(res['results'], 1): search_results += f"[{i}] {r['title']}: {r['content'][:200]}... \n"
            except: pass

        file_content = ""
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            file_ext = filename.rsplit('.', 1)[1].lower()
            if file_ext == 'pdf':
                pdf = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                file_content = "\n[PDF CONTENT]: " + "".join([p.extract_text() for p in pdf.pages if p.extract_text()])[:8000]
                if not user_question: user_question = "Summarize this PDF and give me key insights CEO"
            else:
                file_content = f"\n[FILE {filename}]: ```{file_ext}\n{file_bytes.decode('utf-8', errors='ignore')[:8000]}\n```"

        model = "llama-3.1-405b-realtime" # LATEST AND BEST GROQ
        messages = [{"role": "system", "content": f"You are talking to {user_name}. {SYSTEM_PROMPT}"}] + memory
        messages.append({"role": "user", "content": user_question + file_content + search_results})

        def generate():
            full = ""
            stream = client.chat.completions.create(model=model, messages=messages, max_tokens=2000, temperature=0.4, stream=True)
            buffer = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    buffer += chunk.choices[0].delta.content
                    if re.search(r'[ \n.,;:!?]$', buffer):
                        text = clean_markdown(buffer)
                        full += text
                        yield f"data: {text}\n\n"
                        buffer = ""
            if buffer: yield f"data: {clean_markdown(buffer)}\n\n"
            save_memory(user_id, memory + [{"role": "user", "content": user_question}, {"role": "assistant", "content": full}])
            yield f"data: [DONE]\n\n"
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    except Exception as e: return jsonify({"error": str(e)}), 500
