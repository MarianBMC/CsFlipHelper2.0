import asyncio
import logging
import os
from typing import Any, ClassVar

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
SUPABASE_KEY: str | None = os.getenv("SUPABASE_KEY")


class MemoryDB:
    """Thread-safe/Async-safe Singleton in-memory store for CS2 target items and reference prices."""

    _instance: ClassVar["MemoryDB | None"] = None
    _initialized: bool = False

    def __new__(cls) -> "MemoryDB":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._target_items: dict[str, float] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
        self._client: Client | None = None
        self._initialized = True
        logger.debug("MemoryDB singleton instance initialized.")

    def _get_supabase_client(self) -> Client:
        """Initialize and return the synchronous Supabase client."""
        if self._client is None:
            url = SUPABASE_URL or os.getenv("SUPABASE_URL")
            key = SUPABASE_KEY or os.getenv("SUPABASE_KEY")
            if not url or not key:
                raise ValueError(
                    "SUPABASE_URL and SUPABASE_KEY must be set in the environment or .env file."
                )
            self._client = create_client(url, key)
        return self._client

    def _fetch_target_items_sync(self) -> list[dict[str, Any]]:
        """Execute synchronous Supabase query for active target items."""
        client = self._get_supabase_client()
        response = (
            client.table("target_items")
            .select("market_hash_name, max_buy_price")
            .eq("is_active", True)
            .execute()
        )
        return response.data or []

    async def load_data(self) -> None:
        """Load target items and reference prices from Supabase into memory without blocking the event loop."""
        async with self._lock:
            logger.info("Loading target items and reference prices from Supabase into MemoryDB...")
            try:
                rows = await asyncio.to_thread(self._fetch_target_items_sync)
                self._target_items = {
                    str(row["market_hash_name"]): float(row["max_buy_price"])
                    for row in rows
                    if row.get("market_hash_name") is not None
                    and row.get("max_buy_price") is not None
                }
                logger.info(
                    "Successfully loaded %d target items into MemoryDB.",
                    len(self._target_items),
                )
            except Exception as exc:
                logger.error(
                    "Failed to fetch target items from Supabase: %s",
                    exc,
                    exc_info=True,
                )

    async def get_target_items(self) -> dict[str, float]:
        """Return a shallow copy of the loaded target items and their reference prices."""
        async with self._lock:
            return dict(self._target_items)


memory_db = MemoryDB()
