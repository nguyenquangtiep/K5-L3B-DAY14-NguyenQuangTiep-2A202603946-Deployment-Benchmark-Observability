"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

def budget_key() -> str:
    today = datetime.now(timezone.utc)
    return f"cost:daily:{today:%Y-%m-%d}"

def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    try:
        current_cost = float(
            r.get(budget_key()) or 0
        )
    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Cost guard unavailable",
        )

    if current_cost >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail="Daily budget exceeded",
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (
        input_tokens / 1000 * PRICE_INPUT_PER_1K
        + output_tokens / 1000 * PRICE_OUTPUT_PER_1K
    )

    now = datetime.now(timezone.utc)

    midnight = (
        now + timedelta(days=1)
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    key = f"cost:daily:{now:%Y-%m-%d}"

    try:
        with r.pipeline(transaction=True) as pipe:
            pipe.incrbyfloat(key, cost)
            pipe.expireat(
                key, int(midnight.timestamp())
            )
            pipe.execute()

    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Unable to record cost",
        )

    return cost
