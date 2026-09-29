from fastapi import FastAPI
from sqlalchemy import text

from .database import Base, engine, ensure_sqlite_columns, remove_sqlite_columns
from .models import Ticket
from .routes import router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "https://ticket-iq-v2.vercel.app",
    "https://ticket-iq-v2-ew4p3kjnv-saanvi19.vercel.app",
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
ensure_sqlite_columns(Ticket.__table__)
remove_sqlite_columns(Ticket.__table__, {"sla_due_at", "sla_state"})
if engine.dialect.name == "sqlite":
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE tickets SET "
                "ai_category = COALESCE(ai_category, category), "
                "ai_priority = COALESCE(ai_priority, priority), "
                "category = CASE WHEN review_status IN "
                "('review_required', 'agent_review_required') THEN NULL ELSE category END, "
                "priority = CASE WHEN review_status IN "
                "('review_required', 'agent_review_required') THEN NULL ELSE priority END "
                "WHERE ai_category IS NULL AND ai_priority IS NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE tickets SET customer_reply_review_required = 0 "
                "WHERE customer_reply_review_required IS NULL"
            )
        )

app = FastAPI(title="TicketIQ API")
app.include_router(router, prefix="/api")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "TicketIQ API is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}

