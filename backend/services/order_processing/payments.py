from typing import Any, Dict, List, Optional, Set

from services.payment_parser import SKIP_PAYMENT_TYPE, parse_pln_payment_terms
from .constants import PAYMENT_FIELDS


def format_order_title(order_id: str, token_id: Optional[str]) -> str:
    token = token_id or "usdt"
    suffix = f" {order_id}" if order_id else ""
    return f"zakup {token} na bybit{suffix}"


def normalize_numeric_string(text: str) -> str:
    if not text:
        return ""
    trimmed = "".join(ch for ch in text if ch.isdigit() or ch.isspace())
    return trimmed.replace(" ", "")


def extract_iban(text: str) -> Optional[str]:
    digits = normalize_numeric_string(text)
    return digits if digits.isdigit() and len(digits) == 26 else None


def extract_pl_phone(text: str) -> Optional[str]:
    digits = normalize_numeric_string(text)
    if len(digits) == 9 and digits.isdigit():
        return digits
    if digits.startswith("48") and len(digits) == 11 and digits[2:].isdigit():
        return digits[2:]
    return None


def payment_terms(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    terms = order.get("paymentTermList") or order.get("paymentTerms") or []
    return terms if isinstance(terms, list) else []


def get_my_payment_with_hash(api) -> Optional[Dict[str, Any]]:
    try:
        resp = api.get_user_payment_types()
        methods = resp.get("result") or []
        for method in methods:
            branch = str(method.get("branchName") or "")
            if branch.startswith("###"):
                return method
    except Exception:
        return None
    return None


def _collect_contacts_from_terms(terms: List[Dict[str, Any]]) -> tuple[Set[str], Set[str]]:
    ibans: Set[str] = set()
    phones: Set[str] = set()
    for term in terms:
        for field in PAYMENT_FIELDS:
            val = str(term.get(field, "") or "")
            iban = extract_iban(val)
            if iban:
                ibans.add(iban)
            phone = extract_pl_phone(val)
            if phone:
                phones.add(phone)
    return ibans, phones


def extract_pln_payment_buy(order: Dict[str, Any]) -> Dict[str, str]:
    order_id = str(order.get("id") or order.get("orderId") or "")
    token_id = str(order.get("tokenId") or order.get("tokenName") or "")
    terms = payment_terms(order)
    ibans, phones = _collect_contacts_from_terms(terms)

    full_name = ""
    bank_name = ""
    payment_name = ""
    for term in terms:
        payment_name = payment_name or term.get("paymentConfigVo", {}).get("paymentName", "") or ""
        if not bank_name:
            bank_name = term.get("paymentConfigVo", {}).get("paymentName", "") or term.get("bankName", "") or ""
        if not full_name:
            full_name = term.get("realName", "") or term.get("firstName", "")

    iban_text = ", ".join(sorted(ibans)) if ibans else "Not Found"
    phone_text = ", ".join(sorted(phones)) if phones else "Not Found"
    return {
        "bank": bank_name or "Not Found",
        "phone": phone_text,
        "full_name": full_name or "Not Found",
        "iban": iban_text,
        "order_title": format_order_title(order_id, token_id),
        "payment_name": payment_name or "",
    }


def extract_pln_payment_sell(api, order_id: str = "", token_id: Optional[str] = None) -> Dict[str, str]:
    method = get_my_payment_with_hash(api) or {}
    iban = extract_iban(method.get("accountNo", ""))
    phone = extract_pl_phone(method.get("bankName", "")) or extract_pl_phone(method.get("accountNo", ""))
    realname = method.get("realName") or ""
    fallback_order_id = order_id or method.get("id") or ""
    title_token = token_id or method.get("tokenId") or method.get("tokenName")
    return {
        "bank": "PKO Bank",
        "phone": phone or "Not Found",
        "full_name": realname or "Not Found",
        "iban": iban or "Not Found",
        "order_title": format_order_title(fallback_order_id, title_token) if fallback_order_id else "",
        "payment_name": method.get("paymentConfigVo", {}).get("paymentName", "") or "Bank Transfer",
    }


def extract_payment_type(order: Dict[str, Any]) -> Optional[str]:
    terms = order.get("paymentTermList") or order.get("paymentTerms")
    if isinstance(terms, list) and terms:
        pt = terms[0].get("paymentType")
        if pt is not None:
            return str(pt)
    pt_top = order.get("paymentType")
    if pt_top is not None:
        return str(pt_top)
    return None


def extract_payment_id(order: Dict[str, Any]) -> Optional[str]:
    terms = order.get("paymentTermList") or order.get("paymentTerms")
    if isinstance(terms, list) and terms:
        pid = terms[0].get("id")
        if pid is not None:
            return str(pid)
    pid_top = order.get("paymentId")
    if pid_top is not None:
        return str(pid_top)
    return None


def extract_payment_info_buy(order: Dict[str, Any], missing_text: Optional[str] = None) -> str:
    missing_text = missing_text or "Payment details are missing; please share bank name, account number or phone, and payment title."
    terms = order.get("paymentTermList") or []
    if not isinstance(terms, list) or not terms:
        return missing_text
    term = terms[0]
    currency = str(order.get("currencyId") or order.get("currency") or "").upper()
    payment_type = str(term.get("paymentType") or "")
    if currency == "PLN" and payment_type != SKIP_PAYMENT_TYPE:
        return parse_pln_payment_terms(order)
    for key in ["accountNo", "mobile", "concept", "payMessage"]:
        val = term.get(key)
        if val:
            return str(val)
    return missing_text


def extract_payment_info_sell(
    order: Dict[str, Any],
    api,
    *,
    manual_text: Optional[str] = None,
    pko_text: Optional[str] = None,
) -> str:
    manual_text = manual_text or "Payment details will be provided manually in chat."
    pko_text = pko_text or "PKO details will be provided manually."
    currency = str(order.get("currencyId") or order.get("currency") or "").upper()
    terms = order.get("paymentTermList") or []
    if currency == "PLN":
        method = get_my_payment_with_hash(api)
        if method:
            iban = method.get("accountNo") or "-"
            realname = method.get("realName") or "-"
            return f"PKO: {iban} {realname}"
        return pko_text
    if not isinstance(terms, list) or not terms:
        return manual_text
    return manual_text
