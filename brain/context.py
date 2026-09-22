from dataclasses import dataclass,field
from typing import Any,Dict,List,Optional

@dataclass
class BrainContext:
    user_id:str
    chat_id:Optional[str]=None
    mode:str="normal"
    question:str=""
    messages:List[Dict[str,Any]]=field(default_factory=list)
    file_meta:Optional[Dict[str,Any]]=None
    metadata:Dict[str,Any]=field(default_factory=dict)

    @property
    def last_message(self)->str:
        if not self.messages:return ""
        return str(self.messages[-1].get("content",""))

    def add_message(self,role:str,content:str,**extra):
        item={"role":role,"content":content}
        item.update(extra)
        self.messages.append(item)

    def to_dict(self)->Dict[str,Any]:
        return {
            "user_id":self.user_id,
            "chat_id":self.chat_id,
            "mode":self.mode,
            "question":self.question,
            "messages":self.messages,
            "file_meta":self.file_meta,
            "metadata":self.metadata,
        }

def build_context(user_id:str,chat_id:Optional[str]=None,question:str="",messages:Optional[List[Dict[str,Any]]]=None,mode:str="normal",file_meta:Optional[Dict[str,Any]]=None,**metadata)->BrainContext:
    return BrainContext(
        user_id=str(user_id),
        chat_id=str(chat_id) if chat_id else None,
        mode=mode or "normal",
        question=question or "",
        messages=list(messages or []),
        file_meta=file_meta,
        metadata=metadata,
    )