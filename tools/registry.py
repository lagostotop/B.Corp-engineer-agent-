from typing import Any,Dict,Optional
from .calculator import CalculatorTool
from .file_search import FileSearchTool
from .web_search import WebSearchTool

class ToolRegistry:
    def __init__(self):
        self.tools={
            "calculator":CalculatorTool(),
            "web_search":WebSearchTool(),
            "file_search":FileSearchTool(),
        }

    def get(self,name:str):
        return self.tools.get(str(name or "").strip())

    def names(self):
        return list(self.tools.keys())

    def descriptions(self)->Dict[str,str]:
        return {name:tool.description for name,tool in self.tools.items()}

    def execute(self,name:str,**kwargs)->Dict[str,Any]:
        tool=self.get(name)
        if tool is None:
            return {
                "success":False,
                "error":f"Unknown tool: {name}",
            }
        try:
            return tool.execute(**kwargs)
        except Exception as exc:
            return {
                "success":False,
                "error":f"Tool '{name}' failed: {exc}",
            }

    def execute_for_user(
        self,
        name:str,
        user_id:str,
        chat_id:Optional[str]=None,
        **kwargs,
    )->Dict[str,Any]:
        if name=="file_search":
            return self.execute(
                name,
                user_id=user_id,
                chat_id=chat_id,
                **kwargs,
            )
        return self.execute(name,**kwargs)