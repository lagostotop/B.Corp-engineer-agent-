from typing import Any,Dict,List
from tavily import TavilyClient
from core.config import settings

class WebSearchTool:
    name="web_search"
    description="Search the public web for current or hard-to-find information."

    def __init__(self):
        self.client=TavilyClient(api_key=settings.tavily_api_key) if settings.tavily_api_key else None

    def execute(self,query:str,max_results:int=5)->Dict[str,Any]:
        query=str(query or "").strip()
        if not query:
            return {"success":False,"error":"Search query is required."}
        if not self.client:
            return {"success":False,"error":"Web search is not configured."}
        max_results=max(1,min(int(max_results),10))
        try:
            result=self.client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=True,
                include_raw_content=False,
            )
            results=[]
            for item in result.get("results",[]):
                results.append({
                    "title":item.get("title",""),
                    "url":item.get("url",""),
                    "content":item.get("content",""),
                    "score":item.get("score"),
                })
            return {
                "success":True,
                "query":query,
                "answer":result.get("answer"),
                "results":results,
            }
        except Exception as exc:
            return {"success":False,"error":f"Web search failed: {exc}"}

    def format_results(self,result:Dict[str,Any])->str:
        if not result.get("success"):
            return result.get("error","Web search failed.")
        parts=[]
        if result.get("answer"):
            parts.append(f"Search summary:\n{result['answer']}")
        for i,item in enumerate(result.get("results",[]),1):
            parts.append(
                f"[Source {i}] {item.get('title','')}\n"
                f"URL: {item.get('url','')}\n"
                f"{item.get('content','')}"
            )
        return "\n\n".join(parts)