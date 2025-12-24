import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from exchanges import SUPPORTED_EXCHANGES, create_exchange_client
from repositories.credentials_repository import (
    fetch_user_credentials as repo_fetch_user_credentials,
)
from schemas import AccountPendingOrders, PendingOrder
from services.credentials_service import build_exchange_credentials

PAGE_SIZE = 30
ORDER_STATUS_LABELS = {
    5: "Waiting chain",
    10: "Waiting buyer pay",
    20: "Waiting seller release",
    30: "Appealing",
    90: "Waiting buyer select",
    100: "Objectioning",
    110: "Waiting objection",
}


def _parse_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10**12 else value
        return datetime.fromtimestamp(timestamp)
    if isinstance(value, str):
        try:
            if value.isdigit():
                return _parse_datetime(int(value))
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _normalize_side(value: Any) -> str:
    text = str(value).lower()
    if text in {"1", "sell"}:
        return "SELL"
    return "BUY"


def _parse_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_order_list(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    result = response.get("result")
    if not isinstance(result, dict):
        return []
    items = result.get("items")
    if isinstance(items, list):
        return items
    return []


def _format_order(raw: Dict[str, Any]) -> PendingOrder:
    token = raw.get("tokenId") or raw.get("coin")
    token = token.upper() if isinstance(token, str) else token
    side = _normalize_side(raw.get("side"))
    status_code = _parse_int(raw.get("status"))
    status_label = ORDER_STATUS_LABELS.get(status_code)
    counterparty_name = (
        raw.get("buyerRealName") if side == "SELL" else raw.get("sellerRealName")
    )
    counterparty_name = counterparty_name or raw.get("targetNickName")
    return PendingOrder(
        order_id=str(raw.get("orderId") or raw.get("id") or ""),
        side=side,
        token=token,
        status_code=status_code,
        status_label=status_label,
        fiat_currency=raw.get("currencyId") or raw.get("currency"),
        fiat_amount=_parse_float(
            raw.get("amount")
            or raw.get("fiatAmount")
            or raw.get("totalAmount")
            or raw.get("quantityFiat")
        ),
        price=_parse_float(raw.get("price")),
        crypto_amount=_parse_float(
            raw.get("notifyTokenQuantity")
            or raw.get("quantity")
            or raw.get("coinQuantity")
            or raw.get("qty")
        ),
        counterparty_name=counterparty_name,
        counterparty_nickname=raw.get("targetNickName"),
        created_at=_parse_datetime(
            raw.get("createdTime")
            or raw.get("createdAt")
            or raw.get("createTime")
            or raw.get("createDate")
        ),
        raw=raw,
    )


def _fetch_counterparty_info(client, order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    target_user_id = order.get("targetUserId") or order.get("target_user_id")
    order_id = order.get("orderId") or order.get("id")
    if not target_user_id or not order_id:
        return None
    try:
        response = client.get_counterparty_info(
            originalUid=str(target_user_id),
            orderId=str(order_id),
        )
    except Exception:  # pragma: no cover - network/API failures
        return None
    result = response.get("result") if isinstance(response, dict) else None
    if isinstance(result, dict):
        return result
    return None


def _attach_counterparty_info(client, orders: List[Dict[str, Any]]) -> None:
    for order in orders:
        info = _fetch_counterparty_info(client, order)
        if info:
            order["counterparty_info"] = info


def _load_bybit_pending_orders(creds) -> List[Dict[str, Any]]:
    client = create_exchange_client(creds)
    orders: List[Dict[str, Any]] = []
    page = 1
    while True:
        response = client.get_pending_orders(page=str(page), size=str(PAGE_SIZE))
        batch = _extract_order_list(response)
        if not batch:
            break
        orders.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    _attach_counterparty_info(client, orders)
    return orders


async def get_pending_orders(user_id: str) -> List[AccountPendingOrders]:
    rows = await asyncio.to_thread(repo_fetch_user_credentials, user_id)
    accounts: List[AccountPendingOrders] = []
    for row in rows:
        exchange = row.get("exchange")
        if exchange not in SUPPORTED_EXCHANGES or exchange != "bybit":
            continue
        creds = build_exchange_credentials(row)
        try:
            raw_orders = await asyncio.to_thread(_load_bybit_pending_orders, creds)
            orders = [_format_order(item) for item in raw_orders]
            error = None
        except Exception as exc:  # pragma: no cover - network failures
            orders = []
            error = str(exc)
        accounts.append(
            AccountPendingOrders(
                credential_id=row["id"],
                account_label=row.get("account_label"),
                exchange=exchange,
                orders=orders,
                error=error,
            )
        )
    return accounts
