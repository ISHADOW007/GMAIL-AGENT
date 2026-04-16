"""Node that pauses the graph with LangGraph interrupt until a human responds."""
from __future__ import annotations

from datetime import datetime, timezone

from langgraph.types import interrupt

from email_agent.graph.state import EmailAgentState
from email_agent.models import ClassificationResult, HumanDecision


def make_human_review_node():
    def human_review(state: EmailAgentState) -> EmailAgentState:
        classification = ClassificationResult.model_validate(state["classification"])
        decision_payload = interrupt(
            {
                "review_id": state.get("review_id"),
                "email_id": state.get("email_id"),
                "thread_id": state.get("thread_id"),
                "reason": classification.reason,
                "subject": state.get("email", {}).get("subject"),
                "from_address": state.get("email", {}).get("from_address"),
                "draft": state.get("draft"),
                "classification": state.get("classification"),
            }
        )
        human_decision = HumanDecision.model_validate(decision_payload)

        result: EmailAgentState = {
            "review_id": state.get("review_id", ""),
            "human_decision": human_decision.model_dump(mode="json"),
        }
        if human_decision.decision == "approve" and not state.get("draft"):
            result.update(
                {
                    "delivery_status": "approved_without_delivery",
                    "status": "approved",
                    "final_action": "approved",
                }
            )
        elif human_decision.decision == "reject":
            result.update(
                {
                    "delivery_status": "rejected_after_review",
                    "status": "rejected",
                    "final_action": "reject",
                }
            )
        elif human_decision.decision == "approve":
            result["status"] = "approved"
        elif human_decision.decision == "revise":
            result["status"] = "pending_human"
        else:
            result.update(
                {
                    "delivery_status": "pending_human_review",
                    "status": "pending_human",
                    "final_action": "human_review",
                }
            )

        if human_decision.reviewed_at is None:
            result["human_decision"] = HumanDecision(
                decision=human_decision.decision,
                comments=human_decision.comments,
                reviewer=human_decision.reviewer,
                reviewed_at=datetime.now(timezone.utc),
            ).model_dump(mode="json")

        return result

    return human_review
