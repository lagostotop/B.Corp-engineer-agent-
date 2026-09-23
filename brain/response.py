import json
from typing import Any,Dict,Iterable


def sse_event(event:str,data:Any)->str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data,ensure_ascii=False)}\n\n"
    )


def token_event(text:str)->str:
    return sse_event("token",{"text":str(text)})


def error_event(
    message:str,
    request_id:str="",
)->str:
    data={"message":str(message)}

    if request_id:
        data["request_id"]=str(request_id)

    return sse_event("error",data)


def done_event(
    chat_id:str,
    answer_saved:bool=True,
)->str:
    return sse_event(
        "done",
        {
            "chat_id":str(chat_id),
            "answer_saved":bool(answer_saved),
        },
    )


def chat_id_event(chat_id:str)->str:
    return sse_event(
        "chat_id",
        {"chat_id":str(chat_id)},
    )


def collect_stream(stream:Iterable[Any])->str:
    parts=[]

    for chunk in stream:
        choices=getattr(chunk,"choices",None)

        if not choices:
            continue

        delta=getattr(
            choices[0],
            "delta",
            None,
        )

        if delta is None:
            continue

        text=getattr(
            delta,
            "content",
            None,
        )

        if text:
            parts.append(str(text))

    return "".join(parts)


def response_payload(
    answer:str,
    chat_id:str=None,
    metadata:Dict[str,Any]=None,
)->Dict[str,Any]:
    data={
        "answer":str(answer or ""),
    }

    if chat_id:
        data["chat_id"]=str(chat_id)

    if metadata:
        data["metadata"]=metadata

    return data