from getpass import getpass

from app.db.session import SessionLocal
from app.services.auth_service import get_user_by_username, reset_password


def read_password() -> str:
    while True:
        first = getpass("New password (minimum 6 characters): ")
        second = getpass("Repeat new password: ")
        if first != second:
            print("Passwords do not match.")
            continue
        if len(first) < 6:
            print("Password must be at least 6 characters.")
            continue
        return first


def main() -> None:
    username = input("Admin username [cy]: ").strip() or "cy"
    with SessionLocal() as db:
        user = get_user_by_username(db, username)
        if user is None or user.role != "admin":
            print("Administrator not found:", username)
            return
        password = read_password()
        reset_password(db, user, password)
        print("Administrator password reset; existing sessions were revoked:", username)


if __name__ == "__main__":
    main()
