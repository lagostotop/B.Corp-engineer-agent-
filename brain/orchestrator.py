from typing import Any,Dict,Optional
from .context import BrainContext
from .model_router import ModelRouter
from .planner import Planner
from .verifier import Verifier
from research.agent import ResearchAgent

class BrainOrchestrator:
    def __init__(
        self,
        router:Optional[ModelRouter]=None,
        research_agent:Optional[ResearchAgent]=None
    ):
        self.router=router or ModelRouter()
        self.planner=Planner()
        self.verifier=Verifier()
        self.research_agent=research_agent or ResearchAgent()

    def _research(
        self,
        context:BrainContext,
        question:str
    )->Dict[str,Any]:
        needs_tools=self.planner.needs_tools(
            question,
            context.mode
        )

        has_file=bool(
            context.file_meta
            and context.file_meta.get("type") not in (
                ".png",".jpg",".jpeg"
            )
        )

        if not needs_tools and not has_file:
            return {
                "answer":"",
                "used_tools":[],
                "results":[]
            }

        try:
            return self.research_agent.run(
                question=question,
                user_id=context.user_id,
                chat_id=context.chat_id,
                has_file=has_file,
            )
        except Exception:
            return {
                "answer":"",
                "used_tools":[],
                "results":[]
            }

    def run(
        self,
        context:BrainContext
    )->Dict[str,Any]:
        question=context.question or context.last_message
        plan=self.planner.plan(
            question,
            context.mode
        )

        research=self._research(
            context,
            question
        )

        result=self.router.route(
            messages=context.messages,
            uid=context.user_id,
            cid=context.chat_id,
            file_meta=context.file_meta,
            stream=False,
            force_agent=False,
            last_user_msg=question,
            mode=context.mode,
            agent_result=research.get("answer",""),
        )

        answer=""

        if isinstance(result,dict):
            choices=result.get("choices",[])
            if choices:
                answer=choices[0].get(
                    "message",
                    {}
                ).get(
                    "content",
                    ""
                )
        else:
            choices=getattr(
                result,
                "choices",
                []
            )

            if choices:
                answer=getattr(
                    choices[0].message,
                    "content",
                    ""
                ) or ""

        answer=self.verifier.finalize(
            answer,
            question,
            research.get("results")
        )

        return {
            "answer":answer,
            "plan":plan,
            "verified":bool(answer),
            "used_agent":bool(
                research.get("used_tools")
            ),
            "used_tools":research.get(
                "used_tools",
                []
            ),
        }

    def stream(
        self,
        context:BrainContext
    ):
        question=context.question or context.last_message

        research=self._research(
            context,
            question
        )

        return self.router.route(
            messages=context.messages,
            uid=context.user_id,
            cid=context.chat_id,
            file_meta=context.file_meta,
            stream=True,
            force_agent=False,
            last_user_msg=question,
            mode=context.mode,
            agent_result=research.get("answer",""),
        )