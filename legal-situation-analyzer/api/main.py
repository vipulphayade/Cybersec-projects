import os

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from dataset_verifier import run_dataset_sanity_check
from database import SessionLocal, get_db
from import_service import ensure_seed_data
from schemas import AnalyzeRequest, AnalyzeResponse, FollowupRequest, FollowupResponse
from search import analyze_description, answer_followup, ensure_query_log_table


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        return response


def parse_csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


app = FastAPI(
    title="Legal Situation Analyzer API",
    version="3.0.0",
    description=(
        "Analyzes a housing society situation and maps it to the most relevant "
        "Maharashtra Cooperative Housing Society Model Bye-law."
    ),
)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_csv_env(
        "API_ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"
    ),
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=parse_csv_env("ALLOWED_HOSTS", "localhost,127.0.0.1,api,frontend"),
)


@app.on_event("startup")
def initialize_dataset() -> None:
    session = SessionLocal()
    try:
        ensure_seed_data(session)
        ensure_query_log_table(session)
        run_dataset_sanity_check(session)
    finally:
        session.close()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
@app.post("/api/analyze", response_model=AnalyzeResponse)
@limiter.limit(os.getenv("API_RATE_LIMIT", "20/minute"))
def analyze(
    request: Request, payload: AnalyzeRequest, db: Session = Depends(get_db)
) -> AnalyzeResponse:
    del request
    result = analyze_description(payload.description, db)
    return AnalyzeResponse(**result)


@app.post("/followup", response_model=FollowupResponse)
@app.post("/api/followup", response_model=FollowupResponse)
@limiter.limit(os.getenv("API_RATE_LIMIT", "20/minute"))
def followup(request: Request, payload: FollowupRequest) -> FollowupResponse:
    del request
    result = answer_followup(payload.question, payload.context)
    return FollowupResponse(**result)
