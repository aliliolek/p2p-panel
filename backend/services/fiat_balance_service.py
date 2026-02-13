import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

import requests
from bybit_p2p._exceptions import FailedRequestError

from exchanges import SUPPORTED_EXCHANGES, create_exchange_client
from repositories.credentials_repository import (
    fetch_user_credentials as repo_fetch_user_credentials,
)
from schemas import (
    CreateFiatBalanceAdRequest,
    CreateFiatBalanceBatchRequest,
    DeleteFiatBalanceAdsRequest,
    FiatBalanceConfig,
)
from services.credentials_service import build_exchange_credentials
from services.ads_service import get_ads
from fiat_balance_marker import get_marker, save_marker
from constants import FIAT_BALANCE_REMARK_MARKER

TOKENS = ["USDT", "USDC", "BTC", "ETH"]
FIATS = ["EUR", "PLN", "USD", "BRL"]
PAYMENT_METHOD_ID = "-1"
PRICE_DOWN = 0.92
PRICE_UP = 1.08
MARKET_TICKERS_URL = "https://api.bybit.com/v5/market/tickers"
FIAT_PRECISION = {
    "USD": 3,
    "EUR": 3,
    "PLN": 2,
    "BRL": 3,
}
DEFAULT_TRADING_PREFS = {
    "hasUnPostAd": "0",
    "isKyc": "1",
    "isEmail": "0",
    "isMobile": "0",
    "hasRegisterTime": "0",
    "registerTimeThreshold": "0",
    "orderFinishNumberDay30": "0",
    "completeRateDay30": "",
    "nationalLimit": "",
    "hasOrderFinishNumberDay30": "0",
    "hasCompleteRateDay30": "0",
    "hasNationalLimit": "0",
}


def _stringify_trading_preferences(raw: Any) -> Dict[str, str]:
    prefs = raw if isinstance(raw, dict) else {}
    return {k: str(v) for k, v in (prefs or {}).items()}


def _load_limits() -> Dict[str, List[Dict[str, str]]]:
    path = Path("playground_results/balance_limits.json")
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _load_balances(client) -> Dict[str, float]:
    try:
        resp = client.get_current_balance(accountType="FUND")
        result = resp.get("result") if isinstance(resp, dict) else None
        balances = None
        if isinstance(result, dict):
            balances = result.get("balance") or result.get("list")
        items = balances if isinstance(balances, list) else []
    except Exception:
        items = []
    out: Dict[str, float] = {}
    for item in items:
        token = str(item.get("coin")) if isinstance(item, dict) else ""
        free = None
        if isinstance(item, dict):
            free = (
                item.get("availableBalance")
                or item.get("transferBalance")
                or item.get("walletBalance")
            )
        try:
            free_val = float(free)
        except Exception:
            continue
        out[token.upper()] = free_val
    return out


def _fetch_spot(symbol: str) -> float:
    response = requests.get(
        MARKET_TICKERS_URL,
        params={"category": "spot", "symbol": symbol},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    items = data.get("result", {}).get("list") if isinstance(data, dict) else None
    if not items:
        raise ValueError(f"No ticker for {symbol}")
    price = items[0].get("lastPrice")
    return float(price)


def _compute_price(token: str, fiat: str) -> float:
    token = token.upper()
    fiat = fiat.upper()
    if token == "USDT":
        token_usdt = 1.0
    elif token == "USDC":
        token_usdt = _fetch_spot("USDCUSDT")
    else:
        token_usdt = _fetch_spot(f"{token}USDT")

    if fiat == "USD":
        usdt_fiat = 1.0
    else:
        usdt_fiat = _fetch_spot(f"USDT{fiat}")

    return token_usdt * usdt_fiat


def _round_price(value: float, fiat: str) -> float:
    precision = FIAT_PRECISION.get(fiat.upper(), 2)
    return round(value, precision)


async def get_fiat_balance_config(user_id: str) -> FiatBalanceConfig:
    rows = await asyncio.to_thread(repo_fetch_user_credentials, user_id)
    limits = _load_limits()
    accounts: List[Dict[str, Any]] = []
    marker = get_marker()
    for row in rows:
        if row.get("exchange") not in SUPPORTED_EXCHANGES or row.get("exchange") != "bybit":
            continue
        creds = build_exchange_credentials(row)
        client = create_exchange_client(creds)
        balances = _load_balances(client)
        accounts.append(
            {
                "credential_id": row["id"],
                "account_label": row.get("account_label"),
                "exchange": row.get("exchange"),
                "balances": balances,
            }
        )
    return FiatBalanceConfig(
        tokens=TOKENS,
        fiats=FIATS,
        limits=limits,
        accounts=accounts,
        payment_method_id=PAYMENT_METHOD_ID,
        remark_marker=marker,
    )


async def create_fiat_balance_ad(user_id: str, payload: CreateFiatBalanceAdRequest) -> Dict[str, Any]:
    rows = await asyncio.to_thread(repo_fetch_user_credentials, user_id)
    creds_row = next((row for row in rows if row.get("id") == payload.credential_id), None)
    if not creds_row:
        raise ValueError("Credential not found")
    creds = build_exchange_credentials(creds_row)
    client = create_exchange_client(creds)
    resp = client.post_new_ad(
        tokenId=payload.tokenId,
        currencyId=payload.currencyId,
        side=str(payload.side),
        priceType="0",
        premium="0",
        price=str(payload.price),
        minAmount=str(payload.minAmount),
        maxAmount=str(payload.maxAmount),
        remark=payload.remark,
        tradingPreferenceSet=_stringify_trading_preferences(DEFAULT_TRADING_PREFS),
        paymentIds=[PAYMENT_METHOD_ID],
        quantity=str(payload.quantity),
        paymentPeriod=str(payload.paymentPeriod or "15"),
        itemType="ORIGIN",
    )
    return resp


async def create_fiat_balance_ads_batch(
    user_id: str, payload: CreateFiatBalanceBatchRequest
) -> List[Dict[str, Any]]:
    rows = await asyncio.to_thread(repo_fetch_user_credentials, user_id)
    creds_row = next((row for row in rows if row.get("id") == payload.credential_id), None)
    if not creds_row:
        raise ValueError("Credential not found")
    creds = build_exchange_credentials(creds_row)
    client = create_exchange_client(creds)
    balances = _load_balances(client)
    limits_map = _load_limits()

    results: List[Dict[str, Any]] = []
    for token in payload.tokens:
        for fiat in payload.fiats:
            try:
                base_price = _compute_price(token, fiat)
            except Exception as exc:  # pragma: no cover - external call
                results.append(
                    {
                        "token": token,
                        "fiat": fiat,
                        "side": "N/A",
                        "error": f"price_error: {exc}",
                    }
                )
                continue

            buy_qty = payload.buyQuantityMap.get(token) or payload.buyQuantity or BUY_QTY_DEFAULTS.get(token, 0)
            sell_qty = payload.sellQuantityMap.get(token) or payload.sellQuantity or SELL_QTY_DEFAULTS.get(token, 0)
            marker = payload.remark or get_marker()
            save_marker(marker)

            min_amount = payload.minAmountMap.get(fiat) if payload.minAmountMap else None
            if min_amount is None:
                min_amount = payload.minAmount
            max_amount = payload.maxAmountMap.get(fiat) if payload.maxAmountMap else None
            if max_amount is None:
                max_amount = payload.maxAmount
            entries = limits_map.get(fiat) or []
            if min_amount is None and entries:
                mins = []
                for item in entries:
                    try:
                        mins.append(float(item.get("minAmount")))
                    except Exception:
                        pass
                if mins:
                    min_amount = min(mins)
            if max_amount is None and entries:
                maxs = []
                for item in entries:
                    try:
                        maxs.append(float(item.get("maxAmount")))
                    except Exception:
                        pass
                if maxs:
                    max_amount = max(maxs)
            min_amount = min_amount or 0
            max_amount = max_amount or 0

            pairs = [
                ("0", _round_price(base_price * PRICE_DOWN, fiat), buy_qty),
                ("1", _round_price(base_price * PRICE_UP, fiat), sell_qty),
            ]
            for side, price, qty in pairs:
                if price <= 0:
                    log_entry = {
                        "token": token,
                        "fiat": fiat,
                        "side": side,
                        "price": price,
                        "qty": qty,
                        "minAmount": min_amount,
                        "maxAmount": max_amount,
                        "error": "invalid_price",
                    }
                    print("[fiat-balance] skip invalid price", log_entry)
                    results.append(log_entry)
                    continue

                min_qty_fiat = (min_amount / price) if min_amount else 0
                max_qty_fiat = (max_amount / price) if max_amount else None

                prec = TOKEN_PRECISION.get(token.upper(), 8)
                if side == "0":
                    qty = max(qty, BUY_QTY_DEFAULTS.get(token, 0), min_qty_fiat)
                    if max_qty_fiat:
                        qty = min(qty, max_qty_fiat)
                if side == "1":
                    min_sell = max(SELL_QTY_DEFAULTS.get(token, 0), min_qty_fiat)
                    balance = balances.get(token.upper(), 0)
                    if balance < min_sell:
                        log_entry = {
                            "token": token,
                            "fiat": fiat,
                            "side": side,
                            "price": price,
                            "qty": qty,
                            "minAmount": min_amount,
                            "maxAmount": max_amount,
                            "error": "insufficient_balance_for_min_sell",
                            "balance": balance,
                        }
                        print("[fiat-balance] skip insufficient balance", log_entry)
                        results.append(log_entry)
                        continue
                    qty = max(min_sell, min(qty, balance))
                    if max_qty_fiat:
                        qty = min(qty, max_qty_fiat)
                qty = round(qty, prec)
                try:
                    resp = client.post_new_ad(
                        tokenId=token,
                        currencyId=fiat,
                        side=side,
                        priceType="0",
                        premium="0",
                        price=str(price),
                        minAmount=str(min_amount),
                        maxAmount=str(max_amount),
                        remark=marker,
                        tradingPreferenceSet=_stringify_trading_preferences(DEFAULT_TRADING_PREFS),
                        paymentIds=[PAYMENT_METHOD_ID],
                        quantity=str(qty),
                        paymentPeriod=str(payload.paymentPeriod or "15"),
                        itemType="ORIGIN",
                    )
                    log_entry = {
                        "token": token,
                        "fiat": fiat,
                        "side": side,
                        "price": price,
                        "qty": qty,
                        "minAmount": min_amount,
                        "maxAmount": max_amount,
                        "response": resp,
                        "raw_response": resp,
                    }
                    print("[fiat-balance] ad created", log_entry)
                    results.append(log_entry)
                except FailedRequestError as exc:  # pragma: no cover - network/API
                    raw = getattr(exc, "resp", None) or getattr(exc, "payload", None)
                    log_entry = {
                        "token": token,
                        "fiat": fiat,
                        "side": side,
                        "price": price,
                        "qty": qty,
                        "minAmount": min_amount,
                        "maxAmount": max_amount,
                        "err_code": getattr(exc, "err_code", None),
                        "err_msg": getattr(exc, "err_msg", None),
                        "error": str(exc),
                        "raw_response": raw,
                    }
                    print("[fiat-balance] create error", log_entry)
                    results.append(log_entry)
                except Exception as exc:  # pragma: no cover - network/API
                    log_entry = {
                        "token": token,
                        "fiat": fiat,
                        "side": side,
                        "price": price,
                        "qty": qty,
                        "minAmount": min_amount,
                        "maxAmount": max_amount,
                        "error": str(exc),
                    }
                    print("[fiat-balance] unexpected error", log_entry)
                    results.append(log_entry)
    return results


async def delete_fiat_balance_ads(
    user_id: str, payload: DeleteFiatBalanceAdsRequest
) -> List[Dict[str, Any]]:
    rows = await asyncio.to_thread(repo_fetch_user_credentials, user_id)
    creds_row = next((row for row in rows if row.get("id") == payload.credential_id), None)
    if not creds_row:
        raise ValueError("Credential not found")
    creds = build_exchange_credentials(creds_row)
    client = create_exchange_client(creds)

    deleted: List[Dict[str, Any]] = []
    accounts = await get_ads(user_id)
    account = next((acc for acc in accounts if acc.credential_id == payload.credential_id), None)
    if not account:
        return deleted

    target_ads = [
        ad
        for ad in account.ads
        if payload.remark in (ad.remark or "") and 416 in ad.payment_type_ids
    ]

    for ad in target_ads:
        try:
            resp_del = client.remove_ad(itemId=str(ad.ad_id))
            deleted.append({"ad_id": ad.ad_id, "response": resp_del})
        except Exception as exc:  # pragma: no cover
            deleted.append({"ad_id": ad.ad_id, "error": str(exc)})

    return deleted
BUY_QTY_DEFAULTS = {
    "USDT": 10.0,
    "USDC": 10.0,
    "BTC": 0.00011788,
    "ETH": 0.00360639,
}
SELL_QTY_DEFAULTS = {
    "USDT": 10.0,
    "USDC": 10.0,
    "BTC": 0.00011788,
    "ETH": 0.00360639,
}
TOKEN_PRECISION = {
    "BTC": 8,
    "ETH": 8,
    "USDT": 4,
    "USDC": 4,
}
