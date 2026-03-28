from __future__ import annotations

import base64
import imaplib
import json
import re
import smtplib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.message import EmailMessage as SmtpEmailMessage
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from typing import Any
from uuid import uuid4

from email_agent.config import Settings
from email_agent.models import DraftReply, EmailMessage, OutboxMessage

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:  # pragma: no cover - optional dependency until gmail backend is used
    Request = None
    Credentials = None
    InstalledAppFlow = None
    build = None


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]


def _sort_emails_newest_first(emails: list[EmailMessage]) -> list[EmailMessage]:
    return sorted(emails, key=lambda email: email.received_at, reverse=True)


def _sort_emails_oldest_first(emails: list[EmailMessage]) -> list[EmailMessage]:
    return sorted(emails, key=lambda email: email.received_at)


def _gmail_fetch_window(limit: int) -> int:
    return max(limit, min(limit * 5, 100))


def _gmail_outcome_label_name(outcome: str | None, prefix: str) -> str | None:
    label_suffix = {
        "ignored": "Ignored",
        "pending_human_review": "Needs-Human",
        "draft_saved": "Drafted",
        "sent": "Sent",
        "rejected_after_review": "Rejected",
        "approved_without_delivery": "Approved",
    }.get(outcome or "")
    if not label_suffix:
        return None
    return f"{prefix}-{label_suffix}"


def _append_human_review(path: Path, original_email: EmailMessage, reason: str) -> None:
    rows: list[dict[str, Any]] = []
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
    rows.append(
        {
            "review_id": f"review-{uuid4().hex}",
            "email_id": original_email.id,
            "thread_id": original_email.thread_id,
            "from_address": original_email.from_address,
            "subject": original_email.subject,
            "reason": reason,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def _append_human_review_with_metadata(
    path: Path,
    original_email: EmailMessage,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))

    item = {
        "review_id": f"review-{uuid4().hex}",
        "email_id": original_email.id,
        "thread_id": original_email.thread_id,
        "from_address": original_email.from_address,
        "subject": original_email.subject,
        "reason": reason,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if metadata:
        item.update(metadata)

    rows.append(item)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return item


def _build_reply_message(
    original_email: EmailMessage,
    draft: DraftReply,
    from_address: str | None = None,
) -> SmtpEmailMessage:
    message = SmtpEmailMessage()
    if from_address:
        message["From"] = from_address
    message["To"] = original_email.from_address
    message["Subject"] = draft.subject
    if original_email.message_id:
        message["In-Reply-To"] = original_email.message_id
        message["References"] = original_email.message_id
    message.set_content(draft.body)
    return message


def _parse_internal_date(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _decode_gmail_body(data: str | None) -> str:
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    decoded = base64.urlsafe_b64decode(data + padding)
    return decoded.decode("utf-8", errors="replace")


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _extract_gmail_body(payload: dict[str, Any]) -> str:
    body = payload.get("body", {})
    if payload.get("mimeType") == "text/plain" and body.get("data"):
        return _decode_gmail_body(body["data"])

    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in payload.get("parts", []):
        mime_type = part.get("mimeType")
        part_body = part.get("body", {})
        if mime_type == "text/plain" and part_body.get("data"):
            plain_parts.append(_decode_gmail_body(part_body["data"]))
        elif mime_type == "text/html" and part_body.get("data"):
            html_parts.append(_strip_html(_decode_gmail_body(part_body["data"])))
        else:
            nested = _extract_gmail_body(part)
            if nested:
                plain_parts.append(nested)

    if plain_parts:
        return "\n".join(item for item in plain_parts if item).strip()
    if html_parts:
        return "\n".join(item for item in html_parts if item).strip()
    if body.get("data"):
        return _decode_gmail_body(body["data"])
    return ""


def _email_message_from_gmail_api_message(raw_message: dict[str, Any]) -> EmailMessage:
    payload = raw_message.get("payload", {})
    headers = {
        header["name"].lower(): header["value"]
        for header in payload.get("headers", [])
    }
    return EmailMessage(
        id=raw_message["id"],
        thread_id=raw_message.get("threadId"),
        message_id=headers.get("message-id"),
        from_address=headers.get("from", ""),
        to_address=headers.get("to", ""),
        subject=headers.get("subject", "(No subject)"),
        body=_extract_gmail_body(payload),
        received_at=_parse_internal_date(raw_message.get("internalDate")),
        is_unread="UNREAD" in raw_message.get("labelIds", []),
    )


class MailboxClient(ABC):
    @abstractmethod
    def fetch_unread(self, limit: int) -> list[EmailMessage]:
        raise NotImplementedError

    @abstractmethod
    def save_draft(self, original_email: EmailMessage, draft: DraftReply) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_email(self, original_email: EmailMessage, draft: DraftReply) -> None:
        raise NotImplementedError

    @abstractmethod
    def fetch_thread_messages(
        self,
        thread_id: str | None,
        current_email_id: str | None = None,
    ) -> list[EmailMessage]:
        raise NotImplementedError

    @abstractmethod
    def mark_processed(self, email_id: str, outcome: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def flag_for_human_review(
        self,
        original_email: EmailMessage,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError


class LocalMailboxClient(MailboxClient):
    def __init__(self, inbox_path: Path, outbox_path: Path) -> None:
        self.inbox_path = inbox_path
        self.outbox_path = outbox_path
        self.review_queue_path = self.outbox_path.parent / "review_queue.json"
        self.outbox_path.parent.mkdir(parents=True, exist_ok=True)

    def fetch_unread(self, limit: int) -> list[EmailMessage]:
        emails = [EmailMessage.model_validate(item) for item in self._read_json(self.inbox_path)]
        unread = [email for email in emails if email.is_unread]
        return _sort_emails_newest_first(unread)[:limit]

    def save_draft(self, original_email: EmailMessage, draft: DraftReply) -> None:
        self._append_outbox(
            OutboxMessage(
                email_id=original_email.id,
                action="draft_saved",
                to_address=original_email.from_address,
                subject=draft.subject,
                body=draft.body,
                created_at=datetime.now(timezone.utc),
            )
        )

    def fetch_thread_messages(
        self,
        thread_id: str | None,
        current_email_id: str | None = None,
    ) -> list[EmailMessage]:
        if not thread_id:
            return []
        emails = [EmailMessage.model_validate(item) for item in self._read_json(self.inbox_path)]
        thread_messages = [
            email
            for email in emails
            if email.thread_id == thread_id and email.id != current_email_id
        ]
        return _sort_emails_oldest_first(thread_messages)

    def send_email(self, original_email: EmailMessage, draft: DraftReply) -> None:
        self._append_outbox(
            OutboxMessage(
                email_id=original_email.id,
                action="sent",
                to_address=original_email.from_address,
                subject=draft.subject,
                body=draft.body,
                created_at=datetime.now(timezone.utc),
            )
        )

    def mark_processed(self, email_id: str, outcome: str | None = None) -> None:
        rows = self._read_json(self.inbox_path)
        updated: list[dict[str, Any]] = []
        for row in rows:
            if row.get("id") == email_id:
                row = {**row, "is_unread": False}
            updated.append(row)
        self._write_json(self.inbox_path, updated)

    def flag_for_human_review(
        self,
        original_email: EmailMessage,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _append_human_review_with_metadata(
            self.review_queue_path,
            original_email,
            reason,
            metadata=metadata,
        )

    def _append_outbox(self, message: OutboxMessage) -> None:
        rows = self._read_json(self.outbox_path)
        rows.append(message.model_dump(mode="json"))
        self._write_json(self.outbox_path, rows)

    @staticmethod
    def _read_json(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, payload: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class GmailMailboxClient(MailboxClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.review_queue_path = Path("data/review_queue.json")
        self._service = self._build_service()
        self._label_cache: dict[str, str] | None = None

    def fetch_unread(self, limit: int) -> list[EmailMessage]:
        messages: list[EmailMessage] = []
        for item in self._list_unread_message_refs(limit):
            raw_message = (
                self._service.users()
                .messages()
                .get(
                    userId=self.settings.gmail_user_id,
                    id=item["id"],
                    format="full",
                )
                .execute()
            )
            messages.append(_email_message_from_gmail_api_message(raw_message))
        return _sort_emails_newest_first(messages)[:limit]

    def save_draft(self, original_email: EmailMessage, draft: DraftReply) -> None:
        message = _build_reply_message(
            original_email,
            draft,
            from_address=self.settings.default_from_address,
        )
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        body: dict[str, Any] = {"message": {"raw": encoded_message}}
        if original_email.thread_id:
            body["message"]["threadId"] = original_email.thread_id
        (
            self._service.users()
            .drafts()
            .create(userId=self.settings.gmail_user_id, body=body)
            .execute()
        )

    def send_email(self, original_email: EmailMessage, draft: DraftReply) -> None:
        message = _build_reply_message(
            original_email,
            draft,
            from_address=self.settings.default_from_address,
        )
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        body: dict[str, Any] = {"raw": encoded_message}
        if original_email.thread_id:
            body["threadId"] = original_email.thread_id
        (
            self._service.users()
            .messages()
            .send(userId=self.settings.gmail_user_id, body=body)
            .execute()
        )

    def fetch_thread_messages(
        self,
        thread_id: str | None,
        current_email_id: str | None = None,
    ) -> list[EmailMessage]:
        if not thread_id:
            return []
        raw_thread = (
            self._service.users()
            .threads()
            .get(
                userId=self.settings.gmail_user_id,
                id=thread_id,
                format="full",
            )
            .execute()
        )
        messages = [
            _email_message_from_gmail_api_message(item)
            for item in raw_thread.get("messages", [])
            if item.get("id") != current_email_id
        ]
        return _sort_emails_oldest_first(messages)

    def mark_processed(self, email_id: str, outcome: str | None = None) -> None:
        body: dict[str, Any] = {"removeLabelIds": ["UNREAD"]}
        label_name = _gmail_outcome_label_name(outcome, self.settings.gmail_label_prefix)
        if label_name:
            body["addLabelIds"] = [self._get_or_create_label_id(label_name)]
        (
            self._service.users()
            .messages()
            .modify(
                userId=self.settings.gmail_user_id,
                id=email_id,
                body=body,
            )
            .execute()
        )

    def flag_for_human_review(
        self,
        original_email: EmailMessage,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _append_human_review_with_metadata(
            self.review_queue_path,
            original_email,
            reason,
            metadata=metadata,
        )

    def _build_service(self):
        if not all([Request, Credentials, InstalledAppFlow, build]):
            raise ImportError(
                "Gmail backend requires google-api-python-client, "
                "google-auth-httplib2, and google-auth-oauthlib."
            )

        creds = None
        token_path = self.settings.gmail_token_path
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(token_path),
                GMAIL_SCOPES,
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                credentials_path = self.settings.gmail_credentials_path
                if not credentials_path.exists():
                    raise ValueError(
                        "GMAIL_CREDENTIALS_PATH is missing. Download your OAuth client "
                        "credentials JSON from Google Cloud and place it at "
                        f"{credentials_path}."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path),
                    GMAIL_SCOPES,
                )
                print("Starting Gmail OAuth login...")
                if self.settings.gmail_open_browser:
                    print("Opening your browser for Google sign-in.")
                else:
                    print(
                        "Browser auto-open is disabled. Copy the Google sign-in URL "
                        "from the terminal if it appears and open it manually."
                    )
                creds = flow.run_local_server(
                    port=0,
                    open_browser=self.settings.gmail_open_browser,
                )

            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")

        return build("gmail", "v1", credentials=creds)

    def _list_unread_message_refs(self, limit: int) -> list[dict[str, Any]]:
        response = (
            self._service.users()
            .messages()
            .list(
                userId=self.settings.gmail_user_id,
                labelIds=["INBOX", "UNREAD"],
                maxResults=_gmail_fetch_window(limit),
            )
            .execute()
        )
        return response.get("messages", [])

    def _get_or_create_label_id(self, label_name: str) -> str:
        if self._label_cache is None:
            response = self._service.users().labels().list(
                userId=self.settings.gmail_user_id
            ).execute()
            self._label_cache = {
                label["name"]: label["id"] for label in response.get("labels", [])
            }

        if label_name in self._label_cache:
            return self._label_cache[label_name]

        created = (
            self._service.users()
            .labels()
            .create(
                userId=self.settings.gmail_user_id,
                body={
                    "name": label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        label_id = created["id"]
        self._label_cache[label_name] = label_id
        return label_id


class ImapSmtpMailboxClient(MailboxClient):
    def __init__(self, settings: Settings) -> None:
        missing = [
            name
            for name, value in {
                "IMAP_HOST": settings.imap_host,
                "IMAP_USERNAME": settings.imap_username,
                "IMAP_PASSWORD": settings.imap_password,
                "SMTP_HOST": settings.smtp_host,
                "SMTP_USERNAME": settings.smtp_username,
                "SMTP_PASSWORD": settings.smtp_password,
                "DEFAULT_FROM_ADDRESS": settings.default_from_address,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing IMAP/SMTP settings: {joined}")

        self.settings = settings

    def fetch_unread(self, limit: int) -> list[EmailMessage]:
        messages: list[EmailMessage] = []
        with imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port) as client:
            client.login(self.settings.imap_username, self.settings.imap_password)
            client.select("INBOX")
            _, data = client.search(None, "UNSEEN")
            ids = data[0].split()
            for message_id in ids:
                _, message_data = client.fetch(message_id, "(RFC822)")
                raw_message = message_data[0][1]
                parsed = BytesParser(policy=default).parsebytes(raw_message)
                body = self._extract_body(parsed)
                messages.append(
                    EmailMessage(
                        id=message_id.decode("utf-8"),
                        from_address=parsed.get("From", ""),
                        to_address=parsed.get("To", ""),
                        subject=parsed.get("Subject", "(No subject)"),
                        body=body,
                        received_at=datetime.now(timezone.utc),
                        is_unread=True,
                    )
                )
        return _sort_emails_newest_first(messages)[:limit]

    def save_draft(self, original_email: EmailMessage, draft: DraftReply) -> None:
        # SMTP does not create true mailbox drafts, so we persist a local preview.
        preview_dir = Path("data/drafts")
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / f"{original_email.id}.json"
        preview_path.write_text(
            json.dumps(
                {
                    "email_id": original_email.id,
                    "to_address": original_email.from_address,
                    "subject": draft.subject,
                    "body": draft.body,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def send_email(self, original_email: EmailMessage, draft: DraftReply) -> None:
        message = SmtpEmailMessage()
        message["From"] = self.settings.default_from_address
        message["To"] = original_email.from_address
        message["Subject"] = draft.subject
        message.set_content(draft.body)

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
            server.starttls()
            server.login(self.settings.smtp_username, self.settings.smtp_password)
            server.send_message(message)

    def fetch_thread_messages(
        self,
        thread_id: str | None,
        current_email_id: str | None = None,
    ) -> list[EmailMessage]:
        return []

    def mark_processed(self, email_id: str, outcome: str | None = None) -> None:
        with imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port) as client:
            client.login(self.settings.imap_username, self.settings.imap_password)
            client.select("INBOX")
            client.store(email_id, "+FLAGS", "\\Seen")

    def flag_for_human_review(
        self,
        original_email: EmailMessage,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        review_path = Path("data/review_queue.json")
        return _append_human_review_with_metadata(
            review_path,
            original_email,
            reason,
            metadata=metadata,
        )

    @staticmethod
    def _extract_body(message: Any) -> str:
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_content()
            return ""
        return message.get_content()


def build_mailbox_client(settings: Settings) -> MailboxClient:
    if settings.email_backend == "local":
        return LocalMailboxClient(settings.local_inbox_path, settings.local_outbox_path)
    if settings.email_backend == "gmail":
        return GmailMailboxClient(settings)
    if settings.email_backend == "imap_smtp":
        return ImapSmtpMailboxClient(settings)
    raise ValueError(f"Unsupported EMAIL_BACKEND: {settings.email_backend}")
