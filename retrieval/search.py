from typing import Any,Dict,List,Optional
from .embeddings import EmbeddingService
from database.client import db

class RetrievalSearch:
    def __init__(self,embedding_service:Optional[EmbeddingService]=None):
        self._embeddings=embedding_service

    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings=EmbeddingService()
        return self._embeddings

    def search(
        self,
        user_id:str,
        query:str,
        chat_id:Optional[str]=None,
        limit:int=5,
    )->List[Dict[str,Any]]:
        query=str(query or "").strip()
        if not query:return []

        if not user_id:
            raise ValueError("User identity is required.")

        limit=max(1,min(int(limit),20))
        vector=self.embeddings.embed(query)

        result=db().rpc(
            "match_documents",
            {
                "query_embedding":vector,
                "match_count":limit,
                "filter_user":str(user_id),
                "filter_chat":str(chat_id) if chat_id else None,
            },
        ).execute()

        return result.data or []

    def format_context(self,results:List[Dict[str,Any]])->str:
        if not results:return ""

        parts=[]
        for i,item in enumerate(results,1):
            content=str(item.get("content","")).strip()
            if not content:continue

            similarity=item.get("similarity")
            label=f"[Document {i}]"

            if similarity is not None:
                label+=f" similarity={float(similarity):.3f}"

            parts.append(f"{label}\n{content}")

        return "\n\n".join(parts)