import requests
import os
from config import TAVILY_API_KEY

def search_web(query: str) -> str:
    """Search the web using Tavily"""
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 3
    }
    res = requests.post(url, json=payload)
    results = res.json().get("results", [])
    return "\n".join([f"- {r['title']}: {r['content']}" for r in results])
