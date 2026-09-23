from unittest.mock import MagicMock

from brain.context import build_context
from brain.orchestrator import BrainOrchestrator


class FakeRouter:
    def route(self,**kwargs):
        result=MagicMock()

        message=MagicMock()
        message.content="Test Brain response."

        choice=MagicMock()
        choice.message=message

        result.choices=[choice]

        return result


class FakePlanner:
    def needs_tools(self,question,mode="normal"):
        return False

    def plan(self,question,mode="normal"):
        return ["answer"]


class FakeVerifier:
    def check(self,answer,question="",evidence=None):
        return {
            "ok":bool(answer),
            "answer":answer,
            "issues":[],
            "evidence_used":bool(evidence),
        }


class FakeResearch:
    def run(self,**kwargs):
        return {
            "answer":"",
            "used_tools":[],
            "results":[],
            "plan":[],
        }


def test_orchestrator_returns_answer():
    context=build_context(
        user_id="user-1",
        chat_id="chat-1",
        question="Hello Brain",
        messages=[
            {
                "role":"user",
                "content":"Hello Brain",
            }
        ],
    )

    brain=BrainOrchestrator(
        router=FakeRouter(),
        planner=FakePlanner(),
        verifier=FakeVerifier(),
        research_agent=FakeResearch(),
    )

    result=brain.run(context)

    assert result["answer"]=="Test Brain response."
    assert result["verified"] is True
    assert result["used_tools"]==[]


def test_orchestrator_empty_question():
    context=build_context(
        user_id="user-1",
        chat_id="chat-1",
        question="",
        messages=[],
    )

    brain=BrainOrchestrator(
        router=FakeRouter(),
        planner=FakePlanner(),
        verifier=FakeVerifier(),
        research_agent=FakeResearch(),
    )

    result=brain.run(context)

    assert result["answer"]==""
    assert result["verified"] is False