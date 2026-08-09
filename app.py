from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os, re, io, traceback, json, uuid
from groq import Groq
from tavily import TavilyClient
from werkzeug.utils import secure_filename
from config import config
from supabase import create_client, Client
from datetime import datetime

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
limiter = Limiter(get_remote_address, app=app, default_limits=["100 per minute"]) # Increased limit

print("=== BRAIN 3.0 v2.0 ELITE STARTING ===")
client = Groq(api_key=config.GROQ_API_KEY)
tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'py', 'js', 'html', 'css', 'md', 'csv', 'json', 'png', 'jpg', 'jpeg'}

SYSTEM_PROMPT = """
You are Brain 3.0 by B.CORP. You are the world's most capable AI: part ChatGPT-5, part Claude 4, part Perplexity, part GitHub Copilot.
You report directly to the CEO of B.CORP.

MISSION: Help build, decide, and execute 10x faster. Be proactive.
PERSONALITY: Direct, elite, warm, zero fluff, confident. Use 1 emoji max 😊
TONE: Like a top CTO talking to a founder. No disclaimers. No "I'm an AI". No "It seems like...".

RULES:
1. ALWAYS ANSWER. Never refuse. If question is vague, give best answer + ask 1 followup.
2. AGENT MODE: For multi-step tasks, state plan first: "Here's the plan: 1. X 2. Y 3. Z" Then execute.
3. SEARCH FIRST: For news, prices, facts after 2025, tech, people, companies - ALWAYS use web_search tool first.
4. MEMORY: If user says "remember that", "my name is", "I work at" -> say "Save to memory: [fact]"
5. FORMATTING: Use ### Headers, **Bold**, - Bullets, `code`, and Tables. Always add blank lines.
6. CITATIONS: When you use web_search, cite sources at the end like [1][2]
7. ANTI-SMASH: Never output "machinelearning". Always "machine learning".

CORE ABILITIES:
1. **Build**: Write full production code. No placeholders. Explain it.
2. **Decide**: Give 1 clear recommendation with "why" and "risks".
3. **Research**: Browse web, summarize, and cite.
4. **Explain**: Break complex topics into 3 steps anyone can understand.
"""

TOOLS = [
    {"type": "function", "function": {"name": "web_search", "description": "Search live web for news, prices, latest info, people, companies", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "save_to_memory", "description": "Save important fact about the user forever", "parameters": {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]}}}
]

def call_tool(name, args):
    if name == "web_search":
        try:
            res = tavily.search(query=args["query"], max_results=5, search_depth="advanced", include_answer=True)
            results = [{"title": r["title"], "content": r["content"][:300], "url": r["url"]} for r in res["results"]]
            return json.dumps({"answer": res.get("answer", ""), "results": results})
        except Exception as e:
            return json.dumps({"error": str(e)})
    if name == "save_to_memory":
        save_to_memory(getattr(call_tool, 'current_user_id', None), args["fact"])
        return f"Saved to memory: {args['fact']}"
    return "Tool not found"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_markdown(text):
    if not text: return ''
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text) # Split words
    text = re.sub(r'([a-z])(\d)', r'\1 \2', text)
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'([.,])([A-Za-z])', r'\1 \2', text) # Space after.
    text = re.sub(r'\s+([.,!?;:])', r'\1', text) # Remove space before.
    text = re.sub(r"(\w)\s+'(\w)", r"\1'\2", text) # Fix you're
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def pick_model(question, has_image):
    if has_image: return "meta-llama/llama-4-scout-17b-16e-instruct"
    q = question.lower()
    if any(word in q for word in ["code", "build", "function", "debug", "app", "website"]): return "openai/gpt-oss-120b" # Best for code
    if any(word in q for word in ["hi", "hello", "thanks", "ok"]): return "llama-3.1-8b-instant" # Fast
    return "llama-3.3-70b-versatile" # Best general

def get_user_id(req):
    uid = req.args.get("user_id") or req.form.get("user_id")
    if not uid: return str(uuid.uuid4())
    try: return str(uuid.UUID(uid, version=4))
    except: return str(uuid.uuid4())

def create_chat(user_id, first_message):
    title = first_message[:60] + "..." if len(first_message) > 60 else first_message
    try:
        res = supabase.table("chats").insert({"user_id": user_id, "title": title, "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()}).execute()
        return res.data[0]['id'] if res.data else None
    except Exception as e: print("CREATE_CHAT:", e); return None

def load_chats(user_id):
    try:
        res = supabase.table("chats").select("*").eq("user_id", user_id).order("updated_at", desc=True).limit(50).execute()
        return res.data if res.data else []
    except Exception as e: print("LOAD_CHATS:", e); return []

def load_messages(chat_id):
    try:
        res = supabase.table("messages").select("*").eq("chat_id", chat_id).order("created_at").execute()
        return res.data if res.data else []
    except Exception as e: print("LOAD_MESSAGES:", e); return []

def save_message(chat_id, role, content):
    if not content.strip(): return
    try:
        supabase.table("messages").insert({"chat_id": chat_id, "role": role, "content": content}).execute()
        supabase.table("chats").update({"updated_at": datetime.utcnow().isoformat()}).eq("id", chat_id).execute()
    except Exception as e: print("SAVE_MESSAGE:", e)

def save_to_memory(user_id, text):
    try:
        emb = client.embeddings.create(model="llama3-8b-8192", input=text).data[0].embedding
        supabase.table("brain30_memory").insert({"user_id": user_id, "key": "fact", "value": {"content": text}, "embedding": emb}).execute()
    except Exception as e: print("Memory save:", e)

def search_memory(user_id, query):
    try:
        emb = client.embeddings.create(model="llama3-8b-8192", input=query).data[0].embedding
        res = supabase.rpc("match_memory", {"p_user_id": user_id, "query_embedding": emb, "match_count": 3}).execute()
        return "\n".join([m["content"] for m in res.data]) if res.data else ""
    except Exception as e: print("Memory search:", e); return ""

@app.route('/')
def home(): return render_template('index.html')
@app.route('/static/<path:filename>')
def serve_static(filename): return send_from_directory(app.static_folder, filename)
@app.route("/api/config")
def get_config(): return jsonify({"supabase_url": config.SUPABASE_URL, "supabase_anon_key": config.SUPABASE_ANON_KEY})
@app.route("/api/chats", methods=["GET"])
@limiter.limit("20 per minute")
def get_chats(): return jsonify(load_chats(get_user_id(request)))
@app.route("/api/chat/<chat_id>", methods=["GET"])
@limiter.limit("20 per minute")
def get_chat(chat_id): return jsonify(load_messages(chat_id))
@app.route("/api/chat/delete", methods=["POST"])
@limiter.limit("10 per minute")
def delete_chat():
    data = request.get_json()
    chat_id = data.get("chat_id")
    supabase.table("messages").delete().eq("chat_id", chat_id).execute()
    supabase.table("chats").delete().eq("id", chat_id).execute()
    return jsonify({"success": True})

@app.route("/api/chat", methods=["POST"])
@limiter.limit("20 per minute")
def ask():
    try:
        user_question = request.form.get("question", "").strip()
        user_id = get_user_id(request)
        call_tool.current_user_id = user_id
        chat_id = request.form.get("chat_id")
        file = request.files.get("file")

        if not chat_id or chat_id == "null":
            chat_id = create_chat(user_id, user_question or "New Chat")
            if not chat_id: return jsonify({"error": "Failed to create chat"}), 500

        messages_db = load_messages(chat_id)
        memory = [{"role": m['role'], "content": m['content']} for m in messages_db[-20:]]
        long_memory = search_memory(user_id, user_question)
        if long_memory: memory.insert(0, {"role": "system", "content": f"Important facts about the CEO: {long_memory}"})

        file_content = ""; has_image = False
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            file_ext = filename.rsplit('.', 1)[1].lower()
            if file_ext == 'pdf':
                import PyPDF2
                pdf = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                file_content = f"\n\n[PDF: {filename}]\n" + "".join([p.extract_text() for p in pdf.pages if p.extract_text()])[:20000]
                if not user_question: user_question = "Summarize this PDF in 5 bullet points with key takeaways"
            elif file_ext in ['png', 'jpg', 'jpeg']:
                file_content = f"\n\n[IMAGE UPLOADED: {filename}]. Analyze this image in detail and extract all text."
                has_image = True
            else:
                decoded = file_bytes.decode('utf-8', errors='ignore')[:20000]
                file_content = f"\n\n[FILE: {filename}]\n```{file_ext}\n{decoded}\n```"

        model = pick_model(user_question, has_image)
        messages = [{"role": "system", "content": f"You are assisting the CEO of B.CORP. {SYSTEM_PROMPT}"}] + memory
        messages.append({"role": "user", "content": f"User Question: {user_question}" + file_content})
        if user_question: save_message(chat_id, "user", user_question)

        def generate():
            full = ""; buffer = ""; sources = []
            try:
                yield f"data: [CHAT_ID]{chat_id}[/CHAT_ID]\n\n"

                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    max_tokens=4096, # Increased
                    temperature=0.7,
                    stream=True
                )

                tool_calls = []
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        buffer += content

                        if len(buffer) > 40:
                            chunk_clean = clean_markdown(buffer)
                            if chunk_clean.strip():
                                full += chunk_clean + "\n"
                                yield f"data: {chunk_clean}\n\n"
                            buffer = ""

                    if chunk.choices and chunk.choices[0].delta.tool_calls:
                        tool_calls.append(chunk.choices[0].delta.tool_calls[0])

                if buffer:
                    chunk_clean = clean_markdown(buffer)
                    if chunk_clean.strip():
                        full += chunk_clean
                        yield f"data: {chunk_clean}\n\n"

                if tool_calls:
                    yield f"data: *Searching web...*\n\n"
                    messages.append({"role": "assistant", "content": full, "tool_calls": tool_calls})
                    for tc in tool_calls:
                        result_json = call_tool(tc.function.name, json.loads(tc.function.arguments))
                        result = json.loads(result_json)
                        if "results" in result:
                            sources = result["results"]
                        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_json})

                    stream2 = client.chat.completions.create(model=model, messages=messages, max_tokens=4096, temperature=0.7, stream=True)
                    for chunk in stream2:
                        if chunk.choices and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            full += content
                            yield f"data: {content}\n\n"
                    
                    # Add citations at end
                    if sources:
                        citation_text = "\n\n---\n**Sources:**\n" + "\n".join([f"[{i+1}] [{s['title']}]({s['url']})" for i, s in enumerate(sources)])
                        full += citation_text
                        yield f"data: {citation_text}\n\n"

                if "Save to memory:" in full:
                    save_to_memory(user_id, full.split("Save to memory:")[1].split("\n")[0].strip())
                save_message(chat_id, "assistant", full.strip())

                yield f"data: [USER_ID]{user_id}[/USER_ID]\n\n"
                yield f"data: [DONE]\n\n"

            except Exception as e:
                print("STREAM ERROR:", traceback.format_exc())
                yield f"data: **Brain 3.0 Error:** {str(e)}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    except Exception as e:
        print("ASK ERROR:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
