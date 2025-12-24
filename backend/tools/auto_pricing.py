from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from decimal import Decimal, InvalidOperation
import numpy as np
import requests
from dotenv import load_dotenv

from exchanges import ExchangeCredentials, create_exchange_client
from repositories.credentials_repository import fetch_all_credentials
from security import decrypt_secret
from services.ads_service import _load_bybit_ads

RESULTS_DIR = Path("playground_results")
AUTO_RESULTS_DIR = RESULTS_DIR / "auto_ads"
AUTO_MARKER = "@@@"
AUTO_PAUSED_MARKER = "@*@"
MARKET_PAGE_SIZE = "10000"
SPOT_TICKERS_URL = "https://api.bybit.com/v5/market/tickers"
REST_COUNTRIES_URL = "https://restcountries.com/v3.1/all?fields=cca3,currencies"
MIN_ACTIVITY_USD = 300.0
MAX_COMPETITION_USD = 1_000.0
FIAT_SPOT_FILTERS = {"EUR", "PLN", "TRY", "BRL", "MNT"}
SPOT_BASE_TOKENS = {"USDT", "USDC", "BTC", "ETH"}
SPOT_QUOTE_SUFFIXES = FIAT_SPOT_FILTERS | SPOT_BASE_TOKENS
DEBUG_SNAPSHOTS_ENABLED = False
DEFAULT_CURRENCY_COUNTRY_MAP = {
    "PLN": {"POL"},
    "UAH": {"UKR"},
    "USD": {"USA"},
    "EUR": {"AUT", "BEL", "DEU", "ESP", "FIN", "FRA", "GRC", "IRL", "ITA", "LUX", "NLD", "PRT", "SVK", "SVN", "EST", "LVA", "LTU"},
    "TRY": {"TUR"},
}
CURRENCY_COUNTRY_MAP: Dict[str, Set[str]] = {}

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


@dataclass
class AutoAdContext:
    ad: Dict[str, Any]
    competitors: List[Dict[str, Any]]
    competitor_groups: List[List[Dict[str, Any]]]
    competitors_raw: List[Dict[str, Any]] = None


@dataclass(frozen=True)
class SpotMarketData:
    usd_prices: Dict[str, float]
    fiat_quotes: Dict[Tuple[str, str], Dict[str, float]]


def _load_primary_credentials() -> ExchangeCredentials:
    rows = fetch_all_credentials()
    if not rows:
        raise SystemExit("Add at least one exchange credential first.")
    row = rows[0]
    secret = decrypt_secret(row["api_secret_encrypted"])
    return ExchangeCredentials(
        exchange=row["exchange"],
        api_key=row["api_key"],
        api_secret=secret,
        testnet=row.get("testnet", False),
    )


def _to_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _extract_ad_side(ad: Dict[str, Any]) -> Optional[int]:
    try:
        side = int(ad.get("side"))
    except (TypeError, ValueError):
        return None
    if side in (0, 1):
        return side
    return None


def _split_symbol(symbol: str) -> Optional[Tuple[str, str]]:
    normalized = str(symbol or "").upper()
    for quote in SPOT_QUOTE_SUFFIXES:
        if normalized.endswith(quote) and len(normalized) > len(quote):
            base = normalized[: -len(quote)]
            if base:
                return base, quote
    return None


def _build_currency_country_map() -> Dict[str, Set[str]]:
    response = requests.get(REST_COUNTRIES_URL, timeout=15)
    response.raise_for_status()
    data = response.json()
    mapping: Dict[str, Set[str]] = {}
    for entry in data:
        country_code = str(entry.get("cca3") or "").upper()
        currencies = entry.get("currencies") or {}
        if not country_code or not isinstance(currencies, dict):
            continue
        for code in currencies.keys():
            if not code:
                continue
            currency = code.upper()
            mapping.setdefault(currency, set()).add(country_code)
    return mapping


def _load_currency_country_map() -> Dict[str, Set[str]]:
    try:
        mapping = _build_currency_country_map()
        if mapping:
            return mapping
    except Exception:
        pass
    return {code: set(countries) for code, countries in DEFAULT_CURRENCY_COUNTRY_MAP.items()}


CURRENCY_COUNTRY_MAP = _load_currency_country_map()


def _fetch_spot_market_data() -> SpotMarketData:
    response = requests.get(
        SPOT_TICKERS_URL,
        params={"category": "spot"},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    tickers = payload.get("result", {}).get("list", [])
    usd_prices: Dict[str, float] = {}
    fiat_quotes: Dict[Tuple[str, str], Dict[str, float]] = {}
    for ticker in tickers:
        symbol = str(ticker.get("symbol") or "")
        pair = _split_symbol(symbol)
        if not pair:
            continue
        base, quote = pair
        last_price = _to_float(ticker.get("lastPrice"))
        if quote == "USDT" and last_price is not None:
            usd_prices[base] = last_price
        elif quote == "USDC" and last_price is not None:
            usd_prices.setdefault(base, last_price)
        if quote in FIAT_SPOT_FILTERS and base in SPOT_BASE_TOKENS:
            bid = _to_float(ticker.get("bid1Price"))
            ask = _to_float(ticker.get("ask1Price"))
            if bid is not None and ask is not None:
                fiat_quotes[(base, quote)] = {"bid": bid, "ask": ask}
    usd_prices.setdefault("USDT", 1.0)
    usd_prices.setdefault("USDC", 1.0)
    return SpotMarketData(usd_prices=usd_prices, fiat_quotes=fiat_quotes)


def _token_price_in_usd(token_id: str, market_data: SpotMarketData) -> Optional[float]:
    token = token_id.upper()
    return market_data.usd_prices.get(token)


def _token_fiat_quote(
    token_id: str,
    currency_id: str,
    market_data: SpotMarketData,
) -> Optional[Dict[str, float]]:
    key = (token_id.upper(), currency_id.upper())
    return market_data.fiat_quotes.get(key)


def _usd_to_token_amount(usd_value: float, token_price: Optional[float]) -> Optional[float]:
    if token_price is None or token_price <= 0:
        return None
    return usd_value / token_price


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _price_decimal_count(price_value: Any) -> Optional[int]:
    if price_value in (None, ""):
        return None
    text = str(price_value)
    if "." not in text:
        return 0
    decimals = text.split(".", 1)[1]
    return len(decimals)


def _price_group_gap(price_value: Any) -> Decimal:
    decimals = _price_decimal_count(price_value)
    if decimals is None:
        return Decimal("0.01")
    if decimals == 0:
        return Decimal("1")
    if decimals == 1:
        return Decimal("0.2")
    if decimals == 2:
        return Decimal("0.02")
    return Decimal("0.04")


def _determine_group_gap(ad: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Decimal:
    candidate_prices: List[Any] = [ad.get("price")]
    candidate_prices.extend(comp.get("price") for comp in competitors)
    for price_value in candidate_prices:
        decimals = _price_decimal_count(price_value)
        if decimals is not None:
            return _price_group_gap(price_value)
    return Decimal("0.01")


def _prices_within_gap(
    previous_price: Optional[Decimal],
    current_price: Decimal,
    gap: Decimal,
    ad_side: Optional[int],
) -> bool:
    if previous_price is None:
        return True
    if ad_side == 0:
        delta = previous_price - current_price
    elif ad_side == 1:
        delta = current_price - previous_price
    else:
        delta = (current_price - previous_price).copy_abs()
    if delta < 0:
        return False
    return delta <= gap


def _group_competitors_by_price(
    ad: Dict[str, Any],
    competitors: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    if not competitors:
        return []
    gap = _determine_group_gap(ad, competitors)
    ad_side = _extract_ad_side(ad)
    groups: List[List[Dict[str, Any]]] = []
    current_group: List[Dict[str, Any]] = []
    last_price: Optional[Decimal] = None
    for competitor in competitors:
        price = _to_decimal(competitor.get("price"))
        if price is None:
            if current_group:
                groups.append(current_group)
                current_group = []
            groups.append([competitor])
            last_price = None
            continue
        if not current_group:
            current_group = [competitor]
            last_price = price
            continue
        if _prices_within_gap(last_price, price, gap, ad_side):
            current_group.append(competitor)
        else:
            groups.append(current_group)
            current_group = [competitor]
        last_price = price
    if current_group:
        groups.append(current_group)
    return groups


def _passes_spot_price_guardrails(
    competitor: Dict[str, Any],
    ad_side: Optional[int],
    market_data: SpotMarketData,
) -> bool:
    if ad_side not in (0, 1):
        return True
    currency = str(competitor.get("currencyId") or "").upper()
    if currency not in FIAT_SPOT_FILTERS:
        return True
    token = str(competitor.get("tokenId") or "").upper()
    quote = _token_fiat_quote(token, currency, market_data)
    if not quote:
        return True
    price = _to_float(competitor.get("price"))
    if price is None:
        return True
    bid = quote.get("bid")
    ask = quote.get("ask")
    if bid is None or ask is None:
        return True
    if ad_side == 0:
        # Drop buyers that bid above what spot would pay us
        return price <= bid
    # ad_side == 1 (sell): drop sellers priced below spot ask
    return price >= ask


def _is_auto_enabled(ad: Dict[str, Any]) -> bool:
    remark = str(ad.get("remark") or "")
    if AUTO_MARKER not in remark:
        return False
    return AUTO_PAUSED_MARKER not in remark


def _requires_strict_payment_match(ad: Dict[str, Any]) -> bool:
    remark = str(ad.get("remark") or "")
    return f"{AUTO_MARKER}1" in remark


def _fetch_market_ads(api, ad: Dict[str, Any]) -> List[Dict[str, Any]]:
    resp = api.get_online_ads(
        tokenId=str(ad.get("tokenId")),
        currencyId=str(ad.get("currencyId")),
        side=str(ad.get("side")),
        page="1",
        size=MARKET_PAGE_SIZE,
    )
    return _extract_items(resp)


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


def _extract_payment_codes(ad: Dict[str, Any]) -> set[str]:
    payments = ad.get("payments")
    if isinstance(payments, list) and payments:
        return {str(item) for item in payments if item is not None}
    payment_terms = ad.get("paymentTerms")
    if isinstance(payment_terms, list):
        codes: set[str] = set()
        for item in payment_terms:
            ptype = item.get("paymentType") if isinstance(item, dict) else None
            if ptype is not None:
                codes.add(str(ptype))
        if codes:
            return codes
    payment_ids = ad.get("paymentIds")
    if isinstance(payment_ids, list):
        return {str(item) for item in payment_ids if item is not None}
    return set()


def _shares_payment_method(target_payments: set[str], competitor: Dict[str, Any], strict: bool) -> bool:
    if not target_payments:
        return True
    competitor_payments = _extract_payment_codes(competitor)
    if strict:
        # Strict mode requires the competitor to offer exactly the same payment methods (same items, same count).
        return (
            bool(target_payments)
            and target_payments == competitor_payments
        )
    return bool(target_payments & competitor_payments)


def _requirement_allows(flag_key: str, value_key: str, target_pref: Dict[str, Any], competitor_pref: Dict[str, Any]) -> bool:
    competitor_flag = bool(competitor_pref.get(flag_key))
    if not competitor_flag:
        return True
    target_flag = bool(target_pref.get(flag_key))
    if not target_flag:
        return True
    competitor_value = _to_float(competitor_pref.get(value_key))
    target_value = _to_float(target_pref.get(value_key))
    if competitor_value is None or target_value is None:
        return False
    return competitor_value <= target_value


def _parse_country_codes(raw_codes: str) -> Set[str]:
    if not raw_codes:
        return set()
    return {code.strip().upper() for code in raw_codes.split(",") if code.strip()}


def _currency_country_candidates(currency_id: str) -> Set[str]:
    return CURRENCY_COUNTRY_MAP.get(currency_id.upper(), set())


def _passes_national_limit_filter(competitor_pref: Dict[str, Any], currency_id: str) -> bool:
    has_limit = bool(competitor_pref.get("hasNationalLimit"))
    if not has_limit:
        return True
    whitelist = _parse_country_codes(competitor_pref.get("nationalLimit", ""))
    if not whitelist:
        return True
    currency_candidates = _currency_country_candidates(currency_id)
    if currency_candidates and whitelist & currency_candidates:
        return True
    if len(whitelist) >= 10:
        return True
    return False


def _passes_trading_preferences(target_pref: Dict[str, Any], competitor: Dict[str, Any]) -> bool:
    competitor_pref = competitor.get("tradingPreferenceSet") or {}
    if not isinstance(competitor_pref, dict):
        return True
    if not _requirement_allows(
        "hasRegisterTime",
        "registerTimeThreshold",
        target_pref,
        competitor_pref,
    ):
        return False
    if not _requirement_allows(
        "hasOrderFinishNumberDay30",
        "orderFinishNumberDay30",
        target_pref,
        competitor_pref,
    ):
        return False
    if not _requirement_allows(
        "hasCompleteRateDay30",
        "completeRateDay30",
        target_pref,
        competitor_pref,
    ):
        return False
    return _passes_national_limit_filter(
        competitor_pref,
        str(competitor.get("currencyId") or ""),
    )


def _passes_activity_filters(
    competitor: Dict[str, Any],
    my_last_quantity: Optional[float],
    market_data: SpotMarketData,
) -> bool:
    token = str(competitor.get("tokenId") or "").upper()
    last_quantity = _to_float(competitor.get("lastQuantity"))
    recent_orders = _to_float(competitor.get("recentOrderNum"))
    if last_quantity is None or last_quantity <= 0:
        return False
    token_price = _token_price_in_usd(token, market_data)
    min_liquidity = _usd_to_token_amount(MIN_ACTIVITY_USD, token_price)
    if min_liquidity is not None and last_quantity < min_liquidity:
        return False
    competition_cap = _usd_to_token_amount(MAX_COMPETITION_USD, token_price)
    if (
        competition_cap is not None
        and my_last_quantity is not None
        and last_quantity <= competition_cap
        and last_quantity < my_last_quantity
    ):
        return False
    if recent_orders is None or recent_orders < 50:
        return False
    return True


def _collect_competitors(
    api,
    ad: Dict[str, Any],
    market_data: SpotMarketData,
    market_ads: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    my_min = _to_float(ad.get("minAmount"))
    my_last_quantity = _to_float(ad.get("lastQuantity"))
    my_payment_codes = _extract_payment_codes(ad)
    strict_payment_match = _requires_strict_payment_match(ad)
    target_preferences = ad.get("tradingPreferenceSet") or {}
    my_account_id = str(ad.get("accountId") or "")
    ad_side = _extract_ad_side(ad)
    token_up = str(ad.get("tokenId") or ad.get("token") or "").upper()
    relax_filters = token_up in {"BTC", "ETH", "USDC"}
    market_ads = market_ads if market_ads is not None else _fetch_market_ads(api, ad)
    filtered: List[Dict[str, Any]] = []
    for competitor in market_ads:
        if my_account_id and str(competitor.get("accountId")) == my_account_id:
            continue
        if not _passes_min_gap_filter(my_min, competitor):
            continue
        if not _passes_min_max_gap_filter(competitor):
            continue
        if not _shares_payment_method(my_payment_codes, competitor, strict_payment_match):
            continue
        if relax_filters:
            filtered.append(competitor)
            continue
        if not _passes_spot_price_guardrails(competitor, ad_side, market_data):
            continue
        if not _passes_activity_filters(competitor, my_last_quantity, market_data):
            continue
        if not _passes_trading_preferences(target_preferences, competitor):
            continue
        filtered.append(competitor)
    return filtered


def _save_snapshot(contexts: List[AutoAdContext]) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    target = RESULTS_DIR / "auto_pricing_snapshot.json"
    payload = [asdict(item) for item in contexts]
    with target.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return target


def _save_per_ad_snapshots(contexts: List[AutoAdContext]) -> None:
    AUTO_RESULTS_DIR.mkdir(exist_ok=True, parents=True)
    for context in contexts:
        ad_id = context.ad.get("id") or context.ad.get("ad_id") or "unknown"
        target = AUTO_RESULTS_DIR / f"{ad_id}.json"
        with target.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "ad": context.ad,
                    "competitors": context.competitors,
                    "competitor_groups": context.competitor_groups,
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )


def collect_auto_pricing_contexts(creds: Optional[ExchangeCredentials] = None) -> List[AutoAdContext]:
    creds = creds or _load_primary_credentials()
    api = create_exchange_client(creds)
    my_ads = _load_bybit_ads(creds)
    auto_ads = [ad for ad in my_ads if _is_auto_enabled(ad)]
    market_data = _fetch_spot_market_data()
    contexts: List[AutoAdContext] = []
    for ad in auto_ads:
        market_ads = _fetch_market_ads(api, ad)
        competitors = _collect_competitors(api, ad, market_data, market_ads)
        competitor_groups = _group_competitors_by_price(ad, competitors)
        contexts.append(
            AutoAdContext(
                ad=ad,
                competitors=competitors,
                competitor_groups=competitor_groups,
                competitors_raw=market_ads,
            )
        )
    return contexts


def main() -> None:
    contexts = collect_auto_pricing_contexts()
    if DEBUG_SNAPSHOTS_ENABLED:
        output_file = _save_snapshot(contexts)
        _save_per_ad_snapshots(contexts)
        print(f"Saved snapshot for {len(contexts)} auto ads to {output_file}")
    else:
        print(f"Processed {len(contexts)} auto ads")


if __name__ == "__main__":
    main()
