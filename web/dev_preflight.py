"""Read-only checks before starting local Web development services."""
from pathlib import Path
import re
import subprocess
import sys


_PASSWORD_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?DB_PASSWORD\s*=", re.IGNORECASE)
# Match presence only: no password extraction, expansion or logging.
_NONEMPTY_PASSWORD = re.compile(
    r"^\s*(?:export\s+)?DB_PASSWORD\s*=\s*"
    r'''(?:"[ \t]*(?:\\.|[^ \t"\\])(?:\\.|[^"\\])*"|'[ \t]*[^ \t'][^']*'|[^ \t#'"\r\n][^\r\n]*)'''
    r"[ \t]*(?:#.*)?$",
    re.IGNORECASE,
)


def password_is_configured(env_path: Path) -> bool:
    configured = False
    with env_path.open(encoding="utf-8-sig") as env_file:
        for line in env_file:
            if _PASSWORD_ASSIGNMENT.match(line):
                configured = bool(_NONEMPTY_PASSWORD.fullmatch(line.rstrip("\r\n")))
    return configured


def main() -> int:
    root = Path(__file__).resolve().parent
    if not (root / "backend/.venv/Scripts/python.exe").is_file():
        print("Backend Python is missing: web/backend/.venv/Scripts/python.exe")
        print("Create the backend virtual environment and install requirements-dev.txt.")
        return 1
    env_path = root / "backend/.env"
    if not env_path.is_file():
        print("Development configuration is missing: web/backend/.env")
        print("Copy .env.example to .env and configure the local PostgreSQL DB_PASSWORD before starting Web Center.")
        return 1
    try:
        configured = password_is_configured(env_path)
    except (OSError, UnicodeError):
        print("Cannot read web/backend/.env. Check the local development configuration.")
        return 1
    if not configured:
        print("DB_PASSWORD is empty or missing in web/backend/.env.")
        print("Configure the local yinda_app password before starting Web Center.")
        return 1
    if not (root / "frontend/node_modules").is_dir():
        print("Frontend dependencies are missing: web/frontend/node_modules")
        print("Run npm ci in web/frontend before starting Web Center.")
        return 1
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        print("Cannot check development ports. No services were started.")
        return 1
    occupied = set()
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 5 or fields[0] != "TCP" or fields[3] != "LISTENING":
            continue
        port = fields[1].rsplit(":", 1)[-1]
        if port in {"8000", "8848"}:
            occupied.add((port, fields[4]))
    for port, pid in sorted(occupied):
        print(f"Port {port} is already in use. PID: {pid}")
        print("Please stop the existing development process and retry.")
    if occupied:
        return 1
    print("Development preflight passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
