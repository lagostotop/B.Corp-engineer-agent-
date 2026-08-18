import os, json, re, base64, uuid
from groq import Groq
from datetime import datetime, timezone
from typing import List, Dict, Any
import logging
import time

logger = logging.getLogger(__name__)

GENERATION_TIMEOUT = 120
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
MAX_FILE_SIZE = 10 * 1024 * 1024 # 10MB limit for Render

client = Groq(api_key=os.getenv("GROQ_API_KEY"), timeout=GENERATION_TIMEOUT)

# Import tools
from tools.tavily import search_web

# ============ 1. EMBEDDINGS + RAG ============
def get_embedding(text: str) -> List[float]:
    try:
        # Priority 1: OpenAI
        if os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI
            oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            res = oai.embeddings.create(model=EMBED_MODEL, input=text)
            return res.data[0].embedding

        # Priority 2: Jina
        if os.getenv("JINA_API_KEY"):
            import requests
            r = requests.post("https://api.jina.ai/v1/embeddings",
                headers={"Authorization": f"Bearer {os.getenv('JINA_API_KEY')}"},
                json={"model": "jina-embeddings-v2-base-en", "input": [text]})
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]

        logger.warning("No embedding provider set. Using zeros.")
        return [0.0] * 1536

    except Exception as e:
        logger.exception(f"Embedding error: {e}")
        return [0.0] * 1536

def get_file_type(filepath: str) -> str:
    """RENDER SAFE: Use extension instead of python-magic"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.txt', '.md']: return 'text'
    if ext == '.pdf': return 'pdf'
    if ext == '.docx': return 'docx'
    if ext in ['.png', '.jpg', '.jpeg']: return 'image'
    return 'unknown'

def extract_text_from_file(filepath: str) -> str:
    try:
        # File size check for Render
        if os.path.getsize(filepath) > MAX_FILE_SIZE:
            return "[File too large. Max 10MB]"

        ftype = get_file_type(filepath)

        if ftype == 'text':
            with open(filepath, "r", encoding="utf-8", errors='ignore') as f: 
                return f.read()[:50000] # Limit text

        if ftype == 'pdf':
            import PyPDF2
            reader = PyPDF2.PdfReader(filepath)
            text = "\n".join([p.extract_text() or "" for p in reader.pages])
            return text[:50000]

        if ftype == 'docx':
            import docx
            doc = docx.Document(filepath)
            text = "\n".join([p.text for p in doc.paragraphs])
            return text[:50000]

        if ftype == 'image':
            return "[Image file uploaded]"
            
        return f"[Unsupported file type: {os.path.basename(filepath)}]"
    except Exception as e:
        logger.error(f"Extract error: {e}")
        return f"[Error reading file: {e}]"

def chunk_text(text: str, chunk_size=800) -> List[str]:
    if not text: return []
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def save_to_rag(chat_id: str, uid: str, filepath: str, supabase):
    text = extract_text_from_file(filepath)
    if not text or text.startswith("["): 
        logger.info(f"RAG: Skipped file {filepath} - {text}")
        return
    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks[:20]): # Max 20 chunks per file
        emb = get_embedding(chunk)
        try:
            supabase.table("documents").insert({
                "id": str(uuid.uuid4()),
                "chat_id": chat_id, "user_id": uid,
                "content": chunk, "embedding": emb,
                "metadata": {"chunk": i, "file": os.path.basename(filepath)}
            }).execute()
        except Exception as e:
            logger.error(f"RAG insert failed: {e}")
            break
    logger.info(f"RAG: Saved {len(chunks)} chunks for {chat_id}")

def search_rag(query: str, uid: str, supabase, top_k=3) -> str:
    if not query.strip(): return ""
    q_emb = get_embedding(query)
    try:
        res = supabase.rpc("match_documents", {
            "query_embedding": q_emb,
            "match_count": top_k,
            "filter_user": uid
        }).execute()
        if not res.data: return ""
        return "\n\n".join([f"[DOC {i+1}] {d['content'][:500]}" for i, d in enumerate(res.data)])
    except Exception as e:
        logger.warning(f"Vector search failed, using ILIKE: {e}")
        try:
            res = supabase.table("documents").select("content").eq("user_id", uid).ilike("content", f"%{query[:50]}%").limit(3).execute()
            return "\n\n".join([f"[DOC {i+1}] {d['content'][:500]}" for i, d in enumerate(res.data)]) if res.data else ""
        except:
            return ""

# ============ 2. MEMORY TOOLS ============
def save_memory(user_id: str, key: str, value: str, supabase):
    try:
        supabase.table("brain30_memory").upsert({
            "user_id": user_id, "key": key.lower()[:100], "value": value[:2000],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return f"Saved memory: {key} = {value}"
    except Exception as e:
        return f"Memory save failed: {e}"

def get_memory(user_id: str, query: str, supabase):
    try:
        res = supabase.table("brain30_memory").select("key,value").eq("user_id", user_id).ilike("key", f"%{query.lower()}%").limit(5).execute()
        return [f"{r['key']}: {r['value']}" for r in res.data]
    except: return []

# ============ 3. DEEP RESEARCH V2 ============
def deep_research(topic: str, supabase, uid: str) -> str:
    """4-step research: Plan -> Multi-Search -> Extract -> Synthesize"""
    try:
        logger.info(f"Deep Research Start: {topic}")
        # 1. PLAN
        plan_res = client.chat.completions.create(
            model=os.getenv("GROQ_GENERAL_MODEL", "llama-3.3-70b-versatile"),
            messages=[{"role": "system", "content": "Break this research topic into 4 specific sub-questions. Return ONLY a JSON object: {\"questions\": [\"q1\", \"q2\"]}"},
                      {"role": "user", "content": topic}],
            temperature=0.3, response_format={"type": "json_object"}
        )
        questions = json.loads(plan_res.choices[0].message.content).get("questions", [topic])[:4]

        # 2. SEARCH EACH QUESTION
        findings = []
        all_sources = []
        for q in questions:
            web_res = search_web(q) # Use Tavily
            # Extract URLs from Tavily response for sources
            urls = re.findall(r'Source: (https?://[^\s]+)', web_res)
            all_sources.extend(urls)
            doc_res = search_rag(q, uid, supabase)
            findings.append({"q": q, "web": web_res, "docs": doc_res})
            time.sleep(0.3)

        # 3. EXTRACT KEY POINTS
        extract_res = client.chat.completions.create(
            model=os.getenv("GROQ_GENERAL_MODEL", "llama-3.3-70b-versatile"),
            messages=[{"role": "system", "content": "Extract 5-7 key factual points from this research. Be concise."},
                      {"role": "user", "content": json.dumps(findings)}],
            temperature=0.2
        )
        key_points = extract_res.choices[0].message.content

        # 4. SYNTHESIZE
        sources_list = "\n".join([f"[{i+1}] {url}" for i, url in enumerate(list(dict.fromkeys(all_sources)))])
        final_res = client.chat.completions.create(
            model=os.getenv("GROQ_REASONING_MODEL", "openai/gpt-oss-120b"),
            messages=[{"role": "system", "content": "Write a comprehensive research report with Executive Summary, Key Findings, Analysis, Conclusion. Cite sources inline as [1][2]. Add Sources section at end with URLs."},
                      {"role": "user", "content": f"Topic: {topic}\nKey Points:\n{key_points}\n\nRaw Data:\n{json.dumps(findings)}\n\nAvailable Sources:\n{sources_list}"}],
            temperature=0.4, max_tokens=2000
        )
        return f"# 🔬 Deep Research: {topic}\n\n{final_res.choices[0].message.content}"
    except Exception as e:
        logger.exception(f"Deep research failed: {e}")
        return f"Research failed: {e}"

# ============ 4. AGENT ENGINE V2 ============
AVAILABLE_TOOLS = [
    {"type": "function", "function": {"name": "web_search", "description": "Search web for current info, news, prices", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "search_documents", "description": "Search user's uploaded files", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "deep_research", "description": "Multi-step comprehensive research on a topic", "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}}},
    {"type": "function", "function": {"name": "save_memory", "description": "Save important fact about user", "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}}},
    {"type": "function", "function": {"name": "get_memory", "description": "Recall facts about user", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}
]

class AgentEngine:
    def __init__(self, supabase_client, uid: str):
        self.supabase = supabase_client
        self.uid = uid
        self.max_steps = 6

    def run(self, goal: str, messages: List[Dict], file_meta: Any, chat_id: str) -> Dict[str, Any]:
        steps = []
        agent_messages = [{"role": "system", "content": "You are Brain 4.0, an autonomous AI OS agent by B.CORP. Achieve the goal by calling tools step by step. When you have enough info, answer directly."}] + messages
        agent_messages.append({"role": "user", "content": goal})

        for i in range(self.max_steps):
            res = client.chat.completions.create(
                model=os.getenv("GROQ_GENERAL_MODEL", "llama-3.3-70b-versatile"),
                messages=agent_messages,
                tools=AVAILABLE_TOOLS,
                tool_choice="auto",
                temperature=0.2
            )

            msg = res.choices[0].message
            steps.append({"thought": msg.content, "tool_calls": [tc.model_dump() for tc in msg.tool_calls] if msg.tool_calls else None})

            if not msg.tool_calls:
                self._log_trace(goal, steps)
                return {"answer": msg.content, "steps": steps}

            agent_messages.append(msg)

            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                result = self._execute_tool(func_name, func_args, file_meta, chat_id)

                agent_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": result
                })

        self._log_trace(goal, steps)
        return {"answer": "I completed the research steps.", "steps": steps}

    def _execute_tool(self, name: str, args: Dict, file_meta: Any, chat_id: str) -> str:
        if name == "web_search":
            return search_web(args["query"])

        if name == "search_documents":
            if file_meta: save_to_rag(chat_id, self.uid, file_meta["path"], self.supabase)
            return search_rag(args["query"], self.uid, self.supabase)

        if name == "deep_research":
            return deep_research(args["topic"], self.supabase, self.uid)

        if name == "save_memory":
            return save_memory(self.uid, args["key"], args["value"], self.supabase)

        if name == "get_memory":
            mems = get_memory(self.uid, args["query"], self.supabase)
            return "Memory: " + " | ".join(mems) if mems else "No memory found"

        return "Tool not found"

    def _log_trace(self, goal: str, steps: List):
        try:
            self.supabase.table("Inference_logs").insert({
                "user_id": self.uid, "goal": goal, "steps": json.dumps(steps),
                "created_at": datetime.now(timezone.utc).isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Log error: {e}")

# ============ 5. MODEL ROUTER V2 - 4 TIER ============
class ModelRouter:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant")
        self.GENERAL_MODEL = os.getenv("GROQ_GENERAL_MODEL", "llama-3.3-70b-versatile")
        self.REASONING_MODEL = os.getenv("GROQ_REASONING_MODEL", "openai/gpt-oss-120b")
        self.CODE_MODEL = os.getenv("GROQ_CODE_MODEL", "openai/gpt-oss-120b")
        self.VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

    def _select_model(self, last_msg: str, has_image: bool) -> str:
        msg_lower = last_msg.lower()
        if has_image:
            return self.VISION_MODEL
        if len(last_msg) < 50 and any(w in msg_lower for w in ["hi", "hello", "thanks", "ok", "yes", "no"]):
            return self.FAST_MODEL
        if any(k in msg_lower for k in ["code", "function", "debug", "algorithm", "math"]):
            return self.CODE_MODEL
        return self.GENERAL_MODEL

    def route(self, messages: List[Dict], uid: str, cid: str, file_meta: Any, stream=False):
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        last_user_msg = messages[-1]["content"] if messages else ""
        has_image = bool(file_meta and file_meta.get("path", "").endswith((".png",".jpg",".jpeg")))

        logger.info("[%s] Agent Start: %s", req_id, last_user_msg[:50])

        # 1. RUN AGENT FIRST
        agent = AgentEngine(self.supabase, uid)
        agent_result = agent.run(last_user_msg, messages, file_meta, cid)
        agent_context = agent_result["answer"]

        # 2. MODEL SELECTION FOR FINAL ANSWER
        model = self._select_model(last_user_msg, has_image)
        logger.info("[%s] Final Answer with %s", req_id, model)

        # 3. BUILD FINAL MESSAGES WITH VISION SUPPORT
        system_prompt = "You are Brain 4.0 by B.CORP. Be helpful, accurate, and cite sources from the agent research."
        groq_messages = [{"role": "system", "content": system_prompt}]

        for m in messages[:-1]:
            groq_messages.append({"role": m["role"], "content": m["content"]})

        user_content = f"User Query: {last_user_msg}\n\nAgent Research Results:\n{agent_context}"

        if has_image:
            with open(file_meta["path"], "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            user_content = [
                {"type": "text", "text": user_content},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            ]

        groq_messages.append({"role": "user", "content": user_content})

        return client.chat.completions.create(
            model=model, messages=groq_messages, stream=stream,
            temperature=0.7, max_tokens=4096
        )

# ============ 6. DB HELPERS ============
def save_message(chat_id: str, user_id: str, role: str, content: str, file_meta: Any, client_msg_id: str, supabase):
    try:
        supabase.table("messages").insert({
            "chat_id": chat_id, "user_id": user_id, "role": role, "content": content,
            "file_meta": file_meta, "client_msg_id": client_msg_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        logger.exception(f"save_message error: {e}")

def get_chat_history(chat_id: str, user_id: str, supabase) -> List[Dict]:
    try:
        res = supabase.table("messages").select("id,role,content,created_at,file_meta").eq("chat_id", chat_id).eq("user_id", user_id).order("created_at").execute()
        return res.data
    except Exception as e:
        logger.exception(f"get_chat_history error: {e}")
        return []
