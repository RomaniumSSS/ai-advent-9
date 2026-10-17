from .api import send_invite


def onboard(email: str) -> dict:
    return send_invite(email, role="member", dry_run=False)
