import os
import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def search_web(query: str) -> str:
    """
    Search the web using Tavily. Fallback to groq/compound if Tavily fails.
    Returns formatted results with citations that match brain_core regex.
    Format: Source: https://...
    """
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not set. Using fallback.")
        return _fallback_search(query)

    try:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "advanced",
            "max_results": 4, # brain_core expects 4
            "include_answer": True,
            "include_raw_content": False
        }
        res = requests.post(url, json=payload, timeout=20)
        res.raise_for_status()
        data = res.json()

        answer = data.get("answer", "")
        results = data.get("results", [])

        if not results and not answer:
            return _fallback_search(query)

        # Format MUST match: re.findall(r"Source:\s*(https?://\S+)")
        formatted = f"Answer: {answer}\n\n" if answer else ""

        for i, r in enumerate(results[:4], 1):
            title = r.get("title", "No Title")
            content = r.get("content", "")[:400] # a bit more context
            url = r.get("url", "#")
            formatted += f"[{i}] {title}\n{content}...\nSource: {url}\n\n"

        return formatted.strip()

    except Exception as e:
        logger.exception(f"Tavily search failed: {e}")
        return _fallback_search(query)

def _fallback_search(query: str) -> str:
    """Fallback to groq/compound if Tavily is down"""
    try:
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        res = client.chat.completions.create(
            model="groq/compound",
            messages=[{"role": "user", "content": f"Search the web for current information about: {query}. Provide a summary and list sources with URLs."}],
            temperature=0.1,
            max_tokens=1500
        )
        content = res.choices[0].message.content
        # Try to append Source: lines so regex still works
        return f"Answer: {content}\n\nSource: https://groq.com/compound"
    except Exception as e:
        logger.error(f"Fallback search failed: {e}")
        return f"Web search failed for: {query}. Please try again later."
