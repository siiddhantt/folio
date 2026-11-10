import json
import logging
import os
import traceback
from datetime import UTC, datetime

logger = logging.getLogger(__name__)
_component = "unknown"


def configure_logging(component):
    global _component
    _component = component
    application = logging.getLogger("folio")
    application.setLevel(logging.INFO)
    application.propagate = False
    if not application.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        application.addHandler(handler)


def log_event(name, request_id=None, attempt_id=None, *, level=logging.INFO, error=None, **details):
    """Emit application-owned metadata; telemetry must not interrupt processing."""
    try:
        if error is not None:
            # Only application code identities; never messages, locals, source text or paths.
            frames = []
            for frame, line in traceback.walk_tb(error.__traceback__):
                module = frame.f_globals.get("__name__", "")
                if module.startswith("folio."):
                    frames.append(
                        {"module": module, "function": frame.f_code.co_name, "line": line}
                    )
            details["error_type"] = type(error).__name__
            details["error_frames"] = frames[-8:]
            if isinstance(error, OSError) and isinstance(error.errno, int):
                details["errno"] = error.errno
        logger.log(
            level,
            "%s",
            json.dumps(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "severity": logging.getLevelName(level),
                    "component": _component,
                    "pid": os.getpid(),
                    "event": name,
                    "request_id": str(request_id) if request_id is not None else None,
                    "attempt_id": str(attempt_id) if attempt_id is not None else None,
                    **details,
                }
            ),
        )
    except Exception:
        # A missing log is preferable to changing an accepted document's outcome.
        pass
