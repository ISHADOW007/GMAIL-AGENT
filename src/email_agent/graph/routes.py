from __future__ import annotations

from email_agent.graph.state import EmailAgentState
from email_agent.models import ClassificationResult, HumanDecision, SafetyResult


def route_after_classification(state: EmailAgentState) -> str:
    classification = ClassificationResult.model_validate(state["classification"])

    if classification.action == "ignore":
        return "ignore_email"

    if classification.intent in {"spam", "newsletter"}:
        return "ignore_email"

    if classification.action in {"human_review", "escalate"}:
        return "human_review"

    return "retrieve_context"


def route_after_safety(state: EmailAgentState) -> str:
    safety = SafetyResult.model_validate(state["safety_result"])
    if safety.needs_human or not safety.safe_to_send:
        return "human_review"
    return "send_or_save"


def route_after_human_review(state: EmailAgentState) -> str:
    decision = HumanDecision.model_validate(state["human_decision"])
    if decision.decision == "approve":
        return "send_or_save"
    if decision.decision == "revise":
        return "revise_reply"
    return "update_memory"
