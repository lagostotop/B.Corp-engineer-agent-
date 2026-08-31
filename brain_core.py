import os,json,re,base64,uuid,logging,time,mimetypes,hashlib
from datetime import datetime,timezone
from typing import List,Dict,Any
from groq import Groq
from tools.tavily import search_web

logger=logging.getLogger(__name__)

GENERATION_TIMEOUT=120
MAX_UPLOAD_BYTES=10*1024*1024
MAX_PDF_PAGES=50
MAX_EXTRACTED_TEXT=100000
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
MAX_CHUNKS=100
EMBED_MODEL=os.getenv("EMBED_MODEL","text-embedding-3-small")

TEXT_EXTENSIONS={".txt",".md",".py",".js",".ts",".jsx",".tsx",".html",".css",".csv",".json"}
IMAGE_EXTENSIONS={".png",".jpg",".jpeg"}

client=Groq(api_key=os.getenv("GROQ_API_KEY"),timeout=GENERATION_TIMEOUT)

# Redis cache setup
redis_client = None
try:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        import redis
        redis_client = redis.from_url(redis_url)
        redis_client.ping()
        logger.info("✅ Redis connected")
except Exception as e:
    logger.warning(f"⚠️ Redis not available: {e}")

def get_cache_key(text: str, model: str) -> str:
    return f"llm_cache:{model}:{hashlib.md5(text.encode()).hexdigest()}"

def cached_llm_call(model: str, messages: list, **kwargs):
    if not redis_client:
        return client.chat.completions.create(model=model, messages=messages, **kwargs)
    
    cache_key = get_cache_key(json.dumps(messages), model)
    cached = redis_client.get(cache_key)
    if cached:
        logger.info(f"✅ Cache hit for {model}")
        return json.loads(cached)
    
    response = client.chat.completions.create(model=model, messages=messages, **kwargs)
    redis_client.setex(cache_key, 3600, json.dumps(response.model_dump()))
    return response

def should_use_agent(question:str)->bool:
    q=(question or "").lower()
    triggers=("research","deep research","investigate","compare","analyze","analyse","find the best","look into","step by step","current market","latest news","latest price","current price","recent news","code","debug","function")
    return any(x in q for x in triggers)

def get_last_user_message(messages):
    for message in reversed(messages or []):
        if message.get("role")=="user":
            return message.get("content","") or ""
    return ""

def get_embedding(text:str)->List[float]:
    if not text or not text.strip():
        raise ValueError("Empty text for embedding")

    if os.getenv("OPENAI_API_KEY"):
        from openai import OpenAI
        api=OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        result=api.embeddings.create(model=EMBED_MODEL,input=text)
        return result.data[0].embedding

    if os.getenv("JINA_API_KEY"):
        import requests
        response=requests.post(
            "https://api.jina.ai/v1/embeddings",
            headers={"Authorization":f"Bearer {os.getenv('JINA_API_KEY')}"},
            json={"model":"jina-embeddings-v2-base-en","input":[text]},
            timeout=30
        )
        response.raise_for_status()
        embedding=response.json()["data"][0]["embedding"]
        if len(embedding)!=1536:
            raise ValueError(f"Embedding dimension {len(embedding)} != 1536")
        return embedding

    # Fallback for demo
    logger.warning("No embedding provider, using fallback")
    import numpy as np
    np.random.seed(hash(text) % 2**32)
    return np.random.randn(1536).tolist()

def get_file_type(path:str)->str:
    ext=os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTENSIONS:return "text"
    if ext==".pdf":return "pdf"
    if ext==".docx":return "docx"
    if ext in IMAGE_EXTENSIONS:return "image"
    return "unknown"

def extract_text_from_file(path:str)->str:
    try:
        if not os.path.exists(path):return "[File not found]"
        if os.path.getsize(path)>MAX_UPLOAD_BYTES:return "[File too large. Max 10MB]"

        file_type=get_file_type(path)

        if file_type=="text":
            with open(path,"r",encoding="utf-8",errors="ignore") as f:
                return f.read(MAX_EXTRACTED_TEXT)

        if file_type=="pdf":
            import PyPDF2
            reader=PyPDF2.PdfReader(path)
            text="\n".join(p.extract_text() or "" for p in reader.pages[:MAX_PDF_PAGES])
            return text[:MAX_EXTRACTED_TEXT]

        if file_type=="docx":
            import docx
            document=docx.Document(path)
            text="\n".join(p.text for p in document.paragraphs)
            return text[:MAX_EXTRACTED_TEXT]

        if file_type=="image":return ""
        return f"[Unsupported file type: {os.path.basename(path)}]"

    except Exception as error:
        logger.exception("File extraction failed")
        return f"[Error reading file: {error}]"

def chunk_text(text:str,size:int=CHUNK_SIZE,overlap:int=CHUNK_OVERLAP)->List[str]:
    if not text:return []
    if overlap>=size:overlap=size//4

    chunks=[]
    start=0

    while start<len(text):
        end=min(start+size,len(text))
        chunks.append(text[start:end])
        if end>=len(text):break
        start=end-overlap

    return chunks

def save_to_rag(chat_id:str,uid:str,filepath:str,supabase)->Dict[str,Any]:
    text=extract_text_from_file(filepath)

    if not text or text.startswith("["):
        logger.info("RAG skipped: %s",filepath)
        return {"total":0,"saved":0,"error":text}

    chunks=chunk_text(text)[:MAX_CHUNKS]
    saved=0
    last_error=None

    for index,chunk in enumerate(chunks):
        try:
            embedding=get_embedding(chunk)

            supabase.table("documents").insert({
                "id":str(uuid.uuid4()),
                "chat_id":chat_id,
                "user_id":uid,
                "content":chunk,
                "embedding":embedding,
                "metadata":{"chunk":index,"file":os.path.basename(filepath)}
            }).execute()

            saved+=1

        except Exception as error:
            last_error=str(error)
            logger.exception("RAG insert failed for chunk %d",index)

    logger.info("RAG saved %d/%d chunks for chat %s",saved,len(chunks),chat_id)
    return {"total":len(chunks),"saved":saved,"error":last_error}

def search_rag(query:str,uid:str,chat_id:str,supabase,top_k:int=3)->str:
    if not query or not query.strip():return ""

    try:
        embedding=get_embedding(query)
        result=supabase.rpc("match_documents",{
            "query_embedding":embedding,
            "match_count":top_k,
            "filter_user":uid,
            "filter_chat":chat_id
        }).execute()

        if result.data:
            return "\n\n".join(
                f"[DOC {i+1}] {doc.get('content','')[:1000]}"
                for i,doc in enumerate(result.data)
            )

    except Exception as error:
        logger.warning("Vector search failed: %s",error)

    try:
        result=(
            supabase.table("documents")
            .select("content")
            .eq("user_id",uid)
            .eq("chat_id",chat_id)
            .ilike("content",f"%{query[:50]}%")
            .limit(top_k)
            .execute()
        )

        return "\n\n".join(
            f"[DOC {i+1}] {doc.get('content','')[:1000]}"
            for i,doc in enumerate(result.data or [])
        )

    except Exception:
        return ""

def save_memory(user_id:str,key:str,value:str,supabase):
    try:
        supabase.table("brain30_memory").upsert({
            "user_id":user_id,
            "key":key.lower()[:100],
            "value":value[:2000],
            "updated_at":datetime.now(timezone.utc).isoformat()
        }).execute()
        return f"Saved memory: {key} = {value}"
    except Exception as error:
        logger.exception("Memory save failed")
        return f"Memory save failed: {error}"

def get_memory(user_id:str,query:str,supabase):
    try:
        result=(
            supabase.table("brain30_memory")
            .select("key,value")
            .eq("user_id",user_id)
            .ilike("key",f"%{query.lower()}%")
            .limit(5)
            .execute()
        )
        return [f"{x['key']}: {x['value']}" for x in (result.data or [])]
    except Exception:
        return []

def deep_research(topic:str,supabase,uid:str,chat_id:str)->str:
    try:
        general_model=os.getenv("GROQ_GENERAL_MODEL","llama-3.3-70b-versatile")
        reasoning_model=os.getenv("GROQ_REASONING_MODEL","llama-3.3-70b-versatile")

        plan_response = cached_llm_call(
            model=general_model,
            messages=[
                {"role":"system","content":"Break the topic into 4 specific research questions. Return ONLY JSON with a questions array."},
                {"role":"user","content":topic}
            ],
            temperature=0.3,
            response_format={"type":"json_object"}
        )
        
        if isinstance(plan_response, dict):
            plan_content = plan_response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        else:
            plan_content = plan_response.choices[0].message.content

        questions=json.loads(plan_content).get("questions",[topic])[:4]
        findings=[]
        sources=[]

        for question in questions:
            web_result=search_web(question)
            sources.extend(re.findall(r"Source:\s*(https?://\S+)",web_result))
            findings.append({
                "question":question,
                "web":web_result,
                "documents":search_rag(question,uid,chat_id,supabase)
            })
            time.sleep(0.3)

        extraction_response = cached_llm_call(
            model=general_model,
            messages=[
                {"role":"system","content":"Extract 5-7 important factual points from the research. Be concise."},
                {"role":"user","content":json.dumps(findings)}
            ],
            temperature=0.2
        )

        if isinstance(extraction_response, dict):
            key_points = extraction_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            key_points = extraction_response.choices[0].message.content

        unique_sources=list(dict.fromkeys(sources))
        source_list="\n".join(f"[{i+1}] {url}" for i,url in enumerate(unique_sources))

        final_response = cached_llm_call(
            model=reasoning_model,
            messages=[
                {"role":"system","content":"Write a comprehensive research report with Executive Summary, Key Findings, Analysis and Conclusion. Cite sources as [1], [2] and add a Sources section."},
                {"role":"user","content":f"Topic:\n{topic}\n\nKey Points:\n{key_points}\n\nRaw Data:\n{json.dumps(findings)}\n\nSources:\n{source_list}"}
            ],
            temperature=0.4,
            max_completion_tokens=2000
        )

        if isinstance(final_response, dict):
            final_content = final_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            final_content = final_response.choices[0].message.content

        return f"# 🔬 Deep Research: {topic}\n\n{final_content}"

    except Exception as error:
        logger.exception("Deep research failed")
        return f"Research failed: {error}"

AVAILABLE_TOOLS=[
    {"type":"function","function":{
        "name":"web_search",
        "description":"Search the web for current information.",
        "parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}
    }},
    {"type":"function","function":{
        "name":"search_documents",
        "description":"Search uploaded files.",
        "parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}
    }},
    {"type":"function","function":{
        "name":"deep_research",
        "description":"Perform comprehensive research.",
        "parameters":{"type":"object","properties":{"topic":{"type":"string"}},"required":["topic"]}
    }},
    {"type":"function","function":{
        "name":"save_memory",
        "description":"Save an important user fact.",
        "parameters":{
            "type":"object",
            "properties":{"key":{"type":"string"},"value":{"type":"string"}},
            "required":["key","value"]
        }
    }},
    {"type":"function","function":{
        "name":"get_memory",
        "description":"Recall saved user information.",
        "parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}
    }}
]

class AgentEngine:
    def __init__(self,supabase_client,uid):
        self.supabase=supabase_client
        self.uid=uid
        self.max_steps=6

    def run(self,goal,messages,file_meta,chat_id):
        model=os.getenv("GROQ_GENERAL_MODEL","llama-3.3-70b-versatile")
        agent_messages=[{"role":"system","content":"You are Brain 3.0 by B.CORP. Use tools when necessary. Never reveal private chain-of-thought."}]
        agent_messages.extend(messages)
        steps=[]

        for _ in range(self.max_steps):
            result=client.chat.completions.create(
                model=model,
                messages=agent_messages,
                tools=AVAILABLE_TOOLS,
                tool_choice="auto",
                temperature=0.2
            )

            message=result.choices[0].message
            tool_calls=message.tool_calls or []

            steps.append({
                "tool_calls":[
                    {"name":c.function.name,"arguments":c.function.arguments}
                    for c in tool_calls
                ] or None
            })

            agent_messages.append(message.model_dump(exclude_none=True))

            if not tool_calls:
                self._log_trace(goal,steps)
                return {"answer":message.content or "","steps":steps}

            for call in tool_calls:
                try:
                    args=json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args={}

                result_text=self._execute_tool(call.function.name,args,file_meta,chat_id)
                agent_messages.append({
                    "role":"tool",
                    "tool_call_id":call.id,
                    "name":call.function.name,
                    "content":str(result_text)[:12000]
                })

        self._log_trace(goal,steps)
        return {"answer":"I reached the maximum number of agent steps.","steps":steps}

    def _execute_tool(self,name,args,file_meta,chat_id):
        if name=="web_search":
            return search_web(args.get("query",""))
        if name=="search_documents":
            return search_rag(args.get("query",""), self.uid, chat_id, self.supabase)
        if name=="deep_research":
            return deep_research(args.get("topic",""), self.supabase, self.uid, chat_id)
        if name=="save_memory":
            return save_memory(self.uid, args.get("key",""), args.get("value",""), self.supabase)
        if name=="get_memory":
            memory=get_memory(self.uid, args.get("query",""), self.supabase)
            return "Memory: "+" | ".join(memory) if memory else "No memory found"
        return "Tool not found"

    def _log_trace(self,goal,steps):
        try:
            self.supabase.table("inference_logs").insert({
                "user_id":self.uid,
                "goal":goal,
                "steps":json.dumps(steps),
                "created_at":datetime.now(timezone.utc).isoformat()
            }).execute()
        except Exception as error:
            logger.error("Log error: %s",error)

class ModelRouter:
    def __init__(self,supabase_client):
        self.supabase=supabase_client
        self.FAST_MODEL=os.getenv("GROQ_FAST_MODEL","llama-3.1-8b-instant")
        self.GENERAL_MODEL=os.getenv("GROQ_GENERAL_MODEL","llama-3.3-70b-versatile")
        self.REASONING_MODEL=os.getenv("GROQ_REASONING_MODEL","llama-3.3-70b-versatile")
        self.CODE_MODEL=os.getenv("GROQ_CODE_MODEL","llama-3.3-70b-versatile")
        self.VISION_MODEL=os.getenv("GROQ_VISION_MODEL","llama-3.2-11b-vision-preview")

    def _select_model(self,text,has_image):
        x=(text or "").lower()
        if has_image: return self.VISION_MODEL
        if len(x)<50 and any(word in x.split() for word in ("hi","hello","thanks","ok","yes","no")):
            return self.FAST_MODEL
        if any(keyword in x for keyword in ("code","function","debug","algorithm","program","python","javascript")):
            return self.CODE_MODEL
        return self.GENERAL_MODEL

    def route(self, messages, uid, cid, file_meta, stream=False, force_agent=False, last_user_msg=""):
        has_image=bool(file_meta and file_meta.get("type") in IMAGE_EXTENSIONS)
        agent_result={"answer":""}

        if force_agent:
            agent_result=AgentEngine(self.supabase,uid).run(last_user_msg, messages, file_meta, cid)

        model=self._select_model(last_user_msg,has_image)

        system_prompt=(
            "You are Brain 3.0 by B.CORP. "
            "Answer the user's actual question directly first. "
            "Use agent research as evidence. "
            "Cite sources as [1][2]. "
            "If research is insufficient, say so. "
            "Never mention internal tool calls or private reasoning."
        )

        groq_messages=[{"role":"system","content":system_prompt}]
        groq_messages.extend(m for m in messages[:-1] if m.get("role") in ("user","assistant","system"))

        user_content=(
            f"User Query: {last_user_msg}\n\nAgent Results:\n{agent_result['answer']}"
            if agent_result["answer"]
            else last_user_msg
        )

        if has_image:
            mime_type,_=mimetypes.guess_type(file_meta["name"])
            if mime_type not in {"image/png","image/jpeg"}:
                mime_type="image/jpeg"
            with open(file_meta["temp_path"],"rb") as f:
                b64=base64.b64encode(f.read()).decode()
            user_content=[
                {"type":"text","text":user_content},
                {"type":"image_url","image_url":{"url":f"data:{mime_type};base64,{b64}"}}
            ]

        groq_messages.append({"role":"user","content":user_content})

        if stream:
            return client.chat.completions.create(
                model=model, messages=groq_messages, stream=True,
                temperature=0.7, max_completion_tokens=4096
            )
        else:
            return cached_llm_call(
                model=model, messages=groq_messages,
                temperature=0.7, max_completion_tokens=4096
            )

def save_message(chat_id:str, user_id:str, role:str, content:str, file_meta:Any, client_msg_id:str, supabase)->bool:
    try:
        supabase.table("messages").insert({
            "chat_id":chat_id, "user_id":user_id, "role":role,
            "content":content, "file_meta":file_meta,
            "client_msg_id":client_msg_id,
            "created_at":datetime.now(timezone.utc).isoformat()
        }).execute()
        return True
    except Exception as error:
        logger.exception("save_message error: %s",error)
        return False

def get_chat_history(chat_id:str, user_id:str, supabase)->List[Dict]:
    try:
        result=(
            supabase.table("messages")
            .select("id,role,content,created_at,file_meta")
            .eq("chat_id",chat_id).eq("user_id",user_id)
            .order("created_at").execute()
        )
        return result.data or []
    except Exception as error:
        logger.exception("get_chat_history error: %s",error)
        return []
