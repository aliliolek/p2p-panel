from typing import Any, Dict, List, Optional
from uuid import uuid4
from translitua import translit
from unidecode import unidecode
import pycountry

from repositories.order_state_repository import log_action
from .messages import INTRO_TEMPLATES, MESSAGES, PAYMENT_LABELS, PLN_WARNINGS, STATUS20

def country_name(code: str) -> str:
    normalized = (code or "").strip().upper()
    if not normalized:
        return ""
    try:
        country = (
            pycountry.countries.get(alpha_2=normalized)
            or pycountry.countries.get(alpha_3=normalized)
            or pycountry.countries.lookup(normalized)
        )
        if country:
            return getattr(country, "name", "") or getattr(country, "official_name", "")
    except Exception:
        pass
    return ""


def language_from_kyc(kyc_code: str) -> str:
    normalized = (kyc_code or "").strip().upper()
    if normalized in {"UA", "UKR", "UK"}:
        return "uk"
    return "en"


def pln_warning_messages(side: str, kyc_code: str) -> list[str]:
    lang = language_from_kyc(kyc_code)
    return PLN_WARNINGS.get(side, {}).get(lang, [])


def message_text(key: str, lang: str) -> str:
    msgs = MESSAGES.get(lang) or MESSAGES["en"]
    return msgs.get(key) or MESSAGES["en"].get(key, "")


def _is_latin_name(name: str) -> bool:
    if not name:
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ -'\".")
    return all(ch in allowed for ch in name)


def _normalize_realname(name: str, kyc_code: str) -> str:
    if not name:
        return "-"
    name_str = str(name)
    if _is_latin_name(name_str):
        return name_str
    kyc = (kyc_code or "").strip().upper()
    if kyc in {"UKR", "UA"} and translit:
        try:
            return translit(name_str)
        except Exception:
            pass
    if unidecode:
        try:
            return unidecode(name_str)
        except Exception:
            pass
    return name_str


def counterparty_realname(order: Dict[str, Any], counterparty: Optional[Dict[str, Any]] = None) -> str:
    try:
        side_num = int(order.get("side"))
    except Exception:
        side_num = None
    if side_num == 0:
        raw = order.get("sellerRealName") or "-"
    elif side_num == 1:
        raw = order.get("buyerRealName") or "-"
    else:
        raw = "-"
    kyc_code = (counterparty or {}).get("kycCountryCode") or ""
    return _normalize_realname(raw, kyc_code)


def format_counterparty_info(counterparty: Dict[str, Any], order: Dict[str, Any], side: str) -> str:
    nickname = counterparty.get("nickName") or "-"
    realname_en = counterparty_realname(order, counterparty)
    kyc_code = counterparty.get("kycCountryCode") or "-"
    kyc_name = country_name(kyc_code)
    sell_count = counterparty.get("totalFinishSellCount") or "0"
    buy_count = counterparty.get("totalFinishBuyCount") or "0"
    reg_days = counterparty.get("accountCreateDays") or "0"
    first_trade_days = counterparty.get("firstTradeDays") or "0"
    total_usdt = counterparty.get("totalTradeAmount") or "0"
    avg_transfer = counterparty.get("averageTransferTime") or "0"
    avg_release = counterparty.get("averageReleaseTime") or "0"
    good_appraise = counterparty.get("goodAppraiseCount") or "0"
    bad_appraise = counterparty.get("badAppraiseCount") or "0"
    lines = [
        str(nickname),
        f"🙂 {realname_en}",
        f"🌐 {kyc_code} - {kyc_name}",
        f"🕒⬆️ {avg_transfer} - ⬇️{avg_release}",
        f"🔄 🟢 {buy_count} /  🔴{sell_count}",
        f"👍 {good_appraise} / 👎 {bad_appraise}",
        f"🗓️{reg_days} / {first_trade_days}",
        f"💲 {total_usdt}",
    ]
    return "\n".join(lines)


def build_intro_message(order: Dict[str, Any], counterparty: Dict[str, Any], side: str, lang: Optional[str] = None) -> str:
    if not lang:
        kyc_code = counterparty.get("kycCountryCode") or counterparty.get("kycCountry") or ""
        lang = language_from_kyc(kyc_code)
    token = str(order.get("tokenId") or order.get("coin") or "").upper()
    currency = str(order.get("currencyId") or order.get("currency") or "").upper()
    quantity = order.get("notifyTokenQuantity") or order.get("quantity") or order.get("coinQuantity") or "-"
    amount = (
        order.get("amount")
        or order.get("fiatAmount")
        or order.get("totalAmount")
        or order.get("quantityFiat")
        or "-"
    )
    price = order.get("price") or "-"
    direction_line = f"I {side} {token} {quantity} / {currency} {amount} – ({price})"
    header = "from:" if side == "BUY" else "to:"
    return f"{direction_line}  {header}\n{format_counterparty_info(counterparty, order, side)}"


def _with_bot_prefix(text: str) -> str:
    if not text:
        return text
    prefix = "[BOT]: "
    if text.startswith(prefix):
        return text
    return f"{prefix}{text}"


def send_chat_message(
    api,
    order_id: str,
    text: str,
    credential_id: str,
    *,
    echo: bool = False,
    send: bool = True,
    bot_prefix: bool = True,
) -> None:
    outgoing = _with_bot_prefix(text) if bot_prefix else text
    if echo:
        print(f"[CHAT]{order_id}: {outgoing}")
    if not send:
        return
    try:
        api.send_chat_message(message=outgoing, contentType="str", orderId=order_id, msgUuid=uuid4().hex)
    except Exception as exc:  # pragma: no cover - third-party errors
        log_action(
            order_id,
            credential_id,
            "send_chat_message",
            request={"message": outgoing},
            response={"error": str(exc)},
            status="error",
        )


def send_payment_details(
    api,
    order_id: str,
    credential_id: str,
    info: Dict[str, str],
    *,
    echo: bool,
    send_messages: bool,
    include_title: bool = True,
    include_summary: bool = True,
    lang: str = "en",
    title_note: Optional[str] = None,
) -> None:
    labels = PAYMENT_LABELS.get(lang) or PAYMENT_LABELS["en"]
    bank_raw = info.get("bank", "Not Found")
    bank = "❓ real bank name" if str(bank_raw).strip().lower() == "bank transfer" else bank_raw
    full_name = info.get("full_name", "Not Found")
    iban = info.get("iban", "Not Found")
    phone = info.get("phone", "Not Found")
    title = info.get("order_title", "Not Found")

    send_chat_message(api, order_id, bank, credential_id, echo=echo, send=send_messages, bot_prefix=False)
    send_chat_message(api, order_id, full_name, credential_id, echo=echo, send=send_messages, bot_prefix=False)

    if iban != "Not Found":
        for item in [part.strip() for part in iban.split(",") if part.strip()]:
            send_chat_message(api, order_id, item, credential_id, echo=echo, send=send_messages, bot_prefix=False)
    if phone != "Not Found":
        for item in [part.strip() for part in phone.split(",") if part.strip()]:
            send_chat_message(api, order_id, item, credential_id, echo=echo, send=send_messages, bot_prefix=False)

    if include_title:
        send_chat_message(api, order_id, title, credential_id, echo=echo, send=send_messages, bot_prefix=False)

    if not include_summary:
        return

    block_lines = [
        f"{labels['recipient']}:\n{full_name}",
        f"{labels['account']}:\n{iban}",
        labels["or"],
        f"{labels['phone']}:\n{phone}",
    ]
    if include_title:
        block_lines.append(f"{labels['title']}:\n{title}")
        if title_note:
            block_lines.append(title_note)
    block_msg = "\n\n".join(block_lines)
    send_chat_message(api, order_id, block_msg, credential_id, echo=echo, send=send_messages, bot_prefix=False)


def maybe_ask_missing_bank_transfer(
    api, order_id: str, credential_id: str, info: Dict[str, str], *, echo: bool, send_messages: bool, lang: str = "en"
) -> None:
    payment_name = (info.get("payment_name") or "").lower()
    iban = info.get("iban", "") or ""
    phone = info.get("phone", "") or ""
    bank = info.get("bank", "") or ""
    needs_prompt = payment_name == "bank transfer" or any(
        not field or field == "Not Found" for field in (bank, iban, phone)
    )
    if not needs_prompt:
        return
    msgs = MESSAGES.get(lang) or MESSAGES["en"]
    if not bank or bank == "Not Found":
        send_chat_message(api, order_id, msgs["ask_bank"], credential_id, echo=echo, send=send_messages)
    if not iban or iban == "Not Found":
        send_chat_message(api, order_id, msgs["ask_account"], credential_id, echo=echo, send=send_messages)
    if not phone or phone == "Not Found":
        send_chat_message(api, order_id, msgs["ask_phone"], credential_id, echo=echo, send=send_messages)


def status20_message(side: str, lang: str = "en") -> str:
    return STATUS20.get(lang, STATUS20["en"]).get(side, STATUS20["en"][side])
