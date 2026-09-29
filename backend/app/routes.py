import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from .database import get_db
from .gmail_service import get_gmail_service, send_ticket_reply
from .gmail_sync import synchronize_incoming_emails
from .models import Ticket, TicketConversationMessage
from .schemas import (
    TicketClassificationRequest,
    TicketCustomerReplyDecisionRequest,
    TicketCreate,
    TicketReplyRequest,
    TicketReplyResponse,
    TicketResolutionResponse,
    TicketResponse,
)
from .ticket_service import confirm_ticket_classification
from .ticket_service import decide_ambiguous_customer_reply
from .ticket_service import create_ticket as create_ticket_record
from .ticket_service import resolve_ticket

router = APIRouter()
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
@router.get("/gmail/profile")
def get_gmail_profile() -> dict[str, str | int]:
    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    return {
        "emailAddress": profile["emailAddress"],
        "messagesTotal": profile["messagesTotal"],
        "threadsTotal": profile["threadsTotal"],
    }


@router.post("/gmail/sync")
def sync_gmail_tickets(
    confirm: bool = Query(
        False,
        description="Must be true to explicitly trigger Gmail synchronization.",
    ),
    max_results: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail synchronization requires confirm=true.",
        )

    try:
        return synchronize_incoming_emails(db, max_results=max_results)
    except HttpError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gmail API synchronization failed.",
        ) from error


@router.get("/tickets", response_model=list[TicketResponse])
def list_tickets(
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = None,
    priority: str | None = None,
    db: Session = Depends(get_db),
) -> list[Ticket]:
    query = db.query(Ticket)
    if status_filter is not None:
        query = query.filter(Ticket.status == status_filter)
    if category is not None:
        query = query.filter(Ticket.category == category)
    if priority is not None:
        query = query.filter(Ticket.priority == priority)
    return query.order_by(Ticket.id).all()


@router.put("/tickets/{ticket_id}/classification", response_model=TicketResponse)
def confirm_classification(
    ticket_id: str,
    classification: TicketClassificationRequest,
    db: Session = Depends(get_db),
) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    try:
        return confirm_ticket_classification(
            db,
            ticket,
            category=classification.category,
            priority=classification.priority,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.post("/tickets/{ticket_id}/customer-reply-decision", response_model=TicketResponse)
def decide_customer_reply(
    ticket_id: str,
    decision: TicketCustomerReplyDecisionRequest,
    db: Session = Depends(get_db),
) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    try:
        return decide_ambiguous_customer_reply(db, ticket, status=decision.status)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/tickets/{ticket_id}/reply",
    response_model=TicketReplyResponse,
)
def send_ticket_reply_to_customer(
    ticket_id: str,
    reply_data: TicketReplyRequest,
    db: Session = Depends(get_db),
) -> TicketReplyResponse:
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    customer_email = ticket.customer_email.strip()
    reply_text = reply_data.reply_text.strip()
    if not _EMAIL_PATTERN.fullmatch(customer_email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ticket has an invalid customer email address.",
        )
    if not reply_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Reply text cannot be blank.",
        )

    subject = ticket.subject.strip()
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    try:
        gmail_service = get_gmail_service()
        sent = send_ticket_reply(
            gmail_service,
            customer_email=customer_email,
            subject=subject,
            body=reply_text,
            thread_id=ticket.gmail_thread_id,
            original_message_id=ticket.gmail_message_id,
        )
    except FileNotFoundError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gmail OAuth credentials are not configured on the backend.",
        ) from error
    except (GoogleAuthError, ValueError) as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gmail authorization is unavailable or invalid. Reauthorize the Gmail account.",
        ) from error
    except HttpError as error:
        db.rollback()
        if error.status_code in {401, 403}:
            detail = "Gmail authorization was rejected. Reauthorize the Gmail account."
        elif error.status_code and error.status_code >= 500:
            detail = "Gmail is temporarily unavailable. Try again later."
        else:
            detail = "Gmail rejected the reply request. Verify the ticket's Gmail message data."
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from error
    except OSError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The backend could not access Gmail. Try again later.",
        ) from error

    sent_at = datetime.now(timezone.utc)
    if ticket.gmail_thread_id is None and sent["thread_id"]:
        ticket.gmail_thread_id = sent["thread_id"]
    conversation_message = TicketConversationMessage(
        ticket_id=ticket.id,
        direction="outgoing",
        body=reply_text,
        sent_at=sent_at,
        gmail_message_id=sent["message_id"],
        gmail_thread_id=sent["thread_id"],
    )
    ticket.status = "In Progress"
    ticket.review_status = "agent_replied"
    db.add(conversation_message)
    db.commit()

    return TicketReplyResponse(
        ticket_id=ticket.ticket_id,
        direction=conversation_message.direction,
        sent_at=conversation_message.sent_at,
        gmail_message_id=conversation_message.gmail_message_id,
        gmail_thread_id=conversation_message.gmail_thread_id,
    )


@router.post(
    "/tickets/{ticket_id}/resolve",
    response_model=TicketResolutionResponse,
)
def resolve_ticket_for_customer(
    ticket_id: str,
    db: Session = Depends(get_db),
) -> TicketResolutionResponse:
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    sent = resolve_ticket(db, ticket)
    return TicketResolutionResponse(
        ticket_id=ticket.ticket_id,
        status=ticket.status,
        resolution_email_sent=sent,
        resolution_email_error=ticket.resolution_email_error,
    )


@router.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket(ticket_data: TicketCreate, db: Session = Depends(get_db)) -> Ticket:
    ticket = create_ticket_record(
        db,
        customer_name=ticket_data.customer_name,
        customer_email=ticket_data.customer_email,
        subject=ticket_data.subject,
        message=ticket_data.message,
    )

    return ticket
