"""LeaseFlow orchestrator — FastAPI entry."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CONFIG
from .governance import snapshot
from .logging_setup import setup_logging
from .routers import analyze, documents, health, payments, risk

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    CONFIG.require()
    log.info("leaseflow startup", extra={
        "env": CONFIG.env,
        "model": CONFIG.llm_model,
        "decision_mode": CONFIG.decision_mode,
    })

    stop = asyncio.Event()
    scheduler_task: asyncio.Task | None = None

    if CONFIG.risk_snapshot_on_startup:
        try:
            await asyncio.to_thread(snapshot.take_snapshot)
        except Exception as e:  # noqa: BLE001
            log.exception("startup snapshot failed", extra={"err": str(e)})

    if CONFIG.risk_snapshot_interval_s > 0:
        scheduler_task = asyncio.create_task(
            snapshot.run_scheduler(CONFIG.risk_snapshot_interval_s, stop),
            name="risk-snapshot-scheduler",
        )

    try:
        yield
    finally:
        stop.set()
        if scheduler_task:
            try:
                await asyncio.wait_for(scheduler_task, timeout=5)
            except asyncio.TimeoutError:
                scheduler_task.cancel()
        log.info("leaseflow shutdown")


app = FastAPI(title="LeaseFlow Orchestrator", version="0.1.0", lifespan=lifespan)

# Permissive CORS: a literal ["*"] doesn't work when allow_credentials=True
# (browsers reject the combo). Using allow_origin_regex=".*" makes the
# middleware echo back each request's Origin header — permissive AND
# credential-compatible. If CORS_ORIGINS is explicitly set, honour it;
# otherwise allow everything.
_explicit_origins = [o.strip() for o in CONFIG.cors_origins.split(",") if o.strip()]
_allow_all = (not _explicit_origins) or _explicit_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_explicit_origins if not _allow_all else [],
    allow_origin_regex=".*" if _allow_all else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(documents.router)
app.include_router(payments.router)
app.include_router(risk.router)

# Dev-only fixture endpoint — gated by env flag. Keep off in production.
if CONFIG.dev_fixtures_enabled:
    from .routers import dev as _dev
    app.include_router(_dev.router)
    log.info("dev fixtures endpoint mounted at /dev/generate-fixtures")
