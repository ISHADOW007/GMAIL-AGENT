"""Node that assembles prompt-ready context from live thread data and stored memory."""
from __future__ import annotations

from email_agent.graph.state import EmailAgentState
from email_agent.models import MemoryBundle, NormalizedEmail


def make_retrieve_context_node():
    def retrieve_context(state: EmailAgentState) -> EmailAgentState:
        normalized_email = NormalizedEmail.model_validate(state["normalized_email"])
        memory = MemoryBundle.model_validate(state.get("memory", {}))
        live_thread_summary = state.get("thread_summary")
        live_thread_messages = state.get("thread_messages", [])

        context = {
            "sender": normalized_email.sender,
            "thread_summary": live_thread_summary
            or (memory.thread.summary if memory.thread else None),
            "thread_history": live_thread_messages,
            "recent_messages": memory.thread.recent_messages if memory.thread else [],
            "business_facts": memory.business_facts,
            "similar_replies": memory.similar_replies[:3],
        }
        return {"retrieved_context": context}

    return retrieve_context

