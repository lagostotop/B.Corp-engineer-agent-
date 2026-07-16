from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
import os
import base64
import json
import subprocess
import sys
import tempfile
import re
import io
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
    text = re.sub(r'(\w)!(\w)', r'\1! \2', text)
    if mode!= "code":
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = text.replace('Here is the code:', '').replace('Code Example:', '')
    return text.strip()

def needs_search(query):
    search_keywords = ['price', 'news', 'today', 'latest', '2026', 'current', 'weather', 'score', 'update']
    return any(word in query.lower() for word in search_keywords)

def load_memory(user_id):
    try:
        data = supabase.table("brain30_memory").select("memory").eq("user_id", user_id).single().execute()
        return data.data["memory"] if data.data and data.data.get("memory") else []
    except Exception as e:
        print(f"Memory Load Error: {e}")
        return []

def save_memory(user_id, memory):
    try:
        memory = memory[-30:]
        supabase.table("brain30_memory").upsert({"user_id": user_id, "memory": memory}).execute()
    except Exception as e:
        print(f"Memory Save Error: {e}")

MODE_PROMPTS = {
    "pro": f"""You are Brain 3.0 by B.CORP, Nigeria's most advanced AI. Current date: April 2026.
Company: B.CORP Technologies.
WRITING STYLE: Match Meta AI and ChatGPT. Be clear, structured, helpful.
STRUCTURE RULES:
1. Start with a direct 1-sentence answer.
2. Use ### Headings, **bold labels**, and - bullets.
3. Address the user as "CEO" or by name.
4. Keep it 4-7 sentences total.
5. End with 1 helpful follow-up question.""",
    "pidgin": f"""You be Brain 3.0 by B.CORP. Oga CEO, talk like Meta AI but for Naija. Use ### headings and bullets.""",
    "code": f"""You are Brain 3.0 by B.CORP - Code Master. 
STRUCTURE:
### 1. What this code does
### 2. Issues Found
### 3. Refactored Code
### 4. How to Use"""
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.after_request
def add_header(response):
    if request.path.endswith('sw.js') or request.path.endswith('manifest.json'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    if request.path.endswith('sw.js'):
        response.headers['Content-Type'] = 'application/javascript'
    if request.path.endswith('manifest.json'):
        response.headers['Content-Type'] = 'application/manifest+json'
    return response

@app.route("/config")
def get_config():
    return jsonify({"supabase_url": config.SUPABASE_URL, "supabase_key": config.SUPABASE_KEY})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        if request.is_json:
            data = request.json
            user_question = data.get("question", "").strip()
            mode = data.get("mode", "pro")
            user_name = data.get("user_name", "CEO")
            user_id = data.get("user_id")
            file = None
        else:
            user_question = request.form.get("question", "").strip()
            mode = request.form.get("mode", "pro")
            user_name = request.form.get("user_name", "CEO")
            user_id = request.form.get("user_id")
            file = request.files.get("file")

        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        memory = load_memory(user_id)
        search_results = ""
        if needs_search(user_question):
            try:
                search_response = tavily.search(query=user_question, max_results=3)
                search_results = "\n\n[Live Web Results for April 2026]:\n"
                for i, res in enumerate(search_response['results'], 1):
                    search_results += f"[{i}] {res['title']}: {res['content'][:200]}... Source: {res['url']}\n"
            except Exception as e:
                search_results = f"\n[Web search failed: {e}]"

        file_content = ""
        vision_messages = []
        file_analysis_prompt = ""
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            file_ext = filename.rsplit('.', 1).lower()[1]

            if file_ext in ['png', 'jpg', 'jpeg']:
                b64_image = base64.b64encode(file_bytes).decode()
                file_data = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                vision_messages = [{"type": "text", "text": f"Analyze this image: {user_question}"}, file_data]

            elif file_ext == 'pdf':
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                text_content = "".join([page.extract_text() + "\n" for page in pdf_reader.pages])[:12000]
                file_content = f"\n[PDF: {filename}]\n{text_content}"

            elif file_ext in ['py', 'js', 'html', 'css', 'txt', 'md']:
                text_content = file_bytes.decode('utf-8')[:12000]
                file_content = f"\n[File: {filename}]\n```{file_ext}\n{text_content}\n```"

        base_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS["pro"])
        system_prompt = f"You are talking to {user_name}. {base_prompt}"

        def generate():
            model = "llama-3.2-90b-vision-preview" if vision_messages else "meta-llama/llama-4-maverick-17b-128e-instruct"
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(memory)
            final_user_message = user_question + file_content + search_results
            messages.append({"role": "user", "content": vision_messages if vision_messages else final_user_message})

            stream = client.chat.completions.create(
                model=model, messages=messages, max_tokens=1024, temperature=0.7, top_p=0.9, stream=True
            )

            full_answer = ""
            for chunk in stream:
                if chunk.choices.delta.content is not None:
                    text = chunk.choices.delta.content
                    full_answer += text
                    yield f"data: {text}\n\n"

            memory.append({"role": "user", "content": user_question})
            memory.append({"role": "assistant", "content": clean_markdown(full_answer, mode)})
            save_memory(user_id, memory)
            yield f"data: [DONE]\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/run-code", methods=["POST"])
def run_code():
    try:
        data = request.json
        code = data.get("code", "").strip()
        if not code:
            return jsonify({"error": "No code provided"}), 400
        dangerous = ['os.', 'subprocess.', 'sys.', 'shutil.', 'socket.', 'requests.', '__import__', 'eval(', 'exec(']
        if any(d in code for d in dangerous):
            return jsonify({"output": "❌ Blocked: System access not allowed."})
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        result = subprocess.run([sys.executable, temp_file], capture_output=True, text=True, timeout=3)
        output = result.stdout if result.stdout else result.stderr
        os.remove(temp_file)
        return jsonify({"output": output if output else "Code ran successfully. No output."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
