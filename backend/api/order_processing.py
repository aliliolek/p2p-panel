from fastapi import APIRouter, HTTPException

from schemas import OrderProcessingStatusResponse
from services.order_processing_service import order_processing_worker

router = APIRouter(prefix="/api/order-processing", tags=["order-processing"])


@router.get("/status", response_model=OrderProcessingStatusResponse)
async def get_status() -> OrderProcessingStatusResponse:
    return OrderProcessingStatusResponse(**order_processing_worker.get_status())


@router.post("/start", response_model=OrderProcessingStatusResponse)
async def start_worker() -> OrderProcessingStatusResponse:
    try:
        await order_processing_worker.start()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return OrderProcessingStatusResponse(**order_processing_worker.get_status())


@router.post("/stop", response_model=OrderProcessingStatusResponse)
async def stop_worker() -> OrderProcessingStatusResponse:
    try:
        await order_processing_worker.stop()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return OrderProcessingStatusResponse(**order_processing_worker.get_status())
