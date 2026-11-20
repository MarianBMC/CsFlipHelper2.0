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
        self._target_items: dict[str, dict[str, float | None]] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
        self._client: Client | None = None
        self._initialized = True
        logger.debug("MemoryDB singleton instance initialized.")

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        """Safely convert a database value to float, returning None if NULL or invalid."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

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
            .select("market_hash_name,max_buy_price,max_float,reference_price")
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
                loaded_items: dict[str, dict[str, float | None]] = {}
                for row in rows:
                    raw_name = row.get("market_hash_name")
                    max_buy_price = self._safe_float(row.get("max_buy_price"))
                    if raw_name is None or max_buy_price is None:
                        continue
                    loaded_items[str(raw_name)] = {
                        "max_buy_price": max_buy_price,
                        "max_float": self._safe_float(row.get("max_float")),
                        "reference_price": self._safe_float(row.get("reference_price")),
                    }
                self._target_items = loaded_items
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

    async def get_target_items(self) -> dict[str, dict[str, float | None]]:
        """Return a copy of the loaded target items and their configuration."""
        async with self._lock:
            return {name: dict(cfg) for name, cfg in self._target_items.items()}


memory_db = MemoryDB()
