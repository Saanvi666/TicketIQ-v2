# TicketIQ-v2

AI-powered email-based customer support ticket management system.

## Backend Workflow Settings

Set `AWAITING_CUSTOMER_HOURS` in `backend/.env` to configure automatic closure after a resolution email. It defaults to `48` hours; setting it to `24` changes the waiting period to one day. The backend reads `OPENROUTER_API_KEY` from the same backend environment for resolution-email generation.

Run the backend workflow tests from `backend/` with `python -m unittest discover -s tests -v`.

To preview removal of clearly marked development test tickets and their conversation records, run `python -m scripts.reset_development_tickets` from `backend/`. To perform the cleanup, set `TICKETIQ_ENV=development` for that shell and pass `--confirm-development-reset`. The script only operates on SQLite and only removes records with obvious placeholder/test markers; it does not touch OAuth credentials or other configuration.