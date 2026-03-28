from __future__ import annotations

from email_agent.db.mongo import MongoMemoryStore
from email_agent.graph.state import EmailAgentState


def make_update_memory_node(memory_store: MongoMemoryStore):
    def update_memory(state: EmailAgentState) -> EmailAgentState:
        memory_store.update_after_run(state)
        return {}

    return update_memory
