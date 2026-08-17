import os
import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def search_web(query: str) -> str:
    """
    Search the web using Tavily. Fallback to groq/compound if Tavily fails.
    Returns formatted results with citations.
    """
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not set. Using fallback.")
        return _fallback_search(query)

    try:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "advanced", # "basic" or "advanced"
            "max_results": 5,
            "include_answer": True,
            "include_raw_content": False
        }
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()
        data = res.json()

        # Tavily gives us a direct answer + sources
        answer = data.get("answer", "")
        results = data.get("results", [])

        if not results and not answer:
            return _fallback_search(query)

        formatted = []
        if answer:
            formatted.append(f"**Summary:** {answer}\n")

        formatted.append("**Sources:**")
        for i, r in enumerate(results[:5]):
            title = r.get("title", "No Title")
            content = r.get("content", "")[:300]
            url = r.get("url", "#")
            formatted.append(f"[{i+1}] **{title}**\n{content}...\nSource: {url}")

        return "\n\n".join(formatted)

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
            messages=[{"role": "user", "content": f"Search the web for: {query}"}],
            temperature=0.1
        )
        return f"**Web Search via Groq Compound:**\n{res.choices[0].message.content}"
    except Exception as e:
        logger.error(f"Fallback search failed: {e}")
        return f"Web search failed for: {query}. Please try again later."
