from flask import Blueprint, jsonify
from core.config import settings

health_bp = Blueprint("health", __name__)

@health_bp.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    })