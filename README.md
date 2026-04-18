# Abritel — Donnees & analyse (MVP Data / Produit)

Collecte d'avis depuis **3 sources** (Google Play, App Store, Trustpilot) pour Abritel sur une **fenetre glissante de 18 mois**, enrichissement lexical (categorie + gravite), export **CSV** pour **Power BI**. Le pipeline est **incremental** : chaque execution ne re-scrape que les avis recents et fusionne avec l'historique existant. L'analyse est dans **`2_analyse_complete.ipynb`**.

## Sources de donnees

| Source | Methode | Volume |
|--------|---------|--------|
| **Google Play** | API non officielle (`google-play-scraper`) — pagination complete | ~440 avis |
| **App Store iOS** | API RSS JSON officielle Apple — 10 pages de 50 avis | ~90 avis |
| **Trustpilot** | Extraction JSON `__NEXT_DATA__` — pagination par etoiles (5 x 10 pages) | ~200 avis |

## Mindset : rien sur le Mac, tout dans le projet

- **Une seule chose** installee au niveau machine (si besoin) : [**uv**](https://docs.astral.sh/uv/) — gestionnaire de Python + dependances + venv.
- Toutes les bibliotheques vivent dans **`.venv/`** a la racine du depot (ignore par git). Pas de `pip` global, pas de paquets dans le Python systeme.

### Installer uv (une fois)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Redemarrer le terminal ou `source` le fichier indique par l'installateur pour avoir la commande `uv`.

## Projet : Python + venv geres par uv

A la racine du depot :

```bash
# Optionnel : installer la version de Python indiquee dans .python-version (3.12)
uv python install

# Cree .venv/, resout les deps et installe tout dans le venv (reproductible via uv.lock)
uv sync
```

Ensuite, **toutes** les commandes passent par `uv run` (elles utilisent automatiquement `.venv/`) :

```bash
# Pipeline -> data/avis_enrichis.csv
uv run python 1_pipeline.py
```

### Notebook dans Cursor

Ouvre **`2_analyse_complete.ipynb`** dans Cursor, selectionne l'interpreteur **`.venv/bin/python`** (palette de commandes -> *Python: Select Interpreter*), puis execute les cellules ou *Run All*. Le paquet **`ipykernel`** dans le venv suffit pour que l'editeur pilote le notebook.

## Power BI

Importer **`data/avis_enrichis.csv`** (UTF-8-SIG). Mesures et definitions : voir le notebook, section *Indicateurs cles*. Apres execution du notebook : `data/synthese_categories.csv`, `data/crosstab_categorie_gravite.csv`.

## Fichiers utiles

| Fichier | Role |
|---------|------|
| `pyproject.toml` | Dependances (source de verite pour uv) |
| `uv.lock` | Versions figees (a committer pour l'equipe) |
| `.python-version` | Version Python cible pour `uv python install` |
| `1_pipeline.py` | Scraping 3 sources + categorisation -> CSV |
| `2_analyse_complete.ipynb` | Analyse complete |

## Colonnes du CSV

| Colonne | Description |
|---------|-------------|
| `date` | Date de publication de l'avis (UTC) |
| `note` | Note 1-5 |
| `texte` | Contenu textuel de l'avis |
| `source` | Origine : Google Play, App Store, Trustpilot |
| `Catégorie` | Localisation / Langue, Annulation / Réservation, Financier, Bug Technique, UX / Ergonomie, Service Client, Qualité du bien, Autre |
| `Catégorie_secondaire` | Deuxieme categorie si l'avis matche plusieurs themes (vide sinon) |
| `Gravité` | Haute, Moyenne, Basse |
