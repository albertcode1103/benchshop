import argparse
import getpass
import sqlite3

from .database import initialize_database
from .user_repository import create_user


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a BOTEN administrator account")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Administrator")
    args = parser.parse_args()
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")

    initialize_database()
    try:
        user = create_user(args.email.lower(), None, password, role="admin", display_name=args.name)
    except (ValueError, sqlite3.IntegrityError) as error:
        raise SystemExit(str(error))
    print("Created admin: {} ({})".format(user["email"], user["id"]))


if __name__ == "__main__":
    main()
