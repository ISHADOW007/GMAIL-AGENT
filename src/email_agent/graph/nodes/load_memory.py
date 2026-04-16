"""Node that loads sender/thread memory from the optional Mongo store."""
from __future__ import annotations

from email_agent.db.mongo import MongoMemoryStore
from email_agent.graph.state import EmailAgentState
from email_agent.models import NormalizedEmail


def make_load_memory_node(memory_store: MongoMemoryStore):
    def load_memory(state: EmailAgentState) -> EmailAgentState:
        normalized_email = NormalizedEmail.model_validate(state["normalized_email"])
        memory = memory_store.load_memory_bundle(normalized_email)
        return {"memory": memory.model_dump()}

    return load_memory

