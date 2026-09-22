import base64,mimetypes
from typing import Any,Dict,List,Optional
from groq import Groq
from core.config import settings

class ModelRouter:
    def __init__(self,agent=None):
        self.client=Groq(api_key=settings.groq_api_key,timeout=settings.request_timeout_seconds)
        self.agent=agent
        self.fast_model=settings.groq_fast_model
        self.general_model=settings.groq_general_model
        self.reasoning_model=settings.groq_reasoning_model
        self.code_model=getattr(settings,"groq_code_model",self.general_model)
        self.vision_model=settings.groq_vision_model

    def select_model(self,text:str="",has_image:bool=False,mode:str="normal")->str:
        q=(text or "").lower()
        if has_image:return self.vision_model
        if mode in ("reasoning","deep_research"):return self.reasoning_model
        if mode=="code" or any(x in q for x in ("code","function","debug","algorithm","python","javascript","program")):
            return self.code_model
        if len(q)<50 and any(x in q.split() for x in ("hi","hello","thanks","ok","yes","no")):
            return self.fast_model
        return self.general_model

    def _image_content(self,text:str,file_meta:Dict[str,Any]):
        path=file_meta.get("temp_path")
        if not path:return text
        mime,_=mimetypes.guess_type(file_meta.get("name",""))
        if mime not in ("image/png","image/jpeg"):mime="image/jpeg"
        with open(path,"rb") as f:
            data=base64.b64encode(f.read()).decode()
        return [
            {"type":"text","text":text},
            {"type":"image_url","image_url":{"url":f"data:{mime};base64,{data}"}}
        ]

    def build_messages(self,messages:List[Dict[str,Any]],question:str,agent_result:str="",file_meta:Optional[Dict[str,Any]]=None)->List[Dict[str,Any]]:
        system=(
            "You are Brain 3.0 by B.CORP. "
            "Answer the user's actual question directly. "
            "Use provided research or tool results as evidence. "
            "Do not reveal private chain-of-thought, internal tool calls, or hidden reasoning. "
            "If information is uncertain, state the uncertainty."
        )
        result=[{"role":"system","content":system}]
        for message in messages[:-1]:
            role=message.get("role")
            content=message.get("content","")
            if role in ("user","assistant","system"):
                result.append({"role":role,"content":content})
        content=question
        if agent_result:
            content=f"User Query:\n{question}\n\nResearch/Agent Results:\n{agent_result}"
        if file_meta and file_meta.get("type") in (".png",".jpg",".jpeg"):
            content=self._image_content(content,file_meta)
        result.append({"role":"user","content":content})
        return result

    def route(self,messages:List[Dict[str,Any]],uid:str=None,cid:str=None,file_meta:Optional[Dict[str,Any]]=None,stream:bool=False,force_agent:bool=False,last_user_msg:str="",mode:str="normal"):
        agent_result=""
        if force_agent and self.agent:
            try:
                result=self.agent.run(last_user_msg,messages,file_meta,cid)
                agent_result=result.get("answer","") if isinstance(result,dict) else str(result)
            except Exception:
                agent_result=""

        has_image=bool(file_meta and file_meta.get("type") in (".png",".jpg",".jpeg"))
        model=self.select_model(last_user_msg,has_image,mode)
        prompt=self.build_messages(messages,last_user_msg,agent_result,file_meta)
        args={"model":model,"messages":prompt,"temperature":0.7,"max_completion_tokens":4096}
        if stream:
            args["stream"]=True
        return self.client.chat.completions.create(**args)