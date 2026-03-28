from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from email_agent.graph.state import EmailAgentState
from email_agent.llm.prompts import CLASSIFICATION_SYSTEM_PROMPT
from email_agent.models import ClassificationResult, MemoryBundle, NormalizedEmail


def make_classify_email_node(llm: ChatOpenAI):
    classifier = llm.with_structured_output(ClassificationResult)

    def classify_email(state: EmailAgentState) -> EmailAgentState:
        normalized_email = NormalizedEmail.model_validate(state["normalized_email"])
        memory = MemoryBundle.model_validate(state.get("memory", {}))

        prompt = (
            "Classify this inbound email.\n\n"
            f"Sender: {normalized_email.sender}\n"
            f"Subject: {normalized_email.subject}\n"
            f"Body: {normalized_email.clean_body}\n\n"
            f"Contact importance: {memory.contact.importance if memory.contact else 'normal'}\n"
            f"Thread summary: {memory.thread.summary if memory.thread else 'None'}\n"
            f"Known business facts: {memory.business_facts or ['None']}\n"
        )
        classification = classifier.invoke(
            [
                SystemMessage(content=CLASSIFICATION_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )

        if memory.contact and memory.contact.importance == "vip":
            classification.action = "human_review"
            classification.risk = "high"
            classification.reason = f"{classification.reason} VIP sender requires human review."

        if classification.confidence < 0.7 and classification.action == "draft":
            classification.action = "human_review"
            classification.reason = (
                f"{classification.reason} Confidence below threshold, routing to human review."
            )

        return {
            "classification": classification.model_dump(),
            "status": "classified",
            "final_action": classification.action,
        }

    return classify_email
