import asyncio
import logging
from typing import ClassVar

logger = logging.getLogger(__name__)


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
        self._initialized = True
        logger.debug("MemoryDB singleton instance initialized.")

    async def load_data(self) -> None:
        """Load target items and reference prices from the data source into memory."""
        async with self._lock:
            logger.info("Loading target items and reference prices into MemoryDB...")
            await asyncio.sleep(1.0)
            self._target_items = {
                "AK-47 | Redline (Field-Tested)": 24.50,
                "AWP | Asiimov (Field-Tested)": 118.00,
                "M4A1-S | Printstream (Minimal Wear)": 185.75,
                "Desert Eagle | Blaze (Factory New)": 590.00,
                "Sport Gloves | Vice (Field-Tested)": 1250.00,
            }
            logger.info(
                "Successfully loaded %d target items into MemoryDB.",
                len(self._target_items),
            )

    async def get_target_items(self) -> dict[str, float]:
        """Return a shallow copy of the loaded target items and their reference prices."""
        async with self._lock:
            return dict(self._target_items)


memory_db = MemoryDB()
