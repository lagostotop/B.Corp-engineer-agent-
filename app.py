import os,uuid,json,time,logging
from datetime import datetime,timezone,timedelta
from functools import wraps
from flask import Flask,request,Response,jsonify,send_from_directory,g,stream_with_context
from flask_cors import CORS
from werkzeug.exceptions import HTTPException,RequestEntityTooLarge
from werkzeug.utils import secure_filename
from supabase import create_client,Client,ClientOptions
from brain_core import ModelRouter,save_message,get_chat_history,save_to_rag,MAX_UPLOAD_BYTES,should_use_agent,get_last_user_message

VERSION="8.5.5"
UPLOAD_FOLDER="/tmp/uploads"
SUPABASE_URL=os.getenv("SUPABASE_URL","").strip()
SUPABASE_KEY=os.getenv("SUPABASE_SERVICE_ROLE_KEY","").strip()
REQUIRED_ENV=("SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY","GROQ_API_KEY")

missing=[x for x in REQUIRED_ENV if not os.getenv(x)]
if missing: raise RuntimeError("Missing env: "+", ".join(missing))

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger=logging.getLogger(__name__)

app=Flask(__name__,static_folder="static",template_folder="templates")
app.config["MAX_CONTENT_LENGTH"]=MAX_UPLOAD_BYTES+2*1024*1024

origins=[x.strip() for x in os.getenv("ALLOWED_ORIGINS","*").split(",") if x.strip()]
CORS(app,resources={r"/api/*":{"origins":origins}})

# ===== SUPABASE =====
def get_supabase_client():
    for i in range(3):
        try:
            client=create_client(SUPABASE_URL,SUPABASE_KEY,options=ClientOptions(
                auto_refresh_token=False,persist_session=False,
                postgrest_client_timeout=30,storage_client_timeout=30
            ))
            client.table("chats").select("id").limit(1).execute()
            logger.info("✅ Supabase connected")
            return client
        except Exception as e:
            logger.warning(f"Attempt {i+1}/3 failed: {e}")
            if i<2: time.sleep(2)
            else: raise RuntimeError(f"Supabase failed: {e}")
supabase=get_supabase_client()
router=ModelRouter(supabase)
os.makedirs(UPLOAD_FOLDER,exist_ok=True)

# ===== AUTH =====
def get_user_from_token(token):
    """Verify JWT and get user"""
    try:
        result = supabase.auth.get_user(token)
        if result and result.user:
            return result.user
        return None
    except Exception as e:
        logger.warning(f"Auth failed: {e}")
        return None

def get_current_user():
    """Get current user from request"""
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        user = get_user_from_token(token)
        if user:
            return user
    return None

def get_uid():
    """Get user ID or guest fallback"""
    user = get_current_user()
    if user:
        return user.id
    # Guest mode fallback
    guest_id = os.getenv("TEST_USER_ID", "000000000-0000-0000-0000-000000000001")
    logger.warning(f"⚠️ Guest mode: {guest_id}")
    return guest_id

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error":"Authentication required","code":"UNAUTHORIZED"}),401
        g.user = user
        return f(*args, **kwargs)
    return decorated

# ===== REDIS =====
redis_client=None
try:
    redis_url=os.getenv("REDIS_URL")
    if redis_url:
        import redis
        redis_client=redis.from_url(redis_url)
        redis_client.ping()
        logger.info("✅ Redis connected")
except: logger.warning("⚠️ Redis not available")

def cache_get(k):
    if not redis_client: return None
    try:
        c=redis_client.get(k)
        return json.loads(c) if c else None
    except: return None

def cache_set(k,v,ttl=30):
    if not redis_client: return
    try: redis_client.setex(k,ttl,json.dumps(v))
    except: pass

def cache_del(k):
    if not redis_client: return
    try: redis_client.delete(k)
    except: pass

def cache_del_pattern(p):
    if not redis_client: return
    try:
        keys=redis_client.keys(p)
        if keys: redis_client.delete(*keys)
    except: pass

# ===== HELPERS =====
ALLOWED_EXTENSIONS={"pdf","txt","md","py","js","ts","jsx","tsx","html","css","csv","json","png","jpg","jpeg","docx"}
IMAGE_EXTENSIONS={".png",".jpg",".jpeg"}
def allowed_file(f): return bool(f and "." in f and f.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS)
def is_image_file(f): return os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS

logger.info("Brain 3.0 started | version=%s", VERSION)

# ===== ROUTES =====
@app.before_request
def before():
    g.request_id=uuid.uuid4().hex[:8]
    g.start_time=time.perf_counter()
    g.user = get_current_user()
    g.is_guest = g.user is None
    logger.info("[%s] %s %s | user=%s", g.request_id, request.method, request.path, 
                g.user.id[:8] if g.user else 'guest')

@app.after_request
def after(r):
    r.headers["X-Request-ID"]=g.request_id
    r.headers["X-Response-Time"]=f"{(time.perf_counter()-g.start_time)*1000:.2f}ms"
    return r

@app.errorhandler(RequestEntityTooLarge)
def e413(e): return jsonify({"error":"File too large. Max 10MB","request_id":g.request_id}),413

@app.errorhandler(Exception)
def e500(e):
    rid=getattr(g,"request_id","unknown")
    if isinstance(e,HTTPException): return jsonify({"error":e.description,"request_id":rid}),e.code
    logger.exception("[%s] Unhandled",rid)
    return jsonify({"error":"Internal error","request_id":rid}),500

@app.route("/")
def idx(): return send_from_directory("templates","index.html")
@app.route("/sw.js")
def sw(): return send_from_directory("static","sw.js")
@app.route("/static/<path:p>")
def st(p): return send_from_directory("static",p)

@app.route("/api/auth/config")
def auth_config():
    """Send Supabase config to frontend"""
    return jsonify({
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "supabase_anon_key": os.getenv("SUPABASE_PUBLISHABLE_KEY", ""),
        "auth_enabled": True,
        "version": VERSION
    })

@app.route("/api/auth/me")
def auth_me():
    """Get current user info"""
    user = get_current_user()
    if user:
        return jsonify({
            "id": user.id,
            "email": user.email,
            "created_at": user.created_at,
            "is_guest": False
        })
    return jsonify({"is_guest": True}), 401

# ===== HEALTH =====
@app.route("/health")
def health():
    rs=db=False
    if redis_client:
        try: redis_client.ping(); rs=True
        except: pass
    try: supabase.table("chats").select("id").limit(1).execute(); db=True
    except: pass
    return jsonify({"status":"ok" if db else "degraded","service":"brain3","version":VERSION,
        "auth":"enabled","database":"connected" if db else "disconnected",
        "redis":"connected" if rs else "disconnected",
        "environment":os.getenv("FLASK_ENV","development")})

# ===== CHAT CRUD =====
@app.route("/api/chats",methods=["GET"])
def get_chats():
    uid = get_uid()
    try:
        cache_key=f"chats:{uid}"
        cached=cache_get(cache_key)
        if cached: return jsonify(cached)
        data=(supabase.table("chats").select("id,title,created_at,updated_at")
            .eq("user_id",uid).order("updated_at",desc=True).limit(50).execute()).data or []
        if data: cache_set(cache_key,data,30)
        return jsonify(data)
    except Exception:
        logger.exception("[%s] get_chats_error",g.request_id)
        return jsonify({"error":"DB error"}),500

@app.route("/api/chat/<chat_id>",methods=["GET"])
def get_chat(chat_id):
    uid=get_uid()
    try:
        cache_key=f"chat:{uid}:{chat_id}"
        cached=cache_get(cache_key)
        if cached: return jsonify(cached)
        chat=supabase.table("chats").select("id").eq("id",chat_id).eq("user_id",uid).maybe_single().execute()
        if not chat.data: return jsonify({"error":"Not found"}),404
        history=get_chat_history(chat_id,uid,supabase)
        if history: cache_set(cache_key,history,30)
        return jsonify(history)
    except Exception:
        logger.exception("[%s] get_chat_error",g.request_id)
        return jsonify({"error":"DB error"}),500

@app.route("/api/chat/delete",methods=["POST"])
def delete_chat():
    uid=get_uid()
    data=request.get_json(silent=True) or {}
    chat_id=data.get("chat_id")
    if not chat_id: return jsonify({"error":"chat_id required"}),400
    try:
        ownership=supabase.table("chats").select("id").eq("id",chat_id).eq("user_id",uid).maybe_single().execute()
        if not ownership.data: return jsonify({"error":"Not found"}),404
        supabase.table("messages").delete().eq("chat_id",chat_id).eq("user_id",uid).execute()
        supabase.table("documents").delete().eq("chat_id",chat_id).eq("user_id",uid).execute()
        supabase.table("chats").delete().eq("id",chat_id).eq("user_id",uid).execute()
        cache_del(f"chat:{uid}:{chat_id}")
        cache_del(f"chats:{uid}")
        return jsonify({"success":True})
    except Exception:
        logger.exception("[%s] delete_chat_error",g.request_id)
        return jsonify({"error":"DB error"}),500

# ===== MAIN CHAT =====
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

    if len(question)>20000: return jsonify({"error":"Question too long"}),413
    if not question and not file: return jsonify({"error":"Empty request"}),400

    if requested_chat_id:
        try:
            ownership=supabase.table("chats").select("id").eq("id",chat_id).eq("user_id",uid).maybe_single().execute()
            if not ownership.data: return jsonify({"error":"Chat not found"}),404
        except Exception:
            logger.exception("[%s] ownership check failed",g.request_id)
            return jsonify({"error":"DB error"}),500

    if not is_regen:
        try:
            dup=supabase.table("messages").select("id").eq("client_msg_id",client_msg_id).eq("user_id",uid).maybe_single().execute()
            if dup.data: return jsonify({"error":"Duplicate"}),409
        except Exception:
            logger.exception("[%s] idempotency check failed",g.request_id)
            return jsonify({"error":"DB error"}),500

    try:
        supabase.table("chats").upsert({"id":chat_id,"user_id":uid,
            "title":question[:60] or "New Chat",
            "updated_at":datetime.now(timezone.utc).isoformat()}).execute()
    except Exception:
        logger.exception("[%s] chat creation failed",g.request_id)
        return jsonify({"error":"Unable to create chat"}),500

    filepath=file_meta=db_file_meta=None
    rag_stats={"total":0,"saved":0,"error":None}

    if file and file.filename:
        if not allowed_file(file.filename): return jsonify({"error":"File type not allowed"}),400
        original_name=file.filename
        safe_name=secure_filename(original_name)
        if not safe_name: return jsonify({"error":"Invalid filename"}),400
        filepath=os.path.join(UPLOAD_FOLDER,f"{uuid.uuid4().hex}_{safe_name}")
        try:
            file.save(filepath)
            if os.path.getsize(filepath)>MAX_UPLOAD_BYTES:
                os.remove(filepath); return jsonify({"error":"File too large. Max 10MB"}),413
            ext=os.path.splitext(original_name)[1].lower()
            file_meta={"name":original_name,"type":ext,"temp_path":filepath}
            db_file_meta={"name":original_name,"type":ext}
            if not is_image_file(original_name):
                rag_stats=save_to_rag(chat_id,uid,filepath,supabase)
        except Exception:
            if filepath and os.path.exists(filepath): os.remove(filepath)
            logger.exception("[%s] file upload failed",g.request_id)
            return jsonify({"error":"File upload failed"}),500

    if not is_regen:
        ok=save_message(chat_id,uid,"user",question,db_file_meta,client_msg_id,supabase)
        if not ok: return jsonify({"error":"Failed to save message"}),500

    messages=get_chat_history(chat_id,uid,supabase)
    last_user_msg=get_last_user_message(messages)
    use_agent=request_mode=="agent" or should_use_agent(last_user_msg) or bool(file_meta and not is_image_file(file_meta["name"]))

    logger.info("[%s] chat=%s client=%s mode=%s agent=%s",g.request_id,chat_id,client_type,request_mode,use_agent)

    def generate():
        full=""
        try:
            stream=router.route(messages=messages,uid=uid,cid=chat_id,file_meta=file_meta,
                stream=True,force_agent=use_agent,last_user_msg=last_user_msg)
            for chunk in stream:
                if not chunk.choices: continue
                text=chunk.choices[0].delta.content
                if not text: continue
                full+=text
                yield f"event: token\ndata: {json.dumps({'text':text})}\n\n"
            if full.strip():
                save_message(chat_id,uid,"assistant",full,None,str(uuid.uuid4()),supabase)
                supabase.table("chats").update({"updated_at":datetime.now(timezone.utc).isoformat()}).eq("id",chat_id).eq("user_id",uid).execute()
                cache_del(f"chat:{uid}:{chat_id}"); cache_del(f"chats:{uid}")
        except Exception:
            logger.exception("[%s] generation failed",g.request_id)
            yield f"event: error\ndata: {json.dumps({'message':'Agent failed','request_id':g.request_id})}\n\n"
        finally:
            if filepath and os.path.exists(filepath):
                try: os.remove(filepath)
                except: pass
            if rag_stats["total"]>0:
                yield f"event: rag_status\ndata: {json.dumps(rag_stats)}\n\n"
            yield f"event: done\ndata: {json.dumps({'chat_id':chat_id})}\n\n"

    response=Response(stream_with_context(generate()),mimetype="text/event-stream")
    response.headers.update({"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})
    return response

app.start_time=time.time()

if __name__=="__main__":
    port=int(os.getenv("PORT","5000"))
    logger.info("Brain 3.0 v%s running on port %s",VERSION,port)
    app.run(host="0.0.0.0",port=port)
