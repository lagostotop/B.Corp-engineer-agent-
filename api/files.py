from flask import Blueprint, jsonify

files_bp = Blueprint("files", __name__)

@files_bp.post("/api/files")
def upload_file():
    return jsonify({
        "error": {
            "code": "FILE_PROCESSING_NOT_READY",
            "message": "File processing is temporarily unavailable."
        }
    }), 503