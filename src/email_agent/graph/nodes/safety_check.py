"""Node that applies deterministic safety and policy checks before delivery."""
from __future__ import annotations

from email_agent.graph.state import EmailAgentState
from email_agent.models import ClassificationResult, SafetyResult


def make_safety_check_node():
    def safety_check(state: EmailAgentState) -> EmailAgentState:
        classification = ClassificationResult.model_validate(state["classification"])

        issues: list[str] = []
        policy_tags: list[str] = []

        if classification.intent in {"billing", "complaint"}:
            issues.append("Billing and complaint emails require human approval.")
            policy_tags.append("requires_human_review")

        if classification.action in {"human_review", "escalate"}:
            issues.append("Classification already requested human oversight.")
            policy_tags.append("model_requested_review")

        if classification.risk == "high":
            issues.append("High-risk email cannot be auto-sent.")
            policy_tags.append("high_risk")

        result = SafetyResult(
            safe_to_send=not issues and classification.risk == "low",
            needs_human=bool(issues) or classification.risk != "low",
            issues=issues,
            policy_tags=policy_tags,
        )
        return {"safety_result": result.model_dump()}

    return safety_check

