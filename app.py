from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
import os
import base64
import io
import re
import time
import PyPDF2
import traceback
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
    # 1. Fix glued words: TechnologyThe -> Technology The
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    # 2. Fix dash: Dev-Battery -> Dev - Battery
    text = re.sub(r'(\w)-(\w)', r'\1 - \2', text)
    # 3. Fix colon: Label:text -> Label: text
    text = re.sub(r':(\w)', r': \1', text)
    # 4. Force line breaks before headers
    text = re.sub(r'([^\n])###', r'\1\n\n###', text)
    # 5. Force line breaks before numbers
    text = re.sub(r'([^\n])(\d+\.)', r'\1\n\2', text)
    # 6. Force line breaks before bullets
    text = re.sub(r'([^\n])- \*\*', r'\1\n- **', text)
    # 7. Remove code blocks if not code mode
    if mode!= "code":
        text = re.sub(r'```[\s\S]*?```', '', text)
    # 8. Fix multiple spaces
    text = re.sub(r'[ ]{2,}', ' ', text)
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

# MULTIMEDIA SYSTEM PROMPTS
MODE_PROMPTS = {
    "pro": """You are Brain 3.0 by B.CORP. Current date: July 2026. Answer exactly like Meta AI and ChatGPT.
CRITICAL FORMATTING RULES:
1. Add 2 blank lines before every ### Heading
2. Add 1 blank line before every - **bullet** or 1. numbered list
3. Always put space after : and - Example: **Label**: explanation
4. Never glue words together. Write "Technology. The" not "TechnologyThe"
5. Address user as "CEO".
6. Keep it 5-8 sentences.
7. End with "Would you like me to... CEO?" """,

    "pidgin": """You be Brain 3.0 by B.CORP. Oga CEO.
FORMATTING: Use ### headings with 2 blank lines before. Use - **bold**: bullets with spaces. No glued words. End with question.""",

    "code": """You are Brain 3.0 Code Master.
FORMATTING: Must use exactly:
### 1. What it Does
### 2. Issues Found
### 3. The Fixed Code
### 4. How To Use
Put 2 blank lines before each ###. Address as CEO.""",

    "multimedia": """You are Brain 3.0 Multimedia by B.CORP. Oga CEO.
YOUR JOB: See files/images and reason like a consultant.
CRITICAL FORMATTING RULES:
### 1. What I See
Describe the image/document clearly in 2 lines.

### 2. Analysis
Break down insights, problems, patterns. Use - **Key Point**: explanation

### 3. Recommendation
Tell CEO exactly what to do next. 3 actionable steps.

RULES: Add 2 blank lines before each ###. No glued words. Put space after :"""
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
            except Exception as e:
                print(f"Tavily Error: {e}")

        file_content = ""
        vision_messages = []
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            file_ext = filename.rsplit('.', 1)[1].lower()

            if file_ext in ['png', 'jpg', 'jpeg']:
                b64 = base64.b64encode(file_bytes).decode()
                vision_messages = [
                    {"type": "text", "text": f"User Question: {user_question}. Analyze this image thoroughly."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]
            elif file_ext == 'pdf':
                pdf = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                file_content = "\n[PDF CONTENT]: " + "".join([p.extract_text() for p in pdf.pages if p.extract_text()])[:8000]
                if not user_question:
                    user_question = "Summarize this PDF and give me key insights CEO"
            else:
                file_content = f"\n[FILE {filename}]: ```{file_ext}\n{file_bytes.decode('utf-8', errors='ignore')[:8000]}\n```"

        system_prompt = f"You are talking to {user_name}. {MODE_PROMPTS.get(mode, MODE_PROMPTS['pro'])}"
        model = "llama-3.2-90b-vision-preview" if vision_messages else "llama-3.3-70b-versatile"

        messages = [{"role": "system", "content": system_prompt}] + memory
        messages.append({"role": "user", "content": vision_messages if vision_messages else user_question + file_content + search_results})

        def generate():
            full = ""
            try:
                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=1500, # increased for multimedia
                    temperature=0.5, # lower for better reasoning
                    stream=True
                )
                buffer = ""
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        buffer += chunk.choices[0].delta.content
                        if re.search(r'[ \n.,;:!?]$', buffer):
                            cleaned_chunk = clean_markdown(buffer, mode)
                            full += cleaned_chunk
                            yield f"data: {cleaned_chunk}\n\n"
                            buffer = ""
                        time.sleep(0.01)

                if buffer:
                    cleaned_chunk = clean_markdown(buffer, mode)
                    full += cleaned_chunk
                    yield f"data: {cleaned_chunk}\n\n"

            except Exception as e:
                print(f"Stream Error: {traceback.format_exc()}")
                yield f"data: ❌ Error: {str(e)}\n\n"

            try:
                save_memory(user_id, memory + [{"role": "user", "content": user_question}, {"role": "assistant", "content": full}])
            except Exception as e:
                print(f"Memory Save Error: {e}")

            yield f"data: [DONE]\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
    except Exception as e:
        print(f"Ask Route Error: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route("/run-code", methods=["POST"])
def run_code():
    return jsonify({"output": "Code runner disabled for safety"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT)
