from typing import Any,Dict,List
from .executor import ToolExecutor
from .formatter import format_research

class ResearchAgent:
    def __init__(self):
        self.executor=ToolExecutor()

    def plan(
        self,
        question:str,
        has_file:bool=False
    )->List[Dict[str,Any]]:
        q=(question or "").lower()
        plan=[]

        if any(
            x in q
            for x in (
                "latest",
                "today",
                "news",
                "current",
                "recent"
            )
        ):
            plan.append({
                "tool":"web_search",
                "args":{
                    "query":question,
                    "max_results":5,
                }
            })

        if has_file or any(
            x in q
            for x in (
                "document",
                "file",
                "pdf",
                "upload",
                "uploaded",
                "this file",
                "this document"
            )
        ):
            plan.append({
                "tool":"file_search",
                "args":{
                    "query":question,
                    "limit":5,
                }
            })

        if any(
            x in q
            for x in (
                "calculate",
                "math",
                "what is",
                "how much"
            )
        ) and any(
            x in q
            for x in ("+","-","*","/","=")
        ):
            plan.append({
                "tool":"calculator",
                "args":{
                    "expression":question,
                }
            })

        return plan

    def run(
        self,
        question:str,
        user_id:str,
        chat_id:str=None,
        has_file:bool=False,
    )->Dict[str,Any]:
        plan=self.plan(
            question,
            has_file=has_file
        )

        if not plan:
            return {
                "answer":"",
                "used_tools":[],
                "results":[]
            }

        results=self.executor.run(
            plan,
            user_id=user_id,
            chat_id=chat_id,
        )

        return {
            "answer":format_research(results),
            "used_tools":[
                x["tool"]
                for x in results
                if x.get("success")
            ],
            "results":results,
        }