from typing import Any,Dict,List,Optional
from .chunking import chunk_text
from .embeddings import EmbeddingService
from database.documents import create_document

class RetrievalIndexer:
    def __init__(self,embedding_service:Optional[EmbeddingService]=None):
        self.embeddings=embedding_service or EmbeddingService()

    def index_text(
        self,
        user_id:str,
        chat_id:str,
        text:str,
        metadata:Optional[Dict[str,Any]]=None,
        chunk_size:int=1000,
        overlap:int=200,
        max_chunks:int=100,
    )->Dict[str,Any]:
        chunks=chunk_text(text,chunk_size,overlap,max_chunks)
        if not chunks:
            return {"total":0,"saved":0}

        vectors=self.embeddings.embed_many(chunks)
        saved=0

        for i,(chunk,vector) in enumerate(zip(chunks,vectors)):
            meta=dict(metadata or {})
            meta.update({"chunk_index":i,"chunk_count":len(chunks)})
            create_document(
                user_id=user_id,
                chat_id=chat_id,
                content=chunk,
                embedding=vector,
                metadata=meta,
            )
            saved+=1

        return {"total":len(chunks),"saved":saved}

    def index_chunks(
        self,
        user_id:str,
        chat_id:str,
        chunks:List[str],
        metadata:Optional[Dict[str,Any]]=None,
    )->Dict[str,Any]:
        clean=[str(x).strip() for x in chunks if str(x).strip()]
        if not clean:return {"total":0,"saved":0}

        vectors=self.embeddings.embed_many(clean)
        saved=0

        for i,(chunk,vector) in enumerate(zip(clean,vectors)):
            meta=dict(metadata or {})
            meta.update({"chunk_index":i,"chunk_count":len(clean)})
            create_document(user_id,chat_id,chunk,vector,meta)
            saved+=1

        return {"total":len(clean),"saved":saved}