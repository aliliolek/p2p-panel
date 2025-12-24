import code
import os

from dotenv import load_dotenv

from exchanges import ExchangeCredentials, create_exchange_client
from repositories.credentials_repository import fetch_all_credentials
from security import decrypt_secret


def load_first_credential() -> ExchangeCredentials:
    rows = fetch_all_credentials()
    if not rows:
        raise SystemExit("No credentials found in user_exchange_keys table.")
    row = rows[0]
    secret = decrypt_secret(row["api_secret_encrypted"])
    return ExchangeCredentials(
        exchange=row["exchange"],
        api_key=row["api_key"],
        api_secret=secret,
        testnet=row.get("testnet", False),
    )


def main() -> None:
    load_dotenv()
    creds = load_first_credential()
    client = create_exchange_client(creds)

    banner = (
        "Bybit P2P shell\n"
        "Variable 'api' is available. Example:\n"
        ">>> api.get_pending_orders(page=1, size=3)\n"
    )
    namespace = {"api": client}
    code.interact(banner=banner, local=namespace)


if __name__ == "__main__":
    main()
