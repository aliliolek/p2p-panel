from pathlib import Path

from constants import FIAT_BALANCE_REMARK_MARKER

MARKER_FILE = Path("playground_results/fiat_balance_remark.txt")


def get_marker() -> str:
    if MARKER_FILE.exists():
        try:
            return MARKER_FILE.read_text(encoding="utf-8").strip() or FIAT_BALANCE_REMARK_MARKER
        except Exception:
            return FIAT_BALANCE_REMARK_MARKER
    return FIAT_BALANCE_REMARK_MARKER


def save_marker(value: str) -> None:
    try:
        MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        MARKER_FILE.write_text(value or FIAT_BALANCE_REMARK_MARKER, encoding="utf-8")
    except Exception:
        pass
