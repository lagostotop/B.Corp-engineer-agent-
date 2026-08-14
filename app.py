from flask import Flask,render_template,request,jsonify,Response,stream_with_context,abort,g,send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename
import os,re,io,traceback,json,uuid,base64,logging,threading,time,warnings
from datetime import datetime,timezone
from groq import Groq
from tavily import TavilyClient
from config import config
from supabase import create_client,Client
from PIL import Image,ImageOps,ImageFile
from PIL.Image import DecompressionBombError,DecompressionBombWarning
import jwt
from jwt import PyJWK
import requests

app=Flask(__name__,static_folder="static",template_folder="templates")

# FIX 1: Use config.ALLOWED_ORIGINS not os.getenv
ALLOWED_ORIGINS=config.ALLOWED_ORIGINS
if not ALLOWED_ORIGINS:raise RuntimeError("ALLOWED_ORIGINS must be configured")
origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()]
if "*" in origins:raise RuntimeError("Wildcard CORS not allowed")
CORS(app,resources={r"/api/*":{"origins":origins}})
app.config["MAX_CONTENT_LENGTH"]=20*1024*1024

GENERATION_TIMEOUT=120
MAX_EXTRACTED_TEXT=100_000
MAX_CHUNKS=100
CHUNK_SIZE,CHUNK_OVERLAP=1000,200
MAX_IMAGE_JPEG=3*1024*1024
MAX_IMAGE_PIXELS=20_000_000
MAX_TOOL_CONTEXT_CHARS=8000
MAX_PLAN_STEPS=3
MAX_QUERY_LENGTH=200
MAX_SAVED_RESPONSE_CHARS=50000
MAX_PER_FILE_BYTES=10*1024*1024
Image.MAX_IMAGE_PIXELS=MAX_IMAGE_PIXELS
warnings.simplefilter("error",DecompressionBombWarning)

logging.basicConfig(level=logging.INFO,format='[%(asctime)s] [%(request_id)s] %(levelname)s: %(message)s')
logger=logging.getLogger(__name__)
logger.addFilter(type("F",(logging.Filter,),{"filter":lambda s,r:setattr(r,"request_id",getattr(r,"request_id","-")) or True})())

print("=== BRAIN 3.0 v5.5.1 RENDER SAFE ===")

# BUG FIX: Optional magic for Render
try:
    import magic
    MAGIC_AVAILABLE=True
except ImportError:
    MAGIC_AVAILABLE=False
    logger.warning("python-magic not available. Skipping MIME validation")

JWKS_CACHE={"keys":None,"last_fetch":0}
JWKS_LOCK=threading.Lock()
ALLOWED_JWT_ALGS={"ES256","RS256"}

def get_supabase_jwks(force_refresh=False):
    global JWKS_CACHE
    with JWKS_LOCK:
        now=time.time()
        if not force_refresh and JWKS_CACHE["keys"] and now-JWKS_CACHE["last_fetch"]<3600:return JWKS_CACHE["keys"]
        res=requests.get(f"{config.SUPABASE_URL}/auth/v1/.well-known/jwks.json",timeout=5)
        res.raise_for_status()
        keys=res.json().get("keys",[])
        if not keys:raise RuntimeError("JWKS empty")
        JWKS_CACHE={"keys":keys,"last_fetch":now}
        return keys

def verify_supabase_token(token):
    if not token:raise jwt.InvalidTokenError("Missing token")
    jwks=get_supabase_jwks()
    header=jwt.get_unverified_header(token)
    kid,alg=header.get("kid"),header.get("alg")
    if not kid or not alg or alg not in ALLOWED_JWT_ALGS:raise jwt.InvalidTokenError("Bad header")
    key_data=next((k for k in jwks if k.get("kid")==kid),None)
    if not key_data:jwks=get_supabase_jwks(True);key_data=next((k for k in jwks if k.get("kid")==kid),None)
    if not key_data:raise jwt.InvalidTokenError("Key not found")
    key=PyJWK(key_data,algorithm_name=alg).key
    return jwt.decode(token,key,algorithms=[alg],audience="authenticated",options={"verify_signature":True,"verify_exp":True,"verify_aud":True})

def get_verified_payload():
    if hasattr(g,"_jwt_payload"):return g._jwt_payload
    auth=request.headers.get("Authorization","")
    if not auth.startswith("Bearer "):abort(401,"Missing token")
    try:payload=verify_supabase_token(auth[7:]);g._jwt_payload=payload;return payload
    except jwt.ExpiredSignatureError:abort(401,"Token expired")
    except jwt.InvalidTokenError:abort(401,"Invalid token")

def get_user_id():return str(get_verified_payload().get("sub") or abort(401,"Invalid token"))

def get_user_rate_key():
    try:uid=get_verified_payload().get("sub","anon")
    except:uid="anon"
    return f"{uid}:{get_remote_address()}"

limiter=Limiter(key_func=get_user_rate_key,app=app,default_limits=["200 per minute"])
client=Groq(api_key=config.GROQ_API_KEY,timeout=GENERATION_TIMEOUT)
tavily=TavilyClient(api_key=config.TAVILY_API_KEY)
supabase=create_client(config.SUPABASE_URL,config.SUPABASE_KEY)

def get_embedding(text):
    """Use Groq nomic-embed-text instead of torch"""
    try:
        res=client.embeddings.create(model="nomic-embed-text",input=text)
        return res.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return [0.0]*768

GROQ_GENERAL_MODEL=config.GROQ_GENERAL_MODEL
GROQ_VISION_MODEL=config.GROQ_VISION_MODEL
ALLOWED_EXTENSIONS={"pdf","txt","py","js","ts","jsx","tsx","html","css","md","csv","json","png","jpg","jpeg","docx"}
IMAGE_EXTENSIONS={"png","jpg","jpeg"}
BINARY_EXTENSIONS={"pdf","docx","png","jpg","jpeg"}
TEXT_EXTENSIONS={"txt","py","js","ts","jsx","tsx","html","css","md","csv","json"}
ALLOWED_ROLES={"user","assistant"}
SYSTEM_PROMPT="You are Brain 3.0, AI OS for CEO of B.CORP. You have tools: search, recall_memories, search_documents. Use them when user asks about current info or files. Always cite [SOURCE 1]. End with ### Confidence ### Sources"
TOOL_MAP={"search":"web_search","recall":"recall_memories","doc_search":"search_documents"}
ALLOWED_ACTIONS=set(TOOL_MAP.keys())

def create_chat(user_id,first_message=""):
    title=(first_message or "New Chat").strip()[:80]
    res=supabase.table("chats").insert({"user_id":user_id,"title":title,"created_at":datetime.now(timezone.utc).isoformat()}).execute()
    if not res.data:abort(500,"Failed to create chat")
    return str(res.data[0]["id"])

def get_owned_chat(chat_id,user_id):
    res=supabase.table("chats").select("id").eq("id",chat_id).eq("user_id",user_id).maybe_single().execute()
    if not res.data:abort(403,"Access denied")
    return True

def check_idempotency(client_msg_id,user_id):
    if not client_msg_id:return None
    res=supabase.table("messages").select("*").eq("user_id",user_id).eq("client_msg_id",client_msg_id).maybe_single().execute()
    return res.data

def save_message(chat_id,user_id,role,content,attachment_meta=None,client_msg_id=None,status="completed"):
    get_owned_chat(chat_id,user_id)
    data={"chat_id":chat_id,"user_id":user_id,"role":role if role in ALLOWED_ROLES else "user","content":content,"status":status}
    if attachment_meta:data["attachment"]=attachment_meta
    if client_msg_id:data["client_msg_id"]=client_msg_id
    try:supabase.table("messages").insert(data).execute()
    except Exception as e:
        if getattr(e,'code','')=='23505':abort(409,"Duplicate request")
        raise

def load_messages(chat_id,user_id):
    get_owned_chat(chat_id,user_id)
    msgs=supabase.table("messages").select("*").eq("chat_id",chat_id).order("created_at",desc=True).limit(20).execute().data or []
    return list(reversed([m for m in msgs if m["role"] in ALLOWED_ROLES]))

def needs_tools(q,has_files):
    q=q.lower()
    return has_files or any(t in q for t in ["latest","news","research","current","today","my","document","file"])

def generate_plan(task):
    if not task:return[]
    try:
        res=client.chat.completions.create(model=GROQ_GENERAL_MODEL,messages=[{"role":"system","content":"Return JSON only: {\"steps\":[{\"action\":\"search\"|\"recall\"|\"doc_search\",\"query\":\"string\"}]}"},{"role":"user","content":f'Task:{task}'}],response_format={"type":"json_object"},max_tokens=400,timeout=10)
        steps=json.loads(res.choices[0].message.content).get("steps",[])[:MAX_PLAN_STEPS]
        seen=set();out=[]
        for s in steps:
            if isinstance(s,dict) and s.get("action") in ALLOWED_ACTIONS:
                q=s["query"].strip()[:MAX_QUERY_LENGTH]
                if q and q not in seen:seen.add(q);out.append({"action":s["action"],"query":q})
        return out
    except:return[]

def call_tool(tool_name,args,user_id,chat_id):
    q=args.get("query","").strip()[:MAX_QUERY_LENGTH]
    if not q:return{"success":False,"error":"Empty query"}
    if tool_name=="web_search":
        try:res=tavily.search(query=q,max_results=5,search_depth="advanced",timeout=15);return{"success":True,"results":[{"title":r["title"],"content":r["content"][:400],"url":r["url"]}for r in res["results"]]}
        except:return{"success":False,"error":"Search failed"}
    if tool_name=="recall_memories":
        emb=get_embedding(q)
        res=supabase.rpc("match_embeddings",{"query_embedding":emb,"match_count":5,"filter_user_id":user_id}).execute()
        return{"success":True,"text":"\n".join([r["content"]for r in res.data if r.get("category")!="file"])}
    if tool_name=="search_documents":
        emb=get_embedding(q)
        res=supabase.rpc("match_document_embeddings",{"query_embedding":emb,"filter_user_id":user_id,"filter_chat_id":chat_id,"match_count":5,"similarity_threshold":0.7}).execute()
        if not res.data:return{"success":False,"error":"No match"}
        return{"success":True,"text":"\n".join([r["content"]for r in res.data])}
    return{"success":False,"error":"Tool not found"}

def process_image(b):
    try:
        img=Image.open(io.BytesIO(b))
        if img.width*img.height>MAX_IMAGE_PIXELS:abort(413,"Image too large")
        img=ImageOps.exif_transpose(img).convert("RGB");img.thumbnail((1024,1024))
        buf=io.BytesIO();img.save(buf,format="JPEG",quality=85,optimize=True)
        if buf.tell()>MAX_IMAGE_JPEG:abort(413,"Image too large")
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except DecompressionBombError:abort(413,"Image too large")
    except:abort(400,"Invalid image")

def validate_file_signature(b,ext):
    if not MAGIC_AVAILABLE:return
    if ext in BINARY_EXTENSIONS:
        mime=magic.from_buffer(b[:2048],mime=True)
        exp={"pdf":"application/pdf","docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document","png":"image/png","jpg":"image/jpeg","jpeg":"image/jpeg"}
        if exp.get(ext) and mime!=exp[ext]:abort(400,"Signature mismatch")
        if ext=="docx":
            import zipfile
            z=zipfile.ZipFile(io.BytesIO(b))
            if sum(i.file_size for i in z.infolist())>100*1024*1024:abort(413,"DOCX too large")
            if len(z.infolist())>1000:abort(413,"DOCX entries too many")
    elif ext in TEXT_EXTENSIONS:
        try:b.decode('utf-8')
        except:abort(400,"Bad UTF8")

def process_uploaded_file(file,user_id,chat_id):
    fn=secure_filename(file.filename)
    if'.'not in fn:abort(400,"No extension")
    ext=fn.rsplit(".",1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:abort(400,"Type not allowed")
    b=file.read()
    if len(b)>MAX_PER_FILE_BYTES:abort(413,"File too large")
    validate_file_signature(b,ext)
    if ext in IMAGE_EXTENSIONS:return f"\n\n[IMAGE:{fn}]",True,process_image(b),{"type":"image","name":fn}
    start=time.time();text=""
    if ext=="pdf":
        import PyPDF2
        pdf=PyPDF2.PdfReader(io.BytesIO(b))
        for p in pdf.pages[:50]:
            text+=p.extract_text()or""
            if len(text)>MAX_EXTRACTED_TEXT or time.time()-start>10:break
    elif ext=="docx":
        from docx import Document
        for p in Document(io.BytesIO(b)).paragraphs:
            text+=p.text+"\n"
            if len(text)>MAX_EXTRACTED_TEXT or time.time()-start>10:break
    else:text=b.decode("utf-8",errors="replace")
    text=text[:MAX_EXTRACTED_TEXT]
    if not text.strip():abort(400,"Empty file")
    chunks=[text[i:i+CHUNK_SIZE]for i in range(0,len(text),CHUNK_SIZE-CHUNK_OVERLAP)][:MAX_CHUNKS]
    doc_id=str(uuid.uuid4())
    supabase.table("documents").insert({"id":doc_id,"user_id":user_id,"chat_id":chat_id,"filename":fn,"status":"processing","started_at":datetime.now(timezone.utc).isoformat()}).execute()
    def worker():
        try:
            embs=[get_embedding(c) for c in chunks]
            rows=[{"user_id":user_id,"chat_id":chat_id,"document_id":doc_id,"category":"file","content":c,"embedding":e,"source":f"{fn}#chunk{i}"}for i,(c,e)in enumerate(zip(chunks,embs))]
            supabase.table("embeddings").insert(rows).execute()
            supabase.table("documents").update({"status":"done","completed_at":datetime.now(timezone.utc).isoformat()}).eq("id",doc_id).execute()
        except Exception:supabase.table("documents").update({"status":"failed"}).eq("id",doc_id).execute()
    threading.Thread(target=worker,daemon=True).start()
    return f"\n\n[FILE:{fn} {len(chunks)}chunks]",False,None,{"type":"file","name":fn,"doc_id":doc_id}

@app.route("/api/chats",methods=["GET"])
@limiter.limit("30 per minute")
def get_chats():
    uid=get_user_id()
    res=supabase.table("chats").select("*").eq("user_id",uid).order("created_at",desc=True).limit(50).execute()
    return jsonify(res.data or [])

@app.route("/api/chat/<chat_id>",methods=["GET"])
@limiter.limit("30 per minute")
def get_chat(chat_id):
    return jsonify(load_messages(chat_id,get_user_id()))

@app.route("/api/chat/delete",methods=["POST"]) # FIXED INDENTATION
@limiter.limit("10 per minute")
def delete_chat():
    uid=get_user_id()
    cid=(request.get_json()or{}).get("chat_id")
    if not cid:abort(400)
    get_owned_chat(cid,uid)
    supabase.table("messages").delete().eq("chat_id",cid).eq("user_id",uid).execute()
    supabase.table("chats").delete().eq("id",cid).eq("user_id",uid).execute()
    return jsonify({"success":True})

@app.route("/health") # FIX 2: Health check for Render
def health():
    return jsonify({"status":"ok"})

@app.route("/sw.js")
def sw():
    return send_from_directory("static","sw.js",mimetype="application/javascript")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat",methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    req_id=str(uuid.uuid4())[:8]
    log=logging.LoggerAdapter(logger,{"request_id":req_id})
    uid=get_user_id();q=request.form.get("question","").strip();cid=request.form.get("chat_id");file=request.files.get("file");cmsg=request.form.get("client_msg_id")
    if not cmsg:abort(400,"client_msg_id required")
    if check_idempotency(cmsg,uid):return jsonify({"error":"Duplicate"}),409
    if not q and not file:abort(400,"Empty")
    if not cid or cid=="null":cid=create_chat(uid,q)
    else:get_owned_chat(cid,uid)
    attach=None;fcontent="";has_img=False;img_url=None
    if file:fcontent,has_img,img_url,attach=process_uploaded_file(file,uid,cid);q+=fcontent
    hist=load_messages(cid,uid)
    save_message(cid,uid,"user",q,attach,cmsg)

    # FIX 3: AGENT LOOP - ACTUALLY CALL TOOLS
    context_blocks=[]
    if needs_tools(q,has_img):
        plan=generate_plan(q)
        for step in plan:
            tool_res=call_tool(step["action"],{"query":step["query"]},uid,cid)
            if tool_res.get("success"):
                if "results" in tool_res: # web_search
                    context_blocks.extend([f"[SOURCE] {r['title']}: {r['content']}" for r in tool_res["results"]])
                else: # recall/doc
                    context_blocks.append(tool_res["text"])

    context_str="\n".join(context_blocks)[:MAX_TOOL_CONTEXT_CHARS]

    def stream():
        full="";start=time.time()
        try:
            model=GROQ_VISION_MODEL if has_img else GROQ_GENERAL_MODEL
            msgs=[{"role":"system","content":SYSTEM_PROMPT}]
            if context_str:msgs.append({"role":"system","content":f"CONTEXT:\n{context_str}"})
            msgs+=[{"role":m["role"],"content":m["content"]}for m in hist]
            um={"role":"user","content":q}
            if has_img:um["content"]=[{"type":"text","text":q},{"type":"image_url","image_url":{"url":img_url}}]
            msgs.append(um)
            # FIX 4: Add extra_headers for Groq 0.13.1
            for chunk in client.chat.completions.create(model=model,messages=msgs,stream=True,timeout=GENERATION_TIMEOUT,extra_headers={"HTTP-Referer": "https://b-corp.ai"}):
                if time.time()-start>GENERATION_TIMEOUT:break
                if d:=chunk.choices[0].delta.content:full+=d;yield f"event: token\ndata: {json.dumps({'text':d})}\n\n"
            yield f"event: done\ndata: {json.dumps({'chat_id':cid})}\n\n"
        except Exception as e:log.exception("Stream");yield f"event: error\ndata: {json.dumps({'message':'Server error'})}\n\n"
        finally:
            if full:save_message(cid,uid,"assistant",full[:MAX_SAVED_RESPONSE_CHARS])
    return Response(stream_with_context(stream()),mimetype="text/event-stream",headers={"Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})

if __name__=="__main__":app.run(host="0.0.0.0",port=config.PORT)
