import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.routes import router as api_v1_router
from app.core.memory_db import MemoryDB
from app.services.csfloat import CSFloatScraper
from app.services.sniper import SniperService

load_dotenv()
load_dotenv(Path(__file__).resolve().parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown lifecycle events for the FastAPI application."""
    logger.info("Starting up CS2 Arbitrage Backend...")

    CSFLOAT_API_KEY = os.getenv("CSFLOAT_API_KEY")
    if not CSFLOAT_API_KEY:
        raise ValueError("CSFLOAT_API_KEY is missing from environment variables or .env file.")

    memory_db = MemoryDB()
    await memory_db.load_data()

    scraper = CSFloatScraper(api_key=CSFLOAT_API_KEY)
    sniper = SniperService(scraper=scraper, memory_db=memory_db)

    sniper_task = asyncio.create_task(sniper.run_sniper_loop())
    app.state.sniper_task = sniper_task
    logger.info("Application startup complete. Sniper background loop running.")

    try:
        yield
    finally:
        logger.info("Shutting down CS2 Arbitrage Backend...")
        sniper_task.cancel()
        try:
            await sniper_task
        except asyncio.CancelledError:
            logger.info("Sniper background task cancelled cleanly.")
        await scraper.close()
        logger.info("CSFloatScraper client closed.")


app = FastAPI(
    title="CS2 Arbitrage Tool API",
    version="0.1.0",
    description="Backend API for tracking CS2 skin prices and arbitrage opportunities.",
    lifespan=lifespan,
)

app.include_router(api_v1_router)
