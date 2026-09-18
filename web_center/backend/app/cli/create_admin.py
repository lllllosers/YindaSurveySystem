from getpass import getpass

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.auth import User
from app.schemas.auth import UserCreate
from app.services.auth_service import create_user


def read_password() -> str:
    while True:
        first = getpass("Admin password (minimum 10 characters): ")
        second = getpass("Repeat admin password: ")
        if first != second:
            print("Passwords do not match.")
            continue
        if len(first) < 10:
            print("Password must be at least 10 characters.")
            continue
        return first


def main() -> None:
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

        username = input("Admin username [admin]: ").strip() or "admin"
        display_name = (
            input("Admin display name [系统管理员]: ").strip()
            or "系统管理员"
        )
        password = read_password()

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
