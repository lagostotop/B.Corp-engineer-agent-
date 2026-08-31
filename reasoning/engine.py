# reasoning/engine.py
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ReasoningMode(Enum):
    CHAIN_OF_THOUGHT = "cot"
    TREE_OF_THOUGHTS = "tot"
    SELF_CONSISTENCY = "self_consistency"
    REFLECTION = "reflection"

@dataclass
class ReasoningStep:
    thought: str
    confidence: float
    alternatives: List[str]
    verification: Optional[str] = None

class AdvancedReasoningEngine:
    def __init__(self, groq_client, model="llama-3.3-70b-versatile"):
        self.client = groq_client
        self.model = model
        
    def chain_of_thought(self, query: str, context: str = "", steps: int = 5) -> str:
        """Step-by-step reasoning with verification"""
        prompt = f"""Solve this problem step by step. 
        For each step, show your reasoning and confidence level (0-1).
        After all steps, provide a final answer.

        Context: {context}
        Query: {query}

        Format:
        Step 1: [reasoning] (Confidence: 0.X)
        Step 2: [reasoning] (Confidence: 0.X)
        ...
        Final Answer: [answer]"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        
        return response.choices[0].message.content

    def tree_of_thoughts(self, query: str, branches: int = 3, depth: int = 3) -> Dict:
        """Explore multiple reasoning paths and select best"""
        # Generate multiple initial approaches
        approaches_prompt = f"""
        Generate {branches} different approaches to solve: {query}
        Return as JSON: {{"approaches": ["approach1", "approach2", "approach3"]}}
        """
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": approaches_prompt}],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        approaches = json.loads(response.choices[0].message.content)["approaches"]
        
        # Explore each approach
        results = []
        for approach in approaches:
            # Recursive exploration
            path = self._explore_path(approach, query, depth)
            results.append({
                "approach": approach,
                "path": path,
                "score": self._evaluate_path(path)
            })
        
        # Select best path
        best = max(results, key=lambda x: x["score"])
        return {
            "best_approach": best["approach"],
            "reasoning_path": best["path"],
            "confidence": best["score"],
            "alternatives": results
        }

    def _explore_path(self, approach: str, query: str, depth: int) -> List[str]:
        if depth == 0:
            return [f"Final: {approach}"]
            
        prompt = f"""
        Approach: {approach}
        Question: {query}
        
        What's the next reasoning step? Consider alternatives.
        Provide 2-3 possible next steps with brief reasoning.
        """
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=300
        )
        
        step = response.choices[0].message.content
        return [step] + self._explore_path(f"{approach} -> {step[:50]}", query, depth-1)

    def _evaluate_path(self, path: List[str]) -> float:
        """Score the reasoning path quality"""
        evaluation_prompt = f"""
        Evaluate this reasoning path (score 0-1):
        {' -> '.join(path)}
        
        Consider: logic, completeness, clarity, accuracy potential.
        Return only a number.
        """
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": evaluation_prompt}],
            temperature=0.1,
            max_tokens=50
        )
        
        try:
            return float(response.choices[0].message.content.strip())
        except:
            return 0.5

    def self_consistency(self, query: str, n: int = 5) -> Dict:
        """Generate multiple answers and vote on best"""
        answers = []
        confidence_scores = []
        
        for i in range(n):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Provide a clear, concise answer."},
                    {"role": "user", "content": query}
                ],
                temperature=0.8 + (i * 0.05),  # Vary temperature for diversity
                max_tokens=500
            )
            answers.append(response.choices[0].message.content)
            
            # Self-evaluate confidence
            confidence = self._get_confidence(response.choices[0].message.content, query)
            confidence_scores.append(confidence)
        
        # Find consensus answer
        consensus = self._find_consensus(answers)
        
        return {
            "answer": consensus,
            "confidence": max(confidence_scores),
            "alternatives": answers,
            "scores": confidence_scores
        }

    def _get_confidence(self, answer: str, query: str) -> float:
        prompt = f"""
        Query: {query}
        Answer: {answer}
        
        Rate your confidence in this answer (0-1). Consider:
        - Certainty of facts
        - Logical coherence
        - Completeness
        
        Return only a number.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=10
        )
        try:
            return float(response.choices[0].message.content.strip())
        except:
            return 0.5

    def _find_consensus(self, answers: List[str]) -> str:
        """Find consensus among multiple answers using clustering"""
        # Simple: return most common or first if all unique
        return max(set(answers), key=answers.count) if answers else ""
