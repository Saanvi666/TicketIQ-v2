import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from ml.classifier import predict_category

from .models import Ticket, TicketConversationMessage
from .gmail_service import (
    get_gmail_service,
    send_resolution_email,
)
from .ticket_workflow import CATEGORIES, PRIORITIES, route_ticket

logger = logging.getLogger(__name__)


def generate_ticket_id(db: Session) -> str:
    while True:
        ticket_id = f"TKT-{uuid4().hex[:8].upper()}"

        if (
            db.query(Ticket)
            .filter(Ticket.ticket_id == ticket_id)
            .first()
            is None
        ):
            return ticket_id


def create_ticket(
    db: Session,
    *,
    customer_name: str,
    customer_email: str,
    subject: str,
    message: str,
    gmail_message_id: str | None = None,
    gmail_thread_id: str | None = None,
) -> Ticket:

    predicted_category, confidence = predict_category(
        subject,
        message,
    )

    from .ticket_workflow import assign_priority

    ai_priority, priority_reason = assign_priority(
        subject,
        message,
    )

    assigned_team, review_status = route_ticket(
        predicted_category,
        confidence,
    )

    requires_review = review_status != "auto_routed"

    ticket = Ticket(
        ticket_id=generate_ticket_id(db),
        customer_name=customer_name,
        customer_email=customer_email,
        subject=subject,
        message=message,
        ai_category=predicted_category,
        ai_priority=ai_priority,
        category=(
            None
            if requires_review
            else predicted_category
        ),
        priority=(
            None
            if requires_review
            else ai_priority
        ),
        priority_reason=priority_reason,
        confidence=confidence,
        status="New",
        assigned_team=assigned_team,
        review_status=review_status,
        gmail_message_id=gmail_message_id,
        gmail_thread_id=gmail_thread_id,
    )

    db.add(ticket)
    db.flush()

    db.add(
        TicketConversationMessage(
            ticket_id=ticket.id,
            direction="incoming",
            body=message,
            sent_at=ticket.created_at,
            gmail_message_id=gmail_message_id,
            gmail_thread_id=gmail_thread_id,
        )
    )

    db.commit()
    db.refresh(ticket)

    return ticket


def resolve_ticket(
    db: Session,
    ticket: Ticket,
    gmail_service=None,
) -> bool:
    """
    Generate and send one resolution email.

    After successful delivery:
        ticket -> Awaiting Customer

    If email generation or delivery fails:
        ticket -> Resolved
        resolution_email_error is stored
    """

    # Already successfully sent.
    if ticket.resolution_email_sent_at is not None:
        return True

    # These states should not trigger another resolution email.
    if ticket.status in {"Awaiting Customer", "Closed"}:
        return False

    # If already resolved with no previous error, avoid duplicate sending.
    if ticket.status == "Resolved" and not ticket.resolution_email_error:
        return False

    ticket.status = "Resolved"
    ticket.resolution_email_error = None
    db.commit()

    try:
        conversation = [
            {
                "direction": message.direction,
                "body": message.body,
            }
            for message in (
                db.query(TicketConversationMessage)
                .filter(
                    TicketConversationMessage.ticket_id
                    == ticket.id
                )
                .order_by(
                    TicketConversationMessage.sent_at
                )
                .all()
            )
            if message.direction in {
                "incoming",
                "outgoing",
            }
        ]

        from .ai_drafting import generate_resolution_email

        generated_body = generate_resolution_email(
            ticket,
            conversation,
        )

        email_body = generated_body.strip()

        if not email_body:
            raise ValueError(
                "Generated resolution email is empty"
            )

        gmail_service = (
            gmail_service
            or get_gmail_service()
        )

        sent = send_resolution_email(
            gmail_service,
            customer_email=ticket.customer_email,
            subject=ticket.subject,
            body=email_body,
            thread_id=ticket.gmail_thread_id,
            original_message_id=ticket.gmail_message_id,
        )

        sent_at = datetime.now(timezone.utc)

        ticket.resolution_email_sent_at = sent_at
        ticket.resolution_email_message_id = (
            sent.get("message_id")
        )
        ticket.resolution_email_error = None

        # Only move to Awaiting Customer after the email
        # was successfully delivered.
        ticket.status = "Awaiting Customer"

        db.add(
            TicketConversationMessage(
                ticket_id=ticket.id,
                direction="system",
                body=email_body,
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

        return True

    except Exception as error:
        db.rollback()

        error_message = (
            str(error)[:2000]
            or error.__class__.__name__
        )

        logger.exception(
            "Resolution email failed for ticket %s",
            ticket.ticket_id,
        )

        ticket = (
            db.query(Ticket)
            .filter(Ticket.id == ticket.id)
            .one()
        )

        ticket.status = "Resolved"
        ticket.resolution_email_error = error_message

        db.commit()

        return False


def confirm_ticket_classification(
    db: Session,
    ticket: Ticket,
    *,
    category: str,
    priority: str,
) -> Ticket:

    if priority not in PRIORITIES:
        raise ValueError("Unsupported priority")

    category = category.strip()

    if category not in CATEGORIES:
        raise ValueError("Unsupported category")

    assigned_team, _ = route_ticket(
        category,
        1.0,
    )

    ticket.category = category
    ticket.priority = priority
    ticket.assigned_team = assigned_team
    ticket.review_status = "agent_confirmed"

    db.add(
        TicketConversationMessage(
            ticket_id=ticket.id,
            direction="system",
            body=(
                f"Agent confirmed category: {category}; "
                f"priority: {priority}."
            ),
        )
    )

    db.commit()
    db.refresh(ticket)

    return ticket


def decide_ambiguous_customer_reply(
    db: Session,
    ticket: Ticket,
    *,
    status: str,
) -> Ticket:

    if status not in {"Closed", "Reopened"}:
        raise ValueError(
            "Customer reply decision must be Closed or Reopened"
        )

    if (
        ticket.status != "Awaiting Customer"
        or not ticket.customer_reply_review_required
    ):
        raise ValueError(
            "Ticket has no ambiguous customer reply awaiting review"
        )

    return apply_customer_confirmation(
        db,
        ticket,
        status=status,
        event_body=(
            "Agent reviewed the customer reply and set "
            f"the ticket to {status}."
        ),
    )


def apply_customer_confirmation(
    db: Session,
    ticket: Ticket,
    *,
    status: str,
    event_body: str,
) -> Ticket:

    if status not in {"Closed", "Reopened"}:
        raise ValueError(
            "Unsupported customer decision"
        )

    if ticket.status != "Awaiting Customer":
        raise ValueError(
            "Ticket is no longer awaiting customer confirmation"
        )

    ticket.status = status
    ticket.customer_reply_review_required = False

    if status == "Reopened":
        ticket.resolution_email_sent_at = None
        ticket.resolution_email_message_id = None
        ticket.resolution_email_error = None

    db.add(
        TicketConversationMessage(
            ticket_id=ticket.id,
            direction="system",
            body=event_body,
        )
    )

    db.commit()
    db.refresh(ticket)

    return ticket