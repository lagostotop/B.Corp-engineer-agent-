def deep_research(query: str, supabase, uid: str) -> str:
    """
    Does 3 steps: 1. Web search 2. Search docs 3. Synthesize
    """
    from brain_core import client
    steps = []

    # Step 1: Web
    res = client.chat.completions.create(
        model="groq/compound",
        messages=[{"role": "user", "content": f"Research: {query}"}]
    )
    web_data = res.choices[0].message.content
    steps.append(f"Web: {web_data[:300]}")

    # Step 2: Docs
    from brain_core import search_rag
    doc_data = search_rag(query, uid, supabase)
    steps.append(f"Docs: {doc_data[:300]}")

    # Step 3: Synthesize
    final = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": "Synthesize this research into a report"},
                  {"role": "user", "content": "\n".join(steps)}]
    )
    return final.choices[0].message.content
