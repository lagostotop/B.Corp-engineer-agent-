from flask import Flask, render_template, request, jsonify, Response, stream_with_context, abort, g, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os, re, io, traceback, json, uuid, base64, logging, threading, time, warnings
from datetime import datetime, timezone
from groq import Groq
from tavily import TavilyClient
from config import config
from supabase import create_client, Client
from PIL import Image, ImageOps
from PIL.Image import DecompressionBombError, DecompressionBombWarning
import jwt
from jwt import PyJWK
import requests

from brain_core import (
    ModelRouter, MODELS, get_embedding, create_chat, get_owned_chat,
    check_idempotency, save_message, load_messages, needs_tools,
    generate_plan, call_tool, process_image, process_uploaded_file,
    SYSTEM_PROMPT, ALLOWED_ROLES, MAX_EXTRACTED_TEXT, MAX_PER_FILE_BYTES
)

app = Flask(__name__, static_folder="static", template_folder="templates")

ALLOWED_ORIGINS = config.ALLOWED_ORIGINS
if not ALLOWED_ORIGINS: raise RuntimeError("ALLOWED_ORIGINS must be configured")
origins = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]
if "*" in origins: raise RuntimeError("Wildcard CORS not allowed")
CORS(app, resources={r"/api/*": {"origins": origins}})
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

GENERATION_TIMEOUT = 120
MAX_IMAGE_JPEG = 3 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
warnings.simplefilter("error", DecompressionBombWarning)

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(request_id)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)
logger.addFilter(type("F", (logging.Filter,), {"filter": lambda s, r: setattr(r, "request_id", getattr(r, "request_id", "-")) or True})())

print("=== BRAIN 3.0 v5.6.3 SPLIT ===")

JWKS_CACHE = {"keys": None, "last_fetch": 0}
JWKS_LOCK = threading.Lock()

SUPABASE_PROJECT_REF = config.SUPABASE_URL.split("//")[1].split(".")[0]
EXPECTED_ISS = f"https://{SUPABASE_PROJECT_REF}.supabase.co/auth/v1"
EXPECTED_AUD = "authenticated"
ALLOWED_JWT_ALGS = {"RS256"}

def get_supabase_jwks(force_refresh=False):
    global JWKS_CACHE
    with JWKS_LOCK:
        now = time.time()
        if not force_refresh and JWKS_CACHE["keys"] and now - JWKS_CACHE["last_fetch"] < 3600: return JWKS_CACHE["keys"]
        res = requests.get(f"{config.SUPABASE_URL}/auth/v1/.well-known/jwks.json", timeout=5)
        res.raise_for_status()
        keys = res.json().get("keys", [])
        if not keys: raise RuntimeError("JWKS empty")
        JWKS_CACHE = {"keys": keys, "last_fetch": now}
        return keys

def verify_supabase_token(token):
    if not token: raise jwt.InvalidTokenError("Missing token")
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg"); kid = header.get("kid")
        if alg not in ALLOWED_JWT_ALGS: raise jwt.InvalidTokenError(f"Bad alg: {alg}")
        logger.info(f"JWT Header: alg={alg} kid={kid}")
    except jwt.DecodeError: raise jwt.InvalidTokenError("Invalid token header")

    try:
        jwks = get_supabase_jwks()
        if not kid: raise jwt.InvalidTokenError("Missing kid")
        key_data = next((k for k in jwks if k.get("kid") == kid and k.get("alg") == alg), None)
        if not key_data: jwks = get_supabase_jwks(True); key_data = next((k for k in jwks if k.get("kid") == kid and k.get("alg") == alg), None)
        if not key_data: raise jwt.InvalidTokenError("Key not found in JWKS")
        key = PyJWK(key_data, algorithm_name=alg).key
        payload = jwt.decode(token, key, algorithms=[alg], audience=EXPECTED_AUD, issuer=EXPECTED_ISS)
        logger.info(f"JWT verified {alg} for user: {payload.get('sub')}")
        return payload
    except jwt.ExpiredSignatureError: logger.warning("JWT expired"); raise
    except jwt.InvalidAudienceError: logger.warning(f"JWT invalid audience. Expected {EXPECTED_AUD}"); raise
    except jwt.InvalidIssuerError: logger.warning(f"JWT invalid issuer. Expected {EXPECTED_ISS}"); raise
    except jwt.InvalidSignatureError: logger.warning("JWT invalid signature"); raise
    except Exception as e: logger.exception(f"JWT verification failure: {e}"); raise jwt.InvalidTokenError(str(e))

def get_verified_payload():
    if hasattr(g, "_jwt_payload"): return g._jwt_payload
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "): abort(401, "Missing token")
    token = auth[7:].strip()
    try: payload = verify_supabase_token(token); g._jwt_payload = payload; return payload
    except jwt.ExpiredSignatureError: abort(401, "Token expired")
    except jwt.InvalidTokenError as e: logger.warning("JWT invalid: %s", str(e)); abort(401, f"Invalid token: {str(e)}")
    except Exception: logger.exception("Unexpected JWT verification failure"); abort(401, "Authentication failure")

def get_user_id(): return str(get_verified_payload().get("sub") or abort(401, "Invalid token"))

def get_user_rate_key():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "): return f"auth:{auth[7:16]}:{get_remote_address()}"
    return f"anon:{get_remote_address()}"

limiter = Limiter(key_func=get_user_rate_key, app=app, default_limits=["200 per minute"])
client = Groq(api_key=config.GROQ_API_KEY, timeout=GENERATION_TIMEOUT)
tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
router = ModelRouter(supabase)

@app.route("/api/chats", methods=["GET"])
@limiter.limit("30 per minute")
def get_chats():
    uid = get_user_id()
    res = supabase.table("chats").select("*").eq("user_id", uid).order("created_at", desc=True).limit(50).execute()
    return jsonify(res.data or [])

@app.route("/api/chat/<chat_id>", methods=["GET"])
@limiter.limit("30 per minute")
def get_chat(chat_id):
    return jsonify(load_messages(chat_id, get_user_id()))

@app.route("/api/chat/delete", methods=["POST"])
@limiter.limit("10 per minute")
def delete_chat():
    uid = get_user_id()
    cid = (request.get_json() or {}).get("chat_id")
    if not cid: abort(400)
    get_owned_chat(cid, uid)
    supabase.table("messages").delete().eq("chat_id", cid).eq("user_id", uid).execute()
    supabase.table("chats").delete().eq("id", cid).eq("user_id", uid).execute()
    return jsonify({"success": True})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/sw.js")
def sw():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    req_id = str(uuid.uuid4())[:8]
    log = logging.LoggerAdapter(logger, {"request_id": req_id})
    uid = get_user_id(); q = request.form.get("question", "").strip(); cid = request.form.get("chat_id"); file = request.files.get("file"); cmsg = request.form.get("client_msg_id")
    if not cmsg: abort(400, "client_msg_id required")
    if check_idempotency(cmsg, uid): return jsonify({"error": "Duplicate"}), 409
    if not q and not file: abort(400, "Empty")
    if not cid or cid == "null": cid = create_chat(uid, q)

    has_image = False; file_meta = None; context_text = ""
    if file:
        msg, ctx, has_image, img_data, file_meta = process_uploaded_file(file, uid, cid, supabase, client)
        q += msg; context_text += ctx
        if has_image: q = [{"type": "text", "text": q}, {"type": "image_url", "image_url": {"url": img_data}}]

    save_message(cid, uid, "user", q if isinstance(q, str) else q[0]["text"], file_meta, cmsg, supabase)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context_text: messages.append({"role": "system", "content": f"CONTEXT:\n{context_text[:MAX_TOOL_CONTEXT_CHARS]}"})
    messages.append({"role": "user", "content": q})

    def generate():
        try:
            stream = router.route(messages, uid, cid, has_image, stream=True)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    yield f"event: token\ndata: {json.dumps({'text': text})}\n\n"
        except Exception as e:
            logger.exception(f"Stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        yield f"event: done\ndata: {json.dumps({'chat_id': cid})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
