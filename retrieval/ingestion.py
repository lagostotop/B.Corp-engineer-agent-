import hashlib,os
from typing import Any,Dict,Optional
from .file_parser import extract_text
from .indexer import RetrievalIndexer

class FileIngestionService:
    def __init__(self,indexer:Optional[RetrievalIndexer]=None):
        self._indexer=indexer

    @property
    def indexer(self):
        if self._indexer is None:
            self._indexer=RetrievalIndexer()
        return self._indexer

    def _file_hash(self,path:str)->str:
        digest=hashlib.sha256()
        with open(path,"rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""):
                digest.update(chunk)
        return digest.hexdigest()

    def ingest(
        self,
        path:str,
        filename:str,
        user_id:str,
        chat_id:str
    )->Dict[str,Any]:
        if not path or not os.path.exists(path):
            return {
                "success":False,
                "indexed":False,
                "error":"Uploaded file was not found."
            }

        if not user_id or not chat_id:
            return {
                "success":False,
                "indexed":False,
                "error":"User and chat identity are required."
            }

        try:
            text=extract_text(path,filename)
        except Exception as exc:
            return {
                "success":False,
                "indexed":False,
                "error":f"File extraction failed: {exc}"
            }

        if not text:
            return {
                "success":False,
                "indexed":False,
                "error":"No extractable text found."
            }

        try:
            file_hash=self._file_hash(path)
            extension=os.path.splitext(filename)[1].lower()

            result=self.indexer.index_text(
                user_id=str(user_id),
                chat_id=str(chat_id),
                text=text,
                metadata={
                    "filename":filename,
                    "source":"upload",
                    "extension":extension,
                    "file_hash":file_hash
                }
            )

            return {
                "success":True,
                "indexed":result.get("saved",0)>0,
                "filename":filename,
                "file_hash":file_hash,
                "characters":len(text),
                "chunks":result.get("total",0),
                "saved":result.get("saved",0)
            }

        except Exception as exc:
            return {
                "success":False,
                "indexed":False,
                "filename":filename,
                "error":f"File indexing failed: {exc}"
            }