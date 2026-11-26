"""
Production AI Agent — Part 6 Final Project (bản khung)

Hoàn thành các TODO để đạt đủ 12 tiêu chí trong README.md, rồi kiểm tra:
    python check_production_ready.py

Bản khung này chạy được (uvicorn app.main:app) nhưng chưa đạt tiêu chí nào.
"""
import json
import logging
import time

from datetime import datetime, timezone
from fastapi import (
    FastAPI,
    Request,
    HTTPException,
    Depends,
)
from pydantic import BaseModel, Field
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_cost

from app.config import settings
from utils.mock_llm import ask as llm_ask
from app.redis_client import r, redis_healthy
from contextlib import asynccontextmanager

class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }

        for field in ("path", "method", "status", "ms"):
            if hasattr(record, field):
                data[field] = getattr(record, field)

        return json.dumps(data, ensure_ascii=False)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())

logger = logging.getLogger("app")
logger.handlers.clear()
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


START_TIME = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup")

    try:
        yield
    finally:
        logger.info("shutdown_started")
        r.close()
        logger.info("shutdown_complete")


app = FastAPI(
    title="Production AI Agent",
    lifespan=lifespan,
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)

# Request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()

    response = await call_next(request)

    duration = (time.perf_counter() - start) * 1000

    logger.info(
        "request",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status": response.status_code,
            "ms": round(duration, 2),
        },
    )

    return response


# Health check
@app.get("/health")
def health():
    return {
        "status": "ok",
        "environment": settings.environment,
        "uptime_seconds": round(
            time.time() - START_TIME, 1
        ),
    }

@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(
            status_code=503,
            detail="Redis is unavailable",
        )

    return {
        "ready": True,
        "redis": "ok",
    }

@app.post("/ask")
def ask(
    body: AskRequest,
    api_key: str = Depends(verify_api_key),
):

    check_rate_limit(api_key)

    check_budget()

    answer = llm_ask(body.question)

    input_tokens = max(
        1, len(body.question.split()) * 2
    )

    output_tokens = max(
        1, len(answer.split()) * 2
    )

    cost = record_cost(
        input_tokens,
        output_tokens,
    )

    return {
        "question": body.question,
        "answer": answer,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
        },
    }

