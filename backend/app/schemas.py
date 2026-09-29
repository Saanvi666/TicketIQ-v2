from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .ticket_workflow import CATEGORIES


class TicketCreate(BaseModel):
    customer_name: str
    customer_email: str = Field(
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    subject: str
    message: str


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: str
    customer_name: str
    customer_email: str
    subject: str
    message: str
    ai_category: str | None
    ai_priority: str | None
    category: str | None
    priority: str | None
    priority_reason: str | None
    confidence: float | None
    status: str
    assigned_team: str | None
    review_status: str | None
    customer_reply_review_required: bool
    created_at: datetime
    updated_at: datetime
    conversation_messages: list["ConversationMessageResponse"] = Field(default_factory=list)


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    direction: str
    body: str
    sent_at: datetime


class TicketClassificationRequest(BaseModel):
    category: str = Field(min_length=1, max_length=200)
    priority: str

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        if value not in CATEGORIES:
            raise ValueError("Unsupported category")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        if value not in {"Urgent", "High", "Medium", "Low"}:
            raise ValueError("Unsupported priority")
        return value


class TicketCustomerReplyDecisionRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"Closed", "Reopened"}:
            raise ValueError("Customer reply decision must be Closed or Reopened")
        return value


class TicketReplyRequest(BaseModel):
    reply_text: str = Field(min_length=1, max_length=10000)


class TicketReplyResponse(BaseModel):
    ticket_id: str
    direction: str
    sent_at: datetime
    gmail_message_id: str | None
    gmail_thread_id: str | None


class TicketResolutionResponse(BaseModel):
    ticket_id: str
    status: str
    resolution_email_sent: bool
    resolution_email_error: str | None = None
