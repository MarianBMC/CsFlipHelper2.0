from fastapi import APIRouter, Depends, Request

from app.core.memory_db import MemoryDB
from app.models.schemas import DealResponse, HealthStatusResponse, TargetItemResponse
from app.services.sniper import SniperService

router = APIRouter(prefix="/api/v1", tags=["Sniper"])


def get_memory_db() -> MemoryDB:
    """Dependency provider for the MemoryDB singleton."""
    return MemoryDB()


def get_sniper_service(request: Request) -> SniperService | None:
    """Dependency provider for the active SniperService instance."""
    return SniperService.get_instance() or getattr(request.app.state, "sniper", None)


@router.get("/deals", response_model=list[DealResponse])
async def get_deals(
    sniper: SniperService | None = Depends(get_sniper_service),
) -> list[DealResponse]:
    """Return the in-memory list of detected deals (newest first, capped at 50)."""
    if sniper is None:
        return []
    return [DealResponse(**deal) for deal in sniper.get_deals()]


@router.get("/status", response_model=HealthStatusResponse)
async def get_status(
    db: MemoryDB = Depends(get_memory_db),
    sniper: SniperService | None = Depends(get_sniper_service),
) -> HealthStatusResponse:
    """Return service operational status, target items, and detected deal count."""
    items = await db.get_target_items()
    targets: list[TargetItemResponse] = []
    for name, cfg in items.items():
        if isinstance(cfg, dict):
            raw_buy = cfg.get("max_buy_price")
            raw_float = cfg.get("max_float")
            raw_ref = cfg.get("reference_price")
            targets.append(
                TargetItemResponse(
                    market_hash_name=name,
                    max_buy_price=float(raw_buy) if raw_buy is not None else 0.0,
                    max_float=float(raw_float) if raw_float is not None else None,
                    reference_price=float(raw_ref) if raw_ref is not None else None,
                )
            )
        else:
            targets.append(
                TargetItemResponse(
                    market_hash_name=name,
                    max_buy_price=float(cfg) if cfg is not None else 0.0,
                )
            )
    deals_count = len(sniper.get_deals()) if sniper is not None else 0
    return HealthStatusResponse(
        status="online",
        active_targets=len(targets),
        total_deals=deals_count,
        targets=targets,
    )

