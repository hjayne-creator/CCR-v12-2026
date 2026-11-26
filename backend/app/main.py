from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.rules import router as rules_router
from app.api.runs import router as runs_router
from app.config import get_settings
from app.models.db import init_db
from app.seed import seed_sgs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_sgs()
    logger.info("CCR v12-2026 ready (db=%s)", get_settings().resolved_database_url.split("@")[-1])
    yield


app = FastAPI(title="CCR v12-2026", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(runs_router)
app.include_router(rules_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
