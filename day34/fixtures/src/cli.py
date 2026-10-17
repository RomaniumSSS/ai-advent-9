import argparse
from .api import send_invite


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("--role", choices=["member", "admin"], default="member")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(send_invite(args.email, role=args.role, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
