from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import MagicMock, Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.gmail_sync import (
    _process_customer_reply,
    _send_ticket_acknowledgement,
    close_overdue_awaiting_customer_tickets,
    synchronize_incoming_emails,
)
from app.models import Ticket, TicketConversationMessage
from app.ticket_service import (
    confirm_ticket_classification,
    create_ticket,
    decide_ambiguous_customer_reply,
    resolve_ticket,
)


class TicketWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.db = self.session_factory()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create_ticket(self, confidence=0.9):
        with patch(
            "app.ticket_service.predict_category",
            return_value=("Shipping & Delivery", confidence),
        ):
            return create_ticket(
                self.db,
                customer_name="Alex Customer",
                customer_email="alex@example.com",
                subject="Package delivery",
                message="My package was not received.",
                gmail_message_id="message-1",
                gmail_thread_id="thread-1",
            )

    def test_high_similarity_classification_is_automatically_routed(self):
        ticket = self.create_ticket(confidence=0.9)
        self.assertEqual(ticket.ai_category, "Shipping & Delivery")
        self.assertEqual(ticket.category, "Shipping & Delivery")
        self.assertEqual(ticket.ai_priority, "High")
        self.assertEqual(ticket.priority, "High")
        self.assertEqual(ticket.review_status, "auto_routed")

    def test_low_similarity_classification_requires_agent_review(self):
        ticket = self.create_ticket(confidence=0.55)
        self.assertEqual(ticket.ai_category, "Shipping & Delivery")
        self.assertEqual(ticket.ai_priority, "High")
        self.assertIsNone(ticket.category)
        self.assertIsNone(ticket.priority)
        self.assertEqual(ticket.review_status, "agent_review_required")

    def test_agent_confirmation_stores_final_category_and_priority(self):
        ticket = self.create_ticket(confidence=0.55)
        confirmed = confirm_ticket_classification(
            self.db, ticket, category="Returns, Refunds & Exchanges", priority="Urgent"
        )
        self.assertEqual(confirmed.category, "Returns, Refunds & Exchanges")
        self.assertEqual(confirmed.priority, "Urgent")
        self.assertEqual(confirmed.review_status, "agent_confirmed")

    def test_resolution_generates_and_sends_customer_email_without_ticket_id(self):
        ticket = self.create_ticket()
        ticket.status = "In Progress"
        self.db.commit()
        generated_body = (
            "Hi Alex,\n\nWe have addressed your delivery issue.\n\n"
            "Please reply to this email. If resolved, reply YES - issue solved. "
            "If it remains unresolved, reply NO - issue not solved.\n\nTicketIQ Support"
        )
        with (
            patch("app.ai_drafting.generate_resolution_email", return_value=generated_body) as generate,
            patch(
                "app.ticket_service.send_resolution_email",
                return_value={"message_id": "sent-1", "thread_id": "thread-1"},
            ) as send,
        ):
            self.assertTrue(resolve_ticket(self.db, ticket, gmail_service=Mock()))
        generate.assert_called_once()
        send.assert_called_once()
        self.assertEqual(send.call_args.kwargs["customer_email"], "alex@example.com")
        sent_body = send.call_args.kwargs["body"]
        self.assertEqual(sent_body, generated_body)
        self.assertNotIn(ticket.ticket_id, send.call_args.kwargs["body"])
        self.assertIn("reply YES - issue solved", sent_body)
        self.assertIn("reply NO - issue not solved", sent_body)
        self.assertNotIn("localhost", sent_body)
        self.assertNotIn("href=", sent_body)
        self.assertIn("TicketIQ Support", sent_body)
        self.assertEqual(ticket.status, "Awaiting Customer")
        self.assertIsNotNone(ticket.resolution_email_sent_at)
        self.assertEqual(ticket.conversation_messages[-1].direction, "system")
        self.assertEqual(ticket.conversation_messages[-1].body, sent_body)

    def test_openrouter_resolution_prompt_excludes_internal_ticket_details(self):
        from app.ai_drafting import generate_resolution_email

        ticket = self.create_ticket()
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "Hi Alex,\n\nWe've addressed your issue.\n\nTicketIQ Support"}}]}
        ).encode("utf-8")
        conversation = [{"direction": "incoming", "body": ticket.message}]
        with (
            patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}),
            patch("app.ai_drafting.request.urlopen", return_value=response) as openrouter,
        ):
            email_body = generate_resolution_email(ticket, conversation)
        payload = json.loads(openrouter.call_args.args[0].data.decode("utf-8"))
        prompt = payload["messages"][0]["content"] + payload["messages"][1]["content"]
        self.assertNotIn(ticket.ticket_id, prompt)
        self.assertNotIn("review_status", prompt)
        self.assertIn("do not mention ai", prompt.lower())
        self.assertIn("reply 'yes - issue solved'", prompt.lower())
        self.assertIn("no - issue not solved", prompt.lower())
        self.assertNotIn("localhost", email_body.lower())
        self.assertIn("TicketIQ Support", email_body)

    def test_acknowledgement_is_recorded_without_ticket_id_and_sent_once(self):
        ticket = self.create_ticket()
        sent = {"message_id": "ack-1", "thread_id": "thread-1"}
        with patch("app.gmail_sync.send_ticket_acknowledgement", return_value=sent) as send:
            _send_ticket_acknowledgement(self.db, Mock(), ticket)
            _send_ticket_acknowledgement(self.db, Mock(), ticket)
        send.assert_called_once()
        self.assertIsNotNone(ticket.acknowledgement_sent_at)
        self.assertNotIn(ticket.ticket_id, ticket.conversation_messages[-1].body)

    def test_resolution_failure_does_not_record_a_successful_send(self):
        ticket = self.create_ticket()
        with (
            patch("app.ai_drafting.generate_resolution_email", return_value="Resolution body"),
            patch("app.ticket_service.send_resolution_email", side_effect=OSError("Gmail unavailable")),
        ):
            self.assertFalse(resolve_ticket(self.db, ticket, gmail_service=Mock()))
        self.assertEqual(ticket.status, "Resolved")
        self.assertIsNone(ticket.resolution_email_sent_at)
        self.assertIn("Gmail unavailable", ticket.resolution_email_error)

    def test_duplicate_resolution_attempt_does_not_send_twice(self):
        ticket = self.create_ticket()
        ticket.status = "In Progress"
        self.db.commit()
        with (
            patch("app.ai_drafting.generate_resolution_email", return_value="Resolution body"),
            patch(
                "app.ticket_service.send_resolution_email",
                return_value={"message_id": "sent-1", "thread_id": "thread-1"},
            ) as send,
        ):
            self.assertTrue(resolve_ticket(self.db, ticket, gmail_service=Mock()))
            self.assertTrue(resolve_ticket(self.db, ticket, gmail_service=Mock()))
        send.assert_called_once()

    def test_customer_confirms_resolution_and_ticket_closes(self):
        ticket = self.create_ticket()
        ticket.status = "Awaiting Customer"
        self.db.commit()
        _process_customer_reply(self.db, ticket, self.reply("It is resolved now."), self.reply_result())
        self.assertEqual(ticket.status, "Closed")

    def test_customer_confirmation_ignores_quoted_unresolved_email(self):
        ticket = self.create_ticket()
        ticket.status = "Awaiting Customer"
        self.db.commit()
        reply = (
            "Yes, resolved.\n\nOn Fri, 25 Sept 2026, 11:38 pm Support wrote:\n"
            "> Please confirm whether the issue has been resolved.\n"
            "> If the issue is still not resolved, reply to this email."
        )
        _process_customer_reply(self.db, ticket, self.reply(reply), self.reply_result())
        self.assertEqual(ticket.status, "Closed")
        self.assertEqual(ticket.conversation_messages[-1].direction, "system")
        self.assertIn("confirmed that the issue was resolved", ticket.conversation_messages[-1].body)

    def test_customer_reports_unresolved_issue_and_ticket_reopens(self):
        ticket = self.create_ticket()
        ticket.status = "Awaiting Customer"
        ticket.resolution_email_sent_at = datetime.now(timezone.utc)
        ticket.resolution_email_message_id = "sent-1"
        self.db.commit()
        _process_customer_reply(self.db, ticket, self.reply("It still isn't resolved."), self.reply_result())
        self.assertEqual(ticket.status, "Reopened")
        self.assertIsNone(ticket.resolution_email_sent_at)
        self.assertIsNone(ticket.resolution_email_message_id)

    def test_ambiguous_customer_reply_keeps_ticket_awaiting(self):
        ticket = self.create_ticket()
        ticket.status = "Awaiting Customer"
        self.db.commit()
        result = self.reply_result()
        _process_customer_reply(self.db, ticket, self.reply("Thanks for checking in."), result)
        self.assertEqual(ticket.status, "Awaiting Customer")
        self.assertEqual(result["ambiguous"], 1)
        self.assertTrue(ticket.customer_reply_review_required)
        self.assertEqual(len(ticket.conversation_messages), 2)

    def test_uncertain_resolution_reply_remains_awaiting(self):
        ticket = self.create_ticket()
        ticket.status = "Awaiting Customer"
        self.db.commit()
        result = self.reply_result()
        _process_customer_reply(
            self.db,
            ticket,
            self.reply("I'm not sure the issue is resolved."),
            result,
        )
        self.assertEqual(ticket.status, "Awaiting Customer")
        self.assertTrue(ticket.customer_reply_review_required)

    def test_agent_can_decide_ambiguous_customer_reply(self):
        ticket = self.create_ticket()
        ticket.status = "Awaiting Customer"
        ticket.customer_reply_review_required = True
        self.db.commit()
        decided = decide_ambiguous_customer_reply(self.db, ticket, status="Reopened")
        self.assertEqual(decided.status, "Reopened")
        self.assertFalse(decided.customer_reply_review_required)

    def test_only_overdue_awaiting_tickets_are_automatically_closed(self):
        now = datetime.now(timezone.utc)
        overdue = self.create_ticket()
        overdue.status = "Awaiting Customer"
        overdue.resolution_email_sent_at = now - timedelta(hours=49)
        recent = self.create_ticket()
        recent.status = "Awaiting Customer"
        recent.resolution_email_sent_at = now - timedelta(hours=47)
        in_progress = self.create_ticket()
        in_progress.status = "In Progress"
        in_progress.resolution_email_sent_at = now - timedelta(hours=72)
        self.db.commit()
        with patch.dict("os.environ", {"AWAITING_CUSTOMER_HOURS": "48"}):
            closed = close_overdue_awaiting_customer_tickets(self.db, now=now)
        self.assertEqual(closed, 1)
        self.assertEqual(overdue.status, "Closed")
        self.assertEqual(recent.status, "Awaiting Customer")
        self.assertEqual(in_progress.status, "In Progress")
        self.assertTrue(
            any(
                "automatically closed" in message.body
                for message in overdue.conversation_messages
            )
        )

    def test_duplicate_gmail_message_is_not_processed_again(self):
        self.create_ticket()
        messages = Mock()
        messages.list.return_value.execute.return_value = {"messages": [{"id": "message-1"}]}
        service = Mock()
        service.users.return_value.messages.return_value = messages
        with patch("app.gmail_sync.get_gmail_service", return_value=service):
            result = synchronize_incoming_emails(self.db)
        self.assertEqual(result["duplicates"], 1)
        messages.get.assert_not_called()

    @staticmethod
    def reply(message):
        return {
            "message": message,
            "gmail_message_id": "reply-1",
            "gmail_thread_id": "thread-1",
        }

    @staticmethod
    def reply_result():
        return {
            "customer_replies": 0,
            "closed": 0,
            "reopened": 0,
            "ambiguous": 0,
        }


if __name__ == "__main__":
    unittest.main()