"""Small filesystem checkpoint boundary for the visible notebook HTTP calls."""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def bind_run(path, identity):
    """Keep a run tied to the same API origin and original PDF bytes/name."""
    path = Path(path)
    if path.exists():
        run = json.loads(path.read_text(encoding="utf-8"))
        if run["identity"] != identity:
            raise ValueError("Run identity changed; choose a different output directory.")
        return run
    run = {"identity": identity, "started_at": datetime.now(UTC).isoformat()}
    save_json(path, run)
    return run


def save_json(path, value):
    """Replace one snapshot only after its complete JSON has reached disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def submit_once(path, *, identity, prepare, send, read_saved):
    """Save an intent before sending; reruns use its original body and key.

    HTTP construction belongs to the notebook callbacks. Use one kernel per run.
    prepare is lazy so a lost response cannot refresh an accepted question's head.
    """
    path = Path(path)
    if path.exists():
        intent = json.loads(path.read_text(encoding="utf-8"))
        if intent["identity"] != identity:
            raise ValueError("Checkpoint identity changed; use a new intent for new work.")
    else:
        intent = {"identity": identity, "body": prepare(), "key": str(uuid4())}
        save_json(path, intent)
    if "receipt" in intent:
        response = read_saved(intent["receipt"])
        response.raise_for_status()
        return intent["receipt"]
    response = send(intent["body"], intent["key"])
    response.raise_for_status()
    intent["receipt"] = response.json()
    save_json(path, intent)
    return intent["receipt"]
