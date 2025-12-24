from typing import Any, Dict, Optional

from supabase_client import supabase

ORDER_STATE_TABLE = "order_state"
ORDER_LOG_TABLE = "order_action_log"


def fetch_state(order_id: str) -> Optional[Dict[str, Any]]:
    response = (
        supabase.table(ORDER_STATE_TABLE)
        .select("*")
        .eq("order_id", order_id)
        .limit(1)
        .execute()
    )
    items = response.data or []
    return items[0] if items else None


def upsert_state(record: Dict[str, Any]) -> Dict[str, Any]:
    response = supabase.table(ORDER_STATE_TABLE).upsert(record).execute()
    data = response.data or []
    return data[0] if data else record


def update_flags(order_id: str, **flags: Any) -> None:
    payload = {key: value for key, value in flags.items() if value is not None}
    if not payload:
        return
    supabase.table(ORDER_STATE_TABLE).update(payload).eq("order_id", order_id).execute()


def log_action(
    order_id: str,
    credential_id: str,
    action: str,
    *,
    request: Optional[Dict[str, Any]] = None,
    response: Optional[Dict[str, Any]] = None,
    status: Optional[str] = None,
) -> None:
    record = {
        "order_id": order_id,
        "credential_id": credential_id,
        "action": action,
        "request": request or {},
        "response": response or {},
        "status": status or "success",
    }
    supabase.table(ORDER_LOG_TABLE).insert(record).execute()
