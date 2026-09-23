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
        research_agent:Optional[ResearchAgent]=None,
        planner:Optional[Planner]=None,
        verifier:Optional[Verifier]=None,
    ):
        self.router=router or ModelRouter()
        self.research_agent=research_agent or ResearchAgent()
        self.planner=planner or Planner()
        self.verifier=verifier or Verifier()

    def _empty_research(self)->Dict[str,Any]:
        return {
            "answer":"",
            "used_tools":[],
            "results":[],
            "plan":[],
            "error":None,
        }

    def _research(
        self,
        context:BrainContext,
        question:str,
    )->Dict[str,Any]:
        needs_tools=self.planner.needs_tools(
            question,
            context.mode,
        )

        has_file=bool(
            context.file_meta
            and context.file_meta.get("type")
            not in (
                ".png",
                ".jpg",
                ".jpeg",
            )
        )

        if not needs_tools and not has_file:
            return self._empty_research()

        try:
            result=self.research_agent.run(
                question=question,
                user_id=context.user_id,
                chat_id=context.chat_id,
                has_file=has_file,
            )

            return result or self._empty_research()

        except Exception as exc:
            return {
                **self._empty_research(),
                "error":str(exc),
            }

    def _extract_answer(self,result:Any)->str:
        if isinstance(result,dict):
            choices=result.get("choices",[])

            if choices:
                message=choices[0].get(
                    "message",
                    {},
                )

                return str(
                    message.get("content","") or ""
                )

            return ""

        choices=getattr(
            result,
            "choices",
            [],
        )

        if not choices:
            return ""

        message=getattr(
            choices[0],
            "message",
            None,
        )

        if message is None:
            return ""

        return str(
            getattr(
                message,
                "content",
                "",
            ) or ""
        )

    def run(
        self,
        context:BrainContext,
    )->Dict[str,Any]:
        question=(
            context.question
            or context.last_message
        ).strip()

        if not question:
            return {
                "answer":"",
                "plan":[],
                "verified":False,
                "used_agent":False,
                "used_tools":[],
                "research":{},
            }

        plan=self.planner.plan(
            question,
            context.mode,
        )

        research=self._research(
            context,
            question,
        )

        result=self.router.route(
            messages=context.messages,
            uid=context.user_id,
            cid=context.chat_id,
            file_meta=context.file_meta,
            stream=False,
            force_agent=bool(
                research.get("used_tools")
            ),
            last_user_msg=question,
            mode=context.mode,
            agent_result=research.get(
                "answer",
                "",
            ),
        )

        answer=self._extract_answer(result)

        verification=self.verifier.check(
            answer,
            question,
            research.get("results"),
        )

        return {
            "answer":verification["answer"],
            "plan":plan,
            "verified":verification["ok"],
            "verification":verification,
            "used_agent":bool(
                research.get("used_tools")
            ),
            "used_tools":research.get(
                "used_tools",
                [],
            ),
            "research":research,
        }

    def stream(
        self,
        context:BrainContext,
    ):
        question=(
            context.question
            or context.last_message
        ).strip()

        research=self._research(
            context,
            question,
        )

        return self.router.route(
            messages=context.messages,
            uid=context.user_id,
            cid=context.chat_id,
            file_meta=context.file_meta,
            stream=True,
            force_agent=bool(
                research.get("used_tools")
            ),
            last_user_msg=question,
            mode=context.mode,
            agent_result=research.get(
                "answer",
                "",
            ),
        )