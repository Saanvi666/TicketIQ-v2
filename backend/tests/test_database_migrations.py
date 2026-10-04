import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app import database
from app.gmail_sync import close_overdue_awaiting_customer_tickets
from app.models import Base, Ticket


class SQLiteMigrationTests(unittest.TestCase):
    def test_missing_ticket_columns_are_added_without_losing_existing_data(self):
        engine = create_engine("sqlite:///:memory:")

        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    CREATE TABLE tickets (
                        id INTEGER PRIMARY KEY,
                        ticket_id VARCHAR NOT NULL,
                        customer_name VARCHAR NOT NULL,
                        customer_email VARCHAR NOT NULL,
                        subject VARCHAR NOT NULL,
                        message TEXT NOT NULL
                    )
                    """
                )
                connection.exec_driver_sql(
                    """
                    INSERT INTO tickets
                        (id, ticket_id, customer_name, customer_email, subject, message)
                    VALUES (1, 'TKT-1', 'Alex Customer', 'alex@example.com',
                            'Existing ticket', 'Existing ticket data')
                    """
                )
                connection.exec_driver_sql(
                    """
                    CREATE TABLE ticket_conversation_messages (
                        id INTEGER PRIMARY KEY,
                        ticket_id INTEGER NOT NULL,
                        direction VARCHAR NOT NULL,
                        body TEXT NOT NULL,
                        sent_at DATETIME NOT NULL
                    )
                    """
                )

            with patch.object(database, "engine", engine):
                database.initialize_database()
                for table in Base.metadata.sorted_tables:
                    database.ensure_sqlite_columns(table)

            for table in Base.metadata.sorted_tables:
                actual_columns = {
                    column["name"]
                    for column in inspect(engine).get_columns(table.name)
                }
                expected_columns = {
                    column.name for column in table.columns
                }
                self.assertTrue(expected_columns.issubset(actual_columns))

            actual_columns = {
                column["name"] for column in inspect(engine).get_columns("tickets")
            }
            self.assertIn("assigned_team", actual_columns)
            conversation_columns = {
                column["name"]
                for column in inspect(engine).get_columns(
                    "ticket_conversation_messages"
                )
            }
            self.assertIn("gmail_message_id", conversation_columns)

            with engine.connect() as connection:
                ticket = connection.execute(
                    text(
                        "SELECT ticket_id, customer_name, message FROM tickets "
                        "WHERE id = 1"
                    )
                ).one()

            self.assertEqual(
                tuple(ticket),
                ("TKT-1", "Alex Customer", "Existing ticket data"),
            )

            with engine.connect() as connection:
                reply_review_required = connection.execute(
                    text(
                        "SELECT customer_reply_review_required FROM tickets "
                        "WHERE id = 1"
                    )
                ).scalar_one()
            self.assertFalse(reply_review_required)

            with Session(engine) as session:
                self.assertEqual(
                    close_overdue_awaiting_customer_tickets(session), 0
                )
        finally:
            engine.dispose()
