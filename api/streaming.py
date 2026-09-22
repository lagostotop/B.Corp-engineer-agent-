from flask import Blueprint, Response

streaming_bp = Blueprint("streaming", __name__)

def sse_event(event, data):
    import json
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

def stream_response(generator):
    return Response(
        generator,
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )