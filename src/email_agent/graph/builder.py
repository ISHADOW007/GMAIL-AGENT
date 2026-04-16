"""LangGraph builder that wires nodes, routes, and optional progress callbacks together."""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph

from email_agent.config import Settings
from email_agent.db.mongo import MongoMemoryStore
from email_agent.graph.nodes.classify_email import make_classify_email_node
from email_agent.graph.nodes.draft_reply import make_draft_reply_node
from email_agent.graph.nodes.human_review import make_human_review_node
from email_agent.graph.nodes.ignore_email import make_ignore_email_node
from email_agent.graph.nodes.load_memory import make_load_memory_node
from email_agent.graph.nodes.load_thread import make_load_thread_node
from email_agent.graph.nodes.mark_processed import make_mark_processed_node
from email_agent.graph.nodes.normalize_email import make_normalize_email_node
from email_agent.graph.nodes.queue_human_review import make_queue_human_review_node
from email_agent.graph.nodes.retrieve_context import make_retrieve_context_node
from email_agent.graph.nodes.revise_reply import make_revise_reply_node
from email_agent.graph.nodes.safety_check import make_safety_check_node
from email_agent.graph.nodes.send_or_save import make_send_or_save_node
from email_agent.graph.nodes.update_memory import make_update_memory_node
from email_agent.graph.routes import (
    route_after_classification,
    route_after_human_review,
    route_after_safety,
)
from email_agent.graph.state import EmailAgentState
from email_agent.mailbox import MailboxClient


def _wrap_node(node_name: str, node_fn, progress_callback=None):
    if progress_callback is None:
        return node_fn

    def wrapped_node(state: EmailAgentState):
        # Keep progress reporting outside the node implementations so the same
        # business logic can run with or without the dashboard hooks attached.
        progress_callback("start", node_name, state)
        try:
            result = node_fn(state)
        except GraphInterrupt as error:
            interrupts = []
            if error.args:
                interrupts = [
                    getattr(interrupt, "value", interrupt)
                    for interrupt in error.args[0]
                ]
            progress_callback("interrupt", node_name, {"interrupts": interrupts})
            raise
        except Exception as error:
            progress_callback("error", node_name, {"error": str(error)})
            raise
        progress_callback("complete", node_name, result)
        return result

    return wrapped_node


def build_email_graph(
    llm: ChatOpenAI,
    mailbox: MailboxClient,
    settings: Settings,
    memory_store: MongoMemoryStore | None = None,
    checkpointer=None,
    progress_callback=None,
):
    memory_store = memory_store or MongoMemoryStore.from_settings(settings)

    graph = StateGraph(EmailAgentState)
    graph.add_node(
        "normalize_email",
        _wrap_node("normalize_email", make_normalize_email_node(), progress_callback),
    )
    graph.add_node(
        "load_thread",
        _wrap_node("load_thread", make_load_thread_node(mailbox), progress_callback),
    )
    graph.add_node(
        "load_memory",
        _wrap_node("load_memory", make_load_memory_node(memory_store), progress_callback),
    )
    graph.add_node(
        "classify_email",
        _wrap_node("classify_email", make_classify_email_node(llm), progress_callback),
    )
    graph.add_node(
        "ignore_email",
        _wrap_node("ignore_email", make_ignore_email_node(), progress_callback),
    )
    graph.add_node(
        "retrieve_context",
        _wrap_node("retrieve_context", make_retrieve_context_node(), progress_callback),
    )
    graph.add_node(
        "draft_reply",
        _wrap_node("draft_reply", make_draft_reply_node(llm), progress_callback),
    )
    graph.add_node(
        "safety_check",
        _wrap_node("safety_check", make_safety_check_node(), progress_callback),
    )
    graph.add_node(
        "queue_human_review",
        _wrap_node(
            "queue_human_review",
            make_queue_human_review_node(mailbox, memory_store),
            progress_callback,
        ),
    )
    graph.add_node(
        "human_review",
        _wrap_node(
            "human_review",
            make_human_review_node(),
            progress_callback,
        ),
    )
    graph.add_node(
        "revise_reply",
        _wrap_node("revise_reply", make_revise_reply_node(llm), progress_callback),
    )
    graph.add_node(
        "send_or_save",
        _wrap_node("send_or_save", make_send_or_save_node(mailbox, settings), progress_callback),
    )
    graph.add_node(
        "update_memory",
        _wrap_node("update_memory", make_update_memory_node(memory_store, llm), progress_callback),
    )
    graph.add_node(
        "mark_processed",
        _wrap_node("mark_processed", make_mark_processed_node(mailbox), progress_callback),
    )

    graph.add_edge(START, "normalize_email")
    graph.add_edge("normalize_email", "load_thread")
    graph.add_edge("load_thread", "load_memory")
    graph.add_edge("load_memory", "classify_email")
    # The first branch decides whether this email is ignored, drafted, or
    # paused immediately for a human before any reply is generated.
    graph.add_conditional_edges(
        "classify_email",
        route_after_classification,
        {
            "ignore_email": "ignore_email",
            "human_review": "queue_human_review",
            "retrieve_context": "retrieve_context",
        },
    )
    graph.add_edge("ignore_email", "update_memory")
    graph.add_edge("retrieve_context", "draft_reply")
    graph.add_edge("draft_reply", "safety_check")
    # A drafted reply can still be diverted into review if the safety node
    # decides the response should not continue automatically.
    graph.add_conditional_edges(
        "safety_check",
        route_after_safety,
        {
            "human_review": "queue_human_review",
            "send_or_save": "send_or_save",
        },
    )
    graph.add_edge("queue_human_review", "human_review")
    # Once a review item exists, later approve / revise / reject actions resume
    # from that saved state rather than restarting the whole graph.
    graph.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "send_or_save": "send_or_save",
            "revise_reply": "revise_reply",
            "update_memory": "update_memory",
        },
    )
    graph.add_edge("revise_reply", "queue_human_review")
    graph.add_edge("send_or_save", "update_memory")
    graph.add_edge("update_memory", "mark_processed")
    graph.add_edge("mark_processed", END)

    return graph.compile(
        checkpointer=checkpointer,
        store=getattr(memory_store, "store", None),
    )

