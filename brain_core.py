import os, io, base64, threading, time, json, uuid
from dataclasses import dataclass
from typing import Literal, Any
from datetime import datetime, timezone
from supabase import Client
from PIL import Image, ImageOps
from PIL.Image import DecompressionBombError
import PyPDF2
from docx import Document
from werkzeug.utils import secure_filename
from flask import abort

MAX_EXTRACTED_TEXT = 80_000
MAX_CHUNKS = 100
CHUNK_SIZE, CHUNK_OVERLAP = 1000, 200
MAX_IMAGE_JPEG = 3 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_TOOL_CONTEXT_CHARS = 8000
MAX_PLAN_STEPS = 3
MAX_QUERY_LENGTH = 200
MAX_PER_FILE_BYTES = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf", "txt", "py", "js", "ts", "jsx", "tsx", "html", "css", "md", "csv", "json", "png", "jpg", "jpeg", "docx"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
BINARY_EXTENSIONS = {"pdf", "docx", "png", "jpg", "jpeg"}
TEXT_EXTENSIONS = {"txt", "py", "js", "ts", "jsx", "tsx", "html", "css", "md", "csv", "json"}
ALLOWED_ROLES = {"user", "assistant"}

SYSTEM_PROMPT = """You are Brain 3.0, AI OS for CEO of B.CORP.
Rules:
1. When CONTEXT is provided below, answer using ONLY that context.
2. Cite factual claims using [SOURCE N] format.
3. At the end, provide **Sources** section with [N] [Title](URL).
4. If no CONTEXT is provided, answer from knowledge and do NOT invent sources.
5. Be decisive, direct, and production-ready."""

TOOL_MAP = {"search": "web_search", "recall": "recall_memories", "doc_search": "search_documents"}
ALLOWED_ACTIONS = set(TOOL_MAP.keys())

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

@dataclass
class ModelConfig:
    name: str
    provider: str
    model_id: str
    cost_per_1k_in: float
    cost_per_1k_out: float
    max_tokens: int
    purpose: Literal["fast", "general", "reasoning", "vision"]

MODELS = {
    "fast": ModelConfig("Llama 3.1 8B", "groq", "llama-3.1-8b-instant", 0.05, 0.08, 8192, "fast"),
    "general": ModelConfig("Llama 3.1 70B", "groq", "llama-3.1-70b-versatile", 0.59, 0.79, 8192, "general"),
    "reasoning": ModelConfig("Llama 3.1 70B", "groq", "llama-3.1-70b-versatile", 0.59, 0.79, 8192, "reasoning"),
    "vision": ModelConfig("Llama 3.2 11B Vision", "groq", "llama-3.2-11b-vision-preview", 0.19, 0.19, 8192, "vision"),
}

class ModelRouter:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    def classify_request(self, user_message: str, has_image: bool) -> str:
        msg = user_message.lower()
        if has_image: return "vision"
        if any(k in msg for k in ["calculate", "law", "strategy", "analyze", "compare", "legal"]):
            return "reasoning"
        elif len(user_message.split()) < 20:
            return "fast"
        else:
            return "general"

    def route(self, messages: list, user_id: str, chat_id: str, has_image: bool = False, stream: bool = True) -> Any:
        from app import client, logger, GENERATION_TIMEOUT
        start_time = time.time()
        last_msg = messages[-1]["content"]
        if isinstance(last_msg, list): last_msg = last_msg[0]["text"]
        model_type = self.classify_request(last_msg, has_image)
        config = MODELS[model_type]
        logger.info(f"Routing to {model_type}: {config.name}")

        try:
            response = client.chat.completions.create(
                model=config.model_id,
                messages=messages,
                stream=stream,
                timeout=GENERATION_TIMEOUT,
                extra_headers={"HTTP-Referer": "https://b-corp.ai"}
            )
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            config = MODELS["general"]
            response = client.chat.completions.create(model=config.model_id, messages=messages, stream=stream, timeout=GENERATION_TIMEOUT, extra_headers={"HTTP-Referer": "https://b-corp.ai"})

        latency = time.time() - start_time
        def log_async():
            try:
                self.supabase.table("inference_logs").insert({
                    "model_type": model_type, "model_used": config.name, "input_tokens": 0, "output_tokens": 0,
                    "latency": latency, "cost": 0.0, "user_id": user_id, "chat_id": chat_id
                }).execute()
            except Exception as e: logger.error(f"Failed to log inference: {e}")
        threading.Thread(target=log_async, daemon=True).start()
        return response

def get_embedding(text, client):
    try:
        res = client.embeddings.create(model="nomic-embed-text", input=text)
        return res.data[0].embedding
    except Exception as e: raise RuntimeError("Embedding service unavailable") from e

def create_chat(user_id, first_message, supabase):
    title = (first_message or "New Chat").strip()[:80]
    res = supabase.table("chats").insert({"user_id": user_id, "title": title, "created_at": datetime.now(timezone.utc).isoformat()}).execute()
    if not res.data: abort(500, "Failed to create chat")
    return str(res.data[0]["id"])

def get_owned_chat(chat_id, user_id, supabase):
    res = supabase.table("chats").select("id").eq("id", chat_id).eq("user_id", user_id).maybe_single().execute()
    if not res.data: abort(403, "Access denied")
    return True

def check_idempotency(client_msg_id, user_id, supabase):
    if not client_msg_id: return None
    res = supabase.table("messages").select("*").eq("user_id", user_id).eq("client_msg_id", client_msg_id).maybe_single().execute()
    return res.data

def save_message(chat_id, user_id, role, content, attachment_meta, client_msg_id, supabase, status="completed"):
    get_owned_chat(chat_id, user_id, supabase)
    data = {"chat_id": chat_id, "user_id": user_id, "role": role if role in ALLOWED_ROLES else "user", "content": content, "status": status}
    if attachment_meta: data["attachment"] = attachment_meta
    if client_msg_id: data["client_msg_id"] = client_msg_id
    try: supabase.table("messages").insert(data).execute()
    except Exception as e:
        if getattr(e, 'code', '') == '23505': abort(409, "Duplicate request")
        raise

def load_messages(chat_id, user_id, supabase):
    get_owned_chat(chat_id, user_id, supabase)
    msgs = supabase.table("messages").select("*").eq("chat_id", chat_id).order("created_at", desc=True).limit(20).execute().data or []
    return list(reversed([m for m in msgs if m["role"] in ALLOWED_ROLES]))

CURRENT_PATTERNS = ["latest", "today", "current", "recent", "news", "this week", "2026"]
MEMORY_PATTERNS = ["remember", "you told me", "we discussed", "my preference", "my project"]
DOCUMENT_PATTERNS = ["file", "document", "uploaded", "attached", "this code", "summarize"]

def needs_tools(q, has_files):
    ql = q.lower()
    if has_files: return True
    return any(t in ql for t in CURRENT_PATTERNS + MEMORY_PATTERNS + DOCUMENT_PATTERNS)

def generate_plan(task, client, model):
    if not task: return []
    try:
        sys = "Return JSON only: {\"steps\":[{\"action\":\"search\"|\"recall\"|\"doc_search\",\"query\":\"string\"}]}. Rules: Max 3 steps."
        res = client.chat.completions.create(model=model, messages=[{"role": "system", "content": sys}, {"role": "user", "content": f'Task:{task}'}], response_format={"type": "json_object"}, max_tokens=400, timeout=10)
        steps = json.loads(res.choices[0].message.content).get("steps", [])[:MAX_PLAN_STEPS]
        seen = set(); out = []
        for s in steps:
            if isinstance(s, dict) and s.get("action") in ALLOWED_ACTIONS:
                q = s["query"].strip()[:MAX_QUERY_LENGTH]
                if len(q) > 5 and q not in seen: seen.add(q); out.append({"action": s["action"], "query": q})
        return out
    except: return []

def call_tool(tool_name, args, user_id, chat_id, supabase, client):
    q = args.get("query", "").strip()[:MAX_QUERY_LENGTH]
    if not q: return {"success": False, "error": "Empty query"}
    if tool_name == "web_search":
        from app import tavily
        try: res = tavily.search(query=q, max_results=5, search_depth="advanced", timeout=15); return {"success": True, "results": [{"title": r["title"], "content": r["content"][:400], "url": r["url"]} for r in res["results"]]}
        except: return {"success": False, "error": "Search failed"}
    if tool_name == "recall_memories":
        emb = get_embedding(q, client)
        res = supabase.rpc("match_embeddings", {"query_embedding": emb, "match_count": 5, "filter_user_id": user_id}).execute()
        return {"success": True, "text": "\n".join([r["content"] for r in res.data if r.get("category")!= "file"])}
    if tool_name == "search_documents":
        emb = get_embedding(q, client)
        res = supabase.rpc("match_document_embeddings", {"query_embedding": emb, "filter_user_id": user_id, "filter_chat_id": chat_id, "match_count": 5, "similarity_threshold": 0.7}).execute()
        if not res.data: return {"success": False, "error": "No match"}
        return {"success": True, "text": "\n".join([r["content"] for r in res.data])}
    return {"success": False, "error": "Tool not found"}

def process_image(b):
    try:
        img = Image.open(io.BytesIO(b))
        if img.width * img.height > MAX_IMAGE_PIXELS: abort(413, "Image too large")
        img = ImageOps.exif_transpose(img).convert("RGB"); img.thumbnail((1024, 1024))
        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85, optimize=True)
        if buf.tell() > MAX_IMAGE_JPEG: abort(413, "Image too large")
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except DecompressionBombError: abort(413, "Image too large")
    except: abort(400, "Invalid image")

def validate_file_signature(b, ext):
    if not MAGIC_AVAILABLE: return
    if ext in BINARY_EXTENSIONS:
        mime = magic.from_buffer(b[:2048], mime=True)
        exp = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
        if exp.get(ext) and mime!= exp[ext]: abort(400, "Signature mismatch")

def process_uploaded_file(file, user_id, chat_id, supabase, client):
    fn = secure_filename(file.filename)
    if '.' not in fn: abort(400, "No extension")
    ext = fn.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS: abort(400, "Type not allowed")
    b = file.read()
    if len(b) > MAX_PER_FILE_BYTES: abort(413, "File too large")
    validate_file_signature(b, ext)
    if ext in IMAGE_EXTENSIONS: return f"\n\n[IMAGE:{fn}]", "", True, process_image(b), {"type": "image", "name": fn}
    start = time.time(); text = ""
    if ext == "pdf":
        pdf = PyPDF2.PdfReader(io.BytesIO(b))
        for p in pdf.pages[:50]:
            text += p.extract_text() or ""
            if len(text) > MAX_EXTRACTED_TEXT or time.time() - start > 10: break
    elif ext == "docx":
        for p in Document(io.BytesIO(b)).paragraphs:
            text += p.text + "\n"
            if len(text) > MAX_EXTRACTED_TEXT or time.time() - start > 10: break
    else: text = b.decode("utf-8", errors="replace")
    text = text[:MAX_EXTRACTED_TEXT]
    if not text.strip(): abort(400, "Empty file")
    chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE - CHUNK_OVERLAP)][:MAX_CHUNKS]
    doc_id = str(uuid.uuid4())
    supabase.table("documents").insert({"id": doc_id, "user_id": user_id, "chat_id": chat_id, "filename": fn, "status": "processing", "started_at": datetime.now(timezone.utc).isoformat()}).execute()
    def worker():
        try:
            embs = [get_embedding(c, client) for c in chunks]
            rows = [{"user_id": user_id, "chat_id": chat_id, "document_id": doc_id, "category": "file", "content": c, "embedding": e, "source": f"{fn}#chunk{i}"} for i, (c, e) in enumerate(zip(chunks, embs))]
            supabase.table("embeddings").insert(rows).execute()
            supabase.table("documents").update({"status": "done", "completed_at": datetime.now(timezone.utc).isoformat()}).eq("id", doc_id).execute()
        except Exception: supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
    threading.Thread(target=worker, daemon=True).start()
    return f"\n\n[FILE:{fn} {len(chunks)}chunks]", text, False, None, {"type": "file", "name": fn, "doc_id": doc_id}
