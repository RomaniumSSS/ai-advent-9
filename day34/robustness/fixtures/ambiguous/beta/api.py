from pathlib import Path


def send_invite(email):
    Path("pending.txt").write_text(email, encoding="utf-8")
    return {"queued": True}
