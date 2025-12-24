import asyncio
import contextlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
import math
from pathlib import Path
import json

from exchanges import create_exchange_client
from services.ads_service import _build_update_payload
from services.credentials_service import build_exchange_credentials
from repositories.credentials_repository import fetch_all_credentials
from tools.auto_pricing import (
    AUTO_MARKER,
    AUTO_PAUSED_MARKER,
    AutoAdContext,
    _group_competitors_by_price,
    _to_float,
    collect_auto_pricing_contexts,
)

logger = logging.getLogger("p2p-panel")

SPOT_TICKERS_URL = "https://api.bybit.com/v5/market/tickers"
MIN_SELL_BALANCE = {"BTC": 0.00005, "ETH": 0.001}
FALLBACK_SELL_MULTIPLIER = {"BTC": 1.28, "ETH": 1.28, "USDT": 1.19, "USDC": 1.19}
FALLBACK_BUY_MULTIPLIER = {"BTC": 0.72, "ETH": 0.72, "USDT": 0.81, "USDC": 0.81}
GUARDRAIL_PCT = {"BTC": 0.05, "ETH": 0.05, "USDT": 0.008, "USDC": 0.02}
TOKEN_PRECISION = {"BTC": 8, "ETH": 8, "USDT": 4, "USDC": 4}
PRICE_PRECISION = 2
SNAPSHOT_PATH = Path("playground_results/auto_pricing_cycle.json")
_snapshot_written = False
BUY_FIXED_QTY = {"BTC": 0.25, "ETH": 16.0, "USDT": 49000.0, "USDC": 49000.0}


def _normalize_side(value: Any) -> str:
    if value is None:
        return ""
    try:
        num = int(value)
        if num == 1:
            return "SELL"
        if num == 0:
            return "BUY"
    except Exception:
        pass
    return ""


def _extract_remark_flags(ad: Dict[str, Any]) -> tuple[bool, bool]:
    remark = str(ad.get("remark") or "")
    is_auto = AUTO_MARKER in remark
    is_paused = AUTO_PAUSED_MARKER in remark
    return is_auto, is_paused


def _summarize_price_groups(groups: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for group in groups:
        prices = [_to_float(item.get("price")) for item in group]
        prices = [price for price in prices if price is not None]
        if not prices:
            continue
        summary.append(
            {
                "min_price": min(prices),
                "max_price": max(prices),
                "competitor_count": len(group),
            }
        )
    return summary


def _spot_quote(token: str, fiat: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    token_up = token.upper()
    fiat_up = fiat.upper()
    # Special case: USDC/PLN -> use USDT/PLN as proxy
    if token_up == "USDC" and fiat_up == "PLN":
        symbol = "USDTPLN"
    else:
        symbol = f"{token_up}{fiat_up}"
    if token_up in {"USDT", "USDC"} and fiat_up == "USD":
        return 1.0, 1.0, "USDTUSD"
    resp = requests.get(
        SPOT_TICKERS_URL,
        params={"category": "spot", "symbol": symbol},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("result", {}).get("list") or []
    if not items:
        return None, None, symbol
    ticker = items[0]
    bid = _to_float(ticker.get("bid1Price"))
    ask = _to_float(ticker.get("ask1Price"))
    last_price = _to_float(ticker.get("lastPrice"))
    return bid or last_price, ask or last_price, symbol


def _price_precision(raw_price: Any, fiat: str) -> int:
    return PRICE_PRECISION


def _price_step(fiat: str, precision: Optional[int] = None) -> float:
    prec = PRICE_PRECISION if precision is None else precision
    return 10 ** (-prec)


def _auto_update_flags(remark: str) -> tuple[bool, bool]:
    text = str(remark or "").lower()
    has_p = "#p" in text
    has_q = "#q" in text
    if not (has_p or has_q):
        return True, True
    return has_p, has_q


def _select_competitor(token: str, side: str, groups: List[List[Dict[str, Any]]], sorted_comps: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if token.upper() == "USDT":
        for group in groups:
            if len(group) > 1:
                return group[0]
        return sorted_comps[0] if sorted_comps else None
    return sorted_comps[0] if sorted_comps else None


def _guardrail_filter_competitors(
    side: str,
    token: str,
    spot: Optional[float],
    competitors: List[Dict[str, Any]],
    step: float,
) -> List[Dict[str, Any]]:
    if spot is None or not competitors:
        return []
    guard = GUARDRAIL_PCT.get(token.upper(), 0.02)
    if side == "SELL":
        floor = spot * (1 + guard)
        threshold = floor + step
        return [c for c in competitors if (_to_float(c.get("price")) or 0.0) >= threshold]
    if side == "BUY":
        ceiling = spot * (1 - guard)
        threshold = ceiling - step
        return [c for c in competitors if (_to_float(c.get("price")) or 0.0) <= threshold]
    return list(competitors)


def _fallback_price(side: str, token: str, spot: Optional[float]) -> Optional[float]:
    if spot is None:
        return None
    token_up = token.upper()
    if side == "SELL":
        return spot * FALLBACK_SELL_MULTIPLIER.get(token_up, 1.1)
    if side == "BUY":
        return spot * FALLBACK_BUY_MULTIPLIER.get(token_up, 0.9)
    return None


def _target_price(side: str, competitor: Optional[Dict[str, Any]], step: float, fallback: Optional[float]) -> Optional[float]:
    comp_price = _to_float(competitor.get("price")) if competitor else None
    if comp_price is None:
        return fallback
    if side == "SELL":
        return comp_price - step
    if side == "BUY":
        return comp_price + step
    return fallback


def _load_fund_balances(client) -> Dict[str, float]:
    try:
        resp = client.get_current_balance(accountType="FUND")
        items = resp.get("result", {}).get("balance", [])
    except Exception:
        items = []
    balances: Dict[str, float] = {}
    for item in items:
        token = str(item.get("coin") or "").upper()
        avail = item.get("availableBalance") or item.get("transferBalance") or item.get("walletBalance")
        try:
            balances[token] = float(avail)
        except Exception:
            continue
    return balances


def _min_qty_from_limits(ad: Dict[str, Any], price: float) -> float:
    min_amount = _to_float(ad.get("minAmount") or ad.get("min_amount")) or 0.0
    if price and price > 0:
        return min_amount / price
    return 0.0


def _token_precision(token: str) -> int:
    return TOKEN_PRECISION.get(token.upper(), 8)


def _should_skip(price_new: float, qty_new: float, price_old: Optional[float], qty_old: Optional[float], step: float) -> bool:
    unchanged_price = price_old is not None and abs(price_new - price_old) < step * 0.1
    unchanged_qty = qty_old is not None and abs(qty_new - qty_old) < 1e-9
    return unchanged_price and unchanged_qty


def _should_skip_update(
    price_new: float,
    qty_new: float,
    price_old: Optional[float],
    qty_old: Optional[float],
    step: float,
    update_price: bool,
    update_qty: bool,
) -> bool:
    unchanged_price = price_old is not None and abs(price_new - price_old) < step * 0.1
    unchanged_qty = qty_old is not None and abs(qty_new - qty_old) < 1e-9
    if update_price and update_qty:
        return unchanged_price and unchanged_qty
    if update_price:
        return unchanged_price
    if update_qty:
        return unchanged_qty
    return True


def _build_status_entry(ad: Dict[str, Any], price: float, qty: float, groups: List[List[Dict[str, Any]]], target_price: Optional[float], spot: Optional[Tuple[Optional[float], Optional[float], Optional[str]]] = None) -> Dict[str, Any]:
    ad_id = str(ad.get("id") or ad.get("ad_id") or "")
    is_auto, is_paused = _extract_remark_flags(ad)
    bid = ask = symbol = None
    if spot:
        bid, ask, symbol = spot
    return {
        "ad_id": ad_id,
        "token": str(ad.get("tokenId") or ad.get("token") or ""),
        "fiat_currency": str(ad.get("currencyId") or ad.get("currency") or ""),
        "side": _normalize_side(ad.get("side")),
        "price": price,
        "desired_qty": qty,
        "is_auto_enabled": bool(is_auto and not is_paused),
        "is_auto_paused": bool(is_paused),
        "target_price": target_price,
        "spot_symbol": symbol,
        "spot_bid": bid,
        "spot_ask": ask,
        "competitor_groups": _summarize_price_groups(groups),
    }


def _update_single_ad(client, ad: Dict[str, Any], price: float, qty: float, fiat: str, side: str) -> Optional[Dict[str, Any]]:
    payload = _build_update_payload(ad, ad.get("remark") or "")
    payload["price"] = str(price)
    payload["quantity"] = str(qty)
    status = str(ad.get("status") or "")
    payload["actionType"] = "MODIFY" if status == "10" else "ACTIVE"
    return client.update_ad(**payload)


def _apply_pricing() -> List[Dict[str, Any]]:
    global _snapshot_written
    rows = fetch_all_credentials()
    if not rows:
        return []
    statuses: List[Dict[str, Any]] = []
    snapshot_collect = not _snapshot_written
    snapshot_entries_all: List[Dict[str, Any]] = []
    for row in rows:
        creds = build_exchange_credentials(row)
        client = create_exchange_client(creds)
        balances = _load_fund_balances(client)
        contexts = collect_auto_pricing_contexts(creds)
        spot_cache: Dict[Tuple[str, str], Tuple[Optional[float], Optional[float], Optional[str]]] = {}
        snapshot_entries: List[Dict[str, Any]] = []
        for ctx in contexts:
            ad = ctx.ad
            status = str(ad.get("status") or "")
            remark = str(ad.get("remark") or "")
            side = _normalize_side(ad.get("side"))
            token = str(ad.get("tokenId") or ad.get("token") or "")
            fiat = str(ad.get("currencyId") or ad.get("currency") or "")
            if AUTO_MARKER not in remark or AUTO_PAUSED_MARKER in remark:
                continue
            update_price, update_qty = _auto_update_flags(remark)
            comps = [c for c in ctx.competitors if _to_float(c.get("price")) is not None]
            reverse = side == "BUY"
            comps = sorted(comps, key=lambda c: _to_float(c.get("price")) or 0, reverse=reverse)
            groups = _group_competitors_by_price(ad, comps)
            if snapshot_collect:
                snapshot_entries.append(
                    {
                        "ad": ad,
                        "competitors_before": ctx.competitors_raw or [],
                        "competitors_after": comps,
                    }
                )
            cache_key = (token.upper(), fiat.upper())
            if cache_key not in spot_cache:
                spot_cache[cache_key] = _spot_quote(token, fiat)
            bid, ask, symbol = spot_cache[cache_key]
            spot_ref = ask if side == "SELL" else bid
            precision = _price_precision(ad.get("price"), fiat)
            step = _price_step(fiat, precision)
            eligible_comps = _guardrail_filter_competitors(side, token, spot_ref, comps, step)
            eligible_groups = _group_competitors_by_price(ad, eligible_comps)
            comp = _select_competitor(token, side, eligible_groups, eligible_comps)
            fallback = _fallback_price(side, token, spot_ref)
            target_price = _target_price(side, comp, step, fallback)
            comp_label = "-"
            if comp:
                comp_label = str(comp.get("nickName") or comp.get("nickname") or "").strip() or "-"
            comp_prices = [_to_float(c.get("price")) for c in eligible_comps if _to_float(c.get("price")) is not None]
            prices_display = " ".join(str(round(p, precision)) for p in comp_prices[:5]) if comp_prices else "-"
            print(f"{side} {token}/{fiat} -- {comp_label} - [{prices_display}] - Spot {bid}/{ask} - Target {target_price if target_price is not None else '-'}")
            current_price = _to_float(ad.get("price"))
            current_qty = _to_float(ad.get("lastQuantity"))
            if update_price and target_price is None:
                statuses.append(_build_status_entry(ad, current_price, current_qty, eligible_groups, None, (bid, ask, symbol)))
                continue
            price_for_update = round(target_price, precision) if update_price and target_price is not None else current_price
            token_up = token.upper()
            if side == "SELL":
                available = balances.get(token_up, 0.0)
                sell_qty = math.floor(available)
                if sell_qty <= 0:
                    statuses.append(_build_status_entry(ad, price_for_update, 0.0, groups, price_for_update, (bid, ask, symbol)))
                    continue
                updated_qty = float(sell_qty) if update_qty else current_qty
            else:  # BUY
                fixed = BUY_FIXED_QTY.get(token_up)
                suggested_qty = fixed if fixed is not None else (current_qty if current_qty is not None else 0.0)
                updated_qty = suggested_qty if update_qty else current_qty
                if updated_qty <= 0:
                    statuses.append(_build_status_entry(ad, price_for_update, 0.0, eligible_groups, price_for_update, (bid, ask, symbol)))
                    continue
            if price_for_update is None or updated_qty is None:
                statuses.append(_build_status_entry(ad, current_price, current_qty, eligible_groups, target_price, (bid, ask, symbol)))
                continue
            if _should_skip_update(price_for_update, updated_qty, current_price, current_qty, step, update_price, update_qty):
                statuses.append(_build_status_entry(ad, price_for_update, updated_qty, eligible_groups, price_for_update, (bid, ask, symbol)))
                continue
            try:
                _update_single_ad(client, ad, price_for_update, updated_qty, fiat, side)
            except Exception as exc:
                logger.warning("Auto price update failed ad=%s err=%s", ad.get("id"), exc)
            statuses.append(_build_status_entry(ad, price_for_update, updated_qty, eligible_groups, price_for_update, (bid, ask, symbol)))
        if snapshot_collect and snapshot_entries:
            snapshot_entries_all.extend(snapshot_entries)
    if snapshot_collect and snapshot_entries_all:
        try:
            SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with SNAPSHOT_PATH.open("w", encoding="utf-8") as fh:
                json.dump(snapshot_entries_all, fh, ensure_ascii=False, indent=2)
            _snapshot_written = True
        except Exception:
            pass
    return statuses


class AutoPricingWorker:
    def __init__(self, interval_seconds: int = 30) -> None:
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._last_run_at: Optional[datetime] = None
        self._last_success_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._ads: List[Dict[str, Any]] = []

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
                statuses = await asyncio.to_thread(_apply_pricing)
                self._ads = statuses
                self._last_success_at = datetime.utcnow()
                self._last_error = None
            except Exception as exc:  # pragma: no cover - guard rail
                self._last_error = str(exc)
                logger.exception("Auto pricing cycle failed: %s", exc)
            await asyncio.sleep(self.interval_seconds)

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "last_run_at": self._last_run_at,
            "last_success_at": self._last_success_at,
            "last_error": self._last_error,
            "ads": self._ads,
        }


auto_pricing_worker = AutoPricingWorker()
