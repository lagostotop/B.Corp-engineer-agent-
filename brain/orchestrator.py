from typing import Any,Dict,Optional
from .context import BrainContext
from .model_router import ModelRouter
from .planner import Planner
from .verifier import Verifier

class BrainOrchestrator:
    def __init__(self,router:Optional[ModelRouter]=None):
        self.router=router or ModelRouter()
        self.planner=Planner()
        self.verifier=Verifier()

    def run(self,context:BrainContext)->Dict[str,Any]:
        question=context.question or context.last_message
        plan=self.planner.plan(question,context.mode)
        use_agent=self.planner.needs_tools(question,context.mode)

        result=self.router.route(
            messages=context.messages,
            uid=context.user_id,
            cid=context.chat_id,
            file_meta=context.file_meta,
            stream=False,
            force_agent=use_agent,
            last_user_msg=question,
            mode=context.mode,
        )

        answer=""
        if isinstance(result,dict):
            choices=result.get("choices",[])
            if choices:
                answer=choices[0].get("message",{}).get("content","")
        else:
            choices=getattr(result,"choices",[])
            if choices:
                answer=getattr(choices[0].message,"content","") or ""

        answer=self.verifier.finalize(answer,question)
        return {
            "answer":answer,
            "plan":plan,
            "verified":bool(answer),
            "used_agent":use_agent,
        }

    def stream(self,context:BrainContext):
        question=context.question or context.last_message
        use_agent=self.planner.needs_tools(question,context.mode)
        return self.router.route(
            messages=context.messages,
            uid=context.user_id,
            cid=context.chat_id,
            file_meta=context.file_meta,
            stream=True,
            force_agent=use_agent,
            last_user_msg=question,
            mode=context.mode,
        )