import logging
from datetime import datetime
from typing import Any, Dict, Optional

from repositories.order_state_repository import fetch_state, log_action, update_flags, upsert_state
from services.orders_service import _fetch_counterparty_info

from services.payment_parser import SKIP_PAYMENT_TYPE
from .messaging import (
    counterparty_realname,
    build_intro_message,
    language_from_kyc,
    message_text,
    pln_warning_messages,
    send_chat_message,
    send_payment_details,
    status20_message,
)
from .chat_requirements import process_chat_requirements
from .payments import (
    extract_payment_id,
    extract_payment_info_buy,
    extract_payment_info_sell,
    extract_payment_type,
    extract_pln_payment_buy,
    extract_pln_payment_sell,
    format_order_title,
)

logger = logging.getLogger("p2p-panel")


def _is_valid_value(value: Any) -> bool:
    return bool(value) and str(value).strip().lower() != "not found"


def _extract_confirmed_payment_name(order: Dict[str, Any]) -> str:
    term = order.get("confirmedPayTerm") or {}
    if isinstance(term, dict):
        name = (
            term.get("paymentName")
            or (term.get("paymentConfig") or {}).get("paymentName")
            or (term.get("paymentConfigVo") or {}).get("paymentName")
        )
        if name:
            return str(name)
    return ""


def _build_payment_state_fields(
    api,
    order: Dict[str, Any],
    side: str,
    counterparty: Dict[str, Any],
) -> tuple[Dict[str, Any], set[str]]:
    currency = str(order.get("currencyId") or order.get("currency") or "").upper()
    if currency != "PLN":
        return {}, set()

    order_id = str(order.get("id") or order.get("orderId") or "")
    token_id = str(order.get("tokenId") or order.get("tokenName") or "")
    if side == "BUY":
        my_info = extract_pln_payment_sell(api, order_id, token_id)
        to_info = extract_pln_payment_buy(order)
        to_info["full_name"] = counterparty_realname(order, counterparty)
        order_title = to_info.get("order_title") or my_info.get("order_title") or format_order_title(order_id, token_id)
        return {
            "from_full_name": my_info.get("full_name"),
            "to_bank": to_info.get("bank"),
            "to_phone": to_info.get("phone"),
            "to_full_name": to_info.get("full_name"),
            "to_iban": to_info.get("iban"),
            "order_title": order_title,
        }, set()

    confirmed_name = _extract_confirmed_payment_name(order)
    my_info = extract_pln_payment_sell(api, order_id, token_id)
    order_title = my_info.get("order_title") or format_order_title(order_id, token_id)
    return {
        "from_bank": confirmed_name,
        "from_full_name": counterparty_realname(order, counterparty),
        "to_full_name": my_info.get("full_name"),
        "order_title": order_title,
    }, {"from_phone", "from_iban"}


def _apply_payment_state_fields(
    state: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    overwrite_fields: set[str],
    clear_fields: set[str],
) -> None:
    for key in clear_fields:
        state[key] = None
    for key, value in payload.items():
        if value is None or not _is_valid_value(value):
            continue
        if key in overwrite_fields or not state.get(key):
            state[key] = value


def load_order_details(api, order_id: str) -> Optional[Dict[str, Any]]:
    try:
        response = api.get_order_details(orderId=order_id)
    except Exception:  # pragma: no cover - network/API failures
        return None
    if not isinstance(response, dict):
        return None
    details = response.get("result")
    if isinstance(details, dict):
        return details
    return None


def resolve_payment_term(api, order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    terms = order.get("paymentTermList") or order.get("paymentTerms") or []
    if isinstance(terms, list) and terms:
        return terms[0]
    details = api.get_order_details(orderId=str(order.get("id") or order.get("orderId") or ""))
    result = details.get("result") if isinstance(details, dict) else None
    if isinstance(result, dict):
        term_list = result.get("paymentTermList") or []
        if isinstance(term_list, list) and term_list:
            order["paymentTermList"] = term_list
            return term_list[0]
    return None


def should_mark_paid(order: Dict[str, Any], payment_type: Optional[str], state: Dict[str, Any]) -> bool:
    side = str(order.get("side")).upper()
    status = str(order.get("status"))
    if side not in {"0", "BUY"}:
        return False
    if status != "10":
        return False
    if payment_type == SKIP_PAYMENT_TYPE:
        return False
    return not state.get("mark_paid_sent")


def mark_as_paid(api, order: Dict[str, Any]) -> Dict[str, Any]:
    order_id = str(order.get("id") or order.get("orderId") or "")
    term = resolve_payment_term(api, order)
    payment_type = str(term.get("paymentType")) if term else ""
    payment_id = str(term.get("id")) if term else ""
    payload = {
        "orderId": order_id,
        "paymentType": str(payment_type),
        "paymentId": payment_id or "",
    }
    resp = api.mark_as_paid(**payload)
    logger.info("mark_as_paid order=%s resp=%s", order_id, resp)
    return resp


def _handle_payment_info_buy(
    api,
    order: Dict[str, Any],
    credential_id: str,
    *,
    echo: bool,
    send_messages: bool,
    lang: str,
    counterparty: Optional[Dict[str, Any]] = None,
) -> None:
    currency = str(order.get("currencyId") or order.get("currency") or "").upper()
    order_id = str(order.get("id") or order.get("orderId") or "")
    if currency == "PLN":
        info = extract_pln_payment_buy(order)
        info["full_name"] = counterparty_realname(order, counterparty)
        send_chat_message(
            api,
            order_id,
            message_text("bot_check", lang),
            credential_id,
            echo=echo,
            send=send_messages,
        )
        send_payment_details(
            api,
            order_id,
            credential_id,
            info,
            echo=echo,
            send_messages=send_messages,
            include_summary=False,
            lang=lang,
            title_note=message_text("title_note", lang),
        )
    else:
        msg = extract_payment_info_buy(order, missing_text=message_text("payment_missing", lang))
        send_chat_message(api, order_id, msg, credential_id, echo=echo, send=send_messages)


def _handle_payment_info_sell(
    api,
    order: Dict[str, Any],
    credential_id: str,
    *,
    echo: bool,
    send_messages: bool,
    lang: str,
) -> None:
    currency = str(order.get("currencyId") or order.get("currency") or "").upper()
    order_id = str(order.get("id") or order.get("orderId") or "")
    if currency == "PLN":
        token_id = str(order.get("tokenId") or order.get("tokenName") or "")
        info = extract_pln_payment_sell(api, order_id, token_id)
        send_chat_message(
            api,
            order_id,
            message_text("bot_send", lang),
            credential_id,
            echo=echo,
            send=send_messages,
        )
        send_payment_details(
            api,
            order_id,
            credential_id,
            info,
            echo=echo,
            send_messages=send_messages,
            include_title=True,
            lang=lang,
            title_note=message_text("title_note", lang),
        )
    else:
        msg = extract_payment_info_sell(
            order,
            api,
            manual_text=message_text("manual_details", lang),
            pko_text=message_text("manual_payment_details", lang),
        )
        send_chat_message(api, order_id, msg, credential_id, echo=echo, send=send_messages)


def process_single_order(
    api,
    creds: Dict[str, Any],
    order: Dict[str, Any],
    record_state: bool = True,
    echo: bool = False,
    force_all_messages: bool = False,
    send_messages: bool = True,
) -> None:
    order_id = str(order.get("id") or order.get("orderId") or "")
    if not order_id:
        return
    order_details = load_order_details(api, order_id)
    if order_details:
        order = order_details
    counterparty_info = order.get("counterparty_info") or _fetch_counterparty_info(api, order) or {}
    payment_type = extract_payment_type(order)
    if payment_type == SKIP_PAYMENT_TYPE:
        return
    side = "SELL" if str(order.get("side")) in {"1", "sell", "SELL"} else "BUY"
    currency = str(order.get("currencyId") or order.get("currency") or "").upper()
    lang = language_from_kyc(counterparty_info.get("kycCountryCode") or counterparty_info.get("kycCountry") or "")
    state = fetch_state(order_id) if record_state else None
    if not state:
        state = {
            "order_id": order_id,
            "credential_id": creds.get("id", ""),
            "exchange": "bybit",
            "side": side,
            "status_code": order.get("status"),
            "payment_type": payment_type,
            "first_messages_sent": False,
            "counterparty_msg_sent": False,
            "payment_info_sent": False,
            "status20_msg_sent": False,
            "mark_paid_sent": False,
        }
    state["status_code"] = order.get("status")
    state["payment_type"] = payment_type
    state["last_seen_at"] = datetime.utcnow().isoformat()
    payment_fields, clear_fields = _build_payment_state_fields(api, order, side, counterparty_info)
    _apply_payment_state_fields(
        state,
        payment_fields,
        overwrite_fields={"from_bank"},
        clear_fields=clear_fields,
    )
    if record_state:
        upsert_state(state)

    if not state.get("first_messages_sent"):
        if currency == "PLN":
            kyc_code = counterparty_info.get("kycCountryCode") or counterparty_info.get("kycCountry") or ""
            for msg in pln_warning_messages(side, kyc_code):
                send_chat_message(api, order_id, msg, creds["id"], echo=echo, send=send_messages)
        text = build_intro_message(order, counterparty_info, side, lang=lang)
        send_chat_message(api, order_id, text, creds["id"], echo=echo, send=send_messages, bot_prefix=False)
        if record_state:
            update_flags(order_id, first_messages_sent=True, counterparty_msg_sent=True)
            log_action(order_id, creds["id"], "first_message", request={"message": text})

    if not state.get("payment_info_sent"):
        if side == "BUY":
            _handle_payment_info_buy(
                api,
                order,
                creds["id"],
                echo=echo,
                send_messages=send_messages,
                lang=lang,
                counterparty=counterparty_info,
            )
        else:
            _handle_payment_info_sell(api, order, creds["id"], echo=echo, send_messages=send_messages, lang=lang)
        if record_state:
            update_flags(order_id, payment_info_sent=True)
            log_action(order_id, creds["id"], "payment_info", request={"message": "sent"})

    chat_updates = process_chat_requirements(
        api,
        order,
        state,
        side=side,
        lang=lang,
        credential_id=creds.get("id", ""),
        echo=echo,
        send_messages=send_messages,
    )
    if record_state and chat_updates:
        update_flags(order_id, **chat_updates)
        state.update(chat_updates)

    if (force_all_messages or str(order.get("status")) == "20") and not state.get("status20_msg_sent"):
        text = status20_message(side, lang=lang)
        send_chat_message(api, order_id, text, creds["id"], echo=echo, send=send_messages)
        if record_state:
            update_flags(order_id, status20_msg_sent=True)
            log_action(order_id, creds["id"], "status20_message", request={"message": text})

    if should_mark_paid(order, payment_type, state):
        resp = mark_as_paid(api, order)
        status_text = resp.get("ret_msg") if isinstance(resp, dict) else ""
        if status_text and status_text.lower() != "success":
            logger.error("mark_as_paid error order=%s resp=%s", order_id, resp)
            if record_state:
                log_action(order_id, creds["id"], "mark_as_paid", response=resp, status="error")
        else:
            if record_state:
                log_action(order_id, creds["id"], "mark_as_paid", response=resp, status="success")
                update_flags(order_id, mark_paid_sent=True)
