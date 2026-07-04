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

# Configure Groq - FREE, no billing
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

    # STEP 51: BLOCK CODE SPAM IN NON-CODE MODES
    if mode!= "code":
        text = re.sub(r'```[\s\S]*?```', '', text) # Remove all code blocks
        text = text.replace('Here is the code:', '').replace('Code Example:', '')

    text = text.replace('da ', 'the ').replace('wey ', 'that ').replace('na ', 'is ')
    return text.strip()

# UPDATED: STRICT PROMPTS - NO AUTO CODE
MODE_PROMPTS = {
    "pro": """You are B.CORP Brain 3.0, a professional engineer for Nigeria.
    CRITICAL RULES:
    1. Keep answers SHORT. 3-5 sentences max. Use bullet points.
    2. Professional English. No Pidgin.
    3. NEVER add Python code, code examples, or 'Code Example' unless user says 'show code' or 'write python'.
    4. End with a helpful summary.""",

    "pidgin": """You are B.CORP Brain 3.0. Reply in Nigerian Pidgin English only.
    RULES: Keep am short. 3-4 lines. Use 'na, wey, da'.
    NEVER bring Python code unless user ask for am.""",

    "teacher": """You are B.CORP Brain 3.0 Strict Teacher.
    RULES: Explain topic in 4 sentences max, then ask 1 question.
    NO CODE unless user say 'show me code'.""",

    "short": """You are B.CORP Brain 3.0 Short Mode.
    RULES: Answer in maximum 3 lines only. Use bullet points. NO CODE.""",

    "proverb": """You are B.CORP Brain 3.0 with Nigerian Wisdom.
    RULES: Answer professionally in 4 sentences, then add: 'Proverb: [relevant Nigerian proverb]'
    NO CODE unless user ask.""",

    "code": """You are B.CORP Brain 3.0 Code Master. Like Meta AI.
    RULES:
    1. Give working Python code FIRST in ```python block.
    2. Then explain what the code does in 2-3 lines.
    3. Only give code when in this mode."""
}

@app.route('/')
def home():
    return render_template('index.html')

# STEP 49: B.CORP BRANDED PAGES - NO EXTERNAL LINKS
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
        # Handle both JSON and FormData for file upload
        if request.is_json:
            data = request.json
            user_question = data.get("question", "").strip()
            memory = data.get("memory", [])
            mode = data.get("mode", "pro")
            file = None
        else:
            user_question = request.form.get("question", "").strip()
            memory = json.loads(request.form.get("memory", "[]"))
            mode = request.form.get("mode", "pro")
            file = request.files.get("file")

        # Select system prompt based on mode
        system_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS["pro"])

        file_content = ""
        vision_messages = []

        # Handle file upload
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()

            # If image - use vision model
            if filename.lower().endswith(('png', 'jpg', 'jpeg')):
                file_data = {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64.b64encode(file_bytes).decode()}"
                    }
                }
                file_content = f"\n[User uploaded image: {filename}]"
                vision_messages = [
                    {"type": "text", "text": f"Analyze this image and answer: {user_question}"},
                    file_data
                ]
            # If text/code/pdf - read content
            else:
                try:
                    text_content = file_bytes.decode('utf-8')[:8000]
                    file_content = f"\n[User uploaded {filename}]:\n{text_content}"
                except:
                    file_content = f"\n[User uploaded {filename} - binary file, cannot read]"

        def generate():
            # Use vision model if image uploaded
            model = "llama-3.2-90b-vision-preview" if vision_messages else "llama-3.3-70b-versatile"

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(memory)

            # Build user message
            if vision_messages:
                messages.append({"role": "user", "content": vision_messages})
            else:
                messages.append({"role": "user", "content": user_question + file_content})

            # Stream from Groq
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=800, # REDUCED FOR SHORTER ANSWERS
                temperature=0.3,
                stream=True
            )

            full_answer = ""
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    text = chunk.choices[0].delta.content
                    full_answer += text
                    yield f"data: {text}\n\n"

            # FIX: CLEAN FULL ANSWER BEFORE [DONE]
            full_answer = clean_markdown(full_answer, mode)

            memory.append({"role": "user", "content": user_question + file_content})
            memory.append({"role": "assistant", "content": full_answer})

            # REMOVED: AUDIO/TTS COMPLETELY

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
            return jsonify({"error": "Only Python supported for now"}), 400

        # SAFETY: Block dangerous imports/functions
        dangerous = ['os.', 'subprocess.', 'sys.', 'shutil.', 'socket.', 'requests.', '__import__', 'eval(', 'exec(']
        if any(d in code for d in dangerous):
            return jsonify({"output": "❌ Blocked: This code tries to access system. Only safe math/prints allowed."})

        # Create temp file and run safely
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            result = subprocess.run([sys.executable, temp_file], capture_output=True, text=True, timeout=3)
            output = result.stdout if result.stdout else result.stderr
            if not output: output = "Code ran successfully. No output."
        except subprocess.TimeoutExpired: output = "❌ Timeout: Code took too long. Max 3 seconds."
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
            explanation = "Image uploaded. Please ask your question about it in chat for full vision analysis."
        else:
            prompt = f"Explain '{topic}' as B.CORP Engineering Agent for Nigeria. Cover: what it is, how it works, key components, applications. Use professional technical English. Max 5 sentences. NO CODE."

            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                max_tokens=400,
                temperature=0.3
            )
            explanation = chat_completion.choices[0].message.content

        # REMOVED AUDIO

        return jsonify({
            "answer": explanation,
            "status": "success"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# REMOVED: generate_audio() and /audio/ route completely

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
