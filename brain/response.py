import json
from typing import Any,Dict,Iterable

def sse_event(event:str,data:Any)->str:
    return f"event: {event}\ndata: {json.dumps(data,ensure_ascii=False)}\n\n"

def token_event(text:str)->str:
    return sse_event("token",{"text":text})

def error_event(message:str,request_id:str="")->str:
    data={"message":message}
    if request_id:data["request_id"]=request_id
    return sse_event("error",data)

def done_event(chat_id:str)->str:
    return sse_event("done",{"chat_id":chat_id})

def chat_id_event(chat_id:str)->str:
    return sse_event("chat_id",{"chat_id":chat_id})

def collect_stream(stream:Iterable[Any])->str:
    parts=[]
    for chunk in stream:
        choices=getattr(chunk,"choices",None)
        if not choices:continue
        delta=getattr(choices[0],"delta",None)
        text=getattr(delta,"content",None)
        if text:parts.append(text)
    return "".join(parts)

def response_payload(answer:str,chat_id:str=None,metadata:Dict[str,Any]=None)->Dict[str,Any]:
    data={"answer":answer}
    if chat_id:data["chat_id"]=chat_id
    if metadata:data["metadata"]=metadata
    return data