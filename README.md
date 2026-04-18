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

Toutes les colonnes sont **toujours presentes** dans le CSV (schema fixe pour Power BI) :

| Colonne | Description |
|---------|-------------|
| `date` | Date de publication de l’avis (UTC) |
| `note` | Note 1-5 |
| `texte` | Contenu textuel de l’avis |
| `source` | Origine : Google Play, App Store, Trustpilot |
| `longueur_texte` | Nombre de mots du texte |
| `n_caracteres` | Nombre de caracteres du texte |
| `Catégorie` | Categorie finale (= Ollama si disponible, sinon mots-cles) |
| `Catégorie_secondaire` | Deuxieme categorie si l’avis matche plusieurs themes (vide sinon) |
| `Catégorie_mots_cles` | Resultat de la categorisation par mots-cles (toujours present) |
| `Catégorie_ollama` | Resultat du LLM Ollama (vide si Ollama n’a pas tourne) |
| `Gravité` | Haute, Moyenne, Basse |
| `Gravité_texte` | Gravite evaluee uniquement sur le texte (independante de la note et de la categorie) |
| `Autre_type` | Pour les avis « Autre » : `positif court` / `positif thematique` / `negatif non categorise` / `neutre` (vide sinon) |
| `version_release` | Version de l’app active au moment de l’avis (croisee avec `data/releases.csv`) |

### Double categorisation : mots-cles + LLM

Le pipeline utilise **deux methodes complementaires** pour categoriser chaque avis :

1. **Mots-cles** (deterministe, rapide) : ~300 mots-cles FR/EN mappes aux 8 categories. Resultat dans `Catégorie_mots_cles`.
2. **LLM local** (Ollama gemma4:31b, temperature 0) : valide et corrige la categorie pour chaque avis. Resultat dans `Catégorie_ollama`.

La colonne `Catégorie` contient le **resultat final** : Ollama si disponible, mots-cles sinon. Cela permet de comparer les deux methodes et de mesurer le taux de reclassification.

**Configuration :**

```bash
ollama serve &
ollama pull gemma4:31b
ABRITEL_OLLAMA_TIMEOUT=300 uv run python 1_pipeline.py
```

- **Auto-detection** : si `ollama serve` tourne, il est utilise automatiquement
- **Cache incremental** : les avis deja valides ne repassent pas par Ollama
- **Jamais en CI** : les runners GitHub n’ont pas Ollama

| Variable | Defaut | Description |
|---|---|---|
| `ABRITEL_OLLAMA` | auto | `0` pour forcer la desactivation |
| `ABRITEL_OLLAMA_MODEL` | `gemma4:31b` | Modele Ollama |
| `ABRITEL_OLLAMA_MODE` | `all` | `all` = tous les avis, `autre` = seulement les « Autre » |
| `ABRITEL_OLLAMA_TIMEOUT` | `300` | Timeout par requete (secondes) |
