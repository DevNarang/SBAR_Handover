from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
TIMEZONE_NAME = "Asia/Kolkata"


def now() -> datetime:
    """Naive hospital clock in IST (Asia/Kolkata). JWT expiry stays UTC."""
    return datetime.now(IST).replace(tzinfo=None)
