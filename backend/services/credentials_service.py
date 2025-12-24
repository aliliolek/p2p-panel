import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import HTTPException, status

from config import settings
from exchanges import ExchangeCredentials, SUPPORTED_EXCHANGES, verify_credentials
from repositories.credentials_repository import (
    delete_credential as repo_delete_credential,
    fetch_all_credentials as repo_fetch_all_credentials,
    fetch_user_credentials as repo_fetch_user_credentials,
    insert_credential,
    update_status,
)
from schemas import CredentialCreate, CredentialResponse
from security import decrypt_secret, encrypt_secret

VERIFIABLE_EXCHANGES = {"bybit"}


def _preview_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return api_key
    return f"{api_key[:4]}...{api_key[-4:]}"


def _format_row(row: Dict[str, Any]) -> CredentialResponse:
    return CredentialResponse(
        id=row["id"],
        exchange=row["exchange"],
        account_label=row.get("account_label"),
        api_key_preview=_preview_key(row["api_key"]),
        status=row.get("status", "pending"),
        last_check_at=row.get("last_check_at"),
        last_check_response=row.get("last_check_response"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def build_exchange_credentials(row: Dict[str, Any]) -> ExchangeCredentials:
    secret = decrypt_secret(row["api_secret_encrypted"])
    return ExchangeCredentials(
        exchange=row["exchange"],
        api_key=row["api_key"],
        api_secret=secret,
        testnet=row.get("testnet", False),
    )


async def list_credentials(user_id: str) -> List[CredentialResponse]:
    rows = await asyncio.to_thread(repo_fetch_user_credentials, user_id)
    return [_format_row(row) for row in rows]


async def create_credential(
    user_id: str,
    payload: CredentialCreate,
) -> CredentialResponse:
    record = {
        "user_id": user_id,
        "exchange": payload.exchange,
        "account_label": payload.account_label,
        "api_key": payload.api_key,
        "api_secret_encrypted": encrypt_secret(payload.api_secret),
        "status": "pending",
    }
    try:
        row = await asyncio.to_thread(insert_credential, record)
    except RuntimeError as exc:  # pragma: no cover - network/database error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store credentials",
        ) from exc
    asyncio.create_task(verify_and_update(row))
    return _format_row(row)


async def delete_credential(user_id: str, credential_id: str) -> bool:
    return await asyncio.to_thread(repo_delete_credential, user_id, credential_id)


async def fetch_all_credentials() -> List[Dict[str, Any]]:
    return await asyncio.to_thread(repo_fetch_all_credentials)


def _should_verify_now(row: Dict[str, Any]) -> bool:
    last_check = row.get("last_check_at")
    if not last_check:
        return True
    if isinstance(last_check, str):
        last_check_dt = datetime.fromisoformat(last_check.replace("Z", "+00:00"))
    else:
        last_check_dt = last_check
    delta = datetime.now(timezone.utc) - last_check_dt
    return delta.total_seconds() >= settings.credential_check_interval_seconds


def _needs_processing(row: Dict[str, Any]) -> bool:
    exchange = row.get("exchange")
    if exchange not in SUPPORTED_EXCHANGES:
        return False
    return _should_verify_now(row)


def should_process(row: Dict[str, Any]) -> bool:
    return _needs_processing(row)


async def _mark_unverifiable(row: Dict[str, Any]) -> None:
    await asyncio.to_thread(
        update_status,
        row["id"],
        status_value="pending",
        last_check_response={
            "message": f"Verification for {row['exchange']} is not available yet."
        },
        last_check_at=datetime.now(timezone.utc),
    )


async def verify_and_update(row: Dict[str, Any]) -> None:
    exchange = row["exchange"]
    if exchange not in VERIFIABLE_EXCHANGES:
        await _mark_unverifiable(row)
        return

    creds = build_exchange_credentials(row)
    try:
        result = await asyncio.to_thread(verify_credentials, creds)
        status_value = "active" if result.success else "error"
        response_body = result.payload
        checked_at = result.checked_at
    except Exception as exc:  # pragma: no cover - third-party errors
        status_value = "error"
        response_body = {"message": str(exc)}
        checked_at = datetime.now(timezone.utc)

    await asyncio.to_thread(
        update_status,
        row["id"],
        status_value=status_value,
        last_check_response=response_body,
        last_check_at=checked_at,
    )
