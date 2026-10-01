from fastapi import FastAPI
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, ensure_sqlite_columns, remove_sqlite_columns
from .models import Ticket
from .routes import router


app = FastAPI(title="TicketIQ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_origin_regex=r"https://ticket-iq-v2.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... your existing database code ...

app.include_router(router, prefix="/api")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "TicketIQ API is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}