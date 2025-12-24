import asyncio
import contextlib
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from exchanges import ExchangeCredentials, create_exchange_client
from repositories.credentials_repository import fetch_all_credentials
from services.credentials_service import build_exchange_credentials
from services.orders_service import _load_bybit_pending_orders

from services.order_processing.processors import process_single_order

logger = logging.getLogger("p2p-panel")

POLL_INTERVAL_SECONDS = 30


def _process_single_order(
    api,
    creds: Dict[str, Any],
    order: Dict[str, Any],
    record_state: bool = True,
    echo: bool = False,
    force_all_messages: bool = False,
    send_messages: bool = True,
) -> None:
    process_single_order(
        api,
        creds,
        order,
        record_state=record_state,
        echo=echo,
        force_all_messages=force_all_messages,
        send_messages=send_messages,
    )


async def _process_account(row: Dict[str, Any]) -> None:
    creds_obj = build_exchange_credentials(row)
    client = create_exchange_client(creds_obj)
    orders = await asyncio.to_thread(_load_bybit_pending_orders, creds_obj)
    for order in orders:
        _process_single_order(client, row, order)


def process_pending_order_by_id(
    creds: ExchangeCredentials,
    credential_id: str,
    order_id: str,
    *,
    record_state: bool = False,
    echo: bool = False,
) -> bool:
    client = create_exchange_client(creds)
    orders = _load_bybit_pending_orders(creds)
    for order in orders:
        oid = str(order.get("id") or order.get("orderId") or "")
        if oid == order_id:
            _process_single_order(
                client,
                {"id": credential_id},
                order,
                record_state=record_state,
                echo=echo,
            )
            return True
    return False


class OrderProcessingWorker:
    def __init__(self, interval_seconds: int = POLL_INTERVAL_SECONDS) -> None:
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._last_run_at: Optional[datetime] = None
        self._last_success_at: Optional[datetime] = None
        self._last_error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running:
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while True:
            self._last_run_at = datetime.utcnow()
            try:
                rows = await asyncio.to_thread(fetch_all_credentials)
                for row in rows:
                    if row.get("exchange") != "bybit":
                        continue
                    await _process_account(row)
                self._last_success_at = datetime.utcnow()
                self._last_error = None
            except Exception as exc:  # pragma: no cover
                self._last_error = str(exc)
                logger.exception("Order processing cycle failed: %s", exc)
            await asyncio.sleep(self.interval_seconds)

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "last_run_at": self._last_run_at,
            "last_success_at": self._last_success_at,
            "last_error": self._last_error,
        }


order_processing_worker = OrderProcessingWorker()
