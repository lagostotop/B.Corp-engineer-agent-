from typing import Any,Dict,List

def format_research(results:List[Dict[str,Any]])->str:
    if not results:
        return ""

    parts=[]

    for item in results:
        tool=item.get("tool","unknown")
        data=item.get("result",{})

        parts.append(f"=== {tool.upper()} ===")

        if isinstance(data,dict):
            if data.get("context"):
                parts.append(data["context"])

            elif data.get("answer"):
                parts.append(str(data["answer"]))

            elif data.get("result") is not None:
                parts.append(str(data["result"]))

        parts.append("")

    return "\n".join(parts)