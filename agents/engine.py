import json
import os
from typing import List, Dict, Any
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

# Import tools - we'll build these next
from tools.tavily import search_web
from tools.file_search import search_documents

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class AgentEngine:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.tools = {
            "search_web": search_web,
            "search_documents": search_documents
        }
        self.max_steps = 5

    def run(self, goal: str, chat_history: List[Dict]) -> Dict[str, Any]:
        """
        Main agent loop. Takes a goal and decides which tools to call.
        """
        steps = []
        final_answer = ""

        system_prompt = f"""You are Brain 4.0, an autonomous agent.
        You have access to these tools: {list(self.tools.keys())}

        Rules:
        1. Think step by step
        2. Call ONE tool at a time
        3. Use search_web for current info
        4. Use search_documents for user's uploaded files
        5. When done, return final answer

        Respond in JSON: {{"thought": "...", "tool": "tool_name or 'finish'", "args": {{...}}}}
        """

        for i in range(self.max_steps):
            # 1. Decide what to do next
            messages = [{"role": "system", "content": system_prompt}] + chat_history
            messages.append({"role": "user", "content": f"Goal: {goal}\nSteps so far: {steps}"})

            # This is where we'd call GPT-5. For now using simple logic
            decision = self._decide_next_action(goal, steps)
            steps.append(decision)

            # 2. Execute tool
            if decision["tool"] == "finish":
                final_answer = decision["args"]["answer"]
                break

            tool_func = self.tools.get(decision["tool"])
            if tool_func:
                tool_result = tool_func(**decision["args"])
                chat_history.append({"role": "assistant", "content": f"Called {decision['tool']}: {tool_result}"})

        # 3. Log to Supabase for debugging
        self._log_trace(goal, steps)

        return {"answer": final_answer, "steps": steps}

    def _decide_next_action(self, goal: str, steps: List) -> Dict:
        """
        Simple router for now. Later we replace this with GPT-5 function calling
        """
        goal_lower = goal.lower()

        if "search" in goal_lower or "news" in goal_lower or "latest" in goal_lower:
            query = goal.replace("search", "").replace("latest", "").strip()
            return {"thought": "User wants current info", "tool": "search_web", "args": {"query": query}}

        if "file" in goal_lower or "document" in goal_lower:
            query = goal.replace("file", "").replace("document", "").strip()
            return {"thought": "Search user's files", "tool": "search_documents", "args": {"query": query, "user_id": self.user_id}}

        return {"thought": "No tool needed", "tool": "finish", "args": {"answer": f"Got it: {goal}"}}

    def _log_trace(self, goal: str, steps: List):
        """Save agent steps to Supabase so we can debug"""
        try:
            supabase.table("Inference_logs").insert({
                "user_id": self.user_id,
                "goal": goal,
                "steps": json.dumps(steps)
            }).execute()
        except Exception as e:
            print(f"Log error: {e}")

def run_agent(user_id: str, goal: str, chat_history: List[Dict]) -> Dict:
    agent = AgentEngine(user_id)
    return agent.run(goal, chat_history)
