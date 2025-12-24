import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import (
    ads_router,
    auto_pricing_router,
    credentials_router,
    fiat_balance_router,
    fiat_balance_auto_pricing_router,
    info_router,
    orders_router,
    order_processing_router,
)
from config import settings
from services.auto_pricing_service import auto_pricing_worker
from services.fiat_balance_auto_pricing_service import fiat_balance_auto_worker
from services.refresh_worker import CredentialRefreshWorker

logger = logging.getLogger("p2p-panel")

app = FastAPI(title="P2P Panel API")
refresh_worker = CredentialRefreshWorker()

if settings.allowed_origins == ["*"]:
    allow_origins = ["*"]
else:
    allow_origins = settings.allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(info_router)
app.include_router(credentials_router)
app.include_router(orders_router)
app.include_router(order_processing_router)
app.include_router(ads_router)
app.include_router(auto_pricing_router)
app.include_router(fiat_balance_router)
app.include_router(fiat_balance_auto_pricing_router)


@app.on_event("startup")
async def _on_startup() -> None:
    await refresh_worker.start()
    if allow_origins == ["*"]:
        logger.warning(
            "CORS is set to allow all origins with credentials; set ALLOWED_ORIGINS to explicit values for local dev."
        )


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    await refresh_worker.stop()
    await auto_pricing_worker.stop()
    await fiat_balance_auto_worker.stop()


@app.middleware("http")
async def log_preflight(request, call_next):
    if request.method == "OPTIONS":
        origin = request.headers.get("origin", "")
        logger.info("CORS preflight %s %s origin=%s", request.method, request.url.path, origin)
    response = await call_next(request)
    return response


@app.get("/api/diag/cors")
async def cors_diag():
    return {
        "allow_origins": allow_origins,
        "allow_credentials": True,
    }
