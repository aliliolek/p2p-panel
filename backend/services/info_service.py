import httpx
import logging
from typing import Tuple

from config import settings
from exchanges import SUPPORTED_EXCHANGES
from schemas import ApiInfoResponse

logger = logging.getLogger("p2p-panel")


async def _fetch_public_ip() -> Tuple[str | None, str | None]:
    if settings.server_public_ip:
        return settings.server_public_ip, None
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get("https://api.ipify.org?format=json")
        response.raise_for_status()
        data = response.json()
        return data["ip"], None
    except Exception as exc:  # pragma: no cover - network dependency
        logger.warning("Unable to fetch public IP: %s", exc)
        return None, str(exc)


async def get_api_info() -> ApiInfoResponse:
    public_ip, ip_error = await _fetch_public_ip()
    return ApiInfoResponse(
        public_ip=public_ip,
        ip_error=ip_error,
        supported_exchanges=list(SUPPORTED_EXCHANGES),
    )
