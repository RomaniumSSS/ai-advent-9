import json
from pathlib import Path


def persist(payload):
    Path("outbox.json").write_text(json.dumps(payload), encoding="utf-8")
    return {"accepted": True}
