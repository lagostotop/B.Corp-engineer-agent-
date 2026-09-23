from typing import Any,Dict,List,Optional

from tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(self,tools:Optional[ToolRegistry]=None):
        self.tools=tools or ToolRegistry()

    def run(
        self,
        plan:List[Dict[str,Any]],
        user_id:str,
        chat_id:str=None,
    )->List[Dict[str,Any]]:
        results=[]

        if not isinstance(plan,list):
            return [{
                "tool":"unknown",
                "success":False,
                "result":{"error":"Invalid tool plan."},
            }]

        for step in plan:
            if not isinstance(step,dict):
                results.append({
                    "tool":"unknown",
                    "success":False,
                    "result":{"error":"Invalid tool step."},
                })
                continue

            tool=str(step.get("tool","")).strip()
            args=step.get("args") or {}

            if not tool:
                results.append({
                    "tool":"unknown",
                    "success":False,
                    "result":{"error":"Tool name is required."},
                })
                continue

            if not isinstance(args,dict):
                results.append({
                    "tool":tool,
                    "success":False,
                    "result":{"error":"Tool arguments must be an object."},
                })
                continue

            try:
                result=self.tools.execute_for_user(
                    tool,
                    user_id=user_id,
                    chat_id=chat_id,
                    **args,
                )

                results.append({
                    "tool":tool,
                    "success":bool(result.get("success")),
                    "result":result,
                })

            except TypeError as exc:
                results.append({
                    "tool":tool,
                    "success":False,
                    "result":{
                        "error":f"Invalid arguments for tool '{tool}': {exc}"
                    },
                })

            except Exception as exc:
                results.append({
                    "tool":tool,
                    "success":False,
                    "result":{
                        "error":f"Tool '{tool}' failed: {exc}"
                    },
                })

        return results