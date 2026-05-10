-- Crée la base metadata pour Superset, à côté de `airflow` (metadata Airflow)
-- et `voc` (data warehouse VoC). Exécuté automatiquement au premier démarrage
-- du conteneur Postgres via /docker-entrypoint-initdb.d.

CREATE DATABASE superset;
