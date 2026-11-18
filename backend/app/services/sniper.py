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
    MAX_SEEN_CACHE_SIZE: int = 1000
    CSFLOAT_SELLING_FEE_RATE: float = 0.02
    DEFAULT_MARKUP_MULTIPLIER: float = 1.15
    MIN_NET_PROFIT_MARGIN: float = 0.0

    def __init__(self, scraper: CSFloatScraper, memory_db: MemoryDB) -> None:
        self.scraper = scraper
        self.memory_db = memory_db
        self._seen_listing_ids: set[str] = set()

    def _record_seen_listing(self, listing_id: str) -> None:
        """Record an alerted listing ID and prune cache in-memory if it exceeds capacity."""
        if len(self._seen_listing_ids) >= self.MAX_SEEN_CACHE_SIZE:
            self._seen_listing_ids.clear()
        self._seen_listing_ids.add(listing_id)

    def _resolve_target_params(
        self,
        target: float | dict[str, Any],
        max_float_override: float | None = None,
        min_float_override: float | None = None,
        reference_price_override: float | None = None,
    ) -> tuple[float, float | None, float | None, float | None]:
        """Extract max_buy_price, min_float, max_float, and reference_price from target config."""
        if isinstance(target, dict):
            raw_max_buy = target.get("max_buy_price", 0.0)
            max_buy_price = float(raw_max_buy) if raw_max_buy is not None else 0.0
            raw_min_f = min_float_override if min_float_override is not None else target.get("min_float")
            raw_max_f = max_float_override if max_float_override is not None else target.get("max_float")
            raw_ref = (
                reference_price_override
                if reference_price_override is not None
                else (target.get("reference_price") or target.get("estimated_resale_price"))
            )
            min_float = float(raw_min_f) if raw_min_f is not None else None
            max_float = float(raw_max_f) if raw_max_f is not None else None
            ref_price = float(raw_ref) if raw_ref is not None else None
            return max_buy_price, min_float, max_float, ref_price

        max_buy_price = float(target)
        return max_buy_price, min_float_override, max_float_override, reference_price_override

    def _extract_reference_price(
        self,
        listing: dict[str, Any],
        max_buy_price: float,
        explicit_reference_price: float | None,
    ) -> float:
        """Resolve reference resale price in USD from config, CSFloat listing metadata, or fallback estimate."""
        if explicit_reference_price is not None and explicit_reference_price > 0:
            return explicit_reference_price

        ref_data = listing.get("reference")
        if isinstance(ref_data, dict):
            raw_ref_cents = ref_data.get("base_price") or ref_data.get("predicted_price") or ref_data.get("price")
            if raw_ref_cents is not None:
                try:
                    ref_dollars = float(raw_ref_cents) / 100.0
                    if ref_dollars > 0:
                        return ref_dollars
                except (ValueError, TypeError):
                    pass

        return round(max_buy_price * self.DEFAULT_MARKUP_MULTIPLIER, 2)

    @classmethod
    def calculate_net_profit(
        cls,
        buy_price: float,
        reference_price: float,
        fee_rate: float | None = None,
    ) -> tuple[float, float, float]:
        """Calculate net resale value after CSFloat selling fee, net profit in USD, and profit margin %."""
        effective_fee = cls.CSFLOAT_SELLING_FEE_RATE if fee_rate is None else fee_rate
        net_resale = reference_price * (1.0 - effective_fee)
        net_profit = net_resale - buy_price
        profit_margin_pct = (net_profit / buy_price) * 100.0 if buy_price > 0 else 0.0
        return round(net_resale, 2), round(net_profit, 2), round(profit_margin_pct, 2)

    async def evaluate_listing(
        self,
        listing: dict[str, Any],
        max_buy_price: float | dict[str, Any],
        max_float: float | None = None,
        min_float: float | None = None,
        reference_price: float | None = None,
        min_profit_margin_pct: float | None = None,
    ) -> dict[str, Any] | None:
        """Evaluate a single CSFloat listing in RAM for price, float range, and positive net profit."""
        # 1. Auction Filtering: Verify listing is a fixed-price "Buy It Now" item, not an auction.
        listing_type = listing.get("type")
        if listing_type is not None and listing_type != "buy_now":
            return None

        if listing.get("auction_details") is not None or listing.get("is_auction") is True:
            return None

        raw_price = listing.get("price")
        if raw_price is None:
            return None

        try:
            price_dollars = float(raw_price) / 100.0
        except (ValueError, TypeError):
            return None

        if price_dollars <= 0:
            return None

        target_max_price, target_min_float, target_max_float, target_ref_price = (
            self._resolve_target_params(
                max_buy_price,
                max_float_override=max_float,
                min_float_override=min_float,
                reference_price_override=reference_price,
            )
        )

        if price_dollars > target_max_price:
            return None

        item_data = listing.get("item") or {}
        raw_float = item_data.get("float_value")
        try:
            float_value = float(raw_float) if raw_float is not None else None
        except (ValueError, TypeError):
            float_value = None

        # 2. Strict Float Range Filter (exclusively in RAM)
        if target_max_float is not None:
            if float_value is None or float_value > target_max_float:
                return None

        if target_min_float is not None:
            if float_value is None or float_value < target_min_float:
                return None

        # 3. Net Profit Calculation (after CSFloat ~2% selling fee)
        resolved_ref_price = self._extract_reference_price(
            listing=listing,
            max_buy_price=target_max_price,
            explicit_reference_price=target_ref_price,
        )
        _, net_profit, net_profit_margin_pct = self.calculate_net_profit(
            buy_price=price_dollars,
            reference_price=resolved_ref_price,
        )

        required_margin = (
            min_profit_margin_pct
            if min_profit_margin_pct is not None
            else self.MIN_NET_PROFIT_MARGIN
        )
        if net_profit <= 0 or net_profit_margin_pct <= required_margin:
            return None

        market_hash_name = (
            item_data.get("market_hash_name")
            or listing.get("market_hash_name")
            or "Unknown Item"
        )
        raw_listing_id = listing.get("id")
        listing_id = str(raw_listing_id) if raw_listing_id is not None else ""
        buy_url = f"https://csfloat.com/item/{raw_listing_id}"

        return {
            "market_hash_name": str(market_hash_name),
            "float_value": float_value,
            "price": price_dollars,
            "reference_price": resolved_ref_price,
            "net_profit": net_profit,
            "net_profit_margin_pct": net_profit_margin_pct,
            "listing_id": listing_id,
            "buy_url": buy_url,
            "url": buy_url,
        }

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

                for market_hash_name, target_config in target_items.items():
                    listings = await self.scraper.get_listings(market_hash_name)

                    for listing in listings:
                        deal = await self.evaluate_listing(listing, target_config)
                        if deal is not None:
                            listing_id = deal["listing_id"]
                            if listing_id and listing_id in self._seen_listing_ids:
                                continue

                            if listing_id:
                                self._record_seen_listing(listing_id)

                            if not deal.get("market_hash_name") or deal["market_hash_name"] == "Unknown Item":
                                deal["market_hash_name"] = market_hash_name

                            max_buy_display, _, _, _ = self._resolve_target_params(target_config)
                            logger.critical(
                                "DEAL FOUND! [%s] for $[%.2f] (Max: $%.2f | Ref: $%.2f | Net Profit: +$%.2f [%.2f%%] | Float: %s | URL: %s)",
                                deal["market_hash_name"],
                                deal["price"],
                                max_buy_display,
                                deal["reference_price"],
                                deal["net_profit"],
                                deal["net_profit_margin_pct"],
                                deal["float_value"],
                                deal["buy_url"],
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
