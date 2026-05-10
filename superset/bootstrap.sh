#!/bin/bash
# Bootstrap idempotent Superset :
#   1. Migrer la metastore Postgres
#   2. Créer le user admin (depuis .env)
#   3. Initialiser les rôles
#   4. Importer la datasource VoC + datasets de référence
# Tournée en one-shot par le service `superset-init` (cf. docker-compose.yml).

set -euo pipefail

echo "[bootstrap] superset db upgrade…"
superset db upgrade

echo "[bootstrap] superset fab create-admin (idempotent)…"
superset fab create-admin \
    --username "${SUPERSET_ADMIN_USER:-admin}" \
    --firstname "${SUPERSET_ADMIN_FIRSTNAME:-Admin}" \
    --lastname "${SUPERSET_ADMIN_LASTNAME:-User}" \
    --email "${SUPERSET_ADMIN_EMAIL:-admin@voc.local}" \
    --password "${SUPERSET_ADMIN_PASSWORD:-admin}" \
    || echo "[bootstrap] admin already exists, skipping"

echo "[bootstrap] superset init (rôles + permissions)…"
superset init

# Provisioning de la datasource VoC + datasets via le script Python.
# On utilise l'API SQLAlchemy interne de Superset plutôt qu'un import YAML, plus fiable
# entre versions et sans gymnastique sur les UUID.
echo "[bootstrap] provisioning datasource + datasets…"
python /app/assets/provision.py

echo "[bootstrap] done."
