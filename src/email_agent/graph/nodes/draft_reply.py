from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from email_agent.graph.state import EmailAgentState
from email_agent.llm.prompts import DRAFT_SYSTEM_PROMPT
from email_agent.models import ClassificationResult, DraftReply, NormalizedEmail


def make_draft_reply_node(llm: ChatOpenAI):
    drafter = llm.with_structured_output(DraftReply)

    def draft_reply(state: EmailAgentState) -> EmailAgentState:
        normalized_email = NormalizedEmail.model_validate(state["normalized_email"])
        classification = ClassificationResult.model_validate(state["classification"])
        context = state.get("retrieved_context", {})

        prompt = (
            "Draft a reply for this email.\n\n"
            f"Intent: {classification.intent}\n"
            f"Urgency: {classification.urgency}\n"
            f"Risk: {classification.risk}\n"
            f"Reason: {classification.reason}\n\n"
            f"Sender: {normalized_email.sender}\n"
            f"Subject: {normalized_email.subject}\n"
            f"Body: {normalized_email.clean_body}\n\n"
            "Use any prior thread history to stay consistent and avoid repeating "
            "questions that were already answered.\n\n"
            f"Context: {context}"
        )
        draft = drafter.invoke(
            [
                SystemMessage(content=DRAFT_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        return {"draft": draft.model_dump(), "status": "drafted"}

    return draft_reply
