import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from exchanges import SUPPORTED_EXCHANGES, create_exchange_client
from repositories.credentials_repository import (
    fetch_user_credentials as repo_fetch_user_credentials,
)
from schemas import AccountAds, AdItem
from fiat_balance_marker import get_marker as get_fiat_marker
from services.credentials_service import build_exchange_credentials

PAGE_SIZE = 30
AD_STATUS_LABELS = {
    10: "Online",
    20: "Offline",
    30: "Completed",
}
AUTO_MARKER = "@@@"
AUTO_PAUSED_MARKER = "@*@"
AUTO_MARKERS = (AUTO_MARKER, AUTO_PAUSED_MARKER)
logger = logging.getLogger("p2p-panel")


def _parse_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
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


def _extract_payment_names(raw: Dict[str, Any]) -> List[str]:
    payment_terms = raw.get("paymentTerms") or []
    names: List[str] = []
    if isinstance(payment_terms, list):
        for item in payment_terms:
            if not isinstance(item, dict):
                continue
            config = item.get("paymentConfig") or {}
            name = config.get("paymentName")
            if name:
                names.append(str(name))
    return names


def _extract_payment_type_ids(raw: Dict[str, Any]) -> List[int]:
    payment_terms = raw.get("paymentTerms") or []
    ids: List[int] = []
    if isinstance(payment_terms, list):
        for item in payment_terms:
            try:
                value = int(item.get("paymentType"))
                ids.append(value)
            except Exception:
                continue
    return ids


def _is_fiat_balance_ad(ad: AdItem) -> bool:
    remark = ad.remark or ""
    if 416 not in ad.payment_type_ids:
        return False
    marker = get_fiat_marker()
    return marker in remark


def _extract_ads_list(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    result = response.get("result")
    if not isinstance(result, dict):
        return []
    items = result.get("items")
    if isinstance(items, list):
        return items
    return []


def _format_ad(raw: Dict[str, Any]) -> AdItem:
    token = raw.get("tokenId") or raw.get("coin")
    token = token.upper() if isinstance(token, str) else token
    side = _normalize_side(raw.get("side"))
    price = _parse_float(raw.get("price"))
    crypto_amount = _parse_float(raw.get("lastQuantity") or raw.get("quantity"))
    fiat_amount = None
    if crypto_amount is not None and price is not None:
        fiat_amount = crypto_amount * price
    status_code = raw.get("status")
    status_label = AD_STATUS_LABELS.get(status_code, f"Status {status_code}")
    return AdItem(
        ad_id=str(raw.get("id") or raw.get("itemId") or ""),
        side=side,
        token=token,
        fiat_currency=raw.get("currencyId") or raw.get("currency"),
        price=price,
        crypto_amount=crypto_amount,
        fiat_amount=fiat_amount,
        fee=_parse_float(raw.get("fee")),
        min_amount=_parse_float(raw.get("minAmount")),
        max_amount=_parse_float(raw.get("maxAmount")),
        status_code=status_code,
        status_label=status_label,
        updated_at=_parse_datetime(raw.get("updateDate") or raw.get("updatedAt")),
        payment_methods=_extract_payment_names(raw),
        remark=str(raw.get("remark") or ""),
        payment_type_ids=_extract_payment_type_ids(raw),
    )


def _load_bybit_ads(creds) -> List[Dict[str, Any]]:
    client = create_exchange_client(creds)
    ads: List[Dict[str, Any]] = []
    page = 1
    while True:
        response = client.get_ads_list(page=str(page), size=str(PAGE_SIZE))
        batch = _extract_ads_list(response)
        if not batch:
            break
        ads.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    return ads


def _save_snapshot(credential_id: str, ads: List[Dict[str, Any]]) -> None:
    try:
        output_dir = Path("playground_results")
        output_dir.mkdir(exist_ok=True)
        target = output_dir / f"ads_{credential_id}.json"
        with target.open("w", encoding="utf-8") as fh:
            json.dump(ads, fh, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _find_user_credential(user_id: str, credential_id: str) -> Dict[str, Any]:
    rows = repo_fetch_user_credentials(user_id)
    for row in rows:
        if str(row.get("id")) == str(credential_id):
            return row
    raise ValueError("Credential not found for user")


def _load_single_ad(creds, ad_id: str) -> Dict[str, Any]:
    ads = _load_bybit_ads(creds)
    for ad in ads:
        if str(ad.get("id") or ad.get("itemId") or ad.get("ad_id")) == str(ad_id):
            return ad
    raise ValueError("Ad not found")


def _strip_auto_markers(text: str) -> str:
    cleaned = str(text or "")
    for marker in AUTO_MARKERS:
        cleaned = cleaned.replace(marker, "")
    return cleaned.rstrip()


def _extract_payment_ids(ad: Dict[str, Any]) -> List[str]:
    if ad.get("paymentIds"):
        return [str(pid) for pid in ad.get("paymentIds") if pid]
    payment_terms = ad.get("paymentTerms")
    if isinstance(payment_terms, list):
        ids: List[str] = []
        for item in payment_terms:
            pid = item.get("id") if isinstance(item, dict) else None
            if pid:
                ids.append(str(pid))
        if ids:
            return ids
    payments = ad.get("payments")
    if isinstance(payments, list):
        return [str(pid) for pid in payments if pid]
    return []


def _apply_auto_marker(text: str, enable: bool) -> str:
    base = _strip_auto_markers(text)
    suffix_space = "" if not base or base.endswith((" ", "\n")) else " "
    return f"{base}{suffix_space}{AUTO_MARKER if enable else AUTO_PAUSED_MARKER}"


def _pick_ad_field(ad: Dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in ad:
            return ad.get(key)
    return default


def _build_update_payload(ad: Dict[str, Any], remark: str) -> Dict[str, Any]:
    return {
        "id": str(_pick_ad_field(ad, "id", "itemId", "ad_id", default="")),
        "priceType": str(_pick_ad_field(ad, "priceType", default="0")),
        "premium": str(_pick_ad_field(ad, "premium", default="0")),
        "price": str(_pick_ad_field(ad, "price", default="")),
        "minAmount": str(_pick_ad_field(ad, "minAmount", "min_amount", default="")),
        "maxAmount": str(_pick_ad_field(ad, "maxAmount", "max_amount", default="")),
        "remark": remark,
        "tradingPreferenceSet": _pick_ad_field(ad, "tradingPreferenceSet", default={}) or {},
        "paymentIds": _extract_payment_ids(ad),
        "actionType": "MODIFY",
        "quantity": str(_pick_ad_field(ad, "lastQuantity", default="")),
        "paymentPeriod": str(_pick_ad_field(ad, "paymentPeriod", default="15")),
    }


async def get_ads(user_id: str) -> List[AccountAds]:
    rows = await asyncio.to_thread(repo_fetch_user_credentials, user_id)
    accounts: List[AccountAds] = []
    for row in rows:
        exchange = row.get("exchange")
        if exchange not in SUPPORTED_EXCHANGES or exchange != "bybit":
            continue
        creds = build_exchange_credentials(row)
        try:
            raw_ads = await asyncio.to_thread(_load_bybit_ads, creds)
            _save_snapshot(row["id"], raw_ads)
            ads = [_format_ad(item) for item in raw_ads]
            fiat_balance_ads = [ad for ad in ads if _is_fiat_balance_ad(ad)]
            error = None
        except Exception as exc:  # pragma: no cover
            ads = []
            fiat_balance_ads = []
            error = str(exc)
        accounts.append(
            AccountAds(
                credential_id=row["id"],
                account_label=row.get("account_label"),
                exchange=exchange,
                ads=ads,
                fiat_balance_ads=fiat_balance_ads,
                error=error,
            )
        )
    return accounts


async def toggle_auto_marker(user_id: str, credential_id: str, ad_id: str, enable: bool) -> Dict[str, Any]:
    row = await asyncio.to_thread(_find_user_credential, user_id, credential_id)
    creds = build_exchange_credentials(row)
    api = create_exchange_client(creds)
    ad = await asyncio.to_thread(_load_single_ad, creds, ad_id)
    remark = ad.get("remark") or ""
    new_remark = _apply_auto_marker(remark, enable)
    payload = _build_update_payload(ad, new_remark)
    try:
        resp = await asyncio.to_thread(api.update_ad, **payload)
    except Exception as exc:  # pragma: no cover - third-party error
        raw_error = getattr(exc, "args", None) or str(exc)
        logger.error("toggle_auto_marker failed ad=%s enable=%s raw=%r", ad_id, enable, raw_error)
        return {"remark": remark, "response": {"error": str(exc), "raw": raw_error}}
    logger.info("toggle_auto_marker ad=%s enable=%s resp=%s", ad_id, enable, resp)
    return {"remark": new_remark, "response": resp}


async def take_ad_offline(user_id: str, credential_id: str, ad_id: str) -> Dict[str, Any]:
    row = await asyncio.to_thread(_find_user_credential, user_id, credential_id)
    creds = build_exchange_credentials(row)
    api = create_exchange_client(creds)
    ad = await asyncio.to_thread(_load_single_ad, creds, ad_id)
    remark = ad.get("remark") or ""
    update_resp = None
    # If it was auto, pause it first
    if any(marker in remark for marker in AUTO_MARKERS):
        new_remark = _apply_auto_marker(remark, enable=False)
        payload = _build_update_payload(ad, new_remark)
        update_resp = await asyncio.to_thread(api.update_ad, **payload)
        logger.info("take_ad_offline update_remark ad=%s resp=%s", ad_id, update_resp)
    remove_resp = await asyncio.to_thread(api.remove_ad, itemId=str(ad_id))
    logger.info("take_ad_offline remove ad=%s resp=%s", ad_id, remove_resp)
    return {"remark_update": update_resp, "remove_response": remove_resp}


async def activate_ad(user_id: str, credential_id: str, ad_id: str) -> Dict[str, Any]:
    row = await asyncio.to_thread(_find_user_credential, user_id, credential_id)
    creds = build_exchange_credentials(row)
    api = create_exchange_client(creds)
    ad = await asyncio.to_thread(_load_single_ad, creds, ad_id)
    remark = ad.get("remark") or ""
    payload = _build_update_payload(ad, remark)
    payload["actionType"] = "ACTIVE"
    resp = await asyncio.to_thread(api.update_ad, **payload)
    logger.info("activate_ad ad=%s resp=%s", ad_id, resp)
    return {"remark": remark, "response": resp}
