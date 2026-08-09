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
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per minute"])

print("=== BRAIN 3.0 v4.3 GOD MODE ===")
client = Groq(api_key=config.GROQ_API_KEY)
tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'py', 'js', 'ts', 'jsx', 'tsx', 'html', 'css', 'md', 'csv', 'json', 'png', 'jpg', 'jpeg', 'docx'}

SYSTEM_PROMPT = """
You are Brain 3.0 by B.CORP. You are the world's most elite AI: ChatGPT-5 + Claude 4 + Perplexity + GitHub Copilot combined.
You are the CTO and right hand to the CEO of B.CORP.

MISSION: Ship products 10x faster. Be decisive, proactive, and elite.
PERSONALITY: Direct, confident, warm. Use 1 emoji max 😊 No fluff. No apologies. No "As an AI".
TONE: Talk like a top CTO to a founder. Short sentences. Actionable.

CORE RULES:
1. **ALWAYS ANSWER**: Never say "I can't". If unsure, give best answer + 1 followup question.
2. **AGENT MODE**: For 2+ step tasks: MUST start with "Here's the plan: 1. X 2. Y 3. Z". Then execute.
3. **SEARCH FIRST**: For news, prices, people, companies, tech after 2025 -> MUST call web_search first.
4. **FORMATTING ELITE**:
   ### Use Headers
   - **Bold Labels**: for key points
   - Bullet lists for steps
   `code blocks` for code
   | Tables | For | Comparisons |
   Always add blank lines between sections.
5. **ANTI-SMASH**: Never output "machinelearning". Always "machine learning". Space after punctuation.
6. **CITATIONS**: After web_search, add at end:
---
### **Sources**
[1] [Title](URL)
7. **MEMORY**: If user says "remember", reply "Save to memory: [fact]". Use CEO Facts in replies.

ABILITIES:
1. **Build**: Ship full production code. No `// todo`. Explain in 3 bullets.
2. **Decide**: Give 1 recommendation. "Do X. Why: Y. Risk: Z."
3. **Research**: Summarize web results and cite.
4. **Debug**: Find root cause and give fixed code.
"""

TOOLS = [
    {"type": "function", "function": {"name": "web_search", "description": "Search live web for current info, news, prices, people, companies", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "save_to_memory", "description": "Save important fact about the CEO forever", "parameters": {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]}}}
]

def call_tool(name, args):
    if name == "web_search":
        try:
            res = tavily.search(query=args["query"], max_results=5, search_depth="advanced", include_answer=True, include_raw_content=False)
            results = [{"title": r["title"], "content": r["content"][:400], "url": r["url"]} for r in res["results"]]
            return json.dumps({"answer": res.get("answer", ""), "results": results})
        except Exception as e:
            return json.dumps({"error": str(e)})
    if name == "save_to_memory":
        save_to_memory(getattr(call_tool, 'current_user_id', None), args["fact"])
        return f"Saved to memory: {args['fact']}"
    return "Tool not found"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def final_clean(text):
    if not text: return ''
    text = re.sub(r'web_search\s*\{.*?\}', '', text, flags=re.DOTALL)
    text = re.sub(r'save_to_memory\s*\{.*?\}', '', text, flags=re.DOTALL)
    text = re.sub(r'(\w)"(\w)', r'\1 "$2', text) # FIX [1]"Title
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'([a-z])(\d)', r'\1 \2', text)
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'([.,!?])([A-Za-z])', r'\1 \2', text)
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    text = re.sub(r"(\w)\s+'(\w)", r"\1'\2", text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def pick_model(question, has_image):
    if has_image: return "meta-llama/llama-4-scout-17b-16e-instruct"
    q = question.lower()
    if any(word in q for word in ["code", "build", "function", "debug", "react", "flask", "api"]): return "openai/gpt-oss-120b"
    if len(q) < 50: return "llama-3.1-8b-instant"
    return "llama-3.3-70b-versatile"

def get_user_id(req):
    uid = req.args.get("user_id") or req.form.get("user_id")
    if not uid: return str(uuid.uuid4())
    try: return str(uuid.UUID(uid, version=4))
    except: return str(uuid.uuid4())

def create_chat(user_id, first_message):
    title = first_message[:70] + "..." if len(first_message) > 70 else first_message
    try:
        res = supabase.table("chats").insert({"user_id": user_id, "title": title, "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()}).execute()
        return res.data[0]['id'] if res.data else None
    except Exception as e: print("CREATE_CHAT:", e); return None

def load_chats(user_id):
    try: return supabase.table("chats").select("*").eq("user_id", user_id).order("updated_at", desc=True).limit(100).execute().data or []
    except Exception as e: print("LOAD_CHATS:", e); return []

def load_messages(chat_id):
    try: return supabase.table("messages").select("*").eq("chat_id", chat_id).order("created_at").execute().data or []
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
        res = supabase.rpc("match_memory", {"p_user_id": user_id, "query_embedding": emb, "match_count": 5}).execute()
        return "\n".join([f"- {m['content']}" for m in res.data]) if res.data else ""
    except Exception as e: print("Memory search:", e); return ""

@app.route('/')
def home(): return render_template('index.html')
@app.route('/static/<path:filename>')
def serve_static(filename): return send_from_directory(app.static_folder, filename)
@app.route("/api/config")
def get_config(): return jsonify({"supabase_url": config.SUPABASE_URL, "supabase_anon_key": config.SUPABASE_ANON_KEY})
@app.route("/api/chats", methods=["GET"])
@limiter.limit("30 per minute")
def get_chats(): return jsonify(load_chats(get_user_id(request)))
@app.route("/api/chat/<chat_id>", methods=["GET"])
@limiter.limit("30 per minute")
def get_chat(chat_id): return jsonify(load_messages(chat_id))
@app.route("/api/chat/delete", methods=["POST"])
@limiter.limit("15 per minute")
def delete_chat():
    data = request.get_json()
    chat_id = data.get("chat_id")
    supabase.table("messages").delete().eq("chat_id", chat_id).execute()
    supabase.table("chats").delete().eq("id", chat_id).execute()
    return jsonify({"success": True})

@app.route("/api/chat", methods=["POST"])
@limiter.limit("30 per minute")
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
        memory = [{"role": m['role'], "content": m['content']} for m in messages_db[-25:]]
        long_memory = search_memory(user_id, user_question)
        if long_memory: memory.insert(0, {"role": "system", "content": f"CEO Facts to remember:\n{long_memory}"})

        file_content = ""; has_image = False
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            file_ext = filename.rsplit('.', 1)[1].lower()
            if file_ext == 'pdf':
                import PyPDF2
                pdf = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                file_content = f"\n\n[PDF: {filename}]\n" + "".join([p.extract_text() for p in pdf.pages if p.extract_text()])[:25000]
                if not user_question: user_question = "Summarize this PDF in 5 bullets with key takeaways and action items"
            elif file_ext in ['png', 'jpg', 'jpeg']:
                file_content = f"\n\n[IMAGE: {filename}]. Describe this image in detail and extract any text."
                has_image = True
            else:
                decoded = file_bytes.decode('utf-8', errors='ignore')[:25000]
                file_content = f"\n\n[FILE: {filename}]\n```{file_ext}\n{decoded}\n```"

        model = pick_model(user_question, has_image)
        messages = [{"role": "system", "content": f"CEO of B.CORP. {SYSTEM_PROMPT}"}] + memory
        messages.append({"role": "user", "content": f"Question: {user_question}" + file_content})
        if user_question: save_message(chat_id, "user", user_question)

        def generate():
            full = ""; sources = []
            try:
                yield f"data: [CHAT_ID]{chat_id}[/CHAT_ID]\n\n"

                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    max_tokens=4096,
                    temperature=0.7,
                    stream=True
                )

                tool_calls = []
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full += content
                        yield f"data: {content}\n\n"

                    if chunk.choices and chunk.choices[0].delta.tool_calls:
                        tool_calls.append(chunk.choices[0].delta.tool_calls[0])

                # GOD MODE FIX: FORCE 2ND LLM CALL TO REFORMAT WITH MARKDOWN
                if tool_calls:
                    yield f"data: *Searching web for latest info...*\n\n"
                    messages.append({"role": "assistant", "content": full, "tool_calls": tool_calls})
                    for tc in tool_calls:
                        result_json = call_tool(tc.function.name, json.loads(tc.function.arguments))
                        result = json.loads(result_json)
                        if "results" in result: sources = result["results"]
                        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_json})

                    # CRITICAL: TELL LLM TO FORMAT NOW
                    messages.append({"role": "system", "content": "Using the search results above, write a final answer with ### Headers, **Bold**, bullet lists, and cite sources at the end. Add blank lines."})
                    
                    full = "" # RESET
                    stream2 = client.chat.completions.create(model=model, messages=messages, max_tokens=4096, temperature=0.7, stream=True)
                    for chunk in stream2:
                        if chunk.choices and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            full += content
                            yield f"data: {content}\n\n"

                    if sources:
                        citation_text = "\n\n---\n### **Sources**\n" + "\n".join([f"[{i+1}] [{s['title']}]({s['url']})" for i, s in enumerate(sources)])
                        full += citation_text
                        yield f"data: {citation_text}\n\n"

                full = final_clean(full)
                if "Save to memory:" in full:
                    fact = full.split("Save to memory:")[1].split("\n")[0].strip()
                    save_to_memory(user_id, fact)

                save_message(chat_id, "assistant", full)
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
