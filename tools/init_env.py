"""Create a private local configuration without printing the generated key."""

from pathlib import Path
import secrets


def main() -> None:
    path = Path(__file__).resolve().parents[1] / ".env"
    if path.exists():
        print("Existing .env preserved.")
        return
    with path.open("x", encoding="utf-8") as config:
        config.write(f"APP_API_KEY={secrets.token_urlsafe(32)}\nAPP_HOST=127.0.0.1\nAPP_PORT=8000\n")
    print("Created .env with a private key. Open the file locally to use the key.")


if __name__ == "__main__":
    main()
