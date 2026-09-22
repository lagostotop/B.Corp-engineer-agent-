import re
from typing import List

class Planner:
    AGENT_WORDS=("research","investigate","compare","analyze","analyse","latest","current","news","debug","code","calculate")

    def needs_tools(self,question:str,mode:str="normal")->bool:
        if mode in ("agent","research","deep_research","code","reasoning"):
            return True
        q=(question or "").lower()
        return any(x in q for x in self.AGENT_WORDS)

    def plan(self,question:str,mode:str="normal")->List[str]:
        q=(question or "").strip()
        if not q:return []
        if not self.needs_tools(q,mode):return ["answer"]
        if mode in ("research","deep_research"):
            return ["research","verify","answer"]
        if mode=="code":
            return ["understand","solve","verify","answer"]
        if re.search(r"\b(compare|difference|versus|vs)\b",q,re.I):
            return ["gather_information","compare","verify","answer"]
        return ["understand","gather_information","verify","answer"]