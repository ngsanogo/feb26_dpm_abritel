# Superset (image locale)

`superset_config.py` et le `Dockerfile` servent à une **démo locale** (Postgres + Redis + Celery).

**Sécurité** : les mots de passe Postgres et les clés `SUPERSET_SECRET_KEY` / `AIRFLOW_SECRET_KEY` du `.env.example` sont des **placeholders de développement**. Ne jamais les réutiliser tels quels sur un serveur exposé : définir des secrets forts et les injecter via l’environnement ou un gestionnaire de secrets.
