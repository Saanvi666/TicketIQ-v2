import base64
import binascii
import logging
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr
import re
from typing import Any

from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from .gmail_service import (
    build_ticket_acknowledgement_body,
    get_gmail_service,
    send_ticket_acknowledgement,
)
from .models import Ticket, TicketConversationMessage
from .ticket_service import create_ticket
from .ticket_workflow import (
    awaiting_customer_wait_period,
    interpret_customer_resolution,
)


class MalformedGmailMessage(ValueError):
    pass


logger = logging.getLogger(__name__)

_EMAIL_PATTERN = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)

_PLACEHOLDER_VALUES = {
    "string",
    "test",
    "example",
    "null",
    "none",
}

_AUTOMATED_LOCAL_PARTS = {
    "mailer-daemon",
    "no-reply",
    "noreply",
    "do-not-reply",
    "donotreply",
    "postmaster",
}


def _decode_text(data: str | None) -> str:
    if not data:
        return ""

    return base64.urlsafe_b64decode(
        data.encode("ascii") + b"==="
    ).decode(
        "utf-8",
        errors="replace",
    )


def _header_value(
    headers: list[dict[str, str]],
    name: str,
) -> str:
    value = next(
        (
            header.get("value", "")
            for header in headers
            if header.get("name", "").lower()
            == name.lower()
        ),
        "",
    )

    try:
        return str(make_header(decode_header(value)))
    except (LookupError, UnicodeError):
        return value


def _find_body(payload: dict[str, Any]) -> str:
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        return _decode_text(body_data).strip()

    for part in payload.get("parts", []) or []:
        body = _find_body(part)

        if body:
            return body

    return ""


def _is_automated_message(
    headers: list[dict[str, str]],
    sender_email: str,
) -> bool:
    header_values = {
        header.get("name", "").lower():
        header.get("value", "").strip().lower()
        for header in headers
    }

    if header_values.get("auto-submitted", "") not in {"", "no"}:
        return True

    if header_values.get("precedence", "") in {
        "bulk",
        "list",
        "junk",
    }:
        return True

    if (
        header_values.get("list-id")
        or header_values.get("list-unsubscribe")
    ):
        return True

    return (
        sender_email.split("@", 1)[0].lower()
        in _AUTOMATED_LOCAL_PARTS
    )


def extract_gmail_message(
    message: dict[str, Any],
) -> dict[str, str]:

    message_id = message.get("id")
    thread_id = message.get("threadId")

    payload = message.get("payload") or {}
    headers = payload.get("headers") or []

    sender = _header_value(
        headers,
        "From",
    ).strip()

    subject = _header_value(
        headers,
        "Subject",
    ).strip()

    body = _find_body(payload).strip()

    sender_name, sender_email = parseaddr(sender)

    sender_email = sender_email.strip().lower()

    if (
        not message_id
        or not thread_id
        or not sender_email
        or not _EMAIL_PATTERN.fullmatch(sender_email)
        or sender_email.split("@", 1)[0]
        in _PLACEHOLDER_VALUES
        or not subject
        or subject.lower() in _PLACEHOLDER_VALUES
        or not body
        or body.lower() in _PLACEHOLDER_VALUES
    ):
        raise MalformedGmailMessage(
            "Gmail message is missing required ticket fields"
        )

    return {
        "gmail_message_id": message_id,
        "gmail_thread_id": thread_id,
        "customer_name": sender_name or sender_email,
        "customer_email": sender_email,
        "subject": subject,
        "message": body,
    }


def synchronize_incoming_emails(
    db: Session,
    *,
    max_results: int = 25,
) -> dict[str, int]:

    service = get_gmail_service()

    listed = (
        service.users()
        .messages()
        .list(
            userId="me",
            q=(
                "is:unread "
                "-from:me "
                "-in:sent "
                "-category:promotions "
                "-category:social "
                "-category:updates"
            ),
            maxResults=max_results,
        )
        .execute()
    )

    result = {
        "fetched": 0,
        "created": 0,
        "customer_replies": 0,
        "closed": 0,
        "reopened": 0,
        "ambiguous": 0,
        "auto_closed": 0,
        "duplicates": 0,
        "malformed": 0,
        "ignored": 0,
    }

    for message_ref in listed.get("messages", []) or []:

        message_id = message_ref.get("id")

        if not message_id:
            result["malformed"] += 1
            continue

        result["fetched"] += 1

        # Prevent duplicate tickets and duplicate conversation entries.
        if (
            db.query(Ticket)
            .filter(
                Ticket.gmail_message_id == message_id
            )
            .first()
            or
            db.query(TicketConversationMessage)
            .filter(
                TicketConversationMessage.gmail_message_id
                == message_id
            )
            .first()
        ):
            result["duplicates"] += 1
            continue

        try:
            message = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="full",
                )
                .execute()
            )

            if "SENT" in (
                message.get("labelIds") or []
            ):
                result["ignored"] += 1
                continue

            payload = message.get("payload") or {}
            headers = payload.get("headers") or []

            _, sender_email = parseaddr(
                _header_value(
                    headers,
                    "From",
                )
            )

            if _is_automated_message(
                headers,
                sender_email.strip().lower(),
            ):
                result["ignored"] += 1
                continue

            email_data = extract_gmail_message(
                message
            )

            # Check whether this email belongs to an
            # existing ticket waiting for customer confirmation.
            awaiting_ticket = (
                db.query(Ticket)
                .filter(
                    Ticket.gmail_thread_id
                    == email_data["gmail_thread_id"],
                    Ticket.status
                    == "Awaiting Customer",
                )
                .first()
            )

            if awaiting_ticket is not None:

                _process_customer_reply(
                    db,
                    awaiting_ticket,
                    email_data,
                    result,
                )

                service.users().messages().modify(
                    userId="me",
                    id=message_id,
                    body={
                        "removeLabelIds": ["UNREAD"]
                    },
                ).execute()

                continue

            # Otherwise this is a new support request.
            ticket = create_ticket(
                db,
                **email_data,
            )

            # Send acknowledgement after the ticket has
            # successfully been created.
            _send_ticket_acknowledgement(
                db,
                service,
                ticket,
            )

            service.users().messages().modify(
                userId="me",
                id=message_id,
                body={
                    "removeLabelIds": ["UNREAD"]
                },
            ).execute()

            result["created"] += 1

        except (
            MalformedGmailMessage,
            binascii.Error,
            UnicodeError,
        ):
            result["malformed"] += 1

        except HttpError:
            db.rollback()
            raise

    # Automatically close tickets that have waited
    # beyond the configured customer-response period.
    result["auto_closed"] = (
        close_overdue_awaiting_customer_tickets(db)
    )

    return result


def close_overdue_awaiting_customer_tickets(
    db: Session,
    *,
    now: datetime | None = None,
) -> int:

    current_time = (
        now
        or datetime.now(timezone.utc)
    )

    cutoff = (
        current_time
        - awaiting_customer_wait_period()
    )

    tickets = (
        db.query(Ticket)
        .filter(
            Ticket.status
            == "Awaiting Customer",
            Ticket.resolution_email_sent_at.isnot(None),
        )
        .all()
    )

    closed = 0

    for ticket in tickets:

        sent_at = (
            ticket.resolution_email_sent_at
        )

        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(
                tzinfo=timezone.utc
            )

        if sent_at > cutoff:
            continue

        ticket.status = "Closed"

        db.add(
            TicketConversationMessage(
                ticket_id=ticket.id,
                direction="system",
                body=(
                    "Ticket automatically closed after "
                    "the customer response waiting period."
                ),
                sent_at=current_time,
                gmail_thread_id=ticket.gmail_thread_id,
            )
        )

        closed += 1

    if closed:
        db.commit()

    return closed


def _process_customer_reply(
    db: Session,
    ticket: Ticket,
    email_data: dict[str, str],
    result: dict[str, int],
) -> None:

    decision = interpret_customer_resolution(
        email_data["message"]
    )

    conversation_message = TicketConversationMessage(
        ticket_id=ticket.id,
        direction="incoming",
        body=email_data["message"],
        sent_at=datetime.now(timezone.utc),
        gmail_message_id=email_data[
            "gmail_message_id"
        ],
        gmail_thread_id=email_data[
            "gmail_thread_id"
        ],
    )

    db.add(conversation_message)

    result["customer_replies"] += 1

    if decision is None:

        result["ambiguous"] += 1

        ticket.customer_reply_review_required = True

        logger.info(
            "Ambiguous customer resolution reply "
            "for ticket %s",
            ticket.ticket_id,
        )

    else:

        ticket.status = decision
        ticket.customer_reply_review_required = False

        decision_message = (
            "Customer confirmed that the issue was resolved."
            if decision == "Closed"
            else
            "Customer reported that the issue is still unresolved."
        )

        db.add(
            TicketConversationMessage(
                ticket_id=ticket.id,
                direction="system",
                body=decision_message,
                sent_at=datetime.now(timezone.utc),
                gmail_thread_id=ticket.gmail_thread_id,
            )
        )

        if decision == "Reopened":
            ticket.resolution_email_sent_at = None
            ticket.resolution_email_message_id = None
            ticket.resolution_email_error = None

        result[decision.lower()] += 1

        logger.info(
            "Customer resolution reply changed "
            "ticket %s to %s",
            ticket.ticket_id,
            decision,
        )

    db.commit()


def _send_ticket_acknowledgement(
    db: Session,
    service: Any,
    ticket: Ticket,
) -> None:

    # Prevent duplicate acknowledgement emails.
    if ticket.acknowledgement_sent_at is not None:
        return

    try:

        sent = send_ticket_acknowledgement(
            service,
            customer_name=ticket.customer_name,
            customer_email=ticket.customer_email,
            subject=ticket.subject,
            thread_id=ticket.gmail_thread_id,
            original_message_id=ticket.gmail_message_id,
        )

        sent_at = datetime.now(timezone.utc)

        ticket.acknowledgement_sent_at = sent_at
        ticket.acknowledgement_message_id = (
            sent.get("message_id")
        )
        ticket.acknowledgement_error = None

        db.add(
            TicketConversationMessage(
                ticket_id=ticket.id,
                direction="system",
                body=build_ticket_acknowledgement_body(
                    customer_name=ticket.customer_name,
                    subject=ticket.subject,
                ),
                sent_at=sent_at,
                gmail_message_id=sent.get(
                    "message_id"
                ),
                gmail_thread_id=sent.get(
                    "thread_id"
                ),
            )
        )

        db.commit()

    except Exception as error:

        db.rollback()

        message = (
            str(error)[:2000]
            or error.__class__.__name__
        )

        logger.exception(
            "Automatic acknowledgement failed "
            "for ticket %s",
            ticket.ticket_id,
        )

        ticket = (
            db.query(Ticket)
            .filter(
                Ticket.id == ticket.id
            )
            .one()
        )

        ticket.acknowledgement_error = message

        db.commit()