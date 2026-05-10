# Grafana (provisioning)

Les fichiers sous `provisioning/` configurent Grafana au démarrage (datasource Postgres + dashboards).

**Sécurité** : le datasource [`datasources/voc.yml`](provisioning/datasources/voc.yml) utilise des identifiants **de démonstration locale uniquement** (`postgres` / `voc`). Ne pas réutiliser tels quels sur un environnement exposé : prévoir des secrets injectés (variables d’environnement, gestionnaire de secrets) et des mots de passe forts.
