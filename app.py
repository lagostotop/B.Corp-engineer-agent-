from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
import os, base64, io, re, time, PyPDF2, traceback, replicate
from groq import Groq
from tavily import TavilyClient
from werkzeug.utils import secure_filename
from config import config
from supabase import create_client, Client

app = Flask(__name__, static_folder="static", template_folder="templates")
client = Groq(api_key=config.GROQ_API_KEY)
tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

if hasattr(config, 'REPLICATE_API_TOKEN') and config.REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = config.REPLICATE_API_TOKEN
    print(" REPLICATE_API_TOKEN loaded")
else:
    print("[FATAL] REPLICATE_API_TOKEN missing")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'txt', 'py', 'js', 'html', 'css', 'md'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_markdown(text):
    text = re.sub(r'(Brain)(\s*)(\d)', r'\1 \3', text)
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'(\w):(\w)', r'\1: \2', text)
    text = re.sub(r'(\s)-(\s)', r'\1-\2', text)
    text = re.sub(r'([^\n])###', r'\n\n###', text)
    return text.strip()

def needs_image(query): return any(word in query.lower() for word in ['imagine', 'generate image', 'create image', 'draw'])

def generate_image(prompt):
    try:
        output = replicate.run("black-forest-labs/flux-schnell", input={"prompt": f"Ultra realistic, 4k, B.CORP style, {prompt}"})
        return str(output[0] if isinstance(output, list) else output)
    except Exception as e: return f"ERROR: {str(e)}"

def load_memory(user_id):
    try: return supabase.table("brain30_memory").select("memory").eq("user_id", user_id).single().execute().data["memory"]
    except: return []

def save_memory(user_id, memory):
    try: supabase.table("brain30_memory").upsert({"user_id": user_id, "memory": memory[-30:] }).execute()
    except: pass

SYSTEM_PROMPT = "You are Brain 3.0 by B.CORP. Address user as CEO."

@app.route('/')
def home(): return render_template('index.html')
@app.route("/config")
def get_config(): return jsonify({"supabase_url": config.SUPABASE_URL, "supabase_key": config.SUPABASE_KEY})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        user_question = request.form.get("question", "").strip()
        user_id = request.form.get("user_id")
        file = request.files.get("file")
        if not user_id: return jsonify({"error": "Not logged in"}), 401

        if needs_image(user_question):
            prompt = user_question.replace('imagine','').strip()
            image_url = generate_image(prompt)
            if not image_url.startswith("ERROR"): return jsonify({"answer": f"### Generated Image CEO ###\n\n**Prompt**: {prompt}", "image": image_url})
            else: return jsonify({"error": image_url}), 500

        memory = load_memory(user_id)
        file_content = ""
        vision_messages = []
        has_file = False
        if file and allowed_file(file.filename):
            has_file = True
            file_bytes = file.read()
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            if file_ext in ['png', 'jpg', 'jpeg']:
                b64 = base64.b64encode(file_bytes).decode()
                vision_messages = [{"type": "text", "text": f"Analyze this image CEO: {user_question}"}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]

        model = "llama-3.2-11b-vision-preview" if has_file else "llama-3.3-70b-versatile" # THIS IS THE FIX
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + memory
        messages.append({"role": "user", "content": vision_messages if vision_messages else user_question + file_content})

        def generate():
            full = ""
            stream = client.chat.completions.create(model=model, messages=messages, max_tokens=1500, stream=True)
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    text = clean_markdown(chunk.choices[0].delta.content)
                    full += text
                    yield f"data: {text}\n\n"
            save_memory(user_id, memory + [{"role": "user", "content": user_question}, {"role": "assistant", "content": full}])
            yield f"data: [DONE]\n\n"
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    except Exception as e: return jsonify({"error": str(e)}), 500
