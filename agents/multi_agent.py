# agents/multi_agent.py
from typing import List, Dict, Any, Optional
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AgentType(Enum):
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    CODER = "coder"
    CREATIVE = "creative"
    CRITIC = "critic"
    PLANNER = "planner"

class SpecializedAgent:
    def __init__(self, agent_type: AgentType, groq_client):
        self.type = agent_type
        self.client = groq_client
        self.system_prompt = self._get_system_prompt()
        self.tools = self._get_tools()
        
    def _get_system_prompt(self) -> str:
        prompts = {
            AgentType.RESEARCHER: "You are a research specialist. Focus on finding accurate, current information. Be thorough and cite sources.",
            AgentType.ANALYST: "You are an analytical expert. Break down complex problems, identify patterns, and provide structured insights.",
            AgentType.CODER: "You are a senior developer. Write clean, efficient, well-documented code. Follow best practices.",
            AgentType.CREATIVE: "You are a creative thinker. Generate innovative ideas, analogies, and alternative perspectives.",
            AgentType.CRITIC: "You are a critical reviewer. Identify weaknesses, assumptions, and potential improvements.",
            AgentType.PLANNER: "You are a strategic planner. Create detailed, actionable plans with clear steps and milestones."
        }
        return prompts.get(self.type, "You are a helpful AI assistant.")
        
    def _get_tools(self) -> List[str]:
        tool_map = {
            AgentType.RESEARCHER: ["web_search", "search_documents", "deep_research"],
            AgentType.ANALYST: ["data_analysis", "statistical_analysis", "pattern_recognition"],
            AgentType.CODER: ["code_generation", "code_review", "debugging", "testing"],
            AgentType.CREATIVE: ["brainstorming", "ideation", "metaphor_generation"],
            AgentType.CRITIC: ["critical_analysis", "vulnerability_assessment", "quality_review"],
            AgentType.PLANNER: ["task_decomposition", "scheduling", "resource_planning"]
        }
        return tool_map.get(self.type, [])
        
    def execute(self, task: str, context: Dict = None) -> str:
        """Execute task with agent's expertise"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task}
        ]
        
        if context:
            messages.insert(1, {
                "role": "assistant",
                "content": f"Context: {context}"
            })
            
        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=1500
        )
        
        return response.choices[0].message.content

class MultiAgentOrchestrator:
    def __init__(self, groq_client):
        self.client = groq_client
        self.agents = {}
        self.executor = ThreadPoolExecutor(max_workers=5)
        self._initialize_agents()
        
    def _initialize_agents(self):
        for agent_type in AgentType:
            self.agents[agent_type] = SpecializedAgent(agent_type, self.client)
            
    def plan_task(self, task: str) -> Dict[str, Any]:
        """Plan how to execute a task using multiple agents"""
        planner = self.agents[AgentType.PLANNER]
        plan = planner.execute(f"""
        Create a detailed plan for: {task}
        
        Include:
        1. Which agents should be involved
        2. Step-by-step execution order
        3. Dependencies between steps
        4. Expected outputs
        
        Format as JSON with keys: steps, agents, dependencies
        """)
        
        # Parse plan (simplified)
        return {"plan": plan, "agent_types": self._extract_agents(plan)}
        
    def _extract_agents(self, plan: str) -> List[AgentType]:
        """Extract agent types from plan"""
        # Simple extraction - would be more sophisticated in production
        agents = []
        for agent_type in AgentType:
            if agent_type.value in plan.lower():
                agents.append(agent_type)
        return agents or [AgentType.RESEARCHER, AgentType.ANALYST]
        
    def execute_parallel(self, task: str, agents: List[AgentType]) -> Dict[AgentType, str]:
        """Execute task with multiple agents in parallel"""
        contexts = {}
        results = {}
        
        # Prepare contexts
        for agent_type in agents:
            contexts[agent_type] = self.agents[agent_type]._get_system_prompt()
            
        # Execute in parallel
        futures = []
        for agent_type in agents:
            future = self.executor.submit(
                self.agents[agent_type].execute,
                f"From your perspective, analyze: {task}",
                {"context": contexts[agent_type]}
            )
            futures.append((agent_type, future))
            
        for agent_type, future in futures:
            try:
                results[agent_type] = future.result(timeout=30)
            except Exception as e:
                results[agent_type] = f"Error: {str(e)}"
                
        return results
        
    def synthesize_results(self, results: Dict[AgentType, str]) -> str:
        """Synthesize outputs from multiple agents"""
        synthesis_prompt = """
        Synthesize these expert perspectives into a comprehensive response:
        
        """
        
        for agent_type, result in results.items():
            synthesis_prompt += f"\n[{agent_type.value.upper()}]\n{result}\n"
            
        synthesis_prompt += "\n\nProvide a unified, coherent response that integrates all perspectives."
        
        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": synthesis_prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
        
    def execute_with_delegation(self, task: str) -> str:
        """Execute task with dynamic agent delegation"""
        # 1. Plan
        plan = self.plan_task(task)
        
        # 2. Select agents based on plan
        agents = plan.get("agent_types", [AgentType.RESEARCHER, AgentType.ANALYST])
        
        # 3. Execute in parallel
        results = self.execute_parallel(task, agents)
        
        # 4. Synthesize
        final_response = self.synthesize_results(results)
        
        return final_response
