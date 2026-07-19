from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
import os
import base64
import io
import re
import time
import PyPDF2
import traceback
import replicate
from groq import Groq
from tavily import TavilyClient
from werkzeug.utils import secure_filename
from config import config
from supabase import create_client, Client

app = Flask(__name__, static_folder="static", template_folder="templates")

client = Groq(api_key=config.GROQ_API_KEY)
tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

# Set Replicate token SAFELY
if hasattr(config, 'REPLICATE_API_TOKEN') and config.REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = config.REPLICATE_API_TOKEN
    print("[INIT] REPLICATE_API_TOKEN loaded")
else:
    print("[FATAL] REPLICATE_API_TOKEN missing from config.py or Render Env")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'txt', 'py', 'js', 'html', 'css', 'md', 'ico'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_markdown(text):
    # V3.1.7 FINAL: Protect Brain 3.0 and fix spacing
    text = re.sub(r'(Brain)(\s*)(\d)', r'\1 \3', text) # Force "Brain 3"
    text = re.sub(r'(B\.CORP)(\s*)(\d)', r'\1 \3', text) # Force "B.CORP 3"
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text) # CEOthe -> CEO the
    text = re.sub(r'(\w):(\w)', r'\1: \2', text)
    text = re.sub(r'(\w),(\w)', r'\1, \2', text)
    text = re.sub(r'(\s)-(\s)', r'\1-\2', text) # FIX: don't turn "human-like" into "human - like"
    text = re.sub(r'([^\n])###', r'\n\n###', text)
    text = re.sub(r'([^\n])(\d+\.)', r'\n\2', text)
    text = re.sub(r'([^\n])- \*\*', r'\n- **', text)
    text = re.sub(r'[ ]{2,}', ' ', text)
    return text.strip()

def needs_search(query):
    keywords = ['price', 'news', 'today', 'latest', '2026', 'current', 'weather', 'score', 'update', 'research', 'how', 'what', 'why', 'best']
    return any(word in query.lower() for word in keywords)

def needs_image(query):
    query = query.lower()
    keywords = ['imagine', 'generate image', 'create image', 'create a image', 'draw', 'picture of', 'make me a', 'photo of']
    return any(word in query for word in keywords)

def generate_image(prompt):
    try:
        if not os.environ.get("REPLICATE_API_TOKEN"):
            return "ERROR: REPLICATE_API_TOKEN is missing. Add it to Render Environment Variables."

        print(f"[REPLICATE] Generating: {prompt}")
        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": f"Ultra realistic, 4k, B.CORP corporate style, professional lighting, {prompt}",
                "aspect_ratio": "1:1",
                "output_format": "webp",
                "output_quality": 90,
                "num_outputs": 1
            }
        )
        if isinstance(output, list):
            image_url = str(output[0])
        else:
            image_url = str(output)

        print(f"[REPLICATE] Success: {image_url}")
        return image_url
    except Exception as e:
        err = traceback.format_exc()
        print(f"[REPLICATE] Error: {err}")
        return f"ERROR: {str(e)}"

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

SYSTEM_PROMPT = """You are Brain 3.0 by B.CORP. Current date: July 19 2026. You are CEO's personal AI assistant.
You can see images, read PDFs, write code, browse the web, AND generate images.
Act like ChatGPT + Meta AI combined.

CRITICAL FORMATTING RULES:
1. Add 2 blank lines before every ### Heading
2. Add 1 blank line before every - **bullet** or 1. numbered list
3. Always put space after : and - Example: **Label**: explanation
4. Never glue words together. Write "Technology. The" not "TechnologyThe"
5. Address user as "CEO".
6. If user uploads an image/PDF: First do ### 1. What I See ### 2. Analysis ### 3. Recommendation
7. If user asks code: Use ### 1. What it Does ### 2. Code ### 3. How To Use
8. If user asks to generate image: Say "Generating image now CEO..."
9. Keep answers 5-10 sentences. End with "Would you like me to... CEO?" """

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
        user_name = request.form.get("user_name", "CEO") if not request.is_json else request.json.get("user_name", "CEO")
        user_id = request.form.get("user_id") if not request.is_json else request.json.get("user_id")
        file = request.files.get("file")

        if not user_id: return jsonify({"error": "Not logged in"}), 401

        # IMAGE GENERATION - CHECK FIRST BEFORE STREAMING
        if needs_image(user_question):
            prompt = user_question
            for word in ['imagine', 'generate image', 'create image', 'create a image', 'draw', 'picture of', 'make me a', 'photo of']:
                prompt = prompt.replace(word, "")
            prompt = prompt.strip()

            image_url = generate_image(prompt)
            if image_url and not image_url.startswith("ERROR"):
                answer = f"### Generated Image CEO ###\n\n**Prompt**: {prompt}\n\nHere is your image:"
                return jsonify({ "answer": answer, "image": image_url })
            else:
                return jsonify({"error": image_url or "Image generation failed. Check Render Logs"}), 500

        # NORMAL CHAT
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
        has_file = False
        if file and allowed_file(file.filename):
            has_file = True
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            file_ext = filename.rsplit('.', 1)[1].lower()

            if file_ext in ['png', 'jpg', 'jpeg']:
                b64 = base64.b64encode(file_bytes).decode()
                vision_messages = [
                    {"type": "text", "text": f"User: {user_question}. Analyze this image thoroughly CEO."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]
            elif file_ext == 'pdf':
                pdf = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                file_content = "\n[PDF CONTENT]: " + "".join([p.extract_text() for p in pdf.pages if p.extract_text()])[:8000]
                if not user_question:
                    user_question = "Summarize this PDF and give me key insights CEO"
            else:
                file_content = f"\n[FILE {filename}]: ```{file_ext}\n{file_bytes.decode('utf-8', errors='ignore')[:8000]}\n```"

        model = "llama-3.2-90b-vision-preview" if has_file else "llama-3.3-70b-versatile"
        system_prompt = f"You are talking to {user_name}. {SYSTEM_PROMPT}"

        messages = [{"role": "system", "content": system_prompt}] + memory
        messages.append({"role": "user", "content": vision_messages if vision_messages else user_question + file_content + search_results})

        def generate():
            full = ""
            try:
                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=1500,
                    temperature=0.5,
                    stream=True
                )
                buffer = ""
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        buffer += chunk.choices[0].delta.content
                        # FIXED: Only yield on sentence end to prevent "Brain" + "3.0" split
                        if re.search(r'[ \n.,;:!?]$', buffer):
                            cleaned_chunk = clean_markdown(buffer)
                            full += cleaned_chunk
                            yield f"data: {cleaned_chunk}\n\n"
                            buffer = ""
                        time.sleep(0.005) # faster typing feel

                if buffer:
                    cleaned_chunk = clean_markdown(buffer)
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
