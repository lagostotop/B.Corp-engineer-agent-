from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import os
import base64
import json
import subprocess
import sys
import tempfile
import re
from groq import Groq
from tavily import TavilyClient # NEW
from werkzeug.utils import secure_filename
from config import config

app = Flask(__name__, template_folder="templates")

# INIT CLIENTS
client = Groq(api_key=config.GROQ_API_KEY)
tavily = TavilyClient(api_key=config.TAVILY_API_KEY) # NEW

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

# NEW: DECIDE IF WE NEED TO SEARCH WEB
def needs_search(query):
    search_keywords = ['price', 'news', 'today', 'latest', '2026', 'current', 'weather', 'score', 'update']
    return any(word in query.lower() for word in search_keywords)

# UPDATED PROMPTS: AI NOW KNOWS IT CAN SEARCH
MODE_PROMPTS = {
    "pro": """You are B.CORP Brain 3.0, Nigeria's most advanced AI. Current date: April 2026.
    You have access to live web search. Use it for prices, news, current events.
    RULES:
    1. Address the user by name. Be respectful: "CEO", "Sir".
    2. Reference past conversation if relevant.
    3. Keep answers SHORT. 3-5 sentences max. Use ### headings and bullets.
    4. Always cite sources like [1] when using web results.""",

    "pidgin": """You are B.CORP Brain 3.0. Reply in Nigerian Pidgin. Current date: April 2026.
    You fit search web for news and price. Address user as "Oga CEO". Keep am short.""",

    "code": """You are B.CORP Brain 3.0 Code Master. Current date: April 2026. Like Meta AI.
    RULES:
    1. Address user as "CEO". Reference past work.
    2. STEP 1: Explain what the code does.
    3. STEP 2: Give production-level code in ```python block.
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

@app.route("/ask", methods=["POST"])
def ask():
    try:
        if request.is_json:
            data = request.json
            user_question = data.get("question", "").strip()
            memory = data.get("memory", [])
            mode = data.get("mode", "pro")
            user_name = data.get("user_name", "CEO")
            file = None
        else:
            user_question = request.form.get("question", "").strip()
            memory = json.loads(request.form.get("memory", "[]"))
            mode = request.form.get("mode", "pro")
            user_name = request.form.get("user_name", "CEO")
            file = request.files.get("file")

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

        base_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS["pro"])
        system_prompt = f"You are talking to {user_name}. {base_prompt}"

        file_content = ""
        vision_messages = []

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            if filename.lower().endswith(('png', 'jpg', 'jpeg')):
                file_data = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(file_bytes).decode()}"}}
                file_content = f"\n[User uploaded image: {filename}]"
                vision_messages = [{"type": "text", "text": f"Analyze this image and answer: {user_question}"}, file_data]
            else:
                try:
                    text_content = file_bytes.decode('utf-8')[:8000]
                    file_content = f"\n[User uploaded {filename}]:\n{text_content}"
                except:
                    file_content = f"\n[User uploaded {filename} - binary file]"

        def generate():
            model = "llama-3.2-90b-vision-preview" if vision_messages else "llama-3.3-70b-versatile"

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(memory)

            # ADD SEARCH RESULTS TO USER MESSAGE
            final_user_message = user_question + file_content + search_results
            if vision_messages:
                messages.append({"role": "user", "content": vision_messages})
            else:
                messages.append({"role": "user", "content": final_user_message})

            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1200, # MORE TOKENS FOR SEARCH RESULTS
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
            if len(memory) > 30: memory = memory[-30:]

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
