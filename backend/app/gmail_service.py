import base64
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


_BACKEND_DIR = Path(__file__).resolve().parents[1]
_CREDENTIALS_PATH = _BACKEND_DIR / "credentials.json"
_TOKEN_PATH = _BACKEND_DIR / "token.json"


def get_gmail_service() -> Resource:
    """Return an authenticated Gmail API client, refreshing or creating credentials as needed."""
    credentials = None

    if _TOKEN_PATH.exists():
        credentials = Credentials.from_authorized_user_file(
            str(_TOKEN_PATH),
            SCOPES,
        )

    if credentials is None or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not _CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Gmail OAuth credentials not found at {_CREDENTIALS_PATH}"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(_CREDENTIALS_PATH),
                SCOPES,
            )

            credentials = flow.run_local_server(port=0)

        _TOKEN_PATH.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

    return build("gmail", "v1", credentials=credentials)


def send_ticket_reply(
    service: Resource,
    *,
    customer_email: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
    original_message_id: str | None = None,
) -> dict[str, str | None]:
    """Send an email while preserving the existing Gmail conversation thread."""

    message = EmailMessage()

    message["To"] = customer_email
    message["Subject"] = subject

    if original_message_id:
        original_headers = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=original_message_id,
                format="metadata",
                metadataHeaders=["Message-ID", "References"],
            )
            .execute()
            .get("payload", {})
            .get("headers", [])
        )

        headers = {
            header.get("name", "").lower(): header.get("value", "")
            for header in original_headers
        }

        message_id_header = headers.get("message-id")
        references = headers.get("references", "")

        if message_id_header:
            message["In-Reply-To"] = message_id_header
            message["References"] = (
                f"{references} {message_id_header}".strip()
            )

    message.set_content(body)

    send_body: dict[str, str] = {
        "raw": base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode("ascii")
    }

    if thread_id:
        send_body["threadId"] = thread_id

    sent_message = (
        service.users()
        .messages()
        .send(
            userId="me",
            body=send_body,
        )
        .execute()
    )

    return {
        "message_id": sent_message.get("id"),
        "thread_id": sent_message.get("threadId") or thread_id,
    }


def build_ticket_acknowledgement_body(
    *,
    customer_name: str,
    subject: str,
) -> str:
    """Build the acknowledgement email sent when a new ticket is created."""

    customer_name = customer_name.strip() or "Customer"
    subject = subject.strip() or "your support request"

    return (
        f"Hi {customer_name},\n\n"
        f"Thank you for contacting TicketIQ Support. We have received your "
        f"support request regarding \"{subject}\" and our team is currently "
        f"reviewing the issue. We understand the importance of getting your "
        f"concern addressed and will process your request carefully.\n\n"
        "If any additional information is required from you, we will contact "
        "you through this email conversation. Thank you for your patience and "
        "understanding.\n\n"
        "Regards,\n"
        "TicketIQ Support"
    )


def send_ticket_acknowledgement(
    service: Resource,
    *,
    customer_name: str,
    customer_email: str,
    subject: str,
    thread_id: str | None = None,
    original_message_id: str | None = None,
) -> dict[str, str | None]:
    """Send the initial acknowledgement for a newly created ticket."""

    return send_ticket_reply(
        service,
        customer_email=customer_email,
        subject="We received your support request",
        body=build_ticket_acknowledgement_body(
            customer_name=customer_name,
            subject=subject,
        ),
        thread_id=thread_id,
        original_message_id=original_message_id,
    )


def send_resolution_email(
    service: Resource,
    *,
    customer_email: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
    original_message_id: str | None = None,
) -> dict[str, str | None]:
    """Send the resolution email in the existing customer email thread."""

    resolution_subject = (
        subject
        if subject.lower().startswith("re:")
        else f"Re: {subject}"
    )

    return send_ticket_reply(
        service,
        customer_email=customer_email,
        subject=resolution_subject,
        body=body,
        thread_id=thread_id,
        original_message_id=original_message_id,
    )