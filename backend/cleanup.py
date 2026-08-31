from .config_repository import expire_old_shares
from .database import initialize_database


def main() -> None:
    initialize_database()
    count = expire_old_shares()
    print("Expired {} share record(s).".format(count))


if __name__ == "__main__":
    main()
