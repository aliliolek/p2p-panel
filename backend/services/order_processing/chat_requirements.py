from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .messaging import message_text, send_chat_message
from .payments import extract_iban, extract_pl_phone

_ACCOUNT_ID_CACHE: Dict[str, str] = {}


def _parse_ms(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_iso_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _extract_chat_items(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    result = response.get("result")
    if isinstance(result, dict):
        items = result.get("result") or result.get("items") or []
    else:
        items = []
    return items if isinstance(items, list) else []


def _is_valid_value(value: Any) -> bool:
    return bool(value) and str(value).strip().lower() != "not found"


def _get_my_account_id(api, credential_id: str) -> str:
    cached = _ACCOUNT_ID_CACHE.get(credential_id)
    if cached is not None:
        return cached
    try:
        resp = api.get_account_information()
    except Exception:
        _ACCOUNT_ID_CACHE[credential_id] = ""
        return ""
    result = resp.get("result") if isinstance(resp, dict) else None
    account_id = str(result.get("accountId") or "") if isinstance(result, dict) else ""
    _ACCOUNT_ID_CACHE[credential_id] = account_id
    return account_id


def _collect_from_messages(
    items: List[Dict[str, Any]],
    my_account_id: str,
    since_ms: Optional[int],
) -> Tuple[set[str], set[str], set[str], set[str], bool]:
    ibans: set[str] = set()
    phones: set[str] = set()
    echo_ibans: set[str] = set()
    echo_phones: set[str] = set()
    replied = False
    for item in items:
        account_id = str(item.get("accountId") or "")
        if not account_id or account_id == my_account_id:
            continue
        if str(item.get("contentType") or "str") != "str":
            continue
        msg = str(item.get("message") or "")
        if not msg:
            continue
        msg_trimmed = msg.strip()
        msg_ms = _parse_ms(item.get("createDate"))
        if since_ms and msg_ms and msg_ms > since_ms:
            replied = True
        iban = extract_iban(msg)
        if iban:
            ibans.add(iban)
            if msg_trimmed != iban:
                echo_ibans.add(iban)
        phone = extract_pl_phone(msg)
        if phone:
            phones.add(phone)
            if msg_trimmed != phone:
                echo_phones.add(phone)
    return ibans, phones, echo_ibans, echo_phones, replied


def _build_request_messages(
    lang: str,
    missing_bank: bool,
    missing_iban: bool,
    missing_phone: bool,
) -> List[str]:
    suffix = message_text("ask_separate", lang)
    messages: List[str] = []
    if missing_iban:
        messages.append(f"{message_text('ask_account', lang)}\n{suffix}")
    if missing_phone:
        messages.append(f"{message_text('ask_phone', lang)}\n{suffix}")
    if missing_bank:
        messages.append(f"{message_text('ask_bank', lang)}\n{suffix}")
    return messages


def _split_existing(value: Any) -> set[str]:
    if not value or str(value).strip().lower() == "not found":
        return set()
    return {part.strip() for part in str(value).split(",") if part.strip()}


def process_chat_requirements(
    api,
    order: Dict[str, Any],
    state: Dict[str, Any],
    *,
    side: str,
    lang: str,
    credential_id: str,
    echo: bool,
    send_messages: bool,
) -> Dict[str, Any]:
    if side != "BUY":
        return {}
    currency = str(order.get("currencyId") or order.get("currency") or "").upper()
    if currency != "PLN":
        return {}

    my_account_id = _get_my_account_id(api, credential_id)
    order_id = str(order.get("id") or order.get("orderId") or "")
    if not order_id:
        return {}

    last_message_id = str(state.get("last_message_id") or "")
    params: Dict[str, Any] = {"orderId": order_id, "size": "200"}
    if last_message_id:
        params["startMessageId"] = last_message_id
    try:
        resp = api.get_chat_messages(**params)
    except Exception:
        return {}

    items = _extract_chat_items(resp)

    last_id = None
    for item in items:
        msg_id = _parse_ms(item.get("id"))
        if msg_id is not None:
            last_id = max(last_id or msg_id, msg_id)

    last_request_at = _parse_iso_dt(state.get("last_request_at"))
    since_ms = int(last_request_at.timestamp() * 1000) if last_request_at else None
    ibans, phones, echo_ibans, echo_phones, counterparty_replied = _collect_from_messages(
        items, my_account_id, since_ms
    )

    updates: Dict[str, Any] = {}
    if last_id is not None:
        updates["last_message_id"] = str(last_id)

    existing_ibans = _split_existing(state.get("to_iban"))
    existing_phones = _split_existing(state.get("to_phone"))
    new_ibans = sorted(ibans - existing_ibans)
    new_phones = sorted(phones - existing_phones)
    echo_new_ibans = sorted(set(echo_ibans) - existing_ibans)
    echo_new_phones = sorted(set(echo_phones) - existing_phones)

    if new_ibans:
        updates["to_iban"] = ", ".join(sorted(existing_ibans | set(new_ibans)))
    if new_phones:
        updates["to_phone"] = ", ".join(sorted(existing_phones | set(new_phones)))

    missing_iban = not _is_valid_value(updates.get("to_iban") or state.get("to_iban"))
    missing_phone = not _is_valid_value(updates.get("to_phone") or state.get("to_phone"))
    missing_bank = not _is_valid_value(state.get("to_bank"))
    complete = not missing_iban and not missing_phone and not missing_bank

    if send_messages:
        for item in echo_new_ibans:
            send_chat_message(api, order_id, item, credential_id, echo=echo, send=send_messages, bot_prefix=False)
        for item in echo_new_phones:
            send_chat_message(api, order_id, item, credential_id, echo=echo, send=send_messages, bot_prefix=False)

    if complete and not state.get("payment_data_complete") and (state.get("last_request_at") or counterparty_replied):
        msg = message_text("payment_complete", lang)
        send_chat_message(api, order_id, msg, credential_id, echo=echo, send=send_messages)
        updates["payment_data_complete"] = True
        return updates

    if complete:
        return updates

    allow_repeat = False
    if not last_request_at:
        allow_repeat = True
    else:
        if counterparty_replied:
            allow_repeat = True
        else:
            allow_repeat = datetime.now(timezone.utc) - last_request_at >= timedelta(minutes=5)

    if allow_repeat:
        messages = _build_request_messages(lang, missing_bank, missing_iban, missing_phone)
        for msg in messages:
            send_chat_message(api, order_id, msg, credential_id, echo=echo, send=send_messages)
        updates["last_request_at"] = datetime.now(timezone.utc).isoformat()
        updates["last_request_type"] = "BUY"
        updates["last_request_text"] = " | ".join(messages)
        updates["payment_data_complete"] = False

    return updates
