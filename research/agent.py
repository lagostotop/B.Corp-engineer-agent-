from typing import Any,Dict,List,Optional

from .executor import ToolExecutor
from .formatter import format_research


class ResearchAgent:
    WEB_WORDS=(
        "latest",
        "today",
        "news",
        "current",
        "recent",
        "yesterday",
        "this week",
        "this month",
    )

    FILE_WORDS=(
        "document",
        "file",
        "pdf",
        "upload",
        "uploaded",
        "this file",
        "this document",
    )

    CALC_WORDS=(
        "calculate",
        "calculator",
        "math",
        "solve",
        "how much",
        "how many",
        "percentage",
        "percent",
    )

    def __init__(self,executor:Optional[ToolExecutor]=None):
        self.executor=executor or ToolExecutor()

    def _needs_calculator(self,question:str)->bool:
        q=(question or "").lower()

        if not any(word in q for word in self.CALC_WORDS):
            return False

        return any(
            symbol in q
            for symbol in ("+","-","*","/","=","%")
        )

    def plan(
        self,
        question:str,
        has_file:bool=False,
    )->List[Dict[str,Any]]:
        question=str(question or "").strip()

        if not question:
            return []

        q=question.lower()
        plan=[]

        if any(word in q for word in self.WEB_WORDS):
            plan.append({
                "tool":"web_search",
                "args":{
                    "query":question,
                    "max_results":5,
                },
            })

        if has_file or any(word in q for word in self.FILE_WORDS):
            plan.append({
                "tool":"file_search",
                "args":{
                    "query":question,
                    "limit":5,
                },
            })

        if self._needs_calculator(question):
            plan.append({
                "tool":"calculator",
                "args":{
                    "expression":question,
                },
            })

        return plan

    def run(
        self,
        question:str,
        user_id:str,
        chat_id:str=None,
        has_file:bool=False,
    )->Dict[str,Any]:
        question=str(question or "").strip()

        plan=self.plan(
            question,
            has_file=has_file,
        )

        if not plan:
            return {
                "answer":"",
                "used_tools":[],
                "results":[],
                "plan":[],
            }

        results=self.executor.run(
            plan,
            user_id=user_id,
            chat_id=chat_id,
        )

        successful=[
            item["tool"]
            for item in results
            if item.get("success")
        ]

        return {
            "answer":format_research(results),
            "used_tools":successful,
            "results":results,
            "plan":plan,
        }