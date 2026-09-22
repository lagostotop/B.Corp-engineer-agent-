from flask import Blueprint, jsonify
from core.security import authenticate_request
from database.client import db

auth_bp = Blueprint("auth", __name__)

@auth_bp.get("/api/auth/me")
def me():
    user = authenticate_request(db())
    return jsonify({
        "user": {
            "id": str(user.id),
            "email": getattr(user, "email", None),
            "user_metadata": getattr(user, "user_metadata", {}) or {},
        }
    })