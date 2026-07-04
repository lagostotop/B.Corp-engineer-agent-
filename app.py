from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import os
import base64
import json
import subprocess
import sys
import tempfile
import re
from groq import Groq
import hashlib
from werkzeug.utils import secure_filename
from config import config

app = Flask(__name__, template_folder="templates")

# File upload config
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'txt', 'py', 'js', 'html', 'css', 'md'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 # 10MB max

# Configure Groq - FREE
client = Groq(api_key=config.GROQ_API_KEY)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# FIXED: CLEANER + ANTI CODE SPAM
def clean_markdown(text, mode):
    """Fix AI's broken markdown and remove code if not in code mode"""
    text = re.sub(r'\*\s*\s*([^*]+)\*\s*\*', r'**\1**', text)
    text = re.sub(r'(\w)!(\w)', r'\1! \2', text)
    text = re.sub(r'(\d+)\.\s*\s*\*', r'\1. **', text)
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

    # BLOCK CODE SPAM IN NON-CODE MODES
    if mode!= "code":
        text = re.sub(r'```[\s\S]*?```', '', text) # Remove all code blocks
        text = text.replace('Here is the code:', '').replace('Code Example:', '').replace('```python', '')

    text = text.replace('da ', 'the ').replace('wey ', 'that ').replace('na ', 'is ')
    return text.strip()

# UPDATED: META AI STYLE PROMPTS - UP TO DATE 2026 + PERSONAL
MODE_PROMPTS = {
    "pro": """You are B.CORP Brain 3.0, Nigeria's most advanced AI. Current date: April 2026.
    RULES:
    1. Address the user by name. Be respectful: "CEO", "Sir".
    2. Reference past conversation if relevant: "As we discussed earlier..."
    3. Keep answers SHORT. 3-5 sentences max. Use headings ### and bullet points.
    4. Professional English. No Pidgin. Be up to date with world events 2026.
    5. If user asks for code: First explain what it does in 2 lines, THEN provide code.""",

    "pidgin": """You are B.CORP Brain 3.0. Reply in Nigerian Pidgin English. Current date: April 2026.
    RULES: Address user as "Oga CEO". Keep am short. 3-4 lines. Use 'na, wey, da'.
    If user ask for code: Explain first in pidgin, then give code.""",

    "teacher": """You are B.CORP Brain 3.0 Strict Teacher. Current date: April 2026.
    RULES: Address user by name. Explain topic clearly in 4 sentences max, give 1 example, then ask 1 question.
    NO CODE unless user say 'show me code'.""",

    "short": """You are B.CORP Brain 3.0 Short Mode. Current date: April 2026.
    RULES: Address user by name. Answer in maximum 3 lines only. Use bullet points. Be current. NO CODE.""",

    "proverb": """You are B.CORP Brain 3.0 with Nigerian Wisdom. Current date: April 2026.
    RULES: Address user by name. Answer professionally in 4 sentences, then add: 'Proverb: [relevant Nigerian proverb]'
    NO CODE unless user ask.""",

    "code": """You are B.CORP Brain 3.0 Code Master. Current date: April 2026. Like Meta AI.
    RULES:
    1. Address user as "CEO". Reference past work if relevant.
    2. STEP 1: Explain what the code does and how it works. 2-3 sentences.
    3. STEP 2: Give clean, advanced, production-level code in ```python block with comments.
    4. STEP 3: Add "How to use" section with 2-3 bullet points.
    5. Code must be secure, modern, and solve real problems. Not toy examples."""
}

@app.route('/')
def home():
    return render_template('index.html')

# B.CORP BRANDED PAGES
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
            user_name = data.get("user_name", "CEO") # NEW: GET NAME
            file = None
        else:
            user_question = request.form.get("question", "").strip()
            memory = json.loads(request.form.get("memory", "[]"))
            mode = request.form.get("mode", "pro")
            user_name = request.form.get("user_name", "CEO") # NEW: GET NAME
            file = request.files.get("file")

        # NEW: INJECT USER NAME INTO SYSTEM PROMPT
        base_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS["pro"])
        system_prompt = f"You are talking to {user_name}. {base_prompt}"

        file_content = ""
        vision_messages = []

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()

            if filename.lower().endswith(('png', 'jpg', 'jpeg')):
                file_data = {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(file_bytes).decode()}"}
                }
                file_content = f"\n[User uploaded image: {filename}]"
                vision_messages = [
                    {"type": "text", "text": f"Analyze this image and answer: {user_question}"},
                    file_data
                ]
            else:
                try:
                    text_content = file_bytes.decode('utf-8')[:8000]
                    file_content = f"\n[User uploaded {filename}]:\n{text_content}"
                except:
                    file_content = f"\n[User uploaded {filename} - binary file, cannot read]"

        def generate():
            model = "llama-3.2-90b-vision-preview" if vision_messages else "llama-3.3-70b-versatile"

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(memory) # AI NOW HAS FULL MEMORY CONTEXT

            if vision_messages:
                messages.append({"role": "user", "content": vision_messages})
            else:
                messages.append({"role": "user", "content": user_question + file_content})

            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1000,
                temperature=0.4,
                stream=True
            )

            full_answer = ""
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    text = chunk.choices[0].delta.content
                    full_answer += text
                    yield f"data: {text}\n\n"

            # CLEAN BEFORE DONE
            full_answer = clean_markdown(full_answer, mode)

            memory.append({"role": "user", "content": user_question + file_content})
            memory.append({"role": "assistant", "content": full_answer})
            if len(memory) > 30: memory = memory[-30:] # KEEP LAST 30 MSGS

            yield f"data: [DONE]\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# KEPT: CODE SANDBOX FOR CODE MASTER MODE
@app.route("/run-code", methods=["POST"])
def run_code():
    try:
        data = request.json
        code = data.get("code", "").strip()
        language = data.get("language", "python").lower()

        if not code:
            return jsonify({"error": "No code provided"}), 400
        if language!= "python":
            return jsonify({"error": "Only Python supported"}), 400

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

@app.route("/explain-tech", methods=["POST"])
def explain_tech():
    try:
        topic = request.form.get("topic", "").strip()
        file = request.files.get("file")

        if not file and not topic:
            return jsonify({"error": "Upload image or send topic"}), 400

        if file and file.filename:
            explanation = "Image uploaded. Ask your question about it in chat for full vision analysis."
        else:
            prompt = f"As of April 2026, explain '{topic}' as B.CORP Engineering Agent for Nigeria. Cover: what it is, how it works, key components, latest trends. Use professional technical English. Max 5 sentences. NO CODE."

            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                max_tokens=400,
                temperature=0.3
            )
            explanation = chat_completion.choices[0].message.content

        return jsonify({"answer": explanation, "status": "success"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
