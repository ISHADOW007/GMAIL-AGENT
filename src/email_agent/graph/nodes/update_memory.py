"""Node that persists the final workflow outcome back into the memory store."""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from email_agent.db.mongo import MongoMemoryStore
from email_agent.graph.state import EmailAgentState


def make_update_memory_node(memory_store: MongoMemoryStore, llm: ChatOpenAI):
    def update_memory(state: EmailAgentState) -> EmailAgentState:
        memory_store.update_after_run(state, llm=llm)
        return {}

    return update_memory
