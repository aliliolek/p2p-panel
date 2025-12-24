import asyncio
import contextlib
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from constants import FIAT_BALANCE_REMARK_MARKER
from exchanges import create_exchange_client
from fiat_balance_marker import get_marker
from repositories.credentials_repository import fetch_all_credentials
from services.ads_service import _load_bybit_ads
from services.credentials_service import build_exchange_credentials
from services.fiat_balance_service import FIAT_PRECISION, DEFAULT_TRADING_PREFS
from tools.auto_pricing import _group_competitors_by_price, _to_float

import numpy as np

logger = logging.getLogger("p2p-panel")

SPOT_TICKERS_URL = "https://api.bybit.com/v5/market/tickers"
PAYMENT_CODE = "416"
MIN_USD_LIQUIDITY = 300.0
MARKET_PAGE_SIZE = "10000"
FIAT_AUTO_INTERVAL_SECONDS = 60
UPDATE_WINDOW_SECONDS = 300
UPDATE_WINDOW_MAX = 10
# Default margins
FIAT_PAYMENT_ID = "-1"
DEFAULT_SELL_MARGIN_PCT = 0.05
DEFAULT_BUY_MARGIN_PCT = 0.005
TOKEN_MARGIN_OVERRIDES = {
    "USDT": {"sell": 0.001, "buy": 0.005},
    "USDC": {"sell": 0.001, "buy": 0.005},
}
DEFAULT_BUY_USD = 3000.0
BUY_FIXED_QTY = {
    "USDT": 3000.0,
    "USDC": 3000.0,
    "BTC": 0.034326,
    "ETH": 1.037667,
}
TOKEN_PRECISION = {
    "BTC": 8,
    "ETH": 8,
    "USDT": 4,
    "USDC": 4,
}
MIN_ACTIVITY_USD = 300.0
MAX_COMPETITION_USD = 1_000.0
MY_MIN_POINTS = np.array([100, 1_000, 5_000, 50_000, 100_000], dtype=float)
COMPETITOR_MIN_LIMITS = np.array(
    [500, 2_000, 6_000, 65_000, 110_000],
    dtype=float,
)

MIN_POINTS = np.array(
    [100, 500, 1_000, 5_000, 10_000, 30_000, 50_000, 100_000],
    dtype=float,
)
REQ_MAX_POINTS = np.array(
    [2_000, 2_500, 3_000, 14_000, 25_000, 50_000, 80_000, 140_000],
    dtype=float,
)
PRIORITY_NICKS = {
    "alvik",
    "N_1827",
    "GEO_PAPA",
    "Jorge Tambley",
    "Fast Trader�?c��?�?c��?",
    "LeBron1595",
    "Andrey_Exchange",
    "BTC_Enthusiast",
    "VALENTYN",
    "CH-Exchange",
    "King-Change",
    "Marllboro",
    "Ahmed2R",
    "SHULENA",
    "IhorV",
    "Super fast",
    "DADIKER-EXCHANG",
    "InterSpeed",
    "ilya3467",
    "GeoTrade11",
    "bonuscone123",
    "marvel_xchng",
    "bliskavka",
    "Wkantorze_24H",
    "Haffi",
    "ulx_cripto7",
    "ExpressTransfer",
    "XCHAINGER",
    "bestchange.kh",
    "TOPtrader",
    "Nz17kz_crypto",
    "whitemillkey",
    "Nikola4",
    "CryptoLeo",
    "Cryptonaut",
    "P2PHayFast",
    "Fida",
    "Platinum_exch",
    "_Miracle_",
    "ArmTrading001",
    "Kripto_Garant",
    "Realtime_Market",
    "Krabovski",
    "besimkosumcuu",
    "StockSwap",
    "Brek_exchange",
    "Genesis EXCH",
    "abomakha",
    "zakibergig",
    "Cripto_Arg",
    "ama2023",
    "Marckk",
    "InstantCurrency",
    "Rafe0701",
    "Peloviski_DN",
    "Devil66",
    "MZ Digital",
    "CoinOTC",
    "DAILY_EXCHANGE",
    "MerakiCCG.ltd",
    "crypto tech dv",
    "NoWait",
    "CambiosGN",
    "RichGarut",
    "Merci26",
    "EXPRESSO BF",
    "FUSION E-xchang",
    "Adnrey_exchange",
    "POLYANNA",
    "Skylioness",
    "CrazyGeraldo",
}
RATE_LIMIT: Dict[str, deque] = {}


def _extract_items(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    result = response.get("result")
    if not isinstance(result, dict):
        return []
    items = result.get("items")
    if isinstance(items, list):
        return items
    return []


def _has_payment_416(raw: Any) -> bool:
    if isinstance(raw, list):
        return any(str(p) == PAYMENT_CODE for p in raw)
    payments = raw.get("payments") if isinstance(raw, dict) else None
    if isinstance(payments, list) and any(str(p) == PAYMENT_CODE for p in payments):
        return True
    terms = raw.get("paymentTerms") if isinstance(raw, dict) else None
    if isinstance(terms, list):
        for item in terms:
            try:
                if int(item.get("paymentType")) == int(PAYMENT_CODE):
                    return True
            except Exception:
                continue
    return False


def _is_fiat_balance_ad(ad: Dict[str, Any], remark_marker: str) -> bool:
    if not _has_payment_416(ad):
        return False
    remark = str(ad.get("remark") or "")
    if remark_marker:
        return remark_marker in remark
    return FIAT_BALANCE_REMARK_MARKER in remark


def _fetch_token_usd_price(token: str) -> float:
    token_up = token.upper()
    if token_up in {"USDT", "USDC"}:
        return 1.0
    symbol = f"{token_up}USDT"
    response = requests.get(
        SPOT_TICKERS_URL,
        params={"category": "spot", "symbol": symbol},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    items = data.get("result", {}).get("list")
    if not items:
        raise ValueError(f"No ticker for {symbol}")
    price = items[0].get("lastPrice")
    return float(price)


def _load_balances_simple(client) -> Dict[str, float]:
    try:
        resp = client.get_current_balance(accountType="FUND")
        result = resp.get("result") if isinstance(resp, dict) else None
        balances = result.get("balance") if isinstance(result, dict) else None
        items = balances if isinstance(balances, list) else []
    except Exception:
        items = []
    out: Dict[str, float] = {}
    for item in items:
        token = str(item.get("coin")) if isinstance(item, dict) else ""
        free = item.get("availableBalance") if isinstance(item, dict) else None
        if free is None:
            free = item.get("transferBalance") if isinstance(item, dict) else None
        if free is None:
            free = item.get("walletBalance") if isinstance(item, dict) else None
        try:
            val = float(free)
        except Exception:
            continue
        out[token.upper()] = val
    return out


def _usd_liquidity(token: str, quantity: Any, price_cache: Dict[str, float]) -> Optional[float]:
    try:
        qty = float(quantity)
    except Exception:
        return None
    if qty <= 0:
        return None
    token_up = token.upper()
    if token_up not in price_cache:
        price_cache[token_up] = _fetch_token_usd_price(token_up)
    return qty * price_cache[token_up]


def _allowed_competitor_min(my_min: float) -> float:
    return float(np.interp(my_min, MY_MIN_POINTS, COMPETITOR_MIN_LIMITS))


def _passes_min_gap_filter(my_min: Optional[float], competitor: Dict[str, Any]) -> bool:
    competitor_min = _to_float(competitor.get("minAmount"))
    if competitor_min is None or my_min is None:
        return False
    return competitor_min <= _allowed_competitor_min(my_min)


def _passes_min_max_gap_filter(competitor: Dict[str, Any]) -> bool:
    comp_min = _to_float(competitor.get("minAmount"))
    comp_max = _to_float(competitor.get("maxAmount"))
    if comp_min is None or comp_max is None:
        return False
    required_max = float(np.interp(comp_min, MIN_POINTS, REQ_MAX_POINTS))
    return comp_max >= required_max


def _passes_activity_filters(
    competitor: Dict[str, Any],
    my_last_quantity: Optional[float],
    price_cache: Dict[str, float],
) -> bool:
    token = str(competitor.get("tokenId") or "").upper()
    last_quantity = _to_float(competitor.get("lastQuantity"))
    recent_orders = _to_float(competitor.get("recentOrderNum"))
    if last_quantity is None or last_quantity <= 0:
        return False
    usd_liq = _usd_liquidity(token, last_quantity, price_cache)
    if usd_liq is None or usd_liq < MIN_ACTIVITY_USD:
        return False
    if recent_orders is None or recent_orders < 100:
        return False
    # Cap small competitors relative to our size if within MAX_COMPETITION_USD
    token_price = price_cache.get(token) or _fetch_token_usd_price(token)
    if token_price:
        cap_qty = MAX_COMPETITION_USD / token_price
        if (
            my_last_quantity is not None
            and last_quantity <= cap_qty
            and last_quantity < my_last_quantity
        ):
            return False
    return True


def _fetch_spot_ticker(symbol: str) -> Dict[str, Any]:
    response = requests.get(
        SPOT_TICKERS_URL,
        params={"category": "spot", "symbol": symbol},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    items = data.get("result", {}).get("list")
    if not items:
        raise ValueError(f"No spot ticker for {symbol}")
    return items[0]


def _fetch_spot_quote(token: str, fiat: str, spot_cache: Dict[str, Dict[str, Any]], price_cache: Dict[str, float]) -> Dict[str, Optional[float]]:
    token_up = token.upper()
    fiat_up = fiat.upper()

    def _get_ticker(sym: str) -> Optional[Dict[str, Any]]:
        if sym in spot_cache:
            return spot_cache[sym]
        try:
            ticker_local = _fetch_spot_ticker(sym)
            spot_cache[sym] = ticker_local
            return ticker_local
        except Exception:
            return None

    def _bid_ask_from_ticker(sym: str) -> Dict[str, Optional[float]]:
        ticker_local = _get_ticker(sym)
        if not ticker_local:
            return {"bid": None, "ask": None, "symbol": sym}
        return {
            "bid": _to_float(ticker_local.get("bid1Price")),
            "ask": _to_float(ticker_local.get("ask1Price")),
            "symbol": sym,
        }

    # Direct mappings
    if fiat_up == "EUR":
        sym_map = {
            "USDT": "USDTEUR",
            "USDC": "USDCEUR",
            "BTC": "BTCEUR",
            "ETH": "ETHEUR",
        }
        sym = sym_map.get(token_up, f"{token_up}{fiat_up}")
        return _bid_ask_from_ticker(sym)

    if fiat_up == "BRL":
        sym_map = {
            "USDT": "USDTBRL",
            "USDC": "USDCBRL",
            "BTC": "BTCBRL",
            "ETH": "ETHBRL",
        }
        sym = sym_map.get(token_up, f"{token_up}{fiat_up}")
        return _bid_ask_from_ticker(sym)

    if fiat_up == "PLN":
        if token_up == "USDT":
            return _bid_ask_from_ticker("USDTPLN")
        if token_up == "BTC":
            return _bid_ask_from_ticker("BTCPLN")
        if token_up == "ETH":
            return _bid_ask_from_ticker("ETHPLN")
        if token_up == "USDC":
            # USDC -> USDT -> PLN with fee on each conversion
            fee = 0.002
            usdc_usdt = _bid_ask_from_ticker("USDCUSDT")
            usdt_pln = _bid_ask_from_ticker("USDTPLN")
            bid = None
            ask = None
            if usdc_usdt["bid"] is not None and usdt_pln["bid"] is not None:
                bid = usdc_usdt["bid"] * usdt_pln["bid"] * (1 - fee) * (1 - fee)
            if usdc_usdt["ask"] is not None and usdt_pln["ask"] is not None:
                ask = usdc_usdt["ask"] * usdt_pln["ask"] * (1 + fee) * (1 + fee)
            return {"symbol": "USDCPLN(via USDT)", "bid": bid, "ask": ask}

    if fiat_up == "USD":
        fee = 0.0015  # 0.15% loss converting USD <-> USDT
        usdt_factor_down = 1 - fee
        usdt_factor_up = 1 + fee
        if token_up == "USDT":
            return {"symbol": "USDTUSD", "bid": 1 * usdt_factor_down, "ask": 1 * usdt_factor_up}
        if token_up == "USDC":
            usdc_usdt = _bid_ask_from_ticker("USDCUSDT")
            bid = usdc_usdt["bid"] * usdt_factor_down if usdc_usdt["bid"] is not None else None
            ask = usdc_usdt["ask"] * usdt_factor_up if usdc_usdt["ask"] is not None else None
            return {"symbol": "USDCUSD(via USDT)", "bid": bid, "ask": ask}
        if token_up in {"BTC", "ETH"}:
            sym = f"{token_up}USDT"
            ticker = _bid_ask_from_ticker(sym)
            bid = ticker["bid"] * usdt_factor_down if ticker["bid"] is not None else None
            ask = ticker["ask"] * usdt_factor_up if ticker["ask"] is not None else None
            return {"symbol": f"{token_up}USD(via USDT)", "bid": bid, "ask": ask}

    # Fallback: try direct ticker, else None
    return _bid_ask_from_ticker(f"{token_up}{fiat_up}")


def _price_step(fiat: str) -> float:
    precision = FIAT_PRECISION.get(fiat.upper(), 2)
    return 10 ** (-precision)


def _price_precision_from_value(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    text = str(raw)
    if "." not in text:
        return 0
    decimals = text.split(".", 1)[1]
    return len(decimals)


def _round_price(value: float, precision: Optional[int], fiat: str) -> float:
    if precision is None:
        precision = FIAT_PRECISION.get(fiat.upper(), 2)
    return round(value, precision)


def _should_skip_update(price_for_update: float, qty: float, current_price: Optional[float], current_qty: Optional[float], step: float) -> bool:
    # Skip only if both price and qty effectively unchanged
    price_same = current_price is not None and abs(price_for_update - current_price) < step * 0.1
    qty_same = current_qty is not None and abs(qty - current_qty) < 1e-9
    return price_same and qty_same


def _min_qty_needed(min_amount: Any, price: float) -> Optional[float]:
    try:
        min_amt = float(min_amount)
        if price is None or price <= 0:
            return None
        return min_amt / price
    except Exception:
        return None


def _can_update_now(ad_id: str) -> bool:
    window = RATE_LIMIT.setdefault(ad_id, deque())
    now = datetime.utcnow()
    while window and (now - window[0]) > timedelta(seconds=UPDATE_WINDOW_SECONDS):
        window.popleft()
    if len(window) >= UPDATE_WINDOW_MAX:
        return False
    window.append(now)
    return True


def _margin_pct(token: str, side: str) -> float:
    token_up = token.upper()
    side_key = "sell" if side == "SELL" else "buy"
    override = TOKEN_MARGIN_OVERRIDES.get(token_up) or {}
    if side_key == "SELL":
        return override.get("sell", DEFAULT_SELL_MARGIN_PCT)
    return override.get("buy", DEFAULT_BUY_MARGIN_PCT)


def _guardrail_price(ad_side: str, spot: Dict[str, Optional[float]], fiat: str, token: str) -> Optional[float]:
    side = _normalize_side(ad_side)
    margin = _margin_pct(token, side)
    if side == "SELL":
        ask = spot.get("ask")
        if ask is None:
            return None
        return ask * (1 + margin)
    if side == "BUY":
        bid = spot.get("bid")
        if bid is None:
            return None
        return bid * (1 - margin)
    return None


def _suggest_buy_qty(token: str, price_cache: Dict[str, float]) -> Optional[float]:
    token_up = token.upper()
    fixed = BUY_FIXED_QTY.get(token_up)
    if fixed is not None:
        return fixed
    try:
        if token_up not in price_cache:
            price_cache[token_up] = _fetch_token_usd_price(token_up)
        usd_price = price_cache[token_up]
        if usd_price <= 0:
            return None
        return DEFAULT_BUY_USD / usd_price
    except Exception:
        return None


def _update_ad(client, ad: Dict[str, Any], qty: float, price_val: float) -> Optional[Dict[str, Any]]:
    if qty is None or qty <= 0 or price_val is None:
        return None
    ad_id = str(ad.get("id") or ad.get("itemId") or ad.get("ad_id") or "")
    min_amount = ad.get("minAmount") or ad.get("min_amount") or 0
    max_amount = ad.get("maxAmount") or ad.get("max_amount") or 0
    payment_period = ad.get("paymentPeriod") or ad.get("paymentPeriod") or "30"
    remark = ad.get("remark") or ""
    trading_pref = ad.get("tradingPreferenceSet") or DEFAULT_TRADING_PREFS
    status = str(ad.get("status") or "")
    action_type = "MODIFY" if status == "10" else "ACTIVE"
    payload = {
        "id": ad_id,
        "priceType": "0",
        "premium": "0",
        "price": str(price_val),
        "minAmount": str(min_amount),
        "maxAmount": str(max_amount),
        "remark": remark,
        "tradingPreferenceSet": trading_pref,
        "paymentIds": [FIAT_PAYMENT_ID],
        "actionType": action_type,
        "quantity": str(qty),
        "paymentPeriod": str(payment_period),
    }
    try:
        resp = client.update_ad(**payload)
        if not (isinstance(resp, dict) and resp.get("ret_msg") == "SUCCESS"):
            print(resp)
        return resp
    except Exception as exc:
        print({"id": ad_id, "qty": qty, "price": price_val, "error": str(exc)})
        return None


def _normalize_side(value: Any) -> str:
    text = str(value).upper()
    if text in {"0", "BUY"}:
        return "BUY"
    if text in {"1", "SELL"}:
        return "SELL"
    return text


def _collect_competitors(api, ad: Dict[str, Any], price_cache: Dict[str, float]) -> List[Dict[str, Any]]:
    my_min = _to_float(ad.get("minAmount"))
    my_last_quantity = _to_float(ad.get("lastQuantity"))
    resp = api.get_online_ads(
        tokenId=str(ad.get("tokenId")),
        currencyId=str(ad.get("currencyId")),
        side=str(ad.get("side")),
        page="1",
        size=MARKET_PAGE_SIZE,
    )
    market_ads = _extract_items(resp)
    my_account_id = str(ad.get("accountId") or "")
    token = str(ad.get("tokenId") or "")
    filtered: List[Dict[str, Any]] = []
    for competitor in market_ads:
        if my_account_id and str(competitor.get("accountId") or "") == my_account_id:
            continue
        if not _has_payment_416(competitor):
            continue
        if not _passes_min_gap_filter(my_min, competitor):
            continue
        if not _passes_min_max_gap_filter(competitor):
            continue
        usd_value = _usd_liquidity(token, competitor.get("lastQuantity"), price_cache)
        if usd_value is None or usd_value < MIN_USD_LIQUIDITY:
            continue
        if not _passes_activity_filters(competitor, my_last_quantity, price_cache):
            continue
        filtered.append(competitor)
    return filtered


def _summarize_groups(groups: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for group in groups:
        prices = [_to_float(item.get("price")) for item in group]
        prices = [p for p in prices if p is not None]
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


def collect_fiat_balance_contexts(run_sell: bool = True, run_buy: bool = True) -> List[Dict[str, Any]]:
    rows = fetch_all_credentials()
    if not rows:
        return []
    marker = get_marker()
    contexts: List[Dict[str, Any]] = []
    price_cache: Dict[str, float] = {}
    spot_cache: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        if row.get("exchange") != "bybit":
            continue
        creds = build_exchange_credentials(row)
        client = create_exchange_client(creds)
        balances = _load_balances_simple(client)
        ads = _load_bybit_ads(creds)
        target_ads = [ad for ad in ads if _is_fiat_balance_ad(ad, marker)]
        for ad in target_ads:
            side_norm = _normalize_side(ad.get("side"))
            if side_norm == "SELL" and not run_sell:
                continue
            if side_norm == "BUY" and not run_buy:
                continue
            competitors = _collect_competitors(client, ad, price_cache)
            groups = _group_competitors_by_price(ad, competitors)
            summary_groups = _summarize_groups(groups)
            spot = _fetch_spot_quote(
                str(ad.get("tokenId") or ad.get("token") or ""),
                str(ad.get("currencyId") or ad.get("currency") or ""),
                spot_cache,
                price_cache,
            )
            token_val = str(ad.get("tokenId") or ad.get("token") or "")
            fiat_code = str(ad.get("currencyId") or ad.get("currency") or "")
            guardrail_price = _guardrail_price(
                side_norm,
                spot,
                fiat_code,
                token_val,
            )
            filtered_groups = summary_groups
            # Determine target competitor price (first in filtered groups)
            first_price = None
            best_competitor = None
            filtered_prices: List[float] = []
            if guardrail_price is not None:
                # Filter competitors by guardrail
                filtered_competitors: List[Dict[str, Any]] = []
                for comp in competitors:
                    comp_price = _to_float(comp.get("price"))
                    if comp_price is None:
                        continue
                    if side_norm == "SELL":
                        if comp_price < guardrail_price:
                            continue
                    elif side_norm == "BUY":
                        if comp_price > guardrail_price:
                            continue
                    filtered_competitors.append(comp)
                if filtered_competitors:
                    filtered_competitors = sorted(
                        filtered_competitors,
                        key=lambda c: _to_float(c.get("price")) or 0,
                        reverse=(side_norm == "BUY"),
                    )
                    best_competitor = filtered_competitors[0]
                    first_price = _to_float(best_competitor.get("price"))
                    filtered_prices = [
                        _to_float(item.get("price"))
                        for item in filtered_competitors
                        if _to_float(item.get("price")) is not None
                    ]
                filtered_groups = _summarize_groups(_group_competitors_by_price(ad, filtered_competitors))
            target_price = first_price if first_price is not None else guardrail_price
            desired_price = target_price
            if best_competitor and target_price is not None:
                nick = str(best_competitor.get("nickName") or best_competitor.get("nickname") or "").strip()
                step = _price_step(str(ad.get("currencyId") or ad.get("currency") or ""))
                comp_price = _to_float(best_competitor.get("price")) or target_price
                if nick and nick in PRIORITY_NICKS:
                    if side_norm == "SELL":
                        desired_price = max(comp_price - step, 0)
                    else:  # BUY
                        desired_price = comp_price + step
                else:
                    desired_price = comp_price
                fiat_upper = fiat_code.upper()
                token_upper = token_val.upper()
                if fiat_upper in {"USD", "EUR"} and token_upper in {"USDT", "USDC"} and comp_price is not None:
                    if side_norm == "SELL":
                        desired_price = comp_price + step
                    elif side_norm == "BUY":
                        desired_price = max(comp_price - step, 0)
            ad_price_precision = _price_precision_from_value(ad.get("price"))
            comp_precision = _price_precision_from_value(best_competitor.get("price")) if best_competitor else None
            precision = ad_price_precision if ad_price_precision is not None else comp_precision
            if fiat_code.upper() in {"USD", "EUR"} and token_val.upper() in {"USDT", "USDC"}:
                precision = max(precision or 0, 3)
                if side_norm == "SELL" and desired_price is not None and desired_price > 0.999:
                    desired_price = 0.999
            price_for_update = _round_price(desired_price if desired_price is not None else 0, precision, fiat_code)
            ad_id = str(ad.get("id") or ad.get("itemId") or ad.get("ad_id") or "")
            current_price = _to_float(ad.get("price"))
            current_qty = _to_float(ad.get("quantity") or ad.get("lastQuantity"))
            if (
                fiat_code.upper() == "USD"
                and token_val.upper() in {"USDT", "USDC"}
                and side_norm == "SELL"
                and price_for_update > 0.999
            ):
                price_for_update = 0.999
            competitor_label = "-"
            competitor_price = None
            if best_competitor:
                competitor_label = str(best_competitor.get("nickName") or best_competitor.get("nickname") or "").strip() or "-"
                competitor_price = _to_float(best_competitor.get("price"))
            prices_display = ""
            if filtered_prices:
                # keep only prices up to our price
                capped = []
                for val in filtered_prices:
                    if val is None:
                        continue
                    capped.append(val)
                    if desired_price is not None and ((side_norm == "SELL" and val >= desired_price) or (side_norm == "BUY" and val <= desired_price)):
                        break
                prices_display = " ".join(str(_round_price(v, precision, fiat_code)) for v in capped if v is not None)
            updated_qty = None
            min_amount_val = ad.get("minAmount") or ad.get("min_amount") or 0
            precision_qty = TOKEN_PRECISION.get(token_val.upper(), 8)
            if side_norm == "SELL":
                updated_qty = balances.get(token_val.upper(), 0.0)
                updated_qty = round(updated_qty, precision_qty)
                step = _price_step(fiat_code)
                if not _should_skip_update(price_for_update, updated_qty, current_price, current_qty, step):
                    needed_qty = _min_qty_needed(min_amount_val, price_for_update) or 0
                    if updated_qty < needed_qty:
                        continue
                    if _can_update_now(ad_id):
                        print(f"{side_norm} - {token_val}/{fiat_code} -- {competitor_label} - [{prices_display}] - ({guardrail_price}) - {price_for_update}")
                        _update_ad(client, ad, updated_qty, price_for_update)
            elif side_norm == "BUY":
                updated_qty = _suggest_buy_qty(token_val, price_cache)
                if updated_qty is not None:
                    updated_qty = round(updated_qty, precision_qty)
                step = _price_step(fiat_code)
                if not _should_skip_update(price_for_update, updated_qty, current_price, current_qty, step):
                    needed_qty = _min_qty_needed(min_amount_val, price_for_update) or 0
                    if updated_qty < needed_qty:
                        updated_qty = needed_qty
                    if _can_update_now(ad_id):
                        print(f"{side_norm} - {token_val}/{fiat_code} -- {competitor_label} - [{prices_display}] - ({guardrail_price}) - {price_for_update}")
                        _update_ad(client, ad, updated_qty, price_for_update)
            contexts.append(
                {
                    "ad_id": str(ad.get("id") or ad.get("itemId") or ad.get("ad_id") or ""),
                    "account_id": str(ad.get("accountId") or ""),
                    "token": str(ad.get("tokenId") or ad.get("token") or ""),
                    "fiat_currency": str(ad.get("currencyId") or ad.get("currency") or ""),
                    "side": side_norm,
                    "price": _to_float(ad.get("price")),
                    "is_auto_enabled": False,
                    "is_auto_paused": False,
                    "competitor_groups": filtered_groups,
                    "competitor_groups_full": summary_groups,
                    "spot_symbol": spot.get("symbol"),
                    "spot_bid": spot.get("bid"),
                    "spot_ask": spot.get("ask"),
                    "target_price": first_price or target_price,
                    "guardrail_price": guardrail_price,
                    "available_balance": balances.get(token_val.upper(), 0.0),
                    "suggested_buy_qty": _suggest_buy_qty(token_val, price_cache) if side_norm == "BUY" else None,
                    "updated_qty": updated_qty,
                    "desired_price": desired_price,
                }
            )
    return contexts


class FiatBalanceAutoPricingWorker:
    def __init__(self, interval_seconds: int = FIAT_AUTO_INTERVAL_SECONDS) -> None:
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._last_run_at: Optional[datetime] = None
        self._last_success_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._ads: List[Dict[str, Any]] = []
        self.run_sell: bool = True
        self.run_buy: bool = True

    def set_config(self, sell: bool, buy: bool) -> None:
        self.run_sell = sell
        self.run_buy = buy

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
                contexts = await asyncio.to_thread(
                    collect_fiat_balance_contexts,
                    self.run_sell,
                    self.run_buy,
                )
                self._ads = contexts
                self._last_success_at = datetime.utcnow()
                self._last_error = None
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("Fiat balance auto pricing cycle failed: %s", exc)
            await asyncio.sleep(self.interval_seconds)

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "last_run_at": self._last_run_at,
            "last_success_at": self._last_success_at,
            "last_error": self._last_error,
            "ads": self._ads,
            "sell_enabled": self.run_sell,
            "buy_enabled": self.run_buy,
        }


fiat_balance_auto_worker = FiatBalanceAutoPricingWorker()
