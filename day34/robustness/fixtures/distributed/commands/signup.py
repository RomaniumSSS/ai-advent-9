from lib.invitations import prepare_invite as make


def register(email):
    return make(email, role="admin")


def preview(email):
    return make(email, dry_run=True)
