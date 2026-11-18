from fastapi import APIRouter, Depends

from app.core.memory_db import MemoryDB
from app.models.schemas import HealthStatusResponse

router = APIRouter(prefix="/api/v1", tags=["Health"])


def get_memory_db() -> MemoryDB:
    """Dependency provider for the MemoryDB singleton."""
    return MemoryDB()


@router.get("/status", response_model=HealthStatusResponse)
async def get_status(
    db: MemoryDB = Depends(get_memory_db),
) -> HealthStatusResponse:
    """Return service health status and number of loaded arbitrage items."""
    items = await db.get_target_items()
    return HealthStatusResponse(status="running", items_loaded=len(items))
