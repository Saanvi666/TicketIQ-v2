from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import (
    Base,
    engine,
    ensure_sqlite_columns,
    initialize_database,
    remove_sqlite_columns,
)
from .models import Ticket
from .routes import router


# --------------------------------------------------
# Database initialization
# --------------------------------------------------

# Import models before creating tables so SQLAlchemy
# knows about all registered models.
initialize_database()


# --------------------------------------------------
# FastAPI application
# --------------------------------------------------

app = FastAPI(title="TicketIQ API")


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://ticket-iq-v2.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Database compatibility / migrations
# --------------------------------------------------

for table in Base.metadata.sorted_tables:
    ensure_sqlite_columns(table)

# Remove obsolete columns if they exist from an
# earlier version of TicketIQ.
remove_sqlite_columns(
    Ticket.__table__,
    {
        "assigned_agent",
        "sla_due_at",
        "sla_state",
    },
)


# --------------------------------------------------
# Routes
# --------------------------------------------------

app.include_router(router, prefix="/api")


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok"}