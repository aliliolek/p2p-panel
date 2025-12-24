from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from bybit_p2p import P2P

SUPPORTED_EXCHANGES = ("bybit", "binance", "okx")


@dataclass
class ExchangeCredentials:
    exchange: str
    api_key: str
    api_secret: str
    testnet: bool = False


class ExchangeVerificationResult:
    def __init__(self, success: bool, payload: Dict[str, Any]):
        self.success = success
        self.payload = payload
        self.checked_at = datetime.now(timezone.utc)


def create_exchange_client(creds: ExchangeCredentials) -> P2P:
    if creds.exchange != "bybit":
        raise NotImplementedError(f"Exchange {creds.exchange} is not supported yet.")
    return P2P(
        testnet=creds.testnet,
        api_key=creds.api_key,
        api_secret=creds.api_secret,
    )


def _verify_bybit(creds: ExchangeCredentials) -> ExchangeVerificationResult:
    api = create_exchange_client(creds)
    data = api.get_account_information()
    return ExchangeVerificationResult(True, data)


def verify_credentials(creds: ExchangeCredentials) -> ExchangeVerificationResult:
    if creds.exchange == "bybit":
        return _verify_bybit(creds)
    return ExchangeVerificationResult(
        False,
        {
            "message": f"Verification for {creds.exchange} is not implemented yet.",
        },
    )
