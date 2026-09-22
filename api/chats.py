from flask import Blueprint, jsonify, request
from core.errors import ValidationError, NotFoundError
from core.security import current_user_id, authenticate_request
from database.client import db
from database.chats import (
    create_chat,
    get_chat,
    list_chats,
    update_chat,
    delete_chat,
)
from database.messages import list_messages

chats_bp = Blueprint("chats", __name__)

def _auth():
    authenticate_request(db())
    return current_user_id()

@chats_bp.get("/api/chats")
def chats():
    user_id = _auth()
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"chats": list_chats(user_id, limit)})

@chats_bp.post("/api/chats")
def create():
    user_id = _auth()
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "New Chat")).strip()

    if not title:
        raise ValidationError("Chat title cannot be empty.")

    return jsonify({
        "chat": create_chat(user_id, title)
    }), 201

@chats_bp.get("/api/chat/<chat_id>")
def get(chat_id):
    user_id = _auth()
    chat = get_chat(chat_id, user_id)

    if not chat:
        raise NotFoundError("Chat not found.")

    messages = list_messages(chat_id, user_id)

    return jsonify({
        "chat": chat,
        "messages": messages,
    })

@chats_bp.patch("/api/chat/<chat_id>")
def update(chat_id):
    user_id = _auth()
    data = request.get_json(silent=True) or {}

    if "title" not in data:
        raise ValidationError("Missing title.")

    chat = update_chat(chat_id, user_id, data["title"])

    if not chat:
        raise NotFoundError("Chat not found.")

    return jsonify({"chat": chat})

@chats_bp.delete("/api/chat/<chat_id>")
def delete(chat_id):
    user_id = _auth()

    if not delete_chat(chat_id, user_id):
        raise NotFoundError("Chat not found.")

    return jsonify({"deleted": True})