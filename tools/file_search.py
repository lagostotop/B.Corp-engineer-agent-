from typing import Any,Dict,Optional
from retrieval.search import RetrievalSearch

class FileSearchTool:
    name="file_search"
    description="Search the user's indexed uploaded documents using semantic retrieval."

    def __init__(self,search:Optional[RetrievalSearch]=None):
        self.searcher=search or RetrievalSearch()

    def execute(
        self,
        query:str,
        user_id:str,
        chat_id:Optional[str]=None,
        limit:int=5,
    )->Dict[str,Any]:
        query=str(query or "").strip()
        if not query:
            return {"success":False,"error":"Search query is required."}
        if not user_id:
            return {"success":False,"error":"User identity is required."}
        try:
            results=self.searcher.search(
                user_id=str(user_id),
                query=query,
                chat_id=chat_id,
                limit=limit,
            )
            return {
                "success":True,
                "query":query,
                "results":results,
                "context":self.searcher.format_context(results),
            }
        except Exception as exc:
            return {"success":False,"error":f"Document search failed: {exc}"}