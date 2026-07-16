from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
import os
import base64
import io
import re
import PyPDF2
from groq import Groq
from tavily import TavilyClient
from werkzeug.utils import secure_filename
from config import config
from supabase import create_client, Client

app = Flask(__name__, static_folder="static", template_folder="templates")

client = Groq(api_key=config.GROQ_API_KEY)
tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'txt', 'py', 'js', 'html', 'css', 'md', 'ico'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_markdown(text, mode):
    text = re.sub(r'\*\s*\s*([^*]+)\*\s*\*', r'**\1**', text)
    if mode!= "code":
        text = re.sub(r'```[\s\S]*?```', '', text)
    return text.strip()

def needs_search(query):
    keywords = ['price', 'news', 'today', 'latest', '2026', 'current', 'weather', 'score', 'update', 'research', 'how', 'what', 'why', 'best']
    return any(word in query.lower() for word in keywords)

def load_memory(user_id):
    try:
        data = supabase.table("brain30_memory").select("memory").eq("user_id", user_id).single().execute()
        return data.data["memory"] if data.data and data.data.get("memory") else []
    except: return []

def save_memory(user_id, memory):
    try:
        memory = memory[-30:]
        supabase.table("brain30_memory").upsert({"user_id": user_id, "memory": memory}).execute()
    except: pass

MODE_PROMPTS = {
    "pro": """You are Brain 3.0 by B.CORP. Current date: April 2026. Answer exactly like Meta AI and ChatGPT.
RULES:
1. Direct 1-2 sentence answer first.
2. Use ### Headings and - **Bold**: bullets.
3. Address user as "CEO".
4. Keep it 5-8 sentences.
5. End with "Would you like me to... CEO?" """,
    "pidgin": """You be Brain 3.0 by B.CORP. Oga CEO. Answer like Meta AI in Naija Pidgin. Use ### headings. End with question.""",
    "code": """You are Brain 3.0 Code Master. Use ### 1. What it Does, ### 2. Issues, ### 3. Code, ### 4. How To Use. Address as CEO."""
}

@app.route('/')
def home(): return render_template('index.html')
@app.route('/about')
def about(): return render_template('about.html')
@app.route('/features')
def features(): return render_template('features.html')
@app.route('/contact')
def contact(): return render_template('contact.html')
@app.route('/static/<path:filename>')
def serve_static(filename): return send_from_directory(app.static_folder, filename)

@app.route("/config")
def get_config():
    return jsonify({"supabase_url": config.SUPABASE_URL, "supabase_key": config.SUPABASE_KEY})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        user_question = request.form.get("question", "").strip() if not request.is_json else request.json.get("question", "").strip()
        mode = request.form.get("mode", "pro") if not request.is_json else request.json.get("mode", "pro")
        user_name = request.form.get("user_name", "CEO") if not request.is_json else request.json.get("user_name", "CEO")
        user_id = request.form.get("user_id") if not request.is_json else request.json.get("user_id")
        file = request.files.get("file")

        if not user_id: return jsonify({"error": "Not logged in"}), 401

        memory = load_memory(user_id)
        search_results = ""
        if needs_search(user_question):
            try:
                res = tavily.search(query=user_question, max_results=3)
                search_results = "\n\n[Live Web Results]:\n"
                for i, r in enumerate(res['results'], 1):
                    search_results += f"[{i}] {r['title']}: {r['content'][:200]}... \n"
            except: pass

        file_content = ""
        vision_messages = []
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            file_ext = filename.rsplit('.', 1)[1].lower()

            if file_ext in ['png', 'jpg', 'jpeg']:
                b64 = base64.b64encode(file_bytes).decode()
                vision_messages = [{"type": "text", "text": user_question}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]
            elif file_ext == 'pdf':
                pdf = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                file_content = "\n[PDF]: " + "".join([p.extract_text() for p in pdf.pages])[:8000]
            else:
                file_content = f"\n[File {filename}]: ```{file_ext}\n{file_bytes.decode('utf-8')[:8000]}\n```"

        system_prompt = f"You are talking to {user_name}. {MODE_PROMPTS.get(mode, MODE_PROMPTS['pro'])}"
        model = "llama-3.2-90b-vision-preview" if vision_messages else "meta-llama/llama-4-maverick-17b-128e-instruct"

        messages = [{"role": "system", "content": system_prompt}] + memory
        messages.append({"role": "user", "content": vision_messages if vision_messages else user_question + file_content + search_results})

        def generate():
            stream = client.chat.completions.create(model=model, messages=messages, max_tokens=1200, temperature=0.6, stream=True)
            full = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full += text
                    yield f"data: {text}\n\n"
            save_memory(user_id, memory + [{"role": "user", "content": user_question}, {"role": "assistant", "content": clean_markdown(full, mode)}])
            yield f"data: [DONE]\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/run-code", methods=["POST"])
def run_code():
    return jsonify({"output": "Code runner disabled for safety"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT)
