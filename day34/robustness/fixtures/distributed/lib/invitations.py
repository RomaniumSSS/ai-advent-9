from adapters.delivery import persist


def prepare_invite(email, *, role="viewer", dry_run=False):
    payload = {"email": email, "role": role, "sent": True}
    if not dry_run:
        persist(payload)
    return payload


def prepare_invite_preview(email):
    return {"email": email, "preview": True}
