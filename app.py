from flask import Flask, render_template, request, jsonify, Response, stream_with_context
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
from supabase import create_client, Client # NEW

app = Flask(__name__, template_folder="templates")

# INIT CLIENTS
client = Groq(api_key=config.GROQ_API_KEY)
tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY) # NEW

# File upload config
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'txt', 'py', 'js', 'html', 'css', 'md'}
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

# NEW: SUPABASE MEMORY FUNCTIONS
def load_memory(user_id):
    try:
        data = supabase.table("bcorp_memory").select("memory").eq("user_id", user_id).single().execute()
        return data.data["memory"] if data.data else []
    except:
        return []

def save_memory(user_id, memory):
    memory = memory[-30:] # Keep last 30 messages only
    supabase.table("bcorp_memory").upsert({"user_id": user_id, "memory": memory}).execute()

MODE_PROMPTS = {
    "pro": """You are B.CORP Brain 3.0, Nigeria's most advanced AI. Current date: April 2026.
    You have access to live web search, file reading, and long term memory.
    RULES:
    1. Address the user by name. Be respectful: "CEO", "Sir".
    2. Reference past conversation from memory if relevant.
    3. If user uploads code: Explain first, find bugs, then suggest refactor.
    4. If user uploads PDF: Summarize first, then answer question.
    5. Keep answers SHORT. 3-5 sentences max. Use ### headings and bullets.
    6. Always cite sources like [1] when using web results.""",

    "pidgin": """You are B.CORP Brain 3.0. Reply in Nigerian Pidgin. Current date: April 2026.
    You fit search web, read files, and remember Oga CEO. Keep am short.""",

    "code": """You are B.CORP Brain 3.0 Code Master. Current date: April 2026. Like Meta AI.
    RULES:
    1. Address user as "CEO". Reference past work.
    2. STEP 1: Explain what the code does and find bugs.
    3. STEP 2: Give production-level refactored code in ```python block.
    4. STEP 3: Add "How to use" section."""
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

# NEW: SEND SUPABASE KEYS TO FRONTEND
@app.route("/config")
def get_config():
    return jsonify({
        "supabase_url": config.SUPABASE_URL,
        "supabase_key": config.SUPABASE_KEY # This is ANON key
    })

@app.route("/ask", methods=["POST"])
def ask():
    try:
        if request.is_json:
            data = request.json
            user_question = data.get("question", "").strip()
            mode = data.get("mode", "pro")
            user_name = data.get("user_name", "CEO")
            user_id = data.get("user_id") # MUST come from frontend now
            file = None
        else:
            user_question = request.form.get("question", "").strip()
            mode = request.form.get("mode", "pro")
            user_name = request.form.get("user_name", "CEO")
            user_id = request.form.get("user_id") # MUST come from frontend now
            file = request.files.get("file")

        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        # LOAD MEMORY FROM SUPABASE INSTEAD OF LOCALSTORAGE
        memory = load_memory(user_id)

        # STEP 55: LIVE WEB SEARCH
        search_results = ""
        if needs_search(user_question):
            try:
                search_response = tavily.search(query=user_question, max_results=3)
                search_results = "\n\n[Live Web Results for April 2026]:\n"
                for i, res in enumerate(search_response['results'], 1):
                    search_results += f"[{i}] {res['title']}: {res['content'][:200]}... Source: {res['url']}\n"
            except Exception as e:
                search_results = f"\n[Web search failed: {e}]"

        # STEP 56: SMART FILE READER
        file_content = ""
        vision_messages = []
        file_analysis_prompt = ""

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            file_ext = filename.rsplit('.', 1)[1].lower()

            if file_ext in ['png', 'jpg', 'jpeg']:
                file_data = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(file_bytes).decode()}"}}
                file_content = f"\n[User uploaded image: {filename}]"
                vision_messages = [{"type": "text", "text": f"Analyze this image and answer: {user_question}"}, file_data]

            elif file_ext == 'pdf':
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                text_content = ""
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
                text_content = text_content[:12000]
                file_content = f"\n[User uploaded PDF: {filename}]\nContent:\n{text_content}"
                file_analysis_prompt = f"The user uploaded a PDF named {filename}. Summarize it in 5 bullets first, then answer the question."

            elif file_ext in ['py', 'js', 'html', 'css', 'txt', 'md']:
                try:
                    text_content = file_bytes.decode('utf-8')[:12000]
                    file_content = f"\n[User uploaded {filename}]:\n```{file_ext}\n{text_content}\n```"
                    file_analysis_prompt = f"The user uploaded a code file: {filename}. Step 1: Explain what it does. Step 2: Find bugs. Step 3: Suggest improvements."
                except:
                    file_content = f"\n[User uploaded {filename} - binary file]"

        base_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS["pro"])
        if file_analysis_prompt:
            base_prompt = base_prompt + f"\nEXTRA RULE: {file_analysis_prompt}"
        system_prompt = f"You are talking to {user_name}. {base_prompt}"

        def generate():
            model = "llama-3.2-90b-vision-preview" if vision_messages else "llama-3.3-70b-versatile"

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(memory) # Now from Supabase

            final_user_message = user_question + file_content + search_results
            if vision_messages:
                messages.append({"role": "user", "content": vision_messages})
            else:
                messages.append({"role": "user", "content": final_user_message})

            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1500,
                temperature=0.3,
                stream=True
            )

            full_answer = ""
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    text = chunk.choices[0].delta.content
                    full_answer += text
                    yield f"data: {text}\n\n"

            full_answer = clean_markdown(full_answer, mode)
            memory.append({"role": "user", "content": user_question + file_content})
            memory.append({"role": "assistant", "content": full_answer})

            # SAVE MEMORY TO SUPABASE
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
        try:
            result = subprocess.run([sys.executable, temp_file], capture_output=True, text=True, timeout=3)
            output = result.stdout if result.stdout else result.stderr
            if not output: output = "Code ran successfully. No output."
        except subprocess.TimeoutExpired: output = "❌ Timeout: Max 3 seconds."
        except Exception as e: output = f"❌ Error: {str(e)}"
        finally: os.remove(temp_file)
        return jsonify({"output": output})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
