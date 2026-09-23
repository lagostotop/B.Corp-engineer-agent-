import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, Response, g, jsonify, request, send_from_directory, stream_with_context
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from core.config import settings
from core.errors import register_error_handlers
from core.logging import configure_logging, start_request_context
from core.security import authenticate_request, current_user_id
from database.client import db
from database.chats import create_chat, delete_chat, get_chat, list_chats
from database.messages import create_message, list_messages
from brain.context import build_context
from brain.orchestrator import BrainOrchestrator
from retrieval.ingestion import FileIngestionService

VERSION = "10.1.0"
UPLOAD_FOLDER = "/tmp/uploads"

ALLOWED_EXTENSIONS = {
    "pdf", "txt", "md", "py", "js", "ts", "jsx", "tsx",
    "html", "css", "csv", "json", "png", "jpg", "jpeg", "docx"
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

logger = logging.getLogger("brain3.app")


def allowed_file(filename):
    return bool(
        filename
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def is_image_file(filename):
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authenticate_request(db())
        return view(*args, **kwargs)
    return wrapped


def create_app():
    configure_logging()

    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates"
    )

    app.config["MAX_CONTENT_LENGTH"] = (
        settings.max_upload_bytes + 2 * 1024 * 1024
    )

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": settings.allowed_origins or ["*"]
            }
        }
    )

    register_error_handlers(app)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    settings.validate()

    orchestrator = BrainOrchestrator()

    app.config["BRAIN_VERSION"] = VERSION
    app.config["BRAIN_ORCHESTRATOR"] = orchestrator

    @app.before_request
    def before_request():
        start_request_context()
        logger.info("%s %s", request.method, request.path)

    @app.after_request
    def after_request(response):
        response.headers["X-Request-ID"] = getattr(
            g, "request_id", "-"
        )

        started = getattr(
            g,
            "request_started_at",
            time.monotonic()
        )

        response.headers["X-Response-Time"] = (
            f"{(time.monotonic() - started) * 1000:.2f}ms"
        )

        return response

    @app.get("/")
    def index():
        return send_from_directory("templates", "index.html")

    @app.get("/sw.js")
    def service_worker():
        return send_from_directory("static", "sw.js")

    @app.get("/static/<path:path>")
    def static_files(path):
        return send_from_directory("static", path)

    @app.get("/api/auth/config")
    def auth_config():
        return jsonify({
            "supabase_url": settings.supabase_url,
            "supabase_anon_key": settings.supabase_anon_key,
            "auth_enabled": True,
            "version": VERSION
        })

    @app.get("/api/auth/me")
    @auth_required
    def auth_me():
        user = getattr(g, "user", None)

        if user is None:
            return jsonify({
                "error": "Authentication required.",
                "code": "AUTHENTICATION_REQUIRED"
            }), 401

        return jsonify({
            "user": {
                "id": str(user.id),
                "email": getattr(user, "email", None),
                "user_metadata": (
                    getattr(user, "user_metadata", {}) or {}
                )
            }
        })

    @app.get("/health")
    def health():
        database_ok = False

        try:
            db().table("chats").select("id").limit(1).execute()
            database_ok = True
        except Exception:
            logger.exception("Health database check failed")

        return jsonify({
            "status": "ok" if database_ok else "degraded",
            "service": settings.app_name,
            "version": VERSION,
            "environment": settings.environment,
            "database": "connected" if database_ok else "disconnected",
            "auth": "enabled",
            "brain": "orchestrator"
        })

    @app.get("/api/chats")
    @auth_required
    def chats():
        limit = max(
            1,
            min(
                request.args.get("limit", 50, type=int),
                100
            )
        )

        return jsonify(
            list_chats(
                current_user_id(),
                limit
            )
        )

    @app.post("/api/chats")
    @auth_required
    def create_chat_route():
        uid = current_user_id()
        data = request.get_json(silent=True) or {}

        title = str(
            data.get("title", "New Chat")
        ).strip()[:200]

        if not title:
            title = "New Chat"

        chat = create_chat(uid, title)

        return jsonify({
            "chat": chat
        }), 201

    @app.get("/api/chats/<chat_id>")
    @auth_required
    def get_chat_compat_route(chat_id):
        uid = current_user_id()

        chat = get_chat(
            chat_id,
            uid
        )

        if not chat:
            return jsonify({
                "error": "Chat not found.",
                "code": "NOT_FOUND"
            }), 404

        return jsonify({
            "chat": chat,
            "messages": list_messages(
                chat_id,
                uid,
                limit=200
            )
        })

    @app.delete("/api/chats/<chat_id>")
    @auth_required
    def delete_chat_compat_route(chat_id):
        uid = current_user_id()

        if not get_chat(chat_id, uid):
            return jsonify({
                "error": "Chat not found.",
                "code": "NOT_FOUND"
            }), 404

        deleted = delete_chat(
            chat_id,
            uid
        )

        return jsonify({
            "success": deleted,
            "deleted": deleted
        })

    @app.get("/api/chat/<chat_id>")
    @auth_required
    def get_chat_route(chat_id):
        uid = current_user_id()

        chat = get_chat(
            chat_id,
            uid
        )

        if not chat:
            return jsonify({
                "error": "Chat not found.",
                "code": "NOT_FOUND"
            }), 404

        return jsonify(
            list_messages(
                chat_id,
                uid,
                limit=200
            )
        )

    @app.post("/api/chat/delete")
    @auth_required
    def delete_chat_route():
        uid = current_user_id()
        data = request.get_json(silent=True) or {}

        chat_id = str(
            data.get("chat_id", "")
        ).strip()

        if not chat_id:
            return jsonify({
                "error": "chat_id required.",
                "code": "VALIDATION_ERROR"
            }), 400

        if not get_chat(chat_id, uid):
            return jsonify({
                "error": "Chat not found.",
                "code": "NOT_FOUND"
            }), 404

        deleted = delete_chat(
            chat_id,
            uid
        )

        return jsonify({
            "success": deleted,
            "deleted": deleted
        })

    @app.post("/api/chat")
    @auth_required
    def chat():
        uid = current_user_id()

        question = request.form.get(
            "question",
            request.form.get("message", "")
        ).strip()

        client_msg_id = (
            request.form.get("client_msg_id")
            or str(uuid.uuid4())
        )

        requested_chat_id = (
            request.form.get("chat_id")
            or None
        )

        mode = (
            request.form.get("mode", "normal")
            .strip()
            .lower()
        )

        is_regen = request.form.get("is_regen") == "1"
        uploaded_file = request.files.get("file")

        if len(question) > 20000:
            return jsonify({
                "error": "Question too long.",
                "code": "QUESTION_TOO_LONG"
            }), 413

        if not question and not uploaded_file:
            return jsonify({
                "error": "Empty request.",
                "code": "EMPTY_REQUEST"
            }), 400

        if requested_chat_id:
            chat_id = str(requested_chat_id)

            if not get_chat(chat_id, uid):
                return jsonify({
                    "error": "Chat not found.",
                    "code": "NOT_FOUND"
                }), 404

        else:
            new_chat = create_chat(
                uid,
                question[:60] if question else "New Chat"
            )

            chat_id = str(
                new_chat["id"]
            )

        if not is_regen:
            try:
                existing = (
                    db()
                    .table("messages")
                    .select("id")
                    .eq(
                        "client_msg_id",
                        client_msg_id
                    )
                    .eq(
                        "user_id",
                        uid
                    )
                    .limit(1)
                    .execute()
                )

                if existing.data:
                    return jsonify({
                        "error": "Duplicate message.",
                        "code": "DUPLICATE_MESSAGE"
                    }), 409

            except Exception:
                logger.exception(
                    "Idempotency check failed"
                )

                return jsonify({
                    "error": "Database error.",
                    "code": "DATABASE_ERROR"
                }), 500

        filepath = None
        file_meta = None
        db_file_meta = None

        if uploaded_file and uploaded_file.filename:
            original_name = uploaded_file.filename

            if not allowed_file(original_name):
                return jsonify({
                    "error": "File type not allowed.",
                    "code": "FILE_TYPE_NOT_ALLOWED"
                }), 400

            safe_name = secure_filename(
                original_name
            )

            if not safe_name:
                return jsonify({
                    "error": "Invalid filename.",
                    "code": "INVALID_FILENAME"
                }), 400

            filepath = os.path.join(
                UPLOAD_FOLDER,
                f"{uuid.uuid4().hex}_{safe_name}"
            )

            try:
                uploaded_file.save(filepath)

                size = os.path.getsize(filepath)

                if size > settings.max_upload_bytes:
                    os.remove(filepath)
                    filepath = None

                    return jsonify({
                        "error": "File too large.",
                        "code": "FILE_TOO_LARGE"
                    }), 413

                ext = os.path.splitext(
                    original_name
                )[1].lower()

                file_meta = {
                    "name": original_name,
                    "type": ext,
                    "temp_path": filepath,
                    "size": size
                }

                db_file_meta = {
                    "name": original_name,
                    "type": ext,
                    "size": size
                }

                if not is_image_file(original_name):
                    try:
                        ingestion = FileIngestionService()

                        result = ingestion.ingest(
                            path=filepath,
                            filename=original_name,
                            user_id=uid,
                            chat_id=chat_id
                        )

                        if not result.get("success"):
                            logger.warning(
                                "File ingestion failed: %s",
                                result.get(
                                    "error",
                                    "unknown error"
                                )
                            )
                        else:
                            logger.info(
                                "File indexed: %s chunks=%s",
                                original_name,
                                result.get("saved", 0)
                            )

                    except Exception:
                        logger.exception(
                            "File ingestion failed for %s",
                            original_name
                        )

            except Exception:
                if filepath and os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except OSError:
                        pass

                logger.exception(
                    "File upload failed"
                )

                return jsonify({
                    "error": "File upload failed.",
                    "code": "FILE_UPLOAD_FAILED"
                }), 500

        if not is_regen:
            try:
                create_message(
                    uid,
                    chat_id,
                    "user",
                    question,
                    db_file_meta,
                    client_msg_id
                )

            except Exception:
                if filepath and os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except OSError:
                        pass

                logger.exception(
                    "Failed to save user message"
                )

                return jsonify({
                    "error": "Failed to save message.",
                    "code": "MESSAGE_SAVE_FAILED"
                }), 500

        messages = list_messages(
            chat_id,
            uid,
            limit=200
        )

        context = build_context(
            user_id=uid,
            chat_id=chat_id,
            question=question,
            messages=messages,
            mode=mode,
            file_meta=file_meta
        )

        def generate():
            full = ""

            try:
                stream = orchestrator.stream(
                    context
                )

                yield (
                    "event: chat_id\n"
                    f"data: {json.dumps({'chat_id': chat_id})}\n\n"
                )

                for chunk in stream:
                    choices = getattr(
                        chunk,
                        "choices",
                        None
                    )

                    if not choices:
                        continue

                    delta = getattr(
                        choices[0],
                        "delta",
                        None
                    )

                    text = getattr(
                        delta,
                        "content",
                        None
                    )

                    if not text:
                        continue

                    full += text

                    yield (
                        "event: token\n"
                        f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
                    )

                if full.strip():
                    create_message(
                        uid,
                        chat_id,
                        "assistant",
                        full
                    )

                    try:
                        (
                            db()
                            .table("chats")
                            .update({
                                "updated_at": datetime.now(
                                    timezone.utc
                                ).isoformat()
                            })
                            .eq("id", chat_id)
                            .eq("user_id", uid)
                            .execute()
                        )

                    except Exception:
                        logger.exception(
                            "Failed to update chat timestamp"
                        )

            except Exception:
                logger.exception(
                    "Brain generation failed"
                )

                yield (
                    "event: error\n"
                    f"data: {json.dumps({'message': 'Brain generation failed.', 'request_id': getattr(g, 'request_id', '')})}\n\n"
                )

            finally:
                if filepath and os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except OSError:
                        pass

                yield (
                    "event: done\n"
                    f"data: {json.dumps({'chat_id': chat_id})}\n\n"
                )

        response = Response(
            stream_with_context(generate()),
            mimetype="text/event-stream"
        )

        response.headers.update({
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        })

        return response

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(error):
        return jsonify({
            "error": {
                "code": "REQUEST_TOO_LARGE",
                "message": "Request exceeds the allowed size."
            }
        }), 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=settings.port,
        debug=False
    )