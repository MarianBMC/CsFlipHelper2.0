import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CSFLOAT_BASE_URL = "https://csfloat.com/api/v1"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


class CSFloatScraper:
    """Asynchronous scraper service for interacting with the CSFloat API."""

    MAX_RETRIES: int = 3
    BASE_BACKOFF_SECONDS: float = 1.0
    RATE_LIMIT_THRESHOLD: int = 2

    def __init__(self, api_key: str, timeout: float = 15.0) -> None:
        self.api_key = api_key
        headers = {
            "Authorization": f"{api_key}",
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        self.client = httpx.AsyncClient(
            base_url=CSFLOAT_BASE_URL,
            headers=headers,
            timeout=httpx.Timeout(timeout),
        )

    async def _respect_rate_limits(self, headers: httpx.Headers) -> None:
        """Parse X-RateLimit headers and proactively sleep if remaining quota is low."""
        raw_remaining = headers.get("X-RateLimit-Remaining")
        raw_reset = headers.get("X-RateLimit-Reset")

        try:
            remaining = int(raw_remaining) if raw_remaining is not None else 10
        except (ValueError, TypeError):
            remaining = 10

        try:
            reset_timestamp = (
                float(raw_reset) if raw_reset is not None else time.time() + 1.0
            )
        except (ValueError, TypeError):
            reset_timestamp = time.time() + 1.0

        if remaining <= self.RATE_LIMIT_THRESHOLD:
            sleep_duration = max(0.0, reset_timestamp - time.time())
            if sleep_duration > 0:
                logger.warning(
                    "CSFloat rate limit low (X-RateLimit-Remaining=%d). "
                    "Sleeping %.2fs until reset timestamp %.2f.",
                    remaining,
                    sleep_duration,
                    reset_timestamp,
                )
                await asyncio.sleep(sleep_duration)

    async def get_listings(self, market_hash_name: str) -> list[dict[str, Any]]:
        """Fetch active listings for a given market_hash_name with rate-limiting and exponential backoff."""
        params = {"market_hash_name": market_hash_name}

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = await self.client.get("/listings", params=params)
                await self._respect_rate_limits(response.headers)

                if response.status_code == 200:
                    payload = response.json()
                    if isinstance(payload, list):
                        return payload
                    if isinstance(payload, dict) and isinstance(
                        payload.get("data"), list
                    ):
                        return payload["data"]
                    logger.warning(
                        "Unexpected payload structure from CSFloat for '%s': %s",
                        market_hash_name,
                        type(payload).__name__,
                    )
                    return []

                if response.status_code == 429 or 500 <= response.status_code < 600:
                    if attempt < self.MAX_RETRIES:
                        backoff = self.BASE_BACKOFF_SECONDS * (2**attempt)
                        logger.warning(
                            "CSFloat HTTP %d for '%s' (retry %d/%d). Backing off %.2fs...",
                            response.status_code,
                            market_hash_name,
                            attempt + 1,
                            self.MAX_RETRIES,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue

                    logger.error(
                        "CSFloat HTTP %d for '%s' persisted after %d retries.",
                        response.status_code,
                        market_hash_name,
                        self.MAX_RETRIES,
                    )
                    return []

                logger.error(
                    "Non-retryable CSFloat HTTP %d for '%s': %s",
                    response.status_code,
                    market_hash_name,
                    response.text,
                )
                return []

            except httpx.RequestError as exc:
                if attempt < self.MAX_RETRIES:
                    backoff = self.BASE_BACKOFF_SECONDS * (2**attempt)
                    logger.warning(
                        "CSFloat network error for '%s': %s (retry %d/%d). Backing off %.2fs...",
                        market_hash_name,
                        exc,
                        attempt + 1,
                        self.MAX_RETRIES,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue

                logger.error(
                    "CSFloat request failed for '%s' after %d retries: %s",
                    market_hash_name,
                    self.MAX_RETRIES,
                    exc,
                )
                return []
            except ValueError as exc:
                logger.error(
                    "Failed to decode JSON response from CSFloat for '%s': %s",
                    market_hash_name,
                    exc,
                )
                return []

        return []

    async def close(self) -> None:
        """Gracefully close the underlying HTTPX AsyncClient."""
        await self.client.aclose()
