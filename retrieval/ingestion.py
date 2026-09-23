import os
from typing import Any,Dict,Optional
from .file_parser import extract_text
from .indexer import RetrievalIndexer

class FileIngestionService:
    def __init__(self,indexer:Optional[RetrievalIndexer]=None):
        self.indexer=indexer or RetrievalIndexer()

    def ingest(
        self,
        path:str,
        filename:str,
        user_id:str,
        chat_id:str
    )->Dict[str,Any]:
        text=extract_text(path,filename)

        if not text:
            return {
                "success":False,
                "indexed":False,
                "error":"No extractable text found."
            }

        result=self.indexer.index_text(
            user_id=str(user_id),
            chat_id=str(chat_id),
            text=text,
            metadata={
                "filename":filename,
                "source":"upload",
                "extension":os.path.splitext(filename)[1].lower(),
            }
        )

        return {
            "success":True,
            "indexed":True,
            "filename":filename,
            "characters":len(text),
            "chunks":result.get("total",0),
            "saved":result.get("saved",0),
        }