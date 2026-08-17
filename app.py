import os, uuid, json, logging, time
from datetime import datetime, timezone
from flask import Flask, request, Response, jsonify, send_from_directory, g
from flask_cors import CORS
from werkzeug.utils import secure_filename
from supabase import create_client, Client
from brain_core import ModelRouter, save_message, get_chat_history
from agents.engine import run_agent  # <- AGENT ENGINE

# ============ 1. ENV VALIDATION ============
REQUIRED_ENV = ["SUPABASE_URL", "SUPABASE_KEY", "GROQ_API_KEY"]
missing = [x for x in REQUIRED_ENV if not os.getenv(x)]
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============ 2. FLASK SETUP ============
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024 # 20MB limit
CORS(app, resources={r"/api/*": {"origins": os.getenv("ALLOWED_ORIGINS", "*").split(",")}})

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
router = ModelRouter(supabase)

UPLOAD_FOLDER = "/tmp/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

logger.info("SUPABASE_URL: OK")
logger.info("SUPABASE_KEY: OK") 
logger.info("GROQ_API_KEY: OK")

# ============ 3. REQUEST LOGGING ============
@app.before_request
def before_request():
    g.request_id = str(uuid.uuid4())[:8]
    g.start_time = time.perf_counter()
    logger.info("[%s] %s %s", g.request_id, request.method, request.path)

@app.after_request
def after_request(response):
    duration = time.perf_counter() - g.start_time
    logger.info("[%s] status=%s duration=%.3fs", g.request_id, response.status_code, duration)
    response.headers["X-Request-ID"] = g.request_id
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    req_id = getattr(g, "request_id", "unknown")
    logger.exception("[%s] Unhandled exception", req_id)
    return jsonify({"error": "Internal server error", "request_id": req_id}), 500

def log(req_id, msg, **kwargs):
    logger.info("[%s] %s %s", req_id, msg, json.dumps(kwargs) if kwargs else "")

# ============ 4. AUTH ============
def verify_token(token):
    if not token: return None
    try:
        user = supabase.auth.get_user(token)
        return user.user.id if user and user.user else None
    except Exception:
        logger.exception("Token verification failed")
        return None

# ============ 5. ROUTES ============
@app.route("/")
def index(): return send_from_directory("templates", "index.html")

@app.route("/health")
def health(): return jsonify({"status": "ok", "service": "brain4", "version": "6.0.0-agent"})

@app.route("/sw.js")
def service_worker(): return send_from_directory("static", "sw.js")

@app.route("/static/<path:path>")
def send_static(path): return send_from_directory("static", path)

@app.route("/api/chats", methods=["GET"])
def get_chats():
    req_id = g.request_id
    uid = verify_token(request.headers.get("Authorization", "").replace("Bearer ", ""))
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    try:
        res = supabase.table("chats").select("id,title,created_at").eq("user_id", uid).order("created_at", desc=True).limit(50).execute()
        log(req_id, "get_chats", count=len(res.data))
        return jsonify(res.data)
    except Exception as e:
        log(req_id, "get_chats_error", error=str(e))
        return jsonify({"error": "DB error"}), 500

@app.route("/api/chat/<chat_id>", methods=["GET"])
def get_chat(chat_id):
    req_id = g.request_id
    uid = verify_token(request.headers.get("Authorization", "").replace("Bearer ", ""))
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    try:
        chat_check = supabase.table("chats").select("id").eq("id", chat_id).eq("user_id", uid).maybe_single().execute()
        if not chat_check.data: return jsonify({"error": "Not found"}), 404
        
        msgs = get_chat_history(chat_id, uid, supabase)
        log(req_id, "get_chat", chat_id=chat_id, msg_count=len(msgs))
        return jsonify(msgs)
    except Exception as e:
        log(req_id, "get_chat_error", error=str(e))
        return jsonify({"error": "DB error"}), 500

@app.route("/api/chat/delete", methods=["POST"])
def delete_chat():
    req_id = g.request_id
    uid = verify_token(request.headers.get("Authorization", "").replace("Bearer ", ""))
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.json; chat_id = data.get("chat_id")
        if not chat_id: return jsonify({"error": "chat_id required"}), 400
        
        chat_check = supabase.table("chats").select("id").eq("id", chat_id).eq("user_id", uid).maybe_single().execute()
        if not chat_check.data: return jsonify({"error": "Not found"}), 404
        
        supabase.table("messages").delete().eq("chat_id", chat_id).eq("user_id", uid).execute()
        supabase.table("chats").delete().eq("id", chat_id).eq("user_id", uid).execute()
        log(req_id, "delete_chat", chat_id=chat_id)
        return jsonify({"success": True})
    except Exception as e:
        log(req_id, "delete_chat_error", error=str(e))
        return jsonify({"error": "DB error"}), 500

@app.route("/api/chat", methods=["POST"])
def chat():
    req_id = g.request_id
    uid = verify_token(request.headers.get("Authorization", "").replace("Bearer ", ""))
    if not uid: return Response("Unauthorized", status=401)

    question = request.form.get("question", "")
    client_msg_id = request.form.get("client_msg_id")
    chat_id = request.form.get("chat_id") or str(uuid.uuid4())
    is_regen = request.form.get("is_regen") == "1"
    file = request.files.get("file")

    if len(question) > 20000: return jsonify({"error": "Question too long"}), 413
    if not question and not file: return jsonify({"error": "Empty request"}), 400
    
    if chat_id:
        chat_check = supabase.table("chats").select("id").eq("id", chat_id).eq("user_id", uid).maybe_single().execute()
        if not chat_check.data and request.form.get("chat_id"): 
            return jsonify({"error": "Chat not found"}), 404

    file_meta = None; filepath = None
    if file and file.filename:
        ALLOWED = {"pdf","txt","py","js","png","jpg","jpeg","docx","csv","json","md"}
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED: return jsonify({"error": "File type not allowed"}), 400
        
        stored_name = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        filepath = os.path.join(UPLOAD_FOLDER, stored_name)
        file.save(filepath)
        file_meta = {"name": file.filename, "path": filepath}

    if client_msg_id:
        dup = supabase.table("messages").select("id").eq("client_msg_id", client_msg_id).eq("user_id", uid).maybe_single().execute()
        if dup.data: return jsonify({"error": "Duplicate"}), 409

    if not is_regen:
        save_message(chat_id, uid, "user", question, file_meta, client_msg_id, supabase)
    
    messages = get_chat_history(chat_id, uid, supabase)
    log(req_id, "chat_start", chat_id=chat_id, has_file=bool(file))

    def generate():
        full_response = ""
        first_token_time = None
        steps = []
        try:
            # 1. RUN THE AGENT INSTEAD OF DIRECT LLM
            agent_result = run_agent(uid, question, messages)
            final_answer = agent_result["answer"]
            steps = agent_result["steps"]
            
            log(req_id, "agent_steps", steps=json.dumps(steps))

            # 2. STREAM THE FINAL ANSWER
            for word in final_answer.split():
                if first_token_time is None: 
                    first_token_time = time.perf_counter()
                    log(req_id, "first_token", latency=first_token_time - g.start_time)
                
                yield f"event: token\ndata: {json.dumps({'text': word + ' '})}\n\n"
                time.sleep(0.01) # small delay to simulate streaming
            
            # 3. SAVE TO DB
            if final_answer.strip():
                save_message(chat_id, uid, "assistant", final_answer, None, None, supabase)
                supabase.table("chats").upsert({
                    "id": chat_id, "user_id": uid, 
                    "title": question[:60] if question else "New Chat",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).execute()
            log(req_id, "chat_complete", tokens=len(final_answer))

        except Exception as e:
            log(req_id, "agent_error", error=str(e))
            yield f'event: error\ndata: {json.dumps({"message": "Agent failed", "request_id": req_id})}\n\n'
        finally:
            if filepath and os.path.exists(filepath):
                try: os.remove(filepath)
                except: pass

        yield f'event: done\ndata: {json.dumps({"chat_id": chat_id, "steps": steps})}\n\n'

    response = Response(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Brain 4.0 v6.0.0-agent starting on port {port}")
    app.run(host="0.0.0.0", port=port)
