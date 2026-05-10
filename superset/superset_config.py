"""Configuration Superset — pointe la metastore vers Postgres `superset` et
configure Redis comme cache + broker Celery."""

from __future__ import annotations

import os

# --- Sécurité ---
# Clé pour signer les sessions Flask. À surcharger via SUPERSET_SECRET_KEY (.env).
SECRET_KEY = os.environ.get(
    "SUPERSET_SECRET_KEY",
    "CHANGE_ME_SUPERSET_SECRET_KEY",
)

# --- Metastore Superset (Postgres) ---
PG_USER = os.environ.get("POSTGRES_USER", "postgres")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/superset"
)

# --- Cache + Celery (Redis) ---
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 1,
}
DATA_CACHE_CONFIG = CACHE_CONFIG


class CeleryConfig:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    imports = ("superset.sql_lab",)
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    worker_prefetch_multiplier = 1
    task_acks_late = True


CELERY_CONFIG = CeleryConfig

# --- Features Superset utiles pour le MVP ---
FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS_SET": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
}

# Permet aux datasources externes (notre DB `voc`) de s'afficher en SQL Lab.
SQLLAB_CTAS_NO_LIMIT = True

# Pas d'auth externe — on utilise l'auth Superset native (DB).
ENABLE_PROXY_FIX = True
