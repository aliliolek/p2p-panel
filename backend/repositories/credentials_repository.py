from datetime import datetime
from typing import Any, Dict, List

from supabase_client import supabase

TABLE_NAME = "user_exchange_keys"


def fetch_user_credentials(user_id: str) -> List[Dict[str, Any]]:
    response = (
        supabase.table(TABLE_NAME)
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def fetch_all_credentials() -> List[Dict[str, Any]]:
    response = supabase.table(TABLE_NAME).select("*").execute()
    return response.data or []


def insert_credential(record: Dict[str, Any]) -> Dict[str, Any]:
    response = supabase.table(TABLE_NAME).insert(record).execute()
    if not response.data:
        raise RuntimeError("Failed to store credentials")
    return response.data[0]


def delete_credential(user_id: str, credential_id: str) -> bool:
    response = (
        supabase.table(TABLE_NAME)
        .delete()
        .eq("id", credential_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(response.data)


def update_status(
    credential_id: str,
    *,
    status_value: str,
    last_check_response: Dict[str, Any],
    last_check_at: datetime,
) -> None:
    supabase.table(TABLE_NAME).update(
        {
            "status": status_value,
            "last_check_response": last_check_response,
            "last_check_at": last_check_at.isoformat(),
        }
    ).eq("id", credential_id).execute()
