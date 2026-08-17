import json
import os
from typing import List, Dict, Any
from supabase import create_client
from datetime import datetime, timezone
from config import SUPABASE_URL, SUPABASE_KEY
from groq import Groq

# Import tools
from tools.tavily import search_web
from tools.file_search import search_documents
from brain_core import deep_research, save_memory, get_memory

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Define tools for function calling
AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current information, news, prices, latest events",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search user's uploaded documents, PDFs, and files using semantic search",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "user_id": {"type": "string"}}, "required": ["query", "user_id"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deep_research",
            "description": "Perform comprehensive multi-step research on a topic. Plans sub-questions, searches web and docs, then synthesizes a report",
            "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save important facts about the user for long term memory",
            "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory",
            "description": "Recall facts about the user from long term memory",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }
    }
]

class AgentEngine:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.tools_map = {
            "search_web": search_web,
            "search_documents": search_documents,
            "deep_research": deep_research,
            "save_memory": save_memory,
            "get_memory": get_memory
        }
        self.max_steps = 6

    def run(self, goal: str, chat_history: List[Dict]) -> Dict[str, Any]:
        """
        Main agent loop with real function calling
        """
        steps = []

        system_prompt = """You are Brain 4.0, an autonomous AI OS agent by B.CORP.
Your goal: Achieve the user's objective by calling tools step by step.
Rules:
1. Think step by step and call ONE or MORE tools per turn
2. Use search_web for current info, news, prices
3. Use search_documents for user's uploaded files
4. Use deep_research for complex topics that need multiple sources
5. Use save_memory/get_memory to remember user preferences
6. When you have the answer, respond directly without calling tools
Always be helpful and cite sources."""

        # Build message history for the agent
        agent_messages = [{"role": "system", "content": system_prompt}] + chat_history
        agent_messages.append({"role": "user", "content": goal})

        for i in range(self.max_steps):
            # 1. ASK LLM WHAT TO DO WITH FUNCTION CALLING
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=agent_messages,
                tools=AVAILABLE_TOOLS,
                tool_choice="auto",
                temperature=0.2
            )

            msg = res.choices[0].message
            step_data = {"thought": msg.content, "tool_calls": []}

            # 2. CHECK IF DONE
            if not msg.tool_calls:
                self._log_trace(goal, steps)
                return {"answer": msg.content, "steps": steps}

            # 3. EXECUTE ALL TOOL CALLS
            agent_messages.append(msg)
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                step_data["tool_calls"].append({"name": func_name, "args": func_args})

                # Execute tool
                result = self._execute_tool(func_name, func_args)

                # Add result back to conversation
                agent_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": str(result)
                })

            steps.append(step_data)

        self._log_trace(goal, steps)
        return {"answer": "I completed the steps. Here's what I found.", "steps": steps}

    def _execute_tool(self, name: str, args: Dict) -> str:
        """Execute the actual tool function"""
        try:
            if name == "search_web":
                return self.tools_map[name](args["query"])

            if name == "search_documents":
                return self.tools_map[name](args["query"], args.get("user_id", self.user_id))

            if name == "deep_research":
                return self.tools_map[name](args["topic"], supabase, self.user_id)

            if name == "save_memory":
                return self.tools_map[name](self.user_id, args["key"], args["value"], supabase)

            if name == "get_memory":
                mems = self.tools_map[name](self.user_id, args["query"], supabase)
                return "Memory: " + " | ".join(mems) if mems else "No memory found"

            return "Tool not found"
        except Exception as e:
            return f"Tool error: {str(e)}"

    def _log_trace(self, goal: str, steps: List):
        """Save agent steps to Supabase for debugging"""
        try:
            supabase.table("Inference_logs").insert({
                "user_id": self.user_id,
                "goal": goal,
                "steps": json.dumps(steps),
                "created_at": datetime.now(timezone.utc).isoformat()
            }).execute()
        except Exception as e:
            print(f"Log error: {e}")

def run_agent(user_id: str, goal: str, chat_history: List[Dict]) -> Dict:
    agent = AgentEngine(user_id)
    return agent.run(goal, chat_history)
