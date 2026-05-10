# Image Superset custom : ajoute psycopg2 (déjà inclus dans l'image officielle
# mais on s'assure de la présence) et nos assets de provisioning.
FROM apache/superset:4.1.1

USER root

# psycopg2-binary nécessaire pour la metastore Postgres et la datasource VoC.
RUN pip install --no-cache-dir psycopg2-binary==2.9.9

# Bootstrap script + assets pour l'init container.
COPY superset/bootstrap.sh /app/bootstrap.sh
COPY superset/assets /app/assets
RUN chmod +x /app/bootstrap.sh && chown -R superset:superset /app/bootstrap.sh /app/assets

USER superset
