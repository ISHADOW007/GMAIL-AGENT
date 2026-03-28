from __future__ import annotations

import unittest

from email_agent.graph.routes import route_after_classification


def _classification_state(**overrides: object) -> dict:
    classification = {
        "intent": "sales",
        "urgency": "low",
        "risk": "low",
        "action": "draft",
        "reason": "Default route test classification.",
        "confidence": 0.9,
    }
    classification.update(overrides)
    return {"classification": classification}


class RouteAfterClassificationTests(unittest.TestCase):
    def test_routes_action_ignore_to_ignore_email(self) -> None:
        state = _classification_state(intent="other", action="ignore")

        route = route_after_classification(state)

        self.assertEqual(route, "ignore_email")

    def test_routes_newsletter_intent_to_ignore_email(self) -> None:
        state = _classification_state(intent="newsletter", action="draft")

        route = route_after_classification(state)

        self.assertEqual(route, "ignore_email")

    def test_routes_human_review_actions_to_human_review(self) -> None:
        state = _classification_state(intent="other", action="human_review")

        route = route_after_classification(state)

        self.assertEqual(route, "human_review")

    def test_routes_draft_action_to_retrieve_context(self) -> None:
        state = _classification_state(intent="sales", action="draft")

        route = route_after_classification(state)

        self.assertEqual(route, "retrieve_context")


if __name__ == "__main__":
    unittest.main()
