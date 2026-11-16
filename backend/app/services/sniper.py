import asyncio
import logging
from typing import Any

from app.core.memory_db import MemoryDB
from app.services.csfloat import CSFloatScraper

logger = logging.getLogger(__name__)


class SniperService:
    """Core in-memory arbitrage engine for scanning CSFloat listings against target buy prices."""

    ITEM_SCAN_DELAY_SECONDS: float = 1.5
    ERROR_RECOVERY_DELAY_SECONDS: float = 5.0

    def __init__(self, scraper: CSFloatScraper, memory_db: MemoryDB) -> None:
        self.scraper = scraper
        self.memory_db = memory_db

    async def evaluate_listing(
        self, listing: dict[str, Any], max_buy_price: float
    ) -> dict[str, Any] | None:
        """Evaluate a single CSFloat listing in RAM against the target maximum buy price in USD."""
        raw_price = listing.get("price")
        if raw_price is None:
            return None

        try:
            price_dollars = float(raw_price) / 100.0
        except (ValueError, TypeError):
            return None

        if price_dollars <= max_buy_price:
            item_data = listing.get("item") or {}
            market_hash_name = (
                item_data.get("market_hash_name")
                or listing.get("market_hash_name")
                or "Unknown Item"
            )
            raw_float = item_data.get("float_value")
            try:
                float_value = float(raw_float) if raw_float is not None else None
            except (ValueError, TypeError):
                float_value = None

            return {
                "market_hash_name": str(market_hash_name),
                "float_value": float_value,
                "price": price_dollars,
                "listing_id": str(listing.get("id", "")),
            }

        return None

    async def run_sniper_loop(self) -> None:
        """Continuously scan target items from MemoryDB and evaluate live CSFloat listings."""
        logger.info("Starting SniperService background loop...")

        while True:
            try:
                target_items = await self.memory_db.get_target_items()

                if not target_items:
                    logger.debug("No active target items in MemoryDB. Waiting before next cycle...")
                    await asyncio.sleep(self.ERROR_RECOVERY_DELAY_SECONDS)
                    continue

                for market_hash_name, max_buy_price in target_items.items():
                    listings = await self.scraper.get_listings(market_hash_name)

                    for listing in listings:
                        deal = await self.evaluate_listing(listing, max_buy_price)
                        if deal is not None:
                            if not deal.get("market_hash_name") or deal["market_hash_name"] == "Unknown Item":
                                deal["market_hash_name"] = market_hash_name
                            logger.critical(
                                "DEAL FOUND! [%s] for $[%.2f] (Max: $%.2f | Float: %s | ID: %s)",
                                deal["market_hash_name"],
                                deal["price"],
                                max_buy_price,
                                deal["float_value"],
                                deal["listing_id"],
                            )

                    await asyncio.sleep(self.ITEM_SCAN_DELAY_SECONDS)

            except asyncio.CancelledError:
                logger.info("SniperService background loop cancelled. Shutting down cleanly...")
                raise
            except Exception as exc:
                logger.error(
                    "Unexpected error in SniperService loop: %s. Recovering in %.1fs...",
                    exc,
                    self.ERROR_RECOVERY_DELAY_SECONDS,
                    exc_info=True,
                )
                await asyncio.sleep(self.ERROR_RECOVERY_DELAY_SECONDS)
