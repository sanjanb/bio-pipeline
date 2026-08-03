"""File-based cache with TTL for bioinformatics API responses."""

import json
import hashlib
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / ".cache"
DEFAULT_TTL = 3600  # 1 hour


def _cache_path(key: str) -> Path:
    """SHA256 hash of key → file path."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    hashed = hashlib.sha256(key.encode()).hexdigest()
    return CACHE_DIR / f"{hashed}.json"


def get_cached(key: str, ttl: int = DEFAULT_TTL) -> dict | None:
    """Return cached data if fresh, else None."""
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_time = data.get("_cached_at", 0)
        if time.time() - cached_time > ttl:
            return None
        return data.get("data")
    except (json.JSONDecodeError, OSError, KeyError) as e:
        logger.warning("Cache read failed for %s: %s", key, e)
        return None


def set_cached(key: str, data: dict) -> None:
    """Write data to cache."""
    path = _cache_path(key)
    try:
        payload = {"_cached_at": time.time(), "data": data}
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError as e:
        logger.warning("Cache write failed for %s: %s", key, e)