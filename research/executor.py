from typing import Any,Dict,List
from tools.registry import ToolRegistry

class ToolExecutor:
    def __init__(self):
        self.tools=ToolRegistry()

    def run(
        self,
        plan:List[Dict[str,Any]],
        user_id:str,
        chat_id:str=None,
    )->List[Dict[str,Any]]:

        results=[]

        for step in plan:
            tool=step.get("tool")
            args=step.get("args",{})

            try:
                result=self.tools.execute_for_user(
                    tool,
                    user_id=user_id,
                    chat_id=chat_id,
                    **args,
                )

                results.append({
                    "tool":tool,
                    "success":result.get("success",False),
                    "result":result,
                })

            except Exception as exc:
                results.append({
                    "tool":tool,
                    "success":False,
                    "result":{"error":str(exc)}
                })

        return results