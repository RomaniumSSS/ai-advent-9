def send_invite(email: str, *, role: str = "member", dry_run: bool = False) -> dict:
    """Создать приглашение; dry_run не отправляет письмо."""
    if "@" not in email:
        raise ValueError("Некорректный email")
    if role not in {"member", "admin"}:
        raise ValueError("Неизвестная роль")
    return {"email": email, "role": role, "sent": not dry_run}
