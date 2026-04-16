"""Model exports used across the backend."""
from email_agent.models.classification import ClassificationResult
from email_agent.models.draft import DraftReply, OutboxMessage
from email_agent.models.email import EmailMessage, NormalizedEmail
from email_agent.models.memory import ContactMemory, MemoryBundle, MemoryExtraction, ThreadMemory
from email_agent.models.review import HumanDecision, SafetyResult

__all__ = [
    "ClassificationResult",
    "ContactMemory",
    "DraftReply",
    "EmailMessage",
    "HumanDecision",
    "MemoryBundle",
    "MemoryExtraction",
    "NormalizedEmail",
    "OutboxMessage",
    "SafetyResult",
    "ThreadMemory",
]

