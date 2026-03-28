from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from email_agent.graph.state import EmailAgentState
from email_agent.llm.prompts import REVISION_SYSTEM_PROMPT
from email_agent.models import DraftReply, HumanDecision


def make_revise_reply_node(llm: ChatOpenAI):
    reviser = llm.with_structured_output(DraftReply)

    def revise_reply(state: EmailAgentState) -> EmailAgentState:
        draft = DraftReply.model_validate(state["draft"])
        human_decision = HumanDecision.model_validate(state["human_decision"])
        revised = reviser.invoke(
            [
                SystemMessage(content=REVISION_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        "Revise this email draft using the reviewer comments.\n\n"
                        f"Current subject: {draft.subject}\n"
                        f"Current body: {draft.body}\n"
                        f"Reviewer comments: {human_decision.comments or 'No comments provided.'}"
                    )
                ),
            ]
        )
        revised.version = draft.version + 1
        return {"draft": revised.model_dump(), "status": "drafted"}

    return revise_reply
