from typing import Any,Dict,List
from .executor import ToolExecutor
from .formatter import format_research

class ResearchAgent:
    def __init__(self):
        self.executor=ToolExecutor()

    def plan(self,question:str)->List[Dict[str,Any]]:
        q=(question or "").lower()

        plan=[]

        if any(x in q for x in (
            "latest","today","news",
            "current","recent"
        )):
            plan.append({
                "tool":"web_search",
                "args":{
                    "query":question,
                    "max_results":5,
                }
            })

        if any(x in q for x in (
            "document",
            "file",
            "pdf",
            "upload"
        )):
            plan.append({
                "tool":"file_search",
                "args":{
                    "query":question,
                    "limit":5,
                }
            })

        if any(x in q for x in (
            "+","-","*","/",
            "calculate",
            "math"
        )):
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
    )->Dict[str,Any]:

        plan=self.plan(question)

        if not plan:
            return {
                "answer":"",
                "used_tools":[],
            }

        results=self.executor.run(
            plan,
            user_id=user_id,
            chat_id=chat_id,
        )

        return {
            "answer":format_research(results),
            "used_tools":[x["tool"] for x in results],
            "results":results,
        }