import json
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Any, Dict, List

from dotenv import load_dotenv

from exchanges import create_exchange_client
from repositories.credentials_repository import fetch_all_credentials
from services.credentials_service import build_exchange_credentials
from services.order_processing.messaging import counterparty_realname
from services.order_processing.payments import extract_pln_payment_buy, extract_pln_payment_sell
from services.orders_service import _fetch_counterparty_info
from supabase_client import supabase

ORDER_STATE_TABLE = "order_state"

BATCH_SIZE = 50
MAX_ROWS: int | None = None
DRY_RUN = False
ONLY_MISSING = False
OVERWRITE_FIELDS = {"from_bank", "from_phone", "from_iban"}


def _load_first_row_and_creds():
    rows = fetch_all_credentials()
    if not rows:
        raise SystemExit("Add at least one exchange credential first.")
    row = rows[0]
    creds = build_exchange_credentials(row)
    return row, creds


def _fetch_order_ids(limit: int) -> List[str]:
    response = supabase.table(ORDER_STATE_TABLE).select("order_id").range(0, limit - 1).execute()
    rows = response.data or []
    return [str(row.get("order_id") or "") for row in rows if row.get("order_id")]


def _fetch_order_state_batch(offset: int, limit: int) -> List[Dict[str, Any]]:
    response = (
        supabase.table(ORDER_STATE_TABLE)
        .select(
            "order_id, side, "
            "from_bank, from_phone, from_full_name, from_iban, "
            "to_bank, to_phone, to_full_name, to_iban"
        )
        .range(offset, offset + limit - 1)
        .execute()
    )
    return response.data or []


def _missing_fields(row: Dict[str, Any], fields: List[str]) -> bool:
    return any(not row.get(field) for field in fields)


def _update_order_state(order_id: str, payload: Dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        print(f"[DRY RUN] {order_id} -> {payload}")
        return
    supabase.table(ORDER_STATE_TABLE).update(payload).eq("order_id", order_id).execute()


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


def _is_valid_value(value: Any) -> bool:
    return bool(value) and str(value).strip().lower() != "not found"


def _build_payload_buy(api, order: Dict[str, Any]) -> Dict[str, Any]:
    order_id = str(order.get("id") or order.get("orderId") or "")
    token_id = str(order.get("tokenId") or order.get("tokenName") or "")
    my_info = extract_pln_payment_sell(api, order_id, token_id)
    counterparty = order.get("counterparty_info") or _fetch_counterparty_info(api, order) or {}
    counterparty_info = extract_pln_payment_buy(order)
    counterparty_info["full_name"] = counterparty_realname(order, counterparty)
    return {
        "from_full_name": my_info.get("full_name"),
        # "from_bank": my_info.get("bank"),
        # "from_phone": my_info.get("phone"),
        # "from_iban": my_info.get("iban"),
        "to_bank": counterparty_info.get("bank"),
        "to_phone": counterparty_info.get("phone"),
        "to_full_name": counterparty_info.get("full_name"),
        "to_iban": counterparty_info.get("iban"),
    }


def _build_payload_sell(api, order: Dict[str, Any]) -> Dict[str, Any]:
    order_id = str(order.get("id") or order.get("orderId") or "")
    token_id = str(order.get("tokenId") or order.get("tokenName") or "")
    counterparty = order.get("counterparty_info") or _fetch_counterparty_info(api, order) or {}
    counterparty_info = extract_pln_payment_buy(order)
    counterparty_info["full_name"] = counterparty_realname(order, counterparty)
    confirmed_name = _extract_confirmed_payment_name(order)
    from_bank = confirmed_name or counterparty_info.get("bank")
    my_info = extract_pln_payment_sell(api, order_id, token_id)
    payload = {
        "from_bank": from_bank,
        "from_full_name": counterparty_info.get("full_name"),
        "from_phone": None,
        "from_iban": None,
        "to_full_name": my_info.get("full_name"),
        # "to_bank": my_info.get("bank"),
        # "to_phone": my_info.get("phone"),
        # "to_iban": my_info.get("iban"),
    }
    return {key: value for key, value in payload.items() if _is_valid_value(value)}


def populate_order_state_payment_fields(
    api,
    *,
    batch_size: int = BATCH_SIZE,
    max_rows: int | None = MAX_ROWS,
    dry_run: bool = DRY_RUN,
    only_missing: bool = ONLY_MISSING,
) -> None:
    load_dotenv()
    offset = 0
    processed = 0
    target_fields = [
        "from_bank",
        "from_phone",
        "from_full_name",
        "from_iban",
        "to_bank",
        "to_phone",
        "to_full_name",
        "to_iban",
    ]

    while True:
        batch = _fetch_order_state_batch(offset, batch_size)
        if not batch:
            break
        for state in batch:
            order_id = str(state.get("order_id") or "")
            if not order_id:
                continue
            if only_missing and not _missing_fields(state, target_fields):
                continue

            details = api.get_order_details(orderId=order_id)
            order = details.get("result") if isinstance(details, dict) else None
            if not isinstance(order, dict):
                continue

            side_raw = state.get("side") or order.get("side")
            side = str(side_raw).upper()
            if side in {"0", "BUY"}:
                payload = _build_payload_buy(api, order)
            elif side in {"1", "SELL"}:
                payload = _build_payload_sell(api, order)
            else:
                continue

            if only_missing:
                payload = {
                    key: value
                    for key, value in payload.items()
                    if key in OVERWRITE_FIELDS or not state.get(key)
                }
            if not payload:
                continue

            _update_order_state(order_id, payload, dry_run)
            processed += 1
            print(f"updated {order_id} -> {payload}")

            if max_rows and processed >= max_rows:
                return

        offset += batch_size


def dump_order_chats(
    api,
    *,
    limit: int = 20,
    message_size: int = 200,
    start_message_id: str | None = None,
    output_path: str | None = None,
) -> Path:
    order_ids = _fetch_order_ids(limit)
    results: List[Dict[str, Any]] = []
    for order_id in order_ids:
        params = {"orderId": order_id, "size": str(message_size)}
        if start_message_id:
            params["startMessageId"] = str(start_message_id)
        resp = api.get_chat_messages(**params)
        results.append({"order_id": order_id, "response": resp})

    target = Path(output_path) if output_path else Path("playground_results")
    target.mkdir(parents=True, exist_ok=True)
    filename = f"chat_dump_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    path = target / filename
    with path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    pprint({"saved": str(path), "orders": len(results)})
    return path


def main() -> None:
    load_dotenv()
    _, creds = _load_first_row_and_creds()
    api = create_exchange_client(creds)

    # Playground: call whatever you need here.
    # populate_order_state_payment_fields(api, dry_run=True)
    # dump_order_chats(api, limit=20)

    
    # кшиштоф
    pprint(api.get_order_details(
        orderId="2001764006806712320"
    ))
    # pprint(api.get_counterparty_info(
    #     originalUid="413801068",
    #     orderId="2001764006806712320"
    # ))

    # я з кшиштофом
    # pprint(api.get_counterparty_info(
    #     originalUid="428191399",
    #     orderId="2002311478164967424"
    # ))

    # влад 
    # pprint(api.get_order_details(
    #     orderId="2002311478164967424"
    # ))
    # pprint(api.get_counterparty_info(
    #     originalUid="55554257",
    #     orderId="2002311478164967424"
    # ))
    
    # dump_order_chats(api, limit=10)
    # pprint(api.get_account_information())




if __name__ == "__main__":
    main()
