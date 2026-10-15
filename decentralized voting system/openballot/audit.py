import datetime
import time
from typing import List, Dict, Any


def get_ist_datetime(epoch_seconds: float = None) -> datetime.datetime:
    tz_ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")
    if epoch_seconds is not None:
        return datetime.datetime.fromtimestamp(epoch_seconds, tz=tz_ist)
    return datetime.datetime.now(tz=tz_ist)


class AuditLogger:
    """
    Lightweight structured in-memory chronological event logger for OpenBallot.
    Records system actions, ballot receipts, validations, block creation, and peer syncs
    with Indian Standard Time (IST / UTC+05:30) timestamps.
    """
    def __init__(self, max_events: int = 500):
        self.max_events = max_events
        self.events: List[Dict[str, Any]] = []

    def log(self, event_type: str, details: str, status: str = "INFO"):
        now = time.time()
        dt_ist = get_ist_datetime(now)
        record = {
            "timestamp": now,
            "time_str": dt_ist.strftime("%I:%M:%S %p IST"),
            "date_str": dt_ist.strftime("%d %b %Y"),
            "event_type": event_type,
            "details": details,
            "status": status  # "INFO", "SUCCESS", "WARNING", "ERROR"
        }
        self.events.append(record)
        if len(self.events) > self.max_events:
            self.events.pop(0)

    def get_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        # Return newest first
        return list(reversed(self.events[-limit:]))


# Global instance for node server
audit_log = AuditLogger()
