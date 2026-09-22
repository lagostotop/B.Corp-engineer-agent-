from typing import List
from openai import OpenAI
from core.config import settings

class EmbeddingService:
    def __init__(self):
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for embeddings.")
        self.client=OpenAI(api_key=settings.openai_api_key)
        self.model=settings.embedding_model
        self.dimensions=settings.embedding_dimensions

    def embed(self,text:str)->List[float]:
        text=str(text or "").strip()
        if not text:
            raise ValueError("Cannot embed empty text.")
        result=self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
        )
        vector=result.data[0].embedding
        if len(vector)!=self.dimensions:
            raise RuntimeError("Embedding dimension mismatch.")
        return vector

    def embed_many(self,texts:List[str])->List[List[float]]:
        clean=[str(x or "").strip() for x in texts]
        clean=[x for x in clean if x]
        if not clean:return []
        result=self.client.embeddings.create(
            model=self.model,
            input=clean,
            dimensions=self.dimensions,
        )
        vectors=[x.embedding for x in sorted(result.data,key=lambda x:x.index)]
        if any(len(v)!=self.dimensions for v in vectors):
            raise RuntimeError("Embedding dimension mismatch.")
        return vectors