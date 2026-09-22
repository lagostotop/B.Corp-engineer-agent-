from typing import List

def chunk_text(text:str,size:int=1000,overlap:int=200,max_chunks:int=100)->List[str]:
    text=str(text or "").strip()
    if not text:return []

    size=max(100,int(size))
    overlap=max(0,min(int(overlap),size-1))
    max_chunks=max(1,int(max_chunks))

    chunks=[]
    start=0
    length=len(text)

    while start<length and len(chunks)<max_chunks:
        end=min(start+size,length)

        if end<length:
            boundary=max(
                text.rfind("\n\n",start,end),
                text.rfind("\n",start,end),
                text.rfind(". ",start,end),
                text.rfind(" ",start,end),
            )
            if boundary>start+size//2:
                end=boundary+1

        chunk=text[start:end].strip()
        if chunk:chunks.append(chunk)

        if end>=length:break
        start=max(end-overlap,start+1)

    return chunks