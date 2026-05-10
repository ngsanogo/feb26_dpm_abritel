"""Provisioning idempotent des assets Superset au démarrage.

Crée (ou met à jour) :
    - 1 datasource SQLAlchemy : "VoC Postgres" pointant vers la DB `voc`
    - 4 datasets : `marts.dm_sav_tickets`, `marts.dm_marketing_voc`,
      `marts.dm_finance_litiges`, `marts.dm_direction_synthese`

Pas de dashboard pré-créé — la création de charts/dashboards se fait dans l'UI
Superset à partir des datasets ainsi exposés.

Les imports des modèles Superset sont faits dans un contexte Flask actif —
sinon `current_app` lève RuntimeError au chargement des modules.
"""

from __future__ import annotations

import os
import sys

DATABASE_NAME = "VoC Postgres"

PG_USER = os.environ.get("VOC_PG_USER", "postgres")
PG_PASSWORD = os.environ.get("VOC_PG_PASSWORD", "postgres")
PG_HOST = os.environ.get("VOC_PG_HOST", "postgres")
PG_PORT = os.environ.get("VOC_PG_PORT", "5432")
PG_DBNAME = os.environ.get("VOC_PG_DBNAME", "voc")

SQLALCHEMY_URI = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DBNAME}"

DATASETS = [
    ("dm_sav_tickets", "Tickets SAV — backlog par catégorie / sévérité / délai"),
    ("dm_marketing_voc", "VoC Marketing — agrégats jour × marque × catégorie × persona"),
    ("dm_finance_litiges", "Finance — litiges paiement / transparence financière"),
    ("dm_direction_synthese", "Direction — KPIs exécutifs (volume, note, gap concurrents)"),
]
SCHEMA = "marts"


def main() -> int:
    # Imports faits dans le contexte Flask (l'image Superset met /app dans PYTHONPATH).
    from superset.app import create_app  # type: ignore

    app = create_app()
    with app.app_context():
        from superset import db  # type: ignore
        from superset.connectors.sqla.models import SqlaTable  # type: ignore
        from superset.models.core import Database  # type: ignore

        session = db.session

        # 1. Datasource VoC Postgres
        db_obj = session.query(Database).filter_by(database_name=DATABASE_NAME).first()
        if db_obj is None:
            print(f"  + créé datasource {DATABASE_NAME}")
            db_obj = Database(
                database_name=DATABASE_NAME,
                sqlalchemy_uri=SQLALCHEMY_URI,
                expose_in_sqllab=True,
                allow_run_async=True,
            )
            session.add(db_obj)
            session.commit()
        elif db_obj.sqlalchemy_uri != SQLALCHEMY_URI:
            print(f"  ~ mis à jour URI datasource {DATABASE_NAME}")
            db_obj.sqlalchemy_uri = SQLALCHEMY_URI
            session.commit()
        else:
            print(f"  = datasource {DATABASE_NAME} déjà OK")

        # 2. Datasets (un par mart). Les colonnes sont introspectées depuis Postgres
        # quand la table existe ; sinon on crée le dataset vide (sera resync au 1er run).
        for table_name, description in DATASETS:
            ds = (
                session.query(SqlaTable)
                .filter_by(database_id=db_obj.id, schema=SCHEMA, table_name=table_name)
                .first()
            )
            if ds is None:
                print(f"  + créé dataset {SCHEMA}.{table_name}")
                ds = SqlaTable(
                    table_name=table_name,
                    schema=SCHEMA,
                    database=db_obj,
                    description=description,
                )
                session.add(ds)
                session.commit()
            else:
                print(f"  = dataset {SCHEMA}.{table_name} déjà présent")
            try:
                ds.fetch_metadata()
                session.commit()
            except Exception as exc:  # noqa: BLE001
                # La table n'existe pas encore (DAG VoC pas tourné) → OK, on resyncera.
                print(f"    ! fetch_metadata pour {table_name}: {exc}")

    print("[provision] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
