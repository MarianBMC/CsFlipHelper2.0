from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.api.routes import router as api_v1_router
from app.core.memory_db import MemoryDB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown lifecycle events for the FastAPI application."""
    logger.info("Starting up CS2 Arbitrage Backend...")
    db = MemoryDB()
    await db.load_data()
    logger.info("Application startup complete. Ready to accept requests.")
    try:
        yield
    finally:
        logger.info("Shutting down CS2 Arbitrage Backend...")


app = FastAPI(
    title="CS2 Arbitrage Tool API",
    version="0.1.0",
    description="Backend API for tracking CS2 skin prices and arbitrage opportunities.",
    lifespan=lifespan,
)

app.include_router(api_v1_router)
