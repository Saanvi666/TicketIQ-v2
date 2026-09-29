import os
from datetime import timedelta
import re

PRIORITIES = ("Urgent", "High", "Medium", "Low")
CATEGORIES = (
    "Account, Security & Login",
    "App, Website & Feedback",
    "Order Modifications & Cancellations",
    "Payment & Invoicing",
    "Product, Warranty & Tech Specs",
    "Returns, Refunds & Exchanges",
    "Shipping & Delivery",
)


def awaiting_customer_wait_period() -> timedelta:
    try:
        hours = int(os.getenv("AWAITING_CUSTOMER_HOURS", "48"))
        if hours > 0:
            return timedelta(hours=hours)
    except ValueError:
        pass
    return timedelta(hours=48)

_UNRESOLVED_REPLY_PHRASES = (
    "not resolved",
    "isn't resolved",
    "is not resolved",
    "unresolved",
    "still having the issue",
    "not fixed",
    "isn't fixed",
    "is not fixed",
    "not working",
    "still doesn't work",
    "still does not work",
    "doesn't work",
    "does not work",
    "issue persists",
    "still broken",
)

_PRIORITY_RULES = (
    (
        "Urgent",
        (
            "security breach",
            "account hacked",
            "fraud",
            "stolen",
            "unauthorized access",
            "identity theft",
        ),
        "Security or fraud-related language detected",
    ),
    (
        "High",
        (
            "cannot login",
            "can't login",
            "failed payment",
            "payment failed",
            "charged twice",
            "not received",
            "overdue",
            "damaged",
            "lost",
        ),
        "Service-impacting or time-sensitive language detected",
    ),
    (
        "Medium",
        (
            "refund",
            "return",
            "exchange",
            "cancel",
            "invoice",
            "billing",
            "payment",
        ),
        "Transaction or account-action language detected",
    ),
)


def assign_priority(subject: str, message: str) -> tuple[str, str]:
    text = f"{subject} {message}".lower()
    for priority, keywords, reason in _PRIORITY_RULES:
        matched_keyword = next((keyword for keyword in keywords if keyword in text), None)
        if matched_keyword:
            return priority, f"{reason}: '{matched_keyword}'"
    return "Low", "No urgent or time-sensitive indicators detected"


def interpret_customer_resolution(message: str) -> str | None:
    """Return closed/reopened for clear replies, otherwise leave the ticket unchanged."""
    reply_text = re.split(
        r"(?:\r?\n)\s*(?:on .{1,240}?\bwrote:|[-_]{2,}\s*original message\s*[-_]{2,}|"
        r"begin forwarded message:|from:\s*[^\r\n]+)",
        message.strip(),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    reply_text = re.split(
        r"\s+on .{1,240}?\bwrote:\s*",
        reply_text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    reply_text = re.split(r"(?:\r?\n)\s*>", reply_text, maxsplit=1)[0]
    normalized = re.sub(r"\s+", " ", reply_text.strip().lower())
    if not normalized:
        return None

    if re.search(
        r"\b(?:not sure|unsure|uncertain|maybe|perhaps|don't think|do not think|"
        r"don't know|do not know)\b",
        normalized,
    ):
        return None

    if normalized in {"no", "no.", "no!", "no, it's not", "no, it isn't", "no, it is not"} or any(
        phrase in normalized for phrase in _UNRESOLVED_REPLY_PHRASES
    ):
        return "Reopened"

    if normalized in {"yes", "yes.", "yes, it is", "yes, it's resolved", "resolved", "fixed"}:
        return "Closed"
    if re.search(r"\byes\b.{0,30}\b(?:resolved|fixed|solved)\b", normalized):
        return "Closed"
    if re.search(
        r"\b(?:it|this|the issue|everything)\s+(?:is|was|has been)\s+"
        r"(?:now\s+)?(?:resolved|fixed|solved)\b|"
        r"\b(?:it's|it is)\s+working(?: now)?\b|"
        r"\b(?:working now|works now|fixed it|issue is solved|all good now)\b",
        normalized,
    ):
        return "Closed"
    return None


def route_ticket(category: str, confidence: float) -> tuple[str, str]:
    category_text = category.lower()
    team_keywords = {
        "Account & Security Team": ("account", "security", "login"),
        "Website & App Team": ("app", "website", "feedback"),
        "Orders Team": ("order", "modification", "cancellation"),
        "Payments Team": ("payment", "invoicing"),
        "Product Support Team": ("product", "warranty", "tech specs"),
        "Returns Team": ("return", "refund", "exchange"),
        "Shipping Team": ("shipping", "delivery"),
    }
    assigned_team = next(
        (
            team
            for team, keywords in team_keywords.items()
            if any(keyword in category_text for keyword in keywords)
        ),
        "General Support Team",
    )

    if confidence >= 0.85:
        review_status = "auto_routed"
    elif confidence >= 0.70:
        review_status = "review_required"
    else:
        review_status = "agent_review_required"

    return assigned_team, review_status
