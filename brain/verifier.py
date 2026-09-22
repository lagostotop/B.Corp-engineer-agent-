from typing import Any,Dict

class Verifier:
    def check(self,answer:str,question:str="",evidence:Any=None)->Dict[str,Any]:
        text=(answer or "").strip()
        issues=[]

        if not text:
            issues.append("empty_response")

        if len(text)>50000:
            issues.append("response_too_long")

        if "I can't" in text and len(text)<100:
            issues.append("possibly_incomplete")

        return {
            "ok":not issues,
            "answer":text,
            "issues":issues,
            "evidence_used":bool(evidence),
        }

    def finalize(self,answer:str,question:str="",evidence:Any=None)->str:
        result=self.check(answer,question,evidence)
        return result["answer"]