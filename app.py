from flask import Flask, render_template, request, jsonify, send_from_directory, Response, stream_with_context
import os
import base64
import json
import subprocess
import sys
import tempfile
from groq import Groq
from gtts import gTTS
import hashlib
from werkzeug.utils import secure_filename
from config import config

app = Flask(__name__, template_folder="templates")

# Render uses /tmp for writable files
AUDIO_DIR = "/tmp/bcorp_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

# File upload config
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'txt', 'py', 'js', 'html', 'css', 'md'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 # 10MB max

# Configure Groq - FREE, no billing
client = Groq(api_key=config.GROQ_API_KEY)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# NEW: Mode prompts dictionary
MODE_PROMPTS = {
    "pro": """You are BCorp Brain 3.0, a professional engineer and teacher.
    Rules:
    1. Use correct English grammar and spelling always
    2. Add space after markdown symbols: ### Heading, **bold**, *italic*
    3. Put space between words and code: "In Python" not "InPython"
    4. Be clear, helpful, professional tone
    5. If user uploads image, analyze it and answer about it""",

    "pidgin": """You are BCorp Brain 3.0. Reply in Nigerian Pidgin English.
    Rules:
    1. Use words like 'you', 'make', 'na', 'abi', 'how far', 'o'
    2. Be friendly and simple. Example: 'How far boss, this voltage thing easy o'
    3. Still be technically accurate
    4. If user uploads image, analyze it and explain in Pidgin""",

    "teacher": """You are BCorp Brain 3.0 Strict Teacher.
    Rules:
    1. Explain topic clearly first
    2. Then ask user 1 question to test them
    3. If user answers wrong, say 'Incorrect! Try again' and explain why
    4. Use professional tone but firm""",

    "short": """You are BCorp Brain 3.0 Short Mode.
    Rules:
    1. Answer in maximum 3 lines only
    2. No intro, no fluff, no 'here is'. Go direct
    3. Use bullet points if needed
    4. Still be accurate""",

    "proverb": """You are BCorp Brain 3.0 with Nigerian Wisdom.
    Rules:
    1. Answer question professionally first
    2. At the end, add: 'Proverb: [relevant Nigerian proverb]'
    3. Proverb must relate to the answer
    4. Keep technical accuracy""",

    "code": """You are BCorp Brain 3.0 Code Master.
    Rules:
    1. Always give working Python code first in ```python block
    2. Then explain each line below with ### Line X: explanation format
    3. If no code needed, still give example code
    4. Make code runnable and safe"""
}

@app.route('/')
def home():
    return render_template('index.html')

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
            mode = request.form.get("mode", "pro") # NEW: Get mode from frontend
            file = request.files.get("file")

        # NEW: Select system prompt based on mode
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
                max_tokens=1200,
                temperature=0.6,
                stream=True
            )

            full_answer = ""
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    text = chunk.choices[0].delta.content

                    # FIX: Add space after markdown symbols
                    text = text.replace('###', '### ').replace('**', '** ').replace('*', '* ')
                    text = text.replace('InPython', 'In Python').replace('da difference', 'the difference')

                    full_answer += text
                    yield f"data: {text}\n\n"

            # After stream done, save memory + generate audio
            memory.append({"role": "user", "content": user_question + file_content})
            memory.append({"role": "assistant", "content": full_answer})

            # Generate audio after full answer
            audio_url = generate_audio(full_answer)
            if audio_url:
                yield f"data: [AUDIO]{audio_url}\n\n"

            yield f"data: [DONE]\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# STEP 39 - CODE SANDBOX
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
            return jsonify({
                "output": "❌ Blocked: This code tries to access system. Only safe math/prints allowed."
            })

        # Create temp file and run safely
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            # Run with timeout 3 seconds to prevent infinite loops
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=3
            )
            output = result.stdout if result.stdout else result.stderr
            if not output:
                output = "Code ran successfully. No output."
        except subprocess.TimeoutExpired:
            output = "❌ Timeout: Code took too long. Max 3 seconds."
        except Exception as e:
            output = f"❌ Error: {str(e)}"
        finally:
            os.remove(temp_file)

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
            prompt = f"Explain '{topic}' as B.CORP Engineering Agent for Nigeria. Cover: what it is, how it works, key components, applications, safety. Use professional technical English. Max 6 sentences."

            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                max_tokens=500,
                temperature=0.3
            )
            explanation = chat_completion.choices[0].message.content

        audio_url = generate_audio(explanation)

        return jsonify({
            "answer": explanation,
            "audio_url": audio_url,
            "status": "success"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def generate_audio(text: str):
    """gTTS - Google Text-to-Speech, 100% free"""
    try:
        text = text[:300]
        file_hash = hashlib.md5(text.encode()).hexdigest()[:10]
        filename = f"audio_{file_hash}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)

        if not os.path.exists(filepath):
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(filepath)

        return f"/audio/{filename}"
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename, mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=False)            
        
