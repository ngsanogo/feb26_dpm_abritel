# %% [markdown]
# # Analyse complète — Avis Abritel (3 sources)
#
# **Périmètre des données**
# - Sources : script `1_pipeline.py` — **Google Play** (package Android `com.vacationrentals.homeaway`), **App Store iOS** (API RSS Apple), **Trustpilot** (`abritel.fr`).
# - Période : **fenêtre glissante de 18 mois** jusqu'au jour du scraping (jour civil **Europe/Paris**), via pagination.
# - Notes **1 à 5** conservées, toutes sources confondues.
# - Enrichissement : colonnes **Catégorie**, **Catégorie_secondaire** et **Gravité** par **mots-clés** (règles dans `src/abritel/categorisation.py`) — ce n'est pas du machine learning ; l'ordre des règles fixe la catégorie retenue.
# - Précision de la catégorisation : **83,8 %** (annotation manuelle sur 99 avis, cf. `data/annotations_sample.csv`).
#
# **Fichier** : `data/avis_enrichis.csv` (UTF-8-SIG, une ligne = un avis).
# **Usage Power BI** : importer ce CSV, typer `date` en date/heure, `note` en entier, recréer les mêmes mesures que dans la section *Indicateurs clés* ci-dessous.
#
# **Reproductibilité** : exécuter les cellules **dans l'ordre** ; `RANDOM_STATE` et `ALPHA` sont fixés en tête du notebook (échantillons qualitatifs et seuils de significativité).
#
# ---

# %%
# Configuration : chemins, style des graphiques, affichage des tableaux
from __future__ import annotations

import re
from collections import Counter
from itertools import combinations, pairwise
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import scikit_posthocs as sp
import seaborn as sns
from IPython.display import display
from scipy.stats import chi2_contingency, kendalltau, kruskal, mannwhitneyu

from abritel.categorisation import normaliser_texte
from abritel.pipeline import valider_dataframe

# Paramètres d'affichage
plt.rcParams.update(
    {
        "figure.figsize": (10, 5),
        "figure.dpi": 120,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
    }
)
sns.set_theme(style="whitegrid", palette="deep")
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_colwidth", 120)
pd.set_option("display.float_format", lambda x: f"{x:,.4f}".rstrip("0").rstrip("."))

DATA_PATH = Path("data") / "avis_enrichis.csv"
RANDOM_STATE = 42
ALPHA = 0.05

COLONNES_ATTENDUES = [
    "date",
    "note",
    "texte",
    "source",
    "Catégorie",
    "Catégorie_secondaire",
    "Gravité",
]
ORDRE_GRAVITE = ["Haute", "Moyenne", "Basse"]
ORDRE_NOTES = [1, 2, 3, 4, 5]


def _chi2_pvalue_montecarlo(
    table: pd.DataFrame, *, n_sim: int = 20_000, seed: int = 42
) -> tuple[float, float, int, np.ndarray]:
    """χ² avec p-value Monte Carlo si l'approximation est fragile.

    On conserve les marges (totaux lignes/colonnes) et on simule sous H0 (indépendance).
    Retourne (chi2_obs, p_mc, dof, expected).
    """
    chi2_obs, p_asym, dof, expected = chi2_contingency(table)
    if (expected < 5).sum() == 0:
        return float(chi2_obs), float(p_asym), int(dof), expected

    rng = np.random.default_rng(seed)
    row_sums = table.sum(axis=1).to_numpy()
    col_sums = table.sum(axis=0).to_numpy()
    n = int(table.to_numpy().sum())
    p_cols = col_sums / n

    chi2_sim = np.empty(n_sim, dtype=float)
    for k in range(n_sim):
        sim = np.vstack([rng.multinomial(int(r), p_cols) for r in row_sums])
        chi2_sim[k] = chi2_contingency(sim, correction=False)[0]
    p_mc = float((chi2_sim >= chi2_obs).mean())
    return float(chi2_obs), p_mc, int(dof), expected


def _categorie_reporting(row: pd.Series) -> str:
    """Rend 'Autre' lisible quand c'est en réalité du positif (avis 4-5★ très courts)."""
    cat = str(row.get("Catégorie", "Autre"))
    note = row.get("note")
    if cat == "Autre" and pd.notna(note) and int(note) >= 4:
        return "Satisfaction (hors irritants)"
    return cat


def _gravite_texte_only(texte: str) -> str:
    """Alternative non tautologique : gravité uniquement via mots-clés forts (sans la note)."""
    if not isinstance(texte, str) or not texte.strip():
        return "Basse"
    t = normaliser_texte(texte)
    mots_forts = (
        "arnaque",
        "honte",
        "honteux",
        "plainte",
        "escroc",
        "tribunal",
        "justice",
        "avocat",
        "illegal",
        "scandale",
        "escroquerie",
        "fraude",
        "voleur",
        "vol",
    )
    return "Haute" if any(m in t for m in mots_forts) else "Basse"


# %% [markdown]
# ## 1. Chargement et schéma
#
# On charge le CSV en **UTF-8-SIG** et on parse la colonne `date`. Si le fichier est absent, exécuter d’abord : `uv run python 1_pipeline.py`.
#

# %%
if not DATA_PATH.is_file():
    raise FileNotFoundError(
        f"Fichier introuvable : {DATA_PATH.resolve()}\n"
        "Lance le pipeline depuis la racine du projet : uv run python 1_pipeline.py"
    )

df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
df["date"] = pd.to_datetime(df["date"], errors="coerce")

manquantes = [c for c in COLONNES_ATTENDUES if c not in df.columns]
if manquantes:
    raise ValueError(f"Colonnes manquantes : {manquantes}. Colonnes lues : {list(df.columns)}")

# Typage explicite (utile pour recoder pareil dans Power BI)
df["note"] = pd.to_numeric(df["note"], errors="coerce").astype("Int64")
df["texte"] = df["texte"].astype(str)
df["Catégorie_secondaire"] = df["Catégorie_secondaire"].fillna("").astype(str)

# Colonne "Catégorie_reporting" : identique à Catégorie sauf "Autre" très positif
df["Catégorie_reporting"] = df.apply(_categorie_reporting, axis=1)

# Variante de gravité non tautologique (sans la note)
df["Gravité_texte"] = df["texte"].map(_gravite_texte_only)

print("Dimensions :", df.shape[0], "lignes ×", df.shape[1], "colonnes")
print("Période couverte :", df["date"].min(), "→", df["date"].max())
df.dtypes.to_frame("dtype")

# %%
df.head(8)

# %% [markdown]
# ## 2. Contrôle qualité
#
# Vérifications pour des indicateurs fiables : **doublons** (même définition que le pipeline `drop_duplicates`), **doublons cross-source** (même texte/note/date sur plusieurs sources), valeurs manquantes, notes, et **`valider_dataframe`** du package (`abritel.pipeline`) pour aligner les contrôles sur l’export CSV.

# %%
# Doublons au sens pipeline (fusion incrémentale) : source + date + note + texte
dup_pipeline = df.duplicated(subset=["source", "date", "note", "texte"], keep=False)
n_dup_pipeline = int(dup_pipeline.sum())
print(f"Doublons pipeline (source+date+note+texte) — lignes concernées : {n_dup_pipeline}")

# Même contenu sur plusieurs sources (informationnel)
dup_cross = df.duplicated(subset=["date", "note", "texte"], keep=False)
n_dup_cross = int(dup_cross.sum())
print(f"Doublons date+note+texte (y compris cross-source) — lignes concernées : {n_dup_cross}")

# Valeurs manquantes par colonne
na_pct = (df.isna().mean() * 100).round(2)
print("\n% de valeurs manquantes par colonne :")
print(na_pct.to_string())

# Dates non parsées
n_bad_dates = int(df["date"].isna().sum())
if n_bad_dates:
    print(f"\nAttention : {n_bad_dates} date(s) non converties.")

# Notes hors périmètre 1–5 (anomalie)
notes_invalides = df[~df["note"].isin([1, 2, 3, 4, 5]) & df["note"].notna()]
print(f"\nLignes avec note ≠ 1,2,3,4,5 (hors NA) : {len(notes_invalides)}")
if len(notes_invalides) > 0:
    display(notes_invalides[["date", "note", "texte"]].head())

# Colonnes Catégorie / Gravité : pas de NaN pour l'analyse des effectifs
for col in ["Catégorie", "Gravité"]:
    n = df[col].isna().sum()
    print(f"NaN dans {col!r} : {int(n)}")

# Validation alignée sur l'export du pipeline
anomalies = valider_dataframe(df)
if anomalies:
    print("\nAnomalies valider_dataframe :")
    for a in anomalies:
        print(f"  — {a}")
else:
    print("\nvalider_dataframe : aucune anomalie.")

# Calibrage optionnel vs échantillon annoté (mêmes règles que le pipeline actuel)
ann_path = Path("data") / "annotations_sample.csv"
if ann_path.is_file():
    from abritel.categorisation import categoriser_avis

    ann = pd.read_csv(ann_path, encoding="utf-8")

    def _gold_label(row: pd.Series) -> str:
        cc = row.get("categorie_correcte")
        if pd.notna(cc) and str(cc).strip():
            return str(cc).strip()
        return str(row["categorie_auto"]).strip()

    ann["gold"] = ann.apply(_gold_label, axis=1)
    ann["pred"] = ann["texte_extrait"].astype(str).map(categoriser_avis)
    ok = ann["gold"] == ann["pred"]
    acc = float(ok.mean()) if len(ann) else float("nan")
    print(
        f"\nCalibrage ({ann_path.name}, n={len(ann)}) — précision règles actuelles vs gold : {acc:.1%}"
    )
    display(pd.crosstab(ann["gold"], ann["pred"], margins=True))
else:
    print(f"\nPas de fichier {ann_path.as_posix()} — saut du calibrage annoté.")

# %% [markdown]
# ## 3. Indicateurs clés (KPIs) — à reproduire dans Power BI
#
# **Définitions** (dénominateur = nombre d’avis dans le fichier, sauf mention contraire) :
#
# | Mesure | Définition |
# |--------|------------|
# | N avis | `COUNTROWS` |
# | Note moyenne | moyenne arithmétique de `note` (échelle 1–5) |
# | % gravité Haute | part des lignes où `Gravité` = "Haute" |
# | Catégorie dominante | modus de `Catégorie` |
# | Période | `MIN(date)` et `MAX(date)` |
#

# %%
N = len(df)
if N == 0:
    raise ValueError("Aucun avis : impossible de calculer les KPIs.")

note_moyenne = df["note"].mean()
note_mediane = df["note"].median()
pct_haute = 100.0 * (df["Gravité"] == "Haute").sum() / N
pct_moyenne = 100.0 * (df["Gravité"] == "Moyenne").sum() / N
pct_basse = 100.0 * (df["Gravité"] == "Basse").sum() / N

cat_counts = df["Catégorie"].value_counts()
categorie_mode = cat_counts.index[0]
freq_mode = int(cat_counts.iloc[0])
pct_mode = 100.0 * freq_mode / N

kpi = pd.DataFrame(
    [
        {"Indicateur": "Nombre d'avis (n)", "Valeur": N},
        {"Indicateur": "Date minimale", "Valeur": str(df["date"].min())},
        {"Indicateur": "Date maximale", "Valeur": str(df["date"].max())},
        {"Indicateur": "Note moyenne (1–5)", "Valeur": round(float(note_moyenne), 3)},
        {"Indicateur": "Note médiane", "Valeur": float(note_mediane)},
        {"Indicateur": "% gravité Haute", "Valeur": round(pct_haute, 2)},
        {"Indicateur": "% gravité Moyenne", "Valeur": round(pct_moyenne, 2)},
        {"Indicateur": "% gravité Basse", "Valeur": round(pct_basse, 2)},
        {"Indicateur": "Catégorie la plus fréquente", "Valeur": categorie_mode},
        {"Indicateur": "Effectif de cette catégorie", "Valeur": freq_mode},
        {"Indicateur": "% de l'ensemble (catégorie dominante)", "Valeur": round(pct_mode, 2)},
    ]
)
display(kpi)

# %% [markdown]
# ## 4. Distributions univariées
#
# Histogrammes / barres : **notes**, **catégories**, **gravité**, **source**.
#

# %%
fig, axes = plt.subplots(2, 2, figsize=(11, 9))

# Notes (échelle 1 à 5)
note_counts = df["note"].value_counts().reindex(ORDRE_NOTES, fill_value=0)
axes[0, 0].bar(
    note_counts.index.astype(str), note_counts.values, color="steelblue", edgecolor="black"
)
axes[0, 0].set_title("Répartition des notes (1 à 5)")
axes[0, 0].set_xlabel("Note")
axes[0, 0].set_ylabel("Nombre d'avis")

# Catégories (tri par effectif décroissant)
cat_counts = df["Catégorie"].value_counts()
axes[0, 1].barh(cat_counts.index[::-1], cat_counts.values[::-1], color="coral", edgecolor="black")
axes[0, 1].set_title("Volume par catégorie")
axes[0, 1].set_xlabel("Nombre d'avis")

# Gravité (ordre métier fixe : Haute → Moyenne → Basse)
g_full = df["Gravité"].value_counts().reindex(ORDRE_GRAVITE, fill_value=0)
axes[1, 0].bar(g_full.index, g_full.values, color="seagreen", edgecolor="black")
axes[1, 0].set_title("Répartition par gravité")
axes[1, 0].set_ylabel("Nombre d'avis")
axes[1, 0].tick_params(axis="x", rotation=25)

# Source
src_counts = df["source"].value_counts()
axes[1, 1].bar(
    src_counts.index.astype(str), src_counts.values, color="mediumpurple", edgecolor="black"
)
axes[1, 1].set_title("Volume par source")
axes[1, 1].set_ylabel("Nombre d'avis")
axes[1, 1].tick_params(axis="x", rotation=20)

plt.tight_layout()
plt.show()

# Table des fréquences (pour copier vers Excel / Power BI)
freq_table = pd.DataFrame(
    {
        "Catégorie": cat_counts.index,
        "Effectif": cat_counts.values,
        "% du total": (100 * cat_counts.values / N).round(2),
    }
)
display(freq_table)

# Vue "reporting" : évite que "Autre" soit interprété comme une plainte
cat_rep_counts = df["Catégorie_reporting"].value_counts()
freq_reporting = pd.DataFrame(
    {
        "Catégorie_reporting": cat_rep_counts.index,
        "Effectif": cat_rep_counts.values,
        "% du total": (100 * cat_rep_counts.values / N).round(2),
    }
)
print("\nVue reporting (Autre positif → Satisfaction) :")
display(freq_reporting)

# %% [markdown]
# ## 5. Analyse temporelle
#
# Agrégation par **mois calendaire** (année-mois). Attention : les avis reflètent la date côté store, pas la date de scraping.
#

# %%
df_time = df.dropna(subset=["date"]).copy()
df_time["annee_mois"] = df_time["date"].dt.to_period("M").astype(str)

par_mois = df_time.groupby("annee_mois", as_index=False).size()
par_mois = par_mois.rename(columns={"size": "nb_avis"})

fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(par_mois["annee_mois"], par_mois["nb_avis"], marker="o", linewidth=2, markersize=6)
y0 = int(df_time["date"].dt.year.min())
y1 = int(df_time["date"].dt.year.max())
ax.set_title(f"Nombre d'avis par mois ({y0} → {y1})")
ax.set_xlabel("Mois")
ax.set_ylabel("Nombre d'avis")
ax.tick_params(axis="x", rotation=45)
plt.tight_layout()
plt.show()

display(par_mois)

# %% [markdown]
# ## 6. Tableau croisé Catégorie × Gravité
#
# - **Effectifs** : combinaisons observées.
# - **% par ligne** : répartition de la gravité *au sein* de chaque catégorie (utile pour prioriser).
# - **% du total** : contribution de chaque cellule à l'ensemble.
#

# %%
ct = pd.crosstab(df["Catégorie"], df["Gravité"], margins=True, margins_name="Total")
display(ct)

# %%
# % par ligne (sans la ligne Total pour le calcul)
ct_body = pd.crosstab(df["Catégorie"], df["Gravité"])
pct_ligne = ct_body.div(ct_body.sum(axis=1), axis=0) * 100
pct_ligne = pct_ligne.round(2)
pct_ligne["Total ligne (100%)"] = pct_ligne.sum(axis=1).round(2)
print("% de chaque gravité DANS chaque catégorie (ligne = 100%) :")
display(pct_ligne)

# Heatmap des effectifs
plt.figure(figsize=(8, 5))
sns.heatmap(ct_body, annot=True, fmt="d", cmap="Blues", linewidths=0.5)
plt.title("Effectifs : Catégorie × Gravité")
plt.ylabel("Catégorie")
plt.xlabel("Gravité")
plt.tight_layout()
plt.show()

# %% [markdown]
# ## 7. Note selon la catégorie
#
# Boîtes à moustaches : distribution des **notes (1–5)** par catégorie (les médianes aident à comparer l’intensité du score, pas seulement le volume).
#

# %%
ordre_cat = df["Catégorie"].value_counts().index.tolist()
plt.figure(figsize=(10, 5))
sns.boxplot(data=df, x="Catégorie", y="note", order=ordre_cat, palette="Set2")
plt.title("Distribution des notes (1–5) par catégorie")
plt.xlabel("Catégorie")
plt.ylabel("Note")
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
plt.show()

df.groupby("Catégorie", observed=True)["note"].agg(["count", "mean", "median", "std"]).round(3)

# %% [markdown]
# ## 8. Longueur des commentaires (proxy d’effort / détail)
#
# Nombre de caractères (et de mots) par avis : utile pour détecter des avis « courts » vs « argumentés ». Corrélation de **Spearman** entre longueur et note (ordinales) — interprétation prudente.
# **Ordre d’exécution** : la section 15 réutilise `n_caracteres` ; en cas d’exécution isolée, cette colonne y est recréée si besoin.
#

# %%
df["n_caracteres"] = df["texte"].str.len()
df["n_mots"] = df["texte"].str.split().str.len()

fig, axes = plt.subplots(1, 2, figsize=(11, 4))
sns.histplot(df["n_caracteres"], bins=20, kde=True, ax=axes[0], color="teal")
axes[0].set_title("Distribution — longueur (caractères)")
sns.histplot(df["n_mots"], bins=20, kde=True, ax=axes[1], color="orange")
axes[1].set_title("Distribution — nombre de mots")
plt.tight_layout()
plt.show()

# Spearman : monotone entre longueur et note
rho = df[["n_caracteres", "note"]].corr(method="spearman").iloc[0, 1]
print(f"Corrélation de Spearman (caractères vs note) : {rho:.4f}")

df.groupby("Catégorie", observed=True)[["n_caracteres", "n_mots"]].median().round(1)

# %% [markdown]
# ## 9. Courbe de Pareto (catégories)
#
# Les **k** premières catégories cumulent quelle part du volume ? Aide à trancher « vital few » en revue produit.
#

# %%
cat_sorted = df["Catégorie"].value_counts().sort_values(ascending=False)
cum_pct = (100 * cat_sorted.cumsum() / N).round(2)

pareto = pd.DataFrame(
    {"Catégorie": cat_sorted.index, "Effectif": cat_sorted.values, "% cumulé": cum_pct.values}
)

fig, ax1 = plt.subplots(figsize=(10, 5))
x = np.arange(len(cat_sorted))
ax1.bar(x, cat_sorted.values, color="steelblue", edgecolor="black", label="Effectif")
ax1.set_xticks(x)
ax1.set_xticklabels(cat_sorted.index, rotation=25, ha="right")
ax1.set_ylabel("Nombre d'avis")
ax1.set_title("Pareto — catégories (barres) et % cumulé (ligne)")

ax2 = ax1.twinx()
ax2.plot(x, cum_pct.values, color="red", marker="o", linewidth=2, label="% cumulé")
ax2.set_ylabel("% cumulé")
ax2.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100))
ax2.axhline(80, color="gray", linestyle="--", alpha=0.7, label="80 %")
fig.tight_layout()
plt.show()

display(pareto)

# %% [markdown]
# ## 10. Catégorie secondaire (multi-thèmes)
#
# Le pipeline peut attacher une **deuxième** catégorie quand plusieurs thèmes matchent (`Catégorie_secondaire`, sinon chaîne vide). Part des avis concernés, **paires** les plus fréquentes, et heatmap des co-occurrences (top des secondaires par nombre d’avis).

# %%
has_sec = df["Catégorie_secondaire"].str.strip() != ""
n_multi = int(has_sec.sum())
pct_multi = 100.0 * n_multi / len(df) if len(df) else 0.0
print(f"Avis avec Catégorie_secondaire renseignée : {n_multi} ({pct_multi:.2f} % du total)")

pairs = (
    df.loc[has_sec, ["Catégorie", "Catégorie_secondaire"]]
    .value_counts()
    .reset_index(name="effectif")
    .sort_values("effectif", ascending=False)
)
print("\nTop 15 paires (primaire → secondaire) :")
display(pairs.head(15))

if n_multi > 0:
    top_sec = pairs["Catégorie_secondaire"].head(12).tolist()
    sub = df[has_sec & df["Catégorie_secondaire"].isin(top_sec)]
    pair_matrix = pd.crosstab(sub["Catégorie"], sub["Catégorie_secondaire"])
    plt.figure(figsize=(10, 5))
    sns.heatmap(pair_matrix, annot=True, fmt="d", cmap="Purples", linewidths=0.5)
    plt.title("Co-occurrences — top secondaires par volume")
    plt.ylabel("Catégorie")
    plt.xlabel("Catégorie_secondaire")
    plt.tight_layout()
    plt.show()
else:
    print("(Aucune paire à afficher en heatmap.)")

# %% [markdown]
# ## 11. Comparaison inter-sources
#
# Les trois sources (Google Play, App Store, Trustpilot) attirent-elles le même profil de plainte ? Test de **Kruskal-Wallis** (non paramétrique, données ordinales) pour comparer les distributions de notes entre sources.

# %%
# Kruskal-Wallis : notes par source
groups = [g["note"].dropna().values for _, g in df.groupby("source")]
stat, p = kruskal(*groups)
print(f"Kruskal-Wallis H = {stat:.3f}, p = {p:.4f}")
print(
    "→",
    f"Distributions significativement différentes (p < {ALPHA})"
    if p < ALPHA
    else "Pas de différence significative",
)
print()

sources_kw = sorted(df["source"].dropna().unique())
if p < ALPHA and len(sources_kw) >= 2:
    pair_rows = []
    for a, b in combinations(sources_kw, 2):
        xa = df.loc[df["source"] == a, "note"].dropna().astype(int)
        xb = df.loc[df["source"] == b, "note"].dropna().astype(int)
        if len(xa) == 0 or len(xb) == 0:
            continue
        _, p_ab = mannwhitneyu(xa, xb, alternative="two-sided")
        pair_rows.append({"source_a": a, "source_b": b, "p_MannWhitney": p_ab})
    if pair_rows:
        pw = pd.DataFrame(pair_rows)
        m = len(pw)
        pw["p_Bonferroni"] = (pw["p_MannWhitney"] * m).clip(upper=1.0)
        pw["significatif"] = pw["p_Bonferroni"] < ALPHA
        print(
            "Comparaisons par paires (Mann-Whitney, Bonferroni) — interpréter avec prudence sur notes ordinales :"
        )
        display(pw)
print()

# KPIs par source
src_stats = df.groupby("source")["note"].agg(["count", "mean", "median", "std"]).round(3)
src_stats.columns = ["N avis", "Moyenne", "Médiane", "Écart-type"]
display(src_stats)

# Distribution des notes par source
fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
for ax, (source, grp) in zip(axes, df.groupby("source"), strict=False):
    counts = grp["note"].value_counts().reindex(ORDRE_NOTES, fill_value=0)
    ax.bar(counts.index.astype(str), counts.values, color="steelblue", edgecolor="black")
    ax.set_title(f"{source} (n={len(grp)})")
    ax.set_xlabel("Note")
axes[0].set_ylabel("Nombre d'avis")
plt.suptitle("Répartition des notes par source", fontsize=13, y=1.02)
plt.tight_layout()
plt.show()

# Catégories par source (heatmap)
ct_src = pd.crosstab(df["Catégorie"], df["source"])
plt.figure(figsize=(8, 5))
sns.heatmap(ct_src, annot=True, fmt="d", cmap="YlOrRd", linewidths=0.5)
plt.title("Effectifs : Catégorie × Source")
plt.ylabel("Catégorie")
plt.xlabel("Source")
plt.tight_layout()
plt.show()

# χ² d'indépendance Catégorie × Source + résidus
chi2_cs, p_cs, dof_cs, exp_cs = _chi2_pvalue_montecarlo(ct_src)
print(f"Catégorie × Source — Chi² = {chi2_cs:.2f}, ddl = {dof_cs}, p = {p_cs:.4f}")
print(
    "→",
    f"Dépendance significative (p < {ALPHA})"
    if p_cs < ALPHA
    else "Pas de dépendance significative",
)
n_cs = int(ct_src.values.sum())
r_cs, c_cs = ct_src.shape
v_cs = np.sqrt(chi2_cs / (n_cs * min(r_cs - 1, c_cs - 1))) if n_cs > 0 else float("nan")
print(f"Cramér V = {v_cs:.3f}")
low_cs = int((exp_cs < 5).sum())
if low_cs:
    print(
        f"Note : {low_cs} cellule(s) attendues < 5 → p-value estimée par Monte Carlo (marges fixées)."
    )
res_cs = (ct_src.values - exp_cs) / np.sqrt(exp_cs)
res_cs_df = pd.DataFrame(res_cs, index=ct_src.index, columns=ct_src.columns)
plt.figure(figsize=(8, 5))
sns.heatmap(res_cs_df, annot=True, fmt=".2f", cmap="RdBu_r", center=0, linewidths=0.5)
plt.title("Résidus de Pearson : Catégorie × Source")
plt.ylabel("Catégorie")
plt.xlabel("Source")
plt.tight_layout()
plt.show()

# %%
# Test de Dunn — post-hoc canonique pour Kruskal-Wallis.
# Contrairement à Mann-Whitney par paires, Dunn utilise les rangs du test global
# et corrige directement pour les comparaisons multiples (Bonferroni).
if p < ALPHA:
    dunn_df = sp.posthoc_dunn(
        df.dropna(subset=["note", "source"]),
        val_col="note",
        group_col="source",
        p_adjust="bonferroni",
    )
    print("Test de Dunn (post-hoc Kruskal-Wallis, correction Bonferroni) :")
    print("p-values ajustées :")
    display(dunn_df.round(4))

    plt.figure(figsize=(5, 4))
    sns.heatmap(
        dunn_df,
        annot=True,
        fmt=".4f",
        cmap="RdYlGn_r",
        vmin=0,
        vmax=0.1,
        linewidths=0.5,
    )
    plt.title(f"Dunn post-hoc — p-values (seuil α = {ALPHA})")
    plt.tight_layout()
    plt.show()
else:
    print("Kruskal-Wallis non significatif — pas de post-hoc.")

# %% [markdown]
# ## 12. Analyse textuelle (fréquences de mots)
#
# Mots les plus fréquents (stopwords **français + anglais** et termes peu informatifs), comparaison **1★ vs 5★**, **mots distinctifs par catégorie** (score de **lift** : sur-représentation vs le corpus global), et **bigrammes** fréquents.

# %%
_STOPWORDS_FR = {
    "de",
    "la",
    "le",
    "les",
    "des",
    "du",
    "un",
    "une",
    "et",
    "en",
    "est",
    "que",
    "qui",
    "dans",
    "pour",
    "pas",
    "plus",
    "par",
    "sur",
    "au",
    "aux",
    "ce",
    "se",
    "son",
    "sa",
    "ses",
    "mon",
    "ma",
    "mes",
    "nous",
    "vous",
    "ils",
    "je",
    "on",
    "ne",
    "avec",
    "très",
    "tout",
    "été",
    "mais",
    "ou",
    "si",
    "il",
    "elle",
    "a",
    "ai",
    "y",
    "à",
    "d",
    "l",
    "n",
    "s",
    "qu",
    "c",
    "j",
    "m",
    "t",
    "bien",
    "fait",
    "sans",
    "cette",
    "sont",
    "ont",
    "être",
    "avoir",
    "même",
    "peut",
    "entre",
    "aussi",
    "tous",
    "après",
    "avant",
    "ça",
    "nos",
    "leur",
    "comme",
    "car",
    "donc",
    "ni",
    "dont",
    "quand",
    "peu",
    "où",
    "fois",
    "commentaire",
    "abritel",
}

_STOPWORDS_EN = {
    "the",
    "and",
    "for",
    "not",
    "you",
    "are",
    "was",
    "has",
    "have",
    "had",
    "this",
    "that",
    "with",
    "from",
    "your",
    "they",
    "been",
    "their",
    "but",
    "its",
    "our",
    "all",
    "can",
    "will",
    "just",
    "also",
    "yes",
    "one",
    "use",
    "get",
    "out",
    "now",
    "any",
    "why",
    "too",
    "very",
    "more",
    "when",
    "what",
    "who",
    "how",
    "than",
    "then",
    "here",
    "only",
    "some",
    "into",
    "over",
    "such",
    "about",
}
_STOPWORDS = _STOPWORDS_FR | _STOPWORDS_EN | {"app", "application", "review", "updated", "update"}


def _tokenize(text: str) -> list[str]:
    return [
        w
        for w in re.findall(r"[a-zàâäéèêëïîôùûüçœæ]+", text.lower())
        if len(w) > 2 and w not in _STOPWORDS
    ]


# Top 25 mots globaux
all_words = Counter()
for t in df["texte"]:
    all_words.update(_tokenize(t))

top25 = all_words.most_common(25)
mots, freqs = list(zip(*top25, strict=True))

plt.figure(figsize=(10, 5))
plt.barh(list(reversed(mots)), list(reversed(freqs)), color="teal", edgecolor="black")
plt.title("Top 25 mots les plus fréquents (hors stopwords)")
plt.xlabel("Occurrences")
plt.tight_layout()
plt.show()


# Comparaison 1★ vs 5★
def _top_words(mask, n=15):
    c = Counter()
    for t in df.loc[mask, "texte"]:
        c.update(_tokenize(t))
    return c.most_common(n)


fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for ax, note_val, color in [(axes[0], 1, "tomato"), (axes[1], 5, "seagreen")]:
    tw = _top_words(df["note"] == note_val, 15)
    if tw:
        m, f = list(zip(*tw, strict=True))
        ax.barh(list(reversed(m)), list(reversed(f)), color=color, edgecolor="black")
    ax.set_title(f"Top 15 mots — avis {note_val}★")
    ax.set_xlabel("Occurrences")
plt.suptitle("Vocabulaire : 1★ (négatif) vs 5★ (positif)", fontsize=13, y=1.02)
plt.tight_layout()
plt.show()

# Mots distinctifs par catégorie (lift = P(w|cat) / P(w))
total_tokens_global = sum(all_words.values()) or 1
p_w_global = {w: c / total_tokens_global for w, c in all_words.items() if c >= 10}

dist_rows: list[dict[str, object]] = []
MIN_CAT_TOKENS = 30
MIN_W_CAT = 5
for cat in df["Catégorie"].dropna().unique():
    subset = df.loc[df["Catégorie"] == cat, "texte"]
    if len(subset) == 0:
        continue
    cat_ctr: Counter[str] = Counter()
    for t in subset:
        cat_ctr.update(_tokenize(t))
    n_cat = sum(cat_ctr.values())
    if n_cat < MIN_CAT_TOKENS:
        continue
    for w, c in cat_ctr.items():
        if c < MIN_W_CAT:
            continue
        pg = p_w_global.get(w)
        if pg is None or pg <= 0:
            continue
        lift = (c / n_cat) / pg
        dist_rows.append({"Catégorie": cat, "mot": w, "lift": lift, "count": c})

if dist_rows:
    dist_df = pd.DataFrame(dist_rows).sort_values(["Catégorie", "lift"], ascending=[True, False])
    print("Mots sur-représentés par catégorie (lift, min. 10 occ. globales, 5 dans la catégorie) :")
    display(dist_df.groupby("Catégorie", sort=False).head(8).reset_index(drop=True))
else:
    print("(Pas assez de données pour le lift par catégorie.)")

# Bigrammes globaux (sur tokens déjà filtrés)
bg: Counter[tuple[str, str]] = Counter()
for t in df["texte"]:
    tok = _tokenize(t)
    if len(tok) >= 2:
        bg.update(pairwise(tok))

top_big = bg.most_common(20)
if top_big:
    labels = [f"{a} {b}" for (a, b), _ in top_big]
    vals = [n for _, n in top_big]
    plt.figure(figsize=(10, 5))
    plt.barh(list(reversed(labels)), list(reversed(vals)), color="slategray", edgecolor="black")
    plt.title("Top 20 bigrammes")
    plt.xlabel("Occurrences")
    plt.tight_layout()
    plt.show()

# %% [markdown]
# ## 13. Test d'indépendance Catégorie × Gravité (χ²)
#
# Un test du **chi-deux** vérifie si la gravité dépend de la catégorie (H₀ : indépendance). La heatmap des **résidus de Pearson** montre quelles cellules contribuent le plus à l'écart avec l'hypothèse d'indépendance.

# %%
ct_test = pd.crosstab(df["Catégorie"], df["Gravité"])
print(
    "Attention méthodologique : 'Gravité' est calculée à partir de (note + catégorie + mots-clés). "
    "Tester Catégorie × Gravité au χ² est donc en partie tautologique. "
    "On conserve la table et les résidus à des fins descriptives, sans sur-interpréter la p-value."
)
chi2, p, dof, expected = _chi2_pvalue_montecarlo(ct_test)
print(f"(Descriptif) Chi² = {chi2:.2f},  ddl = {dof},  p = {p:.4f}")
n_ct = int(ct_test.values.sum())
r_ct, c_ct = ct_test.shape
cramer_v = np.sqrt(chi2 / (n_ct * min(r_ct - 1, c_ct - 1))) if n_ct > 0 else float("nan")
print(f"Cramér V (taille d'effet) = {cramer_v:.3f}")
low_exp = int((expected < 5).sum())
if low_exp:
    print(
        f"Note : {low_exp} cellule(s) attendues < 5 → p-value estimée par Monte Carlo (marges fixées)."
    )

# Résidus de Pearson : (observé - attendu) / √attendu
residuals = (ct_test.values - expected) / np.sqrt(expected)
res_df = pd.DataFrame(residuals, index=ct_test.index, columns=ct_test.columns)

plt.figure(figsize=(8, 5))
sns.heatmap(res_df, annot=True, fmt=".2f", cmap="RdBu_r", center=0, linewidths=0.5)
plt.title("Résidus de Pearson : Catégorie × Gravité\n(> 2 ou < -2 = contribution forte)")
plt.ylabel("Catégorie")
plt.xlabel("Gravité")
plt.tight_layout()
plt.show()

# %%
# Résidus standardisés ajustés (ASR) — plus rigoureux que les résidus de Pearson.
# Un |ASR| > 1.96 indique une déviation significative à α = 0.05 (test z bilatéral).
# Contrairement aux résidus de Pearson, les ASR tiennent compte des marges de la table.

row_totals = ct_test.sum(axis=1).values
col_totals = ct_test.sum(axis=0).values
n_total = ct_test.values.sum()

asr = np.zeros_like(ct_test.values, dtype=float)
for i in range(ct_test.shape[0]):
    for j in range(ct_test.shape[1]):
        e_ij = expected[i, j]
        denom = np.sqrt(e_ij * (1 - row_totals[i] / n_total) * (1 - col_totals[j] / n_total))
        asr[i, j] = (ct_test.values[i, j] - e_ij) / denom if denom > 0 else 0.0

asr_df = pd.DataFrame(asr, index=ct_test.index, columns=ct_test.columns)

plt.figure(figsize=(8, 5))
sns.heatmap(
    asr_df,
    annot=True,
    fmt=".2f",
    cmap="RdBu_r",
    center=0,
    linewidths=0.5,
    vmin=-5,
    vmax=5,
)
plt.title(
    "Résidus standardisés ajustés (ASR) : Catégorie × Gravité\n(|ASR| > 1.96 = significatif à 5%)"
)
plt.ylabel("Catégorie")
plt.xlabel("Gravité")
plt.tight_layout()
plt.show()

# Résumé des associations significatives
print("Associations significatives (|ASR| > 1.96) :")
for cat in asr_df.index:
    for grav in asr_df.columns:
        val = asr_df.loc[cat, grav]
        if abs(val) > 1.96:
            direction = "sur-représenté" if val > 0 else "sous-représenté"
            print(f"  {cat} × {grav} : ASR = {val:+.2f} ({direction})")

# Variante non tautologique : Catégorie × Gravité_texte (mots-clés forts uniquement)
ct_text = pd.crosstab(df["Catégorie"], df["Gravité_texte"])
chi2_t, p_t, dof_t, exp_t = _chi2_pvalue_montecarlo(ct_text)
print("\nVariante non tautologique (Gravité_texte via mots-clés forts uniquement) :")
print(f"Chi² = {chi2_t:.2f}, ddl = {dof_t}, p = {p_t:.4f}")
low_t = int((exp_t < 5).sum())
if low_t:
    print(f"Note : {low_t} cellule(s) attendues < 5 → p-value Monte Carlo.")

# %% [markdown]
# ## 14. Tendance temporelle et test de tendance
#
# - **Moyenne mobile 30 jours** de la note : la satisfaction évolue-t-elle ?
# - **Volume mensuel par gravité** (aire empilée).
# - **Test de Kendall τ** : tendance monotone significative de la note moyenne mensuelle ?

# %%
# Moyenne mobile 30 jours
df_sorted = df.dropna(subset=["date", "note"]).sort_values("date").copy()
df_sorted = df_sorted.set_index("date")
rolling_mean = df_sorted["note"].rolling("30D", min_periods=5).mean()

fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(rolling_mean.index, rolling_mean.values, color="steelblue", linewidth=2)
ax.axhline(
    df["note"].mean(),
    color="gray",
    linestyle="--",
    alpha=0.6,
    label=f"Moyenne globale ({df['note'].mean():.2f})",
)
ax.set_title("Moyenne mobile 30 jours — Note")
ax.set_ylabel("Note moyenne")
ax.set_xlabel("Date")
ax.legend()
plt.tight_layout()
plt.show()

# Volume mensuel par gravité (aire empilée)
df_time2 = df.dropna(subset=["date"]).copy()
df_time2["mois"] = df_time2["date"].dt.to_period("M").astype(str)
pivot_grav = df_time2.groupby(["mois", "Gravité"]).size().unstack(fill_value=0)
pivot_grav = pivot_grav.reindex(columns=ORDRE_GRAVITE, fill_value=0)

fig, ax = plt.subplots(figsize=(11, 4))
pivot_grav.plot.area(ax=ax, color=["tomato", "orange", "seagreen"], alpha=0.8)
ax.set_title("Volume mensuel par gravité")
ax.set_ylabel("Nombre d'avis")
ax.set_xlabel("Mois")
ax.tick_params(axis="x", rotation=45)
ax.legend(title="Gravité")
plt.tight_layout()
plt.show()

# Test de tendance : Kendall τ sur note moyenne mensuelle
monthly_mean = df_time2.groupby("mois")["note"].mean()
tau, p_tau = kendalltau(range(len(monthly_mean)), monthly_mean.values)
print(f"Kendall τ = {tau:.4f},  p = {p_tau:.4f}")
if p_tau < ALPHA:
    direction = "hausse" if tau > 0 else "baisse"
    print(f"→ Tendance significative à la {direction}")
else:
    print("→ Pas de tendance monotone significative")

# %% [markdown]
# ## 15. Deep dive : 1★ vs 5★
#
# Comparaison des catégories, de la longueur de texte et échantillons qualitatifs entre les extrêmes.

# %%
if "n_caracteres" not in df.columns:
    df["n_caracteres"] = df["texte"].str.len()

df_1star = df[df["note"] == 1]
df_5star = df[df["note"] == 5]

# Catégories comparées
fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
for ax, sub, titre, color in [
    (axes[0], df_1star, f"1★ (n={len(df_1star)})", "tomato"),
    (axes[1], df_5star, f"5★ (n={len(df_5star)})", "seagreen"),
]:
    cat_c = sub["Catégorie"].value_counts()
    ax.barh(cat_c.index[::-1], cat_c.values[::-1], color=color, edgecolor="black")
    ax.set_title(titre)
    ax.set_xlabel("Nombre d'avis")
plt.suptitle("Catégories : 1★ vs 5★", fontsize=13, y=1.02)
plt.tight_layout()
plt.show()

# Longueur moyenne par note
len_by_note = df.groupby("note")["n_caracteres"].agg(["mean", "median"]).round(1)
len_by_note.columns = ["Moyenne (car.)", "Médiane (car.)"]
print("Longueur du texte par note :")
display(len_by_note)

# Échantillons qualitatifs
print("\n--- 5 avis 1★ (échantillon aléatoire) ---")
for _, r in df_1star.sample(min(5, len(df_1star)), random_state=RANDOM_STATE).iterrows():
    print(f"  [{r['source']}] {r['texte'][:150]}")
    print()

print("--- 5 avis 5★ (échantillon aléatoire) ---")
for _, r in df_5star.sample(min(5, len(df_5star)), random_state=RANDOM_STATE).iterrows():
    print(f"  [{r['source']}] {r['texte'][:150]}")
    print()

# %% [markdown]
# ## 16. Matrice de priorisation (Volume × % Gravité Haute)
#
# Scatter plot croisant le **volume** d'avis par catégorie avec le **% de gravité Haute**. Les catégories en haut à droite sont les **priorités absolues** (beaucoup d'avis + forte proportion de gravité haute). Un **score composite** (volume × % Haute) fournit un classement actionnable.

# %%
# Construire la table de priorisation
prio = (
    df.groupby("Catégorie")
    .agg(
        volume=("note", "size"),
        note_moyenne=("note", "mean"),
        pct_haute=("Gravité", lambda s: 100 * (s == "Haute").sum() / len(s)),
    )
    .round(2)
)

prio["score"] = (prio["volume"] * prio["pct_haute"] / 100).round(1)
prio = prio.sort_values("score", ascending=False)

# Scatter plot
fig, ax = plt.subplots(figsize=(10, 6))
scatter = ax.scatter(
    prio["volume"],
    prio["pct_haute"],
    s=prio["score"] * 3 + 30,
    c=prio["note_moyenne"],
    cmap="RdYlGn",
    edgecolors="black",
    linewidth=0.8,
    vmin=1,
    vmax=5,
)
for cat, row in prio.iterrows():
    ax.annotate(
        cat,
        (row["volume"], row["pct_haute"]),
        textcoords="offset points",
        xytext=(8, 5),
        fontsize=9,
    )
ax.set_xlabel("Volume (nombre d'avis)")
ax.set_ylabel("% Gravité Haute")
ax.set_title(
    "Matrice de priorisation — Catégories\n(taille = score composite, couleur = note moyenne)"
)
cbar = plt.colorbar(scatter, ax=ax)
cbar.set_label("Note moyenne")
ax.axhline(50, color="gray", linestyle="--", alpha=0.4)
ax.axvline(prio["volume"].median(), color="gray", linestyle="--", alpha=0.4)
plt.tight_layout()
plt.show()

# Classement actionnable
prio_display = prio[["volume", "pct_haute", "note_moyenne", "score"]].copy()
prio_display.columns = ["Volume", "% Haute", "Note moy.", "Score priorité"]
print("Classement par score de priorité (volume × % gravité haute) :")
display(prio_display)

# %% [markdown]
# ## 17. Exports pour Power BI (optionnel)
#
# Fichiers dérivés dans `data/` :
# - `synthese_categories.csv` : une ligne par catégorie avec effectif et %.
# - `crosstab_categorie_gravite.csv` : effectifs croisés Catégorie × Gravité (sans marges).
# - `crosstab_categorie_source.csv` : effectifs croisés Catégorie × Source.
# - `synthese_secondaire.csv` : paires (Catégorie, Catégorie_secondaire) avec effectif.
# - `priorisation_categories.csv` : matrice de priorisation (section 16) + références de médianes pour quadrants.
#
# Tu peux aussi **uniquement** connecter Power BI à `avis_enrichis.csv` et recréer les mesures DAX à partir de la section 3.

# %%
out_dir = Path("data")
out_dir.mkdir(parents=True, exist_ok=True)

synthese_path = out_dir / "synthese_categories.csv"
crosstab_path = out_dir / "crosstab_categorie_gravite.csv"
crosstab_src_path = out_dir / "crosstab_categorie_source.csv"
synthese_sec_path = out_dir / "synthese_secondaire.csv"
prio_path = out_dir / "priorisation_categories.csv"
freq_reporting_path = out_dir / "synthese_categories_reporting.csv"

synthese = pd.DataFrame(
    {
        "Catégorie": cat_sorted.index,
        "Effectif": cat_sorted.values,
        "pct_total": (100 * cat_sorted.values / N).round(4),
        "pct_cumule": cum_pct.values,
    }
)

synthese.to_csv(synthese_path, index=False, encoding="utf-8-sig")
ct_body.to_csv(crosstab_path, encoding="utf-8-sig")

ct_src_out = pd.crosstab(df["Catégorie"], df["source"])
ct_src_out.to_csv(crosstab_src_path, encoding="utf-8-sig")

has_s = df["Catégorie_secondaire"].str.strip() != ""
pairs_out = (
    df.loc[has_s, ["Catégorie", "Catégorie_secondaire"]]
    .value_counts()
    .reset_index(name="effectif")
    .sort_values("effectif", ascending=False)
)
pairs_out.to_csv(synthese_sec_path, index=False, encoding="utf-8-sig")

prio_export = prio.reset_index()
vm = float(prio["volume"].median())
pm = float(prio["pct_haute"].median())
prio_export["ref_mediane_volume"] = vm
prio_export["ref_mediane_pct_haute"] = pm
prio_export.to_csv(prio_path, index=False, encoding="utf-8-sig")

freq_reporting.to_csv(freq_reporting_path, index=False, encoding="utf-8-sig")

# Affichage volontairement relatif au repo (réplicable si le dossier est déplacé/renommé)
print("Écrit :", synthese_path.as_posix())
print("Écrit :", crosstab_path.as_posix())
print("Écrit :", crosstab_src_path.as_posix())
print("Écrit :", synthese_sec_path.as_posix())
print("Écrit :", prio_path.as_posix())
print("Écrit :", freq_reporting_path.as_posix())

# %% [markdown]
# ## 18. Limites méthodologiques
#
# 1. **Échantillon** : les avis reflètent ce que les sources renvoient au moment de la collecte ; ce n'est pas un historique exhaustif.
# 2. **Catégorisation lexicale** : règles par mots-clés → erreurs possibles (faux positifs / faux négatifs) et thématiques non couvertes regroupées dans « Autre ».
# 3. **Gravité** : heuristique (mots forts + note + catégorie) ; ne remplace pas une revue qualitative sur un sous-ensemble.
# 4. **Causalité** : les corrélations (temporelles ou Spearman) n'impliquent pas un lien causal.
# 5. **Tests statistiques** : les effectifs par cellule sont parfois faibles (< 5), ce qui peut affecter la fiabilité du test χ² (voir alertes numériques en sections 11 et 13).
#
# ---
# **Reproductibilité** : les exports et indicateurs ci-dessus sont calculés à partir de `data/avis_enrichis.csv` avec les mêmes définitions que celles utilisées dans Power BI.
