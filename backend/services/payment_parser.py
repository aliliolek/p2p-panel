import re
from typing import Dict, List, Optional

SKIP_PAYMENT_TYPE = "416"


def _normalize_numeric(text: str) -> str:
    if not text:
        return ""
    trimmed = re.sub(r"^[^\d]+|[^\d]+$", "", text)
    return trimmed.replace(" ", "")


def extract_iban(value: str) -> Optional[str]:
    digits = _normalize_numeric(value)
    return digits if re.fullmatch(r"\d{26}", digits) else None


def extract_polish_phone(value: str) -> Optional[str]:
    digits = _normalize_numeric(value)
    if re.fullmatch(r"\d{9}", digits):
        return digits
    if re.fullmatch(r"48\d{9}", digits):
        return digits[2:]
    return None


def parse_pln_payment_terms(order: Dict[str, any]) -> str:
    terms: List[Dict[str, any]] = order.get("paymentTermList") or []
    if not isinstance(terms, list) or not terms:
        return "не знайдено коректних даних для оплати"

    unique_ibans = set()
    unique_phones = set()
    first_real_name = None
    first_bank_name = None

    fields = [
        "bankName",
        "branchName",
        "accountNo",
        "payMessage",
        "mobile",
        "concept",
        "paymentExt1",
        "paymentExt2",
        "paymentExt3",
        "paymentExt4",
        "paymentExt5",
        "paymentExt6",
        "firstName",
        "lastName",
    ]

    for term in terms:
        for key in fields:
            val = term.get(key)
            if not val:
                continue
            iban = extract_iban(str(val))
            if iban:
                unique_ibans.add(iban)
            phone = extract_polish_phone(str(val))
            if phone:
                unique_phones.add(phone)
        if not first_real_name:
            real_name = term.get("realName")
            if real_name:
                first_real_name = str(real_name).strip()
        if not first_bank_name:
            bank_name = (
                term.get("paymentConfigVo", {}) or {}
            ).get("paymentName") or term.get("bankName")
            if bank_name:
                first_bank_name = str(bank_name).strip()

    final_iban = ", ".join(sorted(unique_ibans)) if unique_ibans else "Not Found"
    final_phone = ", ".join(sorted(unique_phones)) if unique_phones else "Not Found"
    final_name = first_real_name or "Not Found"
    final_bank = first_bank_name or "Not Found"

    return (
        f"bank: {final_bank}\n"
        f"phone: {final_phone}\n"
        f"full_name: {final_name}\n"
        f"iban: {final_iban}"
    )
