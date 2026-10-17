from lib import invitations


def batch(emails):
    return [invitations.prepare_invite(email) for email in emails]
