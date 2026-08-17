def deep_research(topic: str, supabase, uid: str) -> str:
    """
    Phase 1 Deep Research: Plan -> Multi-search -> Extract -> Synthesize -> Cite
    """
    from brain_core import client, search_rag
    import time

    logger.info(f"Deep Research Start: {topic}")
    all_findings = []

    # ========== STEP 1: RESEARCH PLAN ==========
    plan_prompt = f"""You are a research director. For the topic: "{topic}"
Break this down into 3-4 specific sub-questions that need to be answered to fully research this topic.
Return ONLY a JSON array of strings. Example: ["What is X", "How does Y work", "What are the latest trends in Z"]"""

    try:
        plan_res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": plan_prompt}],
            temperature=0.3,
            max_tokens=400,
            response_format={"type": "json_object"}
        )
        plan_data = json.loads(plan_res.choices[0].message.content)
        questions = plan_data.get("questions", [topic])
    except:
        questions = [f"What is {topic}", f"Latest developments in {topic}", f"How does {topic} work"]

    logger.info(f"Research Plan: {questions}")

    # ========== STEP 2: MULTI-SEARCH ==========
    for i, q in enumerate(questions[:4]): # Max 4 questions
        logger.info(f"Researching Q{i+1}: {q}")

        # 2a. Web Search with groq/compound
        try:
            web_res = client.chat.completions.create(
                model="groq/compound",
                messages=[{"role": "user", "content": q}],
                temperature=0.1
            )
            web_data = web_res.choices[0].message.content
        except:
            web_data = "Web search failed"

        # 2b. Document Search
        doc_data = search_rag(q, uid, supabase)

        all_findings.append({
            "question": q,
            "web": web_data,
            "docs": doc_data if doc_data else "No relevant documents found"
        })
        time.sleep(0.5) # Rate limit protection

    # ========== STEP 3: EXTRACT KEY POINTS ==========
    extract_prompt = f"""Extract the 5-7 most important facts from these research findings.
Be concise and factual. Topic: {topic}

Findings: {json.dumps(all_findings, indent=2)}"""

    extract_res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": extract_prompt}],
        temperature=0.2
    )
    key_points = extract_res.choices[0].message.content

    # ========== STEP 4: SYNTHESIZE FINAL REPORT ==========
    synthesis_prompt = f"""You are Brain 4.0 Research Agent. Write a comprehensive research report on: {topic}

Use the key points below. Structure it with:
1. Executive Summary
2. Key Findings
3. Detailed Analysis
4. Conclusion

Cite sources as [1], [2] etc. Be objective and thorough.

Key Points:
{key_points}

Raw Findings:
{json.dumps(all_findings, indent=2)}"""

    final_res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": synthesis_prompt}],
        temperature=0.4,
        max_tokens=2000
    )

    report = final_res.choices[0].message.content
    logger.info(f"Deep Research Complete: {topic}")

    return f"# 🔬 Deep Research Report: {topic}\n\n{report}\n\n---\n*Research completed with {len(questions)} sub-queries across web and documents*"
