import os, uuid, json, logging
from flask import Flask, request, Response, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from supabase import create_client, Client
from brain_core import ModelRouter, save_message, get_chat_history

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app, resources={r"/api/*": {"origins": "*"}})

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") # service_role
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
router = ModelRouter(supabase)

UPLOAD_FOLDER = "/tmp/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def verify_token(token):
    try:
        user = supabase.auth.get_user(token)
        return user.user.id if user else None
    except: return None

@app.route("/")
def index(): return send_from_directory("templates", "index.html")

@app.route("/static/<path:path>")
def send_static(path): return send_from_directory("static", path)

@app.route("/api/chats", methods=["GET"])
def get_chats():
    uid = verify_token(request.headers.get("Authorization", "").replace("Bearer ", ""))
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    res = supabase.table("chats").select("id,title,created_at").eq("user_id", uid).order("created_at", desc=True).limit(50).execute()
    return jsonify(res.data)

@app.route("/api/chat/<chat_id>", methods=["GET"])
def get_chat(chat_id):
    uid = verify_token(request.headers.get("Authorization", "").replace("Bearer ", ""))
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    msgs = get_chat_history(chat_id, uid, supabase)
    return jsonify(msgs)

@app.route("/api/chat/delete", methods=["POST"])
def delete_chat():
    uid = verify_token(request.headers.get("Authorization", "").replace("Bearer ", ""))
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    data = request.json; chat_id = data.get("chat_id")
    supabase.table("messages").delete().eq("chat_id", chat_id).execute()
    supabase.table("chats").delete().eq("id", chat_id).eq("user_id", uid).execute()
    return jsonify({"success": True})

@app.route("/api/chat", methods=["POST"])
def chat():
    uid = verify_token(request.headers.get("Authorization", "").replace("Bearer ", ""))
    if not uid: return Response("Unauthorized", status=401)

    question = request.form.get("question", "")
    client_msg_id = request.form.get("client_msg_id")
    chat_id = request.form.get("chat_id") or str(uuid.uuid4())
    file = request.files.get("file")

    file_meta = None
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        file_meta = {"name": filename, "path": filepath}

    save_message(chat_id, uid, "user", question, file_meta, client_msg_id, supabase)
    messages = get_chat_history(chat_id, uid, supabase)

    def generate():
        full_response = ""
        try:
            stream = router.route(messages, uid, chat_id, bool(file), stream=True)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_response += text
                    yield f"event: token\ndata: {json.dumps({'text': text})}\n\n"

            if full_response.strip():
                save_message(chat_id, uid, "assistant", full_response, None, None, supabase)
                supabase.table("chats").upsert({"id": chat_id, "user_id": uid, "title": question[:50]}).execute()

        except Exception as e:
            logger.exception(f"Stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

        yield f"event: done\ndata: {json.dumps({'chat_id': chat_id})}\n\n"

    return Response(generate(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
