import asyncio
import contextlib
import logging

from config import settings
from services import credentials_service

logger = logging.getLogger("p2p-panel")


class CredentialRefreshWorker:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task:
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
            try:
                rows = await credentials_service.fetch_all_credentials()
                for row in rows:
                    if not credentials_service.should_process(row):
                        continue
                    await credentials_service.verify_and_update(row)
            except Exception as exc:  # pragma: no cover - background guard
                logger.exception("Credential refresh cycle failed: %s", exc)
            await asyncio.sleep(settings.credential_check_interval_seconds)
