from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String)
    customer_email: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    ai_category: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_priority: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    priority: Mapped[str | None] = mapped_column(String, nullable=True)
    priority_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="New")
    assigned_team: Mapped[str | None] = mapped_column(String, nullable=True)
    review_status: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_reply_review_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    acknowledgement_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledgement_message_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    acknowledgement_error: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    resolution_email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_email_message_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    resolution_email_error: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    gmail_message_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    gmail_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    conversation_messages: Mapped[list["TicketConversationMessage"]] = relationship(
        order_by="TicketConversationMessage.sent_at"
    )



class TicketConversationMessage(Base):
    __tablename__ = "ticket_conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id"), index=True
    )
    direction: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    gmail_message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)


