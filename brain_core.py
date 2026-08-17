import os, json, re, base64, uuid
from groq import Groq
from datetime import datetime, timezone
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

GENERATION_TIMEOUT = 120
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small") # Use OpenAI if set

client = Groq(api_key=os.getenv("GROQ_API_KEY"), timeout=GENERATION_TIMEOUT)

# ============ 1. EMBEDDINGS ============
def get_embedding(text: str) -> List[float]:
    """Get embedding. Uses OpenAI if GROQ doesn't support it"""
    try:
        # Try OpenAI first if key exists
        if os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI
            oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            res = oai.embeddings.create(model=EMBED_MODEL, input=text)
            return res.data[0].embedding

        # Fallback: Jina
        if os.getenv("JINA_API_KEY"):
            import requests
            r = requests.post("https://api.jina.ai/v1/embeddings",
                headers={"Authorization": f"Bearer {os.getenv('JINA_API_KEY')}"},
                json={"model": "jina-embeddings-v2-base-en", "input": [text]})
            return r.json()["data"][0]["embedding"]

        # Last resort placeholder - but log it
        logger.warning("No embedding provider set. Using zeros. Set OPENAI_API_KEY or JINA_API_KEY")
        return [0.0] * 1536

    except Exception as e:
        logger.exception(f"Embedding error: {e}")
        return [0.0] * 1536

def extract_text_from_file(filepath: str) -> str:
    """Basic text extraction"""
    try:
        if filepath.endswith(".txt") or filepath.endswith(".md"):
            with open(filepath, "r", encoding="utf-8") as f: return f.read()
        if filepath.endswith(".pdf"):
            import PyPDF2
            reader = PyPDF2.PdfReader(filepath)
            return "\n".join([p.extract_text() for p in reader.pages])
        return f"[Binary file: {os.path.basename(filepath)}]"
    except: return ""

def chunk_text(text: str, chunk_size=800) -> List[str]:
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def save_to_rag(chat_id: str, uid: str, filepath: str, supabase):
    """Upload file -> chunks -> embeddings -> supabase"""
    text = extract_text_from_file(filepath)
    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks):
        emb = get_embedding(chunk)
        supabase.table("documents").insert({
            "id": str(uuid.uuid4()),
            "chat_id": chat_id, "user_id": uid,
            "content": chunk, "embedding": emb,
            "metadata": {"chunk": i, "file": os.path.basename(filepath)}
        }).execute()
    logger.info(f"RAG: Saved {len(chunks)} chunks for {chat_id}")

def search_rag(query: str, uid: str, supabase, top_k=3) -> str:
    """Semantic search"""
    q_emb = get_embedding(query)
    res = supabase.rpc("match_documents", {
        "query_embedding": q_emb,
        "match_count": top_k,
        "filter_user": uid
    }).execute()
    if not res.data: return ""
    return "\n\n".join([f"[DOC] {d['content']}" for d in res.data])

# ============ 2. AGENT TOOLS ============
def needs_tools(q: str, has_files: bool) -> Dict[str, Any]:
    q = q.lower()
    tools = {}
    if has_files: tools["rag"] = True
    if any(k in q for k in ["latest", "news", "today", "price", "stock", "weather"]): tools["web_search"] = q
    if any(k in q for k in ["remember", "recall", "what did i", "my"]): tools["memory"] = q
    return tools

def call_tool(tool_name: str, params: Any, supabase, uid: str) -> str:
    """ACTUAL tool calls"""
    if tool_name == "web_search":
        # Use Groq Compound for real web search
        try:
            res = client.chat.completions.create(
                model="groq/compound",
                messages=[{"role": "user", "content": params}],
                temperature=0.1
            )
            return res.choices[0].message.content
        except:
            return f"[1] [Web Search Failed](https://google.com/search?q={params})"

    if tool_name == "memory":
        # Simple memory: search past messages
        res = supabase.table("messages").select("content").eq("user_id", uid).ilike("content", f"%{params}%").limit(3).execute()
        if res.data: return "From memory: " + " | ".join([m["content"][:200] for m in res.data])
        return ""

    if tool_name == "rag":
        return params # params will be the RAG context

    return ""

# ============ 3. MODEL ROUTER ============
class ModelRouter:
    def __init__(self, supabase_client):
        self.supabase = supabase_client

    def route(self, messages: List[Dict], uid: str, cid: str, file_meta: Any, stream=False):
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        last_user_msg = messages[-1]["content"] if messages else ""
        has_image = bool(file_meta and file_meta.get("path", "").endswith((".png",".jpg",".jpeg")))

        logger.info("[%s] Routing: len=%d has_image=%s", req_id, len(last_user_msg), has_image)

        system_prompt = """You are Brain 3.0, an AI OS by B.CORP.
Be helpful, accurate, and concise.
If you use information from the web or documents, cite it like: [1] [Title](URL)
"""

        # AGENT LOOP: Call tools first
        context_parts = []
        tools = needs_tools(last_user_msg, has_image)

        if "web_search" in tools:
            logger.info("[%s] Calling web_search", req_id)
            result = call_tool("web_search", tools["web_search"], self.supabase, uid)
            context_parts.append(f"Web Results:\n{result}")

        if "memory" in tools:
            logger.info("[%s] Calling memory", req_id)
            result = call_tool("memory", tools["memory"], self.supabase, uid)
            if result: context_parts.append(result)

        if "rag" in tools and file_meta:
            logger.info("[%s] Calling RAG", req_id)
            save_to_rag(cid, uid, file_meta["path"], self.supabase)
            result = search_rag(last_user_msg, uid, self.supabase)
            if result: context_parts.append(f"Document Context:\n{result}")

        if context_parts:
            system_prompt += "\n\nContext:\n" + "\n\n".join(context_parts)

        # MODEL ROUTING LOGIC
        if has_image:
            model = "meta-llama/llama-4-scout-17b-16e-instruct" # Vision
        elif any(k in last_user_msg.lower() for k in ["code", "function", "debug", "algorithm"]):
            model = "openai/gpt-oss-120b" # Reasoning/Coding
        elif len(last_user_msg) < 80:
            model = "llama-3.1-8b-instant" # Fast
        else:
            model = "llama-3.3-70b-versatile" # General

        logger.info("[%s] Selected model: %s", req_id, model)

        # BUILD MESSAGES - Handle vision
        groq_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            role = "assistant" if m["role"] == "assistant" else "user"
            content = m["content"]

            # If this is the last user message and has image, send multimodal
            if role == "user" and m == messages[-1] and has_image:
                try:
                    with open(file_meta["path"], "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    content = [
                        {"type": "text", "text": content},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                except Exception as e:
                    logger.error("[%s] Image encode error: %s", req_id, e)

            groq_messages.append({"role": role, "content": content})

        return client.chat.completions.create(
            model=model,
            messages=groq_messages,
            stream=stream,
            temperature=0.7,
            max_tokens=4096
        )

# ============ 4. DB HELPERS ============
def save_message(chat_id: str, user_id: str, role: str, content: str, file_meta: Any, client_msg_id: str, supabase):
    """Save message to Supabase"""
    try:
        supabase.table("messages").insert({
            "chat_id": chat_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "file_meta": file_meta,
            "client_msg_id": client_msg_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        logger.exception(f"save_message error: {e}")

def get_chat_history(chat_id: str, user_id: str, supabase) -> List[Dict]:
    """Get all messages for a chat - only needed fields"""
    try:
        res = supabase.table("messages")\
           .select("id,role,content,created_at,file_meta")\
           .eq("chat_id", chat_id)\
           .eq("user_id", user_id)\
           .order("created_at")\
           .execute()
        return res.data
    except Exception as e:
        logger.exception(f"get_chat_history error: {e}")
        return []
