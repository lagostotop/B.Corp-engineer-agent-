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
    """Get embedding. Uses OpenAI if GROQ doesn't support it"""
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
        return "\n\n".join([f"[DOC] {d['content']}" for d in res.data])
    except:
        # fallback if RPC doesn't exist
        res = supabase.table("documents").select("content").eq("user_id", uid).ilike("content", f"%{query}%").limit(3).execute()
        return "\n\n".join([f"[DOC] {d['content']}" for d in res.data]) if res.data else ""

# ============ 2. AGENT ENGINE ============
class AgentEngine:
    def __init__(self, supabase_client, uid: str):
        self.supabase = supabase_client
        self.uid = uid
        self.max_steps = 5

    def run(self, goal: str, messages: List[Dict], file_meta: Any) -> Dict[str, Any]:
        """
        Multi-step agent loop. Plans, calls tools, then answers.
        """
        steps = []
        context_parts = []
        has_image = bool(file_meta and file_meta.get("path", "").endswith((".png",".jpg",".jpeg")))

        system_prompt = """You are Brain 4.0, an autonomous AI OS agent by B.CORP.
You can call tools to complete tasks. Think step by step.

Available tools:
1. web_search: for current info, news, prices
2. search_documents: for user's uploaded files
3. search_memory: for past conversations
4. finish: when you have the final answer

Always respond in JSON: {"thought": "...", "tool": "tool_name", "args": {...}}
"""

        for i in range(self.max_steps):
            # 1. DECIDE NEXT ACTION WITH LLM
            decision_prompt = f"Goal: {goal}\nSteps so far: {json.dumps(steps)}\nWhat is the next action?"

            groq_messages = [{"role": "system", "content": system_prompt}] + messages
            groq_messages.append({"role": "user", "content": decision_prompt})

            try:
                res = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=groq_messages,
                    temperature=0.1,
                    max_tokens=500,
                    response_format={"type": "json_object"} # Force JSON
                )
                decision = json.loads(res.choices[0].message.content)
            except:
                # Fallback to simple rules if JSON fails
                decision = self._fallback_router(goal, has_image)

            steps.append(decision)
            logger.info(f"Agent Step {i+1}: {decision}")

            # 2. EXECUTE TOOL
            tool = decision.get("tool")
            args = decision.get("args", {})

            if tool == "finish":
                return {"answer": args.get("answer", goal), "steps": steps}

            tool_result = self._call_tool(tool, args, goal, file_meta)
            if tool_result:
                context_parts.append(tool_result)
                # Add result to messages so LLM sees it next loop
                messages.append({"role": "assistant", "content": f"Tool result: {tool_result}"})

        # Max steps reached
        return {"answer": "I completed the steps but couldn't reach a final answer.", "steps": steps}

    def _call_tool(self, tool_name: str, args: Dict, query: str, file_meta: Any) -> str:
        """Execute the actual tool"""
        if tool_name == "web_search":
            try:
                res = client.chat.completions.create(
                    model="groq/compound",
                    messages=[{"role": "user", "content": args.get("query", query)}],
                    temperature=0.1
                )
                return f"Web Results:\n{res.choices[0].message.content}"
            except:
                return f"[1] [Web Search](https://google.com/search?q={query})"

        if tool_name == "search_documents":
            if file_meta:
                save_to_rag(args.get("chat_id"), self.uid, file_meta["path"], self.supabase)
            return f"Document Context:\n{search_rag(args.get('query', query), self.uid, self.supabase)}"

        if tool_name == "search_memory":
            res = self.supabase.table("messages").select("content").eq("user_id", self.uid).ilike("content", f"%{args.get('query', query)}%").limit(3).execute()
            if res.data: return "From memory: " + " | ".join([m["content"][:200] for m in res.data])
            return ""

        return ""

    def _fallback_router(self, goal: str, has_image: bool) -> Dict:
        goal_lower = goal.lower()
        if "search" in goal_lower or "news" in goal_lower:
            return {"thought": "Need current info", "tool": "web_search", "args": {"query": goal}}
        if "file" in goal_lower or "document" in goal_lower or has_image:
            return {"thought": "Need to search documents", "tool": "search_documents", "args": {"query": goal}}
        if "remember" in goal_lower or "recall" in goal_lower:
            return {"thought": "Need to search memory", "tool": "search_memory", "args": {"query": goal}}
        return {"thought": "Direct answer", "tool": "finish", "args": {"answer": goal}}

    def _log_trace(self, goal: str, steps: List):
        try:
            self.supabase.table("Inference_logs").insert({
                "user_id": self.uid,
                "goal": goal,
                "steps": json.dumps(steps)
            }).execute()
        except Exception as e:
            logger.error(f"Log error: {e}")

# ============ 3. MODEL ROUTER - NOW USES AGENT ============
class ModelRouter:
    def __init__(self, supabase_client):
        self.supabase = supabase_client

    def route(self, messages: List[Dict], uid: str, cid: str, file_meta: Any, stream=False):
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        last_user_msg = messages[-1]["content"] if messages else ""
        has_image = bool(file_meta and file_meta.get("path", "").endswith((".png",".jpg",".jpeg")))

        logger.info("[%s] Routing: len=%d has_image=%s", req_id, len(last_user_msg), has_image)

        # 1. RUN AGENT FIRST
        agent = AgentEngine(self.supabase, uid)
        agent_result = agent.run(last_user_msg, messages, file_meta)
        final_answer = agent_result["answer"]
        steps = agent_result["steps"]

        agent._log_trace(last_user_msg, steps)

        # 2. MODEL SELECTION FOR FINAL ANSWER
        if has_image:
            model = "meta-llama/llama-4-scout-17b-16e-instruct"
        elif any(k in last_user_msg.lower() for k in ["code", "function", "debug"]):
            model = "openai/gpt-oss-120b"
        else:
            model = "llama-3.3-70b-versatile"

        logger.info("[%s] Selected model: %s", req_id, model)

        # 3. BUILD FINAL PROMPT WITH AGENT STEPS AS CONTEXT
        system_prompt = f"""You are Brain 4.0, an AI OS by B.CORP.
The agent already did this work: {json.dumps(steps)}
Summarize the result for the user. Be helpful and cite sources if present.
"""

        groq_messages = [{"role": "system", "content": system_prompt}]
        groq_messages.append({"role": "user", "content": last_user_msg})

        return client.chat.completions.create(
            model=model,
            messages=groq_messages,
            stream=stream,
            temperature=0.7,
            max_tokens=4096
        )

# ============ 4. DB HELPERS ============
def save_message(chat_id: str, user_id: str, role: str, content: str, file_meta: Any, client_msg_id: str, supabase):
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
