import os, json, re, base64, uuid
from groq import Groq
from datetime import datetime, timezone
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

GENERATION_TIMEOUT = 120
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

client = Groq(api_key=os.getenv("GROQ_API_KEY"), timeout=GENERATION_TIMEOUT)

# ============ 1. EMBEDDINGS + RAG ============
def get_embedding(text: str) -> List[float]:
    try:
        if os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI
            oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            res = oai.embeddings.create(model=EMBED_MODEL, input=text)
            return res.data[0].embedding

        if os.getenv("JINA_API_KEY"):
            import requests
            r = requests.post("https://api.jina.ai/v1/embeddings",
                headers={"Authorization": f"Bearer {os.getenv('JINA_API_KEY')}"},
                json={"model": "jina-embeddings-v2-base-en", "input": [text]})
            return r.json()["data"][0]["embedding"]

        logger.warning("No embedding provider set. Using zeros.")
        return [0.0] * 1536

    except Exception as e:
        logger.exception(f"Embedding error: {e}")
        return [0.0] * 1536

def extract_text_from_file(filepath: str) -> str:
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
    q_emb = get_embedding(query)
    try:
        res = supabase.rpc("match_documents", {
            "query_embedding": q_emb,
            "match_count": top_k,
            "filter_user": uid
        }).execute()
        if not res.data: return ""
        return "\n\n".join([f"[DOC] {d['content'][:500]}" for d in res.data])
    except:
        res = supabase.table("documents").select("content").eq("user_id", uid).ilike("content", f"%{query}%").limit(3).execute()
        return "\n\n".join([f"[DOC] {d['content'][:500]}" for d in res.data]) if res.data else ""

# ============ 2. MEMORY TOOLS ============
def save_memory(user_id: str, key: str, value: str, supabase):
    try:
        supabase.table("brain30_memory").upsert({
            "user_id": user_id, "key": key, "value": value,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return f"Saved: {key}"
    except Exception as e:
        return f"Memory save failed: {e}"

def get_memory(user_id: str, query: str, supabase):
    try:
        res = supabase.table("brain30_memory").select("key,value").eq("user_id", user_id).ilike("key", f"%{query}%").limit(5).execute()
        return [f"{r['key']}: {r['value']}" for r in res.data]
    except: return []

# ============ 3. DEEP RESEARCH ============
def deep_research(topic: str, supabase, uid: str) -> str:
    """5-step research: Plan -> Search 3x -> Synthesize"""
    try:
        # 1. PLAN
        plan_res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Break this research topic into 3 specific sub-questions. Return as bullet list."},
                      {"role": "user", "content": topic}],
            temperature=0.3
        )
        plan = plan_res.choices[0].message.content
        questions = [q.strip("- ").strip() for q in plan.split("\n") if q.strip()][:3]

        # 2. SEARCH EACH QUESTION
        findings = []
        for q in questions:
            web_res = client.chat.completions.create(model="groq/compound", messages=[{"role": "user", "content": q}])
            doc_res = search_rag(q, uid, supabase)
            findings.append(f"## {q}\nWeb: {web_res.choices[0].message.content}\nDocs: {doc_res}")

        # 3. SYNTHESIZE
        final_res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Synthesize these findings into a comprehensive report. Cite sources. Use markdown."},
                      {"role": "user", "content": "\n\n".join(findings)}],
            temperature=0.4
        )
        return f"# Research Report: {topic}\n\n{final_res.choices[0].message.content}"
    except Exception as e:
        return f"Research failed: {e}"

# ============ 4. AGENT ENGINE V2 - FUNCTION CALLING ============
AVAILABLE_TOOLS = [
    {"type": "function", "function": {"name": "web_search", "description": "Search web for current info", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "search_documents", "description": "Search user uploaded files", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "deep_research", "description": "Multi-step research on a topic", "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}}},
    {"type": "function", "function": {"name": "save_memory", "description": "Save fact about user", "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}}},
    {"type": "function", "function": {"name": "get_memory", "description": "Recall facts about user", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}
]

class AgentEngine:
    def __init__(self, supabase_client, uid: str):
        self.supabase = supabase_client
        self.uid = uid
        self.max_steps = 6

    def run(self, goal: str, messages: List[Dict], file_meta: Any, chat_id: str) -> Dict[str, Any]:
        steps = []
        agent_messages = [{"role": "system", "content": "You are Brain 4.0, an autonomous AI OS agent by B.CORP. Achieve the goal by calling tools. Call multiple tools if needed. When done, answer directly."}] + messages
        agent_messages.append({"role": "user", "content": goal})

        for i in range(self.max_steps):
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
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
        return {"answer": "Task completed.", "steps": steps}

    def _execute_tool(self, name: str, args: Dict, file_meta: Any, chat_id: str) -> str:
        if name == "web_search":
            res = client.chat.completions.create(model="groq/compound", messages=[{"role": "user", "content": args["query"]}])
            return res.choices[0].message.content

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
                "user_id": self.uid, "goal": goal, "steps": json.dumps(steps)
            }).execute()
        except Exception as e:
            logger.error(f"Log error: {e}")

# ============ 5. MODEL ROUTER ============
class ModelRouter:
    def __init__(self, supabase_client):
        self.supabase = supabase_client

    def route(self, messages: List[Dict], uid: str, cid: str, file_meta: Any, stream=False):
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        last_user_msg = messages[-1]["content"] if messages else ""
        has_image = bool(file_meta and file_meta.get("path", "").endswith((".png",".jpg",".jpeg")))

        logger.info("[%s] Agent Start: %s", req_id, last_user_msg[:50])

        # 1. RUN AGENT FIRST
        agent = AgentEngine(self.supabase, uid)
        agent_result = agent.run(last_user_msg, messages, file_meta, cid)
        final_answer = agent_result["answer"]

        # 2. MODEL SELECTION
        if has_image: model = "meta-llama/llama-4-scout-17b-16e-instruct"
        elif any(k in last_user_msg.lower() for k in ["code", "function", "debug"]): model = "openai/gpt-oss-120b"
        else: model = "llama-3.3-70b-versatile"

        logger.info("[%s] Final Answer with %s", req_id, model)

        # 3. STREAM FINAL ANSWER
        system_prompt = "You are Brain 4.0 by B.CORP. Be helpful, accurate, and cite sources."
        groq_messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"User: {last_user_msg}\n\nAgent Research: {final_answer}"}]

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
