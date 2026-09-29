import argparse
import os

from sqlalchemy import delete

from app.database import SessionLocal, engine
from app.models import Ticket, TicketConversationMessage

_PLACEHOLDER_NAMES = {"string", "test", "test customer", "example"}
_PLACEHOLDER_SUBJECTS = {"string"}


def is_test_ticket(ticket: Ticket) -> bool:
    customer_name = (ticket.customer_name or "").strip().casefold()
    subject = (ticket.subject or "").strip().casefold()
    email = (ticket.customer_email or "").strip().casefold()
    email_domain = email.rsplit("@", 1)[-1]
    return (
        customer_name in _PLACEHOLDER_NAMES
        or subject in _PLACEHOLDER_SUBJECTS
        or email_domain in {"example.com", "example.org", "example.net", "invalid"}
        or ("ticketiq" in subject and "test" in subject)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview or remove obvious development test tickets and their conversation records."
    )
    parser.add_argument(
        "--confirm-development-reset",
        action="store_true",
        help="Delete matching test tickets; requires TICKETIQ_ENV=development.",
    )
    arguments = parser.parse_args()

    if engine.dialect.name != "sqlite":
        parser.error("This development cleanup script only supports SQLite databases.")
    if arguments.confirm_development_reset and os.getenv("TICKETIQ_ENV") != "development":
        parser.error("Set TICKETIQ_ENV=development before confirming this cleanup.")

    with SessionLocal() as db:
        candidates = [ticket for ticket in db.query(Ticket).all() if is_test_ticket(ticket)]
        candidate_ids = [ticket.id for ticket in candidates]
        conversation_count = (
            db.query(TicketConversationMessage)
            .filter(TicketConversationMessage.ticket_id.in_(candidate_ids))
            .count()
            if candidate_ids
            else 0
        )

        if not arguments.confirm_development_reset:
            print(
                f"Dry run: {len(candidate_ids)} test tickets and "
                f"{conversation_count} related conversation messages match explicit test markers."
            )
            print("No records were changed. Re-run with --confirm-development-reset to delete these records.")
            return 0

        if not candidate_ids:
            print("No test tickets matched. No records were changed.")
            return 0

        db.execute(
            delete(TicketConversationMessage).where(
                TicketConversationMessage.ticket_id.in_(candidate_ids)
            )
        )
        db.execute(delete(Ticket).where(Ticket.id.in_(candidate_ids)))
        db.commit()
        remaining = db.query(Ticket).filter(Ticket.id.in_(candidate_ids)).count()
        if remaining:
            raise RuntimeError("Cleanup did not remove all selected test tickets")

    print(
        f"Removed {len(candidate_ids)} marked test tickets and "
        f"{conversation_count} related conversation messages."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())