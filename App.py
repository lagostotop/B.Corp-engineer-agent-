import os,uuid,json,time,logging
from datetime import datetime,timezone
from flask import Flask,request,Response,jsonify,send_from_directory,g,stream_with_context
from flask_cors import CORS
from werkzeug.exceptions import HTTPException,RequestEntityTooLarge
from werkzeug.utils import secure_filename
from supabase import create_client,Client,ClientOptions
from brain_core import ModelRouter,save_message,get_chat_history,save_to_rag,MAX_UPLOAD_BYTES,should_use_agent,get_last_user_message

VERSION="8.5.5"
UPLOAD_FOLDER="/tmp/uploads"
TEST_USER_ID=os.getenv("TEST_USER_ID","000000000-0000-0000-0000-000000000001")
SUPABASE_URL=os.getenv("SUPABASE_URL","").strip()
SUPABASE_KEY=os.getenv("SUPABASE_SERVICE_ROLE_KEY","").strip()
REQUIRED_ENV=("SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY","GROQ_API_KEY")

missing=[x for x in REQUIRED_ENV if not os.getenv(x)]
if missing:
    raise RuntimeError("Missing required environment variables: "+", ".join(missing))

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s - %(message)s")
logger=logging.getLogger(__name__)

app=Flask(__name__,static_folder="static",template_folder="templates")
app.config["MAX_CONTENT_LENGTH"]=MAX_UPLOAD_BYTES+2*1024*1024

# CORS configuration for Render
origins=[x.strip() for x in os.getenv("ALLOWED_ORIGINS","*").split(",") if x.strip()]
CORS(app,resources={r"/api/*":{"origins":origins}})

supabase:Client=create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=ClientOptions(
        auto_refresh_token=False,
        persist_session=False
    )
)

router=ModelRouter(supabase)
os.makedirs(UPLOAD_FOLDER,exist_ok=True)

# Redis for caching on Render
redis_client = None
try:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        import redis
        redis_client = redis.from_url(redis_url)
        redis_client.ping()
        logger.info("✅ Redis connected for session caching")
except Exception as e:
    logger.warning(f"⚠️ Redis not available: {e}")

logger.info(
    "Brain 3.0 started | version=%s | auth=disabled | test_user=%s",
    VERSION,TEST_USER_ID
)

def get_uid():
    return TEST_USER_ID

ALLOWED_EXTENSIONS={
    "pdf","txt","md","py","js","ts","jsx","tsx",
    "html","css","csv","json","png","jpg","jpeg","docx"
}

IMAGE_EXTENSIONS={".png",".jpg",".jpeg"}

def allowed_file(filename):
    return bool(
        filename and "." in filename and
        filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS
    )

def is_image_file(filename):
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS

@app.before_request
def before_request():
    g.request_id=uuid.uuid4().hex[:8]
    g.start_time=time.perf_counter()
    logger.info("[%s] %s %s",g.request_id,request.method,request.path)

@app.after_request
def after_request(response):
    duration=time.perf_counter()-g.start_time
    response.headers["X-Request-ID"]=g.request_id
    response.headers["X-Response-Time"]=f"{duration*1000:.2f}ms"
    return response

@app.errorhandler(RequestEntityTooLarge)
def handle_413(error):
    return jsonify({
        "error":"File too large. Max 10MB",
        "request_id":g.request_id
    }),413

@app.errorhandler(Exception)
def handle_exception(error):
    rid=getattr(g,"request_id","unknown")
    if isinstance(error,HTTPException):
        return jsonify({
            "error":error.description,
            "request_id":rid
        }),error.code

    logger.exception("[%s] Unhandled exception",rid)
    return jsonify({
        "error":"Internal server error",
        "request_id":rid
    }),500

@app.route("/")
def index():
    return send_from_directory("templates","index.html")

@app.route("/sw.js")
def service_worker():
    return send_from_directory("static","sw.js")

@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static",path)

@app.route("/health")
def health():
    # Check Redis if available
    redis_status = False
    if redis_client:
        try:
            redis_client.ping()
            redis_status = True
        except:
            pass
    
    return jsonify({
        "status":"ok",
        "service":"brain3",
        "version":VERSION,
        "auth":"disabled",
        "database":"supabase",
        "redis": redis_status,
        "jarvis":True,
        "environment": os.getenv("FLASK_ENV", "development")
    })

@app.route("/render-health")
def render_health():
    """Render-specific health check endpoint"""
    redis_status = False
    if redis_client:
        try:
            redis_client.ping()
            redis_status = True
        except:
            pass
    
    return jsonify({
        "status": "healthy" if redis_status else "degraded",
        "redis": redis_status,
        "supabase": bool(supabase),
        "groq": bool(os.getenv("GROQ_API_KEY")),
        "version": VERSION,
        "uptime": time.time() - app.start_time if hasattr(app, 'start_time') else 0
    })

@app.route("/metrics")
def metrics():
    """Simple metrics for Render monitoring"""
    return jsonify({
        "version": VERSION,
        "redis_connected": bool(redis_client),
        "supabase_connected": bool(supabase),
        "environment": os.getenv("FLASK_ENV", "development")
    })

@app.route("/api/chats",methods=["GET"])
def get_chats():
    uid=get_uid()
    try:
        # Try cache first
        cache_key = f"chats:{uid}"
        if redis_client:
            cached = redis_client.get(cache_key)
            if cached:
                return jsonify(json.loads(cached))
        
        result=(
            supabase.table("chats")
            .select("id,title,created_at,updated_at")
            .eq("user_id",uid)
            .order("updated_at",desc=True)
            .limit(50)
            .execute()
        )
        
        data = result.data or []
        
        # Cache for 30 seconds
        if redis_client and data:
            redis_client.setex(cache_key, 30, json.dumps(data))
        
        return jsonify(data)
    except Exception:
        logger.exception("[%s] get_chats_error",g.request_id)
        return jsonify({"error":"DB error"}),500

@app.route("/api/chat/<chat_id>",methods=["GET"])
def get_chat(chat_id):
    uid=get_uid()
    try:
        # Try cache
        cache_key = f"chat:{uid}:{chat_id}"
        if redis_client:
            cached = redis_client.get(cache_key)
            if cached:
                return jsonify(json.loads(cached))
        
        chat=(
            supabase.table("chats")
            .select("id")
            .eq("id",chat_id)
            .eq("user_id",uid)
            .maybe_single()
            .execute()
        )

        if not chat.data:
            return jsonify({"error":"Not found"}),404

        history = get_chat_history(chat_id,uid,supabase)
        
        # Cache for 30 seconds
        if redis_client and history:
            redis_client.setex(cache_key, 30, json.dumps(history))

        return jsonify(history)

    except Exception:
        logger.exception("[%s] get_chat_error",g.request_id)
        return jsonify({"error":"DB error"}),500

@app.route("/api/chat/delete",methods=["POST"])
def delete_chat():
    uid=get_uid()
    data=request.get_json(silent=True) or {}
    chat_id=data.get("chat_id")

    if not chat_id:
        return jsonify({"error":"chat_id required"}),400

    try:
        ownership=(
            supabase.table("chats")
            .select("id")
            .eq("id",chat_id)
            .eq("user_id",uid)
            .maybe_single()
            .execute()
        )

        if not ownership.data:
            return jsonify({"error":"Not found"}),404

        (
            supabase.table("messages")
            .delete()
            .eq("chat_id",chat_id)
            .eq("user_id",uid)
            .execute()
        )

        (
            supabase.table("documents")
            .delete()
            .eq("chat_id",chat_id)
            .eq("user_id",uid)
            .execute()
        )

        (
            supabase.table("chats")
            .delete()
            .eq("id",chat_id)
            .eq("user_id",uid)
            .execute()
        )

        # Invalidate cache
        if redis_client:
            redis_client.delete(f"chat:{uid}:{chat_id}")
            redis_client.delete(f"chats:{uid}")

        return jsonify({"success":True})

    except Exception:
        logger.exception("[%s] delete_chat_error",g.request_id)
        return jsonify({"error":"DB error"}),500

@app.route("/api/chat",methods=["POST"])
def chat():
    uid=get_uid()

    question=request.form.get("question","").strip()
    client_msg_id=request.form.get("client_msg_id") or str(uuid.uuid4())
    requested_chat_id=request.form.get("chat_id")
    client_type=request.form.get("client","brain3").strip().lower()
    request_mode=request.form.get("mode","normal").strip().lower()
    chat_id=requested_chat_id or str(uuid.uuid4())
    is_regen=request.form.get("is_regen")=="1"
    file=request.files.get("file")

    if len(question)>20000:
        return jsonify({"error":"Question too long"}),413

    if not question and not file:
        return jsonify({"error":"Empty request"}),400

    if requested_chat_id:
        try:
            ownership=(
                supabase.table("chats")
                .select("id")
                .eq("id",chat_id)
                .eq("user_id",uid)
                .maybe_single()
                .execute()
            )

            if not ownership.data:
                return jsonify({"error":"Chat not found"}),404

        except Exception:
            logger.exception(
                "[%s] ownership check failed",
                g.request_id
            )
            return jsonify({"error":"DB error"}),500

    if not is_regen:
        try:
            duplicate=(
                supabase.table("messages")
                .select("id")
                .eq("client_msg_id",client_msg_id)
                .eq("user_id",uid)
                .maybe_single()
                .execute()
            )

            if duplicate.data:
                return jsonify({"error":"Duplicate"}),409

        except Exception:
            logger.exception(
                "[%s] idempotency check failed",
                g.request_id
            )
            return jsonify({"error":"DB error"}),500

    try:
        (
            supabase.table("chats")
            .upsert({
                "id":chat_id,
                "user_id":uid,
                "title":question[:60] or "New Chat",
                "updated_at":datetime.now(timezone.utc).isoformat()
            })
            .execute()
        )

    except Exception:
        logger.exception(
            "[%s] chat creation failed",
            g.request_id
        )
        return jsonify({
            "error":"Unable to create chat"
        }),500

    filepath=None
    file_meta=None
    db_file_meta=None
    rag_stats={"total":0,"saved":0,"error":None}

    if file and file.filename:

        if not allowed_file(file.filename):
            return jsonify({
                "error":"File type not allowed"
            }),400

        original_name=file.filename
        safe_name=secure_filename(original_name)

        if not safe_name:
            return jsonify({
                "error":"Invalid filename"
            }),400

        filepath=os.path.join(
            UPLOAD_FOLDER,
            f"{uuid.uuid4().hex}_{safe_name}"
        )

        try:
            file.save(filepath)

            if os.path.getsize(filepath)>MAX_UPLOAD_BYTES:
                os.remove(filepath)
                return jsonify({
                    "error":"File too large. Max 10MB"
                }),413

            extension=os.path.splitext(
                original_name
            )[1].lower()

            file_meta={
                "name":original_name,
                "type":extension,
                "temp_path":filepath
            }

            db_file_meta={
                "name":original_name,
                "type":extension
            }

            if not is_image_file(original_name):
                rag_stats=save_to_rag(
                    chat_id,
                    uid,
                    filepath,
                    supabase
                )

        except Exception:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)

            logger.exception(
                "[%s] file upload failed",
                g.request_id
            )

            return jsonify({
                "error":"File upload failed"
            }),500

    if not is_regen:
        ok=save_message(
            chat_id,
            uid,
            "user",
            question,
            db_file_meta,
            client_msg_id,
            supabase
        )

        if not ok:
            return jsonify({
                "error":"Failed to save message"
            }),500

    messages=get_chat_history(
        chat_id,
        uid,
        supabase
    )

    last_user_msg=get_last_user_message(
        messages
    )

    use_agent=(
        request_mode=="agent"
        or should_use_agent(last_user_msg)
        or bool(
            file_meta
            and not is_image_file(
                file_meta["name"]
            )
        )
    )

    logger.info(
        "[%s] chat=%s client=%s mode=%s agent=%s",
        g.request_id,
        chat_id,
        client_type,
        request_mode,
        use_agent
    )

    def generate():
        full_response=""

        try:
            stream=router.route(
                messages=messages,
                uid=uid,
                cid=chat_id,
                file_meta=file_meta,
                stream=True,
                force_agent=use_agent,
                last_user_msg=last_user_msg
            )

            for chunk in stream:

                if not chunk.choices:
                    continue

                text=chunk.choices[0].delta.content

                if not text:
                    continue

                full_response+=text

                yield (
                    "event: token\n"
                    f"data: {json.dumps({'text':text})}\n\n"
                )

            if full_response.strip():

                save_message(
                    chat_id,
                    uid,
                    "assistant",
                    full_response,
                    None,
                    str(uuid.uuid4()),
                    supabase
                )

                (
                    supabase.table("chats")
                    .update({
                        "updated_at":datetime.now(
                            timezone.utc
                        ).isoformat()
                    })
                    .eq("id",chat_id)
                    .eq("user_id",uid)
                    .execute()
                )
                
                # Invalidate chat cache
                if redis_client:
                    redis_client.delete(f"chat:{uid}:{chat_id}")
                    redis_client.delete(f"chats:{uid}")

        except Exception:

            logger.exception(
                "[%s] generation failed",
                g.request_id
            )

            yield (
                "event: error\n"
                f"data: {json.dumps({"
                f"'message':'Agent failed',"
                f"'request_id':'{g.request_id}'"
                "})}\n\n"
            )

        finally:

            if filepath and os.path.exists(filepath):

                try:
                    os.remove(filepath)

                except Exception:
                    logger.warning(
                        "[%s] cleanup failed",
                        g.request_id
                    )

            if rag_stats["total"]>0:

                yield (
                    "event: rag_status\n"
                    f"data: {json.dumps(rag_stats)}\n\n"
                )

            yield (
                "event: done\n"
                f"data: {json.dumps({'chat_id':chat_id})}\n\n"
            )

    response=Response(
        stream_with_context(generate()),
        mimetype="text/event-stream"
    )

    response.headers.update({
        "Cache-Control":"no-cache",
        "X-Accel-Buffering":"no",
        "Connection":"keep-alive"
    })

    return response

# Store start time for uptime tracking
app.start_time = time.time()

if __name__=="__main__":
    port=int(os.getenv("PORT","5000"))

    logger.info(
        "Brain 3.0 v%s running on port %s",
        VERSION,
        port
    )

    app.run(
        host="0.0.0.0",
        port=port
)
