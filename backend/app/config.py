"""Runtime configuration, read from environment variables with safe local defaults."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# SQLite by default so the project runs with zero setup.
# For PostgreSQL set e.g. DATABASE_URL=postgresql+psycopg://user:pass@localhost/ecobyte
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'ecobyte.db').as_posix()}")


def _load_secret() -> str:
    env = os.getenv("ECOBYTE_SECRET_KEY")
    if env:
        return env
    # Persist a random key locally so tokens survive restarts without a hardcoded secret.
    key_file = DATA_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(48)
    key_file.write_text(key)
    return key


SECRET_KEY = _load_secret()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_HOURS = int(os.getenv("ECOBYTE_TOKEN_HOURS", "12"))

CORS_ORIGINS = os.getenv("ECOBYTE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

HISTORICAL_XLSX = DATA_DIR / "EcoByte_2025_Synthetic_Canteen_Data.xlsx"
MODEL_PATH = DATA_DIR / "rf_model.joblib"

MEAL_TYPES = ("breakfast", "lunch", "dinner")
