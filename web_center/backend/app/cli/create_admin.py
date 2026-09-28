import argparse
from getpass import getpass
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.auth import User
from app.schemas.auth import UserCreate
from app.services.auth_service import create_user


def read_password() -> str:
    while True:
        first = getpass("Admin password (minimum 6 characters): ")
        second = getpass("Repeat admin password: ")
        if first != second:
            print("Passwords do not match.")
            continue
        if len(first) < 6:
            print("Password must be at least 6 characters.")
            continue
        return first


def main() -> None:
    parser = argparse.ArgumentParser(description="创建首位管理员")
    parser.add_argument("--username")
    parser.add_argument("--display-name")
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        existing = db.scalar(
            select(User).where(
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
        if existing is not None:
            print("Active administrator already exists:", existing.username)
            return

        username = args.username or input("Admin username [admin]: ").strip() or "admin"
        display_name = args.display_name or input("Admin display name [系统管理员]: ").strip() or "系统管理员"
        password = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else read_password()
        if args.password_stdin and not 6 <= len(password) <= 128:
            raise SystemExit("Admin password must be 6-128 characters.")

        user = create_user(
            db,
            UserCreate(
                username=username,
                display_name=display_name,
                password=password,
                role="admin",
                is_active=True,
            ),
        )
        print("Administrator created:", user.username)


if __name__ == "__main__":
    main()
