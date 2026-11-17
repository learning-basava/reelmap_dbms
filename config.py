"""App settings, read from environment variables (or a local .env file)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from a .env file without overriding real env vars."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "reelmap")

# Cloud databases such as TiDB Cloud need an encrypted (TLS) connection.
MYSQL_SSL = os.getenv("MYSQL_SSL", "false").strip().lower() in ("1", "true", "yes")
MYSQL_SSL_CA = os.getenv("MYSQL_SSL_CA", "").strip()  # optional path to a CA file

# Create the tables automatically on first start if they don't exist yet.
AUTO_INIT_DB = os.getenv("AUTO_INIT_DB", "true").strip().lower() in ("1", "true", "yes")


def mysql_kwargs(with_database=True):
    """Connection settings for PyMySQL, with TLS when MYSQL_SSL is on."""
    kw = {"host": MYSQL_HOST, "port": MYSQL_PORT, "user": MYSQL_USER, "password": MYSQL_PASSWORD,
          "charset": "utf8mb4", "connect_timeout": 10}
    if with_database:
        kw["database"] = MYSQL_DB
    if MYSQL_SSL:
        if MYSQL_SSL_CA:
            ca = MYSQL_SSL_CA
        else:
            import certifi  # trusted public certificates
            ca = certifi.where()
        kw.update(ssl_ca=ca, ssl_verify_cert=True, ssl_verify_identity=True)
    return kw


# Optional: enables the "Ask AI" buttons. Leave empty to use only the idea bank.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
