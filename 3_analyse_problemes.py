"""Analyse des problèmes majeurs par persona — synthèse quanti + quali (Ollama).

Produit : data/analyse_problemes.md
Durée : ~5-10 min (8 appels Ollama pour la synthèse qualitative).

Améliorations CODIR :
- Section méthodologie avec Cohen's Kappa (accord mots-clés ↔ LLM)
- Analyse du biais de source (Trustpilot 100% négatif)
- Évolution temporelle mensuelle des catégories
- Gravité_texte (indépendante de la note) dans la priorisation
- Avertissement renforcé sur l'échantillon Propriétaire (n=44)
- Tableau opportunités rempli avec recommandations actionnables
"""

from __future__ import annotations

import json
import logging
import re
import textwrap
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOG = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────
OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "gemma4:31b"
DATA_PATH = Path("data/avis_enrichis.csv")
OUTPUT_PATH = Path("data/analyse_problemes.md")
MIN_PCT_THRESHOLD = 5  # ignorer les catégories < 5% des avis négatifs du persona
MAX_REVIEWS_PER_BATCH = 60  # cap pour le prompt Ollama
TIMEOUT_S = 300


# ── Data loading ────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    LOG.info("Chargé %d avis depuis %s", len(df), DATA_PATH)
    return df


# ── Cohen's Kappa ───────────────────────────────────────────────────────
def cohen_kappa(y1: list[str], y2: list[str]) -> float:
    """Cohen's Kappa pour l'accord inter-annotateurs sur des catégories."""
    n = len(y1)
    if n == 0 or n != len(y2):
        return 0.0
    categories = sorted(set(y1) | set(y2))
    p_o = sum(1 for a, b in zip(y1, y2, strict=True) if a == b) / n
    p_e = sum(
        (sum(1 for x in y1 if x == c) / n) * (sum(1 for x in y2 if x == c) / n) for c in categories
    )
    if p_e >= 1.0:
        return 1.0
    return (p_o - p_e) / (1 - p_e)


def compute_kappa(df: pd.DataFrame) -> float | None:
    """Calcule le Kappa entre Catégorie_mots_cles et Catégorie_ollama."""
    if "Catégorie_mots_cles" not in df.columns or "Catégorie_ollama" not in df.columns:
        return None
    mask = df["Catégorie_ollama"].notna() & (df["Catégorie_ollama"].astype(str).str.strip() != "")
    sub = df[mask]
    if len(sub) < 50:
        return None
    return cohen_kappa(
        sub["Catégorie_mots_cles"].astype(str).tolist(),
        sub["Catégorie_ollama"].astype(str).tolist(),
    )


# ── Quantitative analysis ──────────────────────────────────────────────
def _colonne_categorie(df: pd.DataFrame) -> str:
    """Retourne la colonne de catégorie la plus fiable disponible."""
    if "Catégorie_ollama" in df.columns and df["Catégorie_ollama"].notna().any():
        non_vide = (df["Catégorie_ollama"].astype(str).str.strip() != "").sum()
        if non_vide > len(df) * 0.5:
            return "Catégorie_ollama"
    return "Catégorie"


def analyse_quanti(persona_df: pd.DataFrame) -> list[dict]:
    """Retourne les catégories triées par fréquence, avec stats."""
    total = len(persona_df)
    if total == 0:
        return []
    col_cat = _colonne_categorie(persona_df)
    LOG.info("  Colonne de catégorie utilisée : %s", col_cat)
    cat_counts = persona_df[col_cat].value_counts()

    # Utiliser Gravité_texte si disponible (indépendante de la note)
    col_grav = "Gravité_texte" if "Gravité_texte" in persona_df.columns else "Gravité"

    results = []
    for cat, count in cat_counts.items():
        pct = count / total * 100
        if pct < MIN_PCT_THRESHOLD:
            continue
        cat_df = persona_df[persona_df[col_cat] == cat]
        haute_pct = (cat_df[col_grav] == "Haute").mean() * 100
        notes = cat_df["note"].value_counts().sort_index().to_dict()
        results.append(
            {
                "categorie": cat,
                "count": int(count),
                "pct": round(pct, 1),
                "haute_pct": round(haute_pct, 1),
                "notes_distrib": notes,
                "textes": cat_df["texte"].tolist(),
            }
        )
    return sorted(results, key=lambda x: -x["count"])


# ── Temporal trends ─────────────────────────────────────────────────────
def analyse_temporelle(neg_df: pd.DataFrame) -> list[dict]:
    """Calcule l'évolution mensuelle des catégories pour les avis négatifs."""
    col_cat = _colonne_categorie(neg_df)
    df = neg_df.copy()
    df["_date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["_date"])
    df["_mois"] = df["_date"].dt.to_period("M")

    mois_list = sorted(df["_mois"].unique())
    if len(mois_list) < 2:
        return []

    trends = []
    for mois in mois_list:
        mois_df = df[df["_mois"] == mois]
        total_mois = len(mois_df)
        if total_mois < 5:
            continue
        cat_counts = mois_df[col_cat].value_counts()
        entry = {"mois": str(mois), "total": total_mois}
        for cat, cnt in cat_counts.items():
            entry[cat] = int(cnt)
        trends.append(entry)
    return trends


# ── Ollama qualitative synthesis ────────────────────────────────────────
def _parse_json_response(content: str) -> dict | None:
    t = content.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*\n?", "", t)
        t = re.sub(r"\n?```\s*$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return None


def synthese_ollama(textes: list[str], categorie: str, persona: str) -> dict | None:
    """Envoie un batch d'avis à Ollama pour identifier les sous-problèmes."""
    formatted = []
    for i, t in enumerate(textes[:MAX_REVIEWS_PER_BATCH], 1):
        clean = str(t).strip().replace("\n", " ")[:300]
        formatted.append(f"{i}. {clean}")
    reviews_block = "\n".join(formatted)

    prompt = textwrap.dedent(f"""\
        Tu es un analyste UX expert en plateformes de location de vacances.

        Voici {len(formatted)} avis négatifs d'utilisateurs "{persona}" sur Abritel,
        classés dans la catégorie "{categorie}".

        AVIS :
        {reviews_block}

        MISSION : Identifie les 2-4 sous-problèmes récurrents dans ces avis.

        Pour chaque sous-problème :
        - "nom" : description courte (5-15 mots)
        - "frequence_pct" : % estimé d'avis de CE LOT concernés par ce sous-problème
        - "citations" : 2-3 citations EXACTES copiées mot pour mot depuis les avis ci-dessus
        - "impact" : 1 phrase sur l'impact concret pour un {persona.lower()}

        Règles :
        - Les citations doivent être des COPIES EXACTES du texte des avis
        - Chaque sous-problème doit concerner au moins 10% des avis du lot
        - Classe du plus fréquent au moins fréquent

        Réponds UNIQUEMENT en JSON valide :
        {{"sous_problemes": [{{"nom": "...", "frequence_pct": 30, "citations": ["...", "..."], "impact": "..."}}]}}
    """)

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0},
        "format": "json",
    }

    for attempt in range(3):
        try:
            LOG.info("  → Ollama: %s / %s (tentative %d)…", categorie, persona, attempt + 1)
            r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=TIMEOUT_S)
            r.raise_for_status()
            content = r.json()["message"]["content"]
            obj = _parse_json_response(content)
            if obj and "sous_problemes" in obj:
                return obj
            LOG.warning("  ⚠ Réponse mal formée, retry…")
        except Exception as e:
            LOG.warning("  ⚠ Erreur Ollama: %s", e)
    return None


# ── Opportunity mapping ────────────────────────────────────────────────
# Recommandations actionnables par catégorie, déduites des sous-problèmes récurrents.
OPPORTUNITES: dict[str, str] = {
    "Financier": (
        "SLA de remboursement garanti (7j max), transparence tarifaire "
        "temps réel (prix final avant paiement), audit de réconciliation des prélèvements"
    ),
    "Annulation / Réservation": (
        "Moteur de synchronisation calendrier multi-plateforme, protocole de "
        "relogement d'urgence J-0, gestion du cycle de vie des annonces (archivage auto)"
    ),
    "Service Client": (
        "Routage francophone prioritaire, escalade vers un humain en < 5 min, "
        "playbook de gestion de crise (annulation jour J, bien insalubre)"
    ),
    "Localisation / Langue": (
        "Correction du bug de géolocalisation NZ/$, audit i18n complet "
        "(devise, langue, indicatif), détection automatique de la locale utilisateur"
    ),
    "Bug Technique": (
        "Sprint de stabilité login/authentification, fix régression partage de liens, "
        "monitoring de performance applicative (crash rate, latence)"
    ),
    "UX / Ergonomie": (
        "Deep linking sans téléchargement forcé de l'app, persistance des filtres "
        "de recherche, refonte de l'architecture d'information (accès factures, réservations)"
    ),
    "Qualité du bien": (
        "Process de vérification photo (hash + date), score de fraîcheur des annonces, "
        "checklist qualité propriétaire avec conséquences (désactivation si non conforme)"
    ),
}


# ── Report generation ───────────────────────────────────────────────────
def _format_problem(rank: int, cat: dict, quali: dict | None) -> str:
    """Formate un problème (quanti + quali) en markdown."""
    lines = []
    lines.append(f"### {rank}. {cat['categorie']} — {cat['count']} avis ({cat['pct']}%)")
    lines.append("")
    lines.append(f"- **Gravité Haute (texte)** : {cat['haute_pct']}% des avis de cette catégorie")
    notes_str = ", ".join(f"{k}★: {v}" for k, v in sorted(cat["notes_distrib"].items()))
    lines.append(f"- **Distribution des notes** : {notes_str}")
    lines.append("")

    if quali and "sous_problemes" in quali:
        for sp in quali["sous_problemes"]:
            lines.append(f"**{sp['nom']}** (~{sp['frequence_pct']}% des avis)")
            lines.append("")
            for cit in sp.get("citations", []):
                clean = cit.strip().replace("\n", " ")
                if len(clean) > 250:
                    clean = clean[:247] + "…"
                lines.append(f"> « {clean} »")
                lines.append("")
            if sp.get("impact"):
                lines.append(f"*Impact* : {sp['impact']}")
                lines.append("")
    else:
        lines.append("**Citations représentatives** :")
        lines.append("")
        for t in cat["textes"][:3]:
            clean = str(t).strip().replace("\n", " ")[:200]
            lines.append(f"> « {clean} »")
            lines.append("")

    return "\n".join(lines)


def _format_temporal(trends: list[dict], categories: list[str]) -> str:
    """Génère le tableau d'évolution temporelle."""
    if not trends:
        return "*Pas assez de données pour une analyse temporelle.*\n"
    lines = []
    # Header
    header = "| Mois | Total |"
    sep = "|------|-------|"
    for cat in categories:
        short = cat.split(" / ")[0][:12]
        header += f" {short} |"
        sep += "------|"
    lines.append(header)
    lines.append(sep)
    # Rows
    for t in trends:
        row = f"| {t['mois']} | {t['total']} |"
        for cat in categories:
            cnt = t.get(cat, 0)
            row += f" {cnt} |"
        lines.append(row)
    lines.append("")
    return "\n".join(lines)


def generate_report(
    df: pd.DataFrame,
    personas: dict[str, list[dict]],
    quali_results: dict[str, dict[str, dict | None]],
) -> str:
    """Génère le rapport markdown complet, prêt pour le CODIR."""
    total = len(df)
    neg_total = len(df[df["type_avis"] == "négatif"])
    # Plage temporelle
    dates = pd.to_datetime(df["date"], utc=True, errors="coerce").dropna()
    date_min = dates.min().strftime("%Y-%m")
    date_max = dates.max().strftime("%Y-%m")

    lines = [
        "# Analyse des problèmes majeurs — Abritel",
        "",
        f"*Généré le {datetime.now().strftime('%Y-%m-%d')} — "
        f"{total} avis analysés ({date_min} → {date_max})*",
        "",
    ]

    # ── Executive Summary ──
    lines.extend(
        [
            "## Résumé exécutif",
            "",
            f"Ce rapport analyse **{neg_total} avis négatifs** (sur {total} collectés) "
            f"provenant de 3 sources (Google Play, App Store, Trustpilot) sur la période "
            f"{date_min} → {date_max}. La classification utilise un pipeline hybride "
            f"mots-clés + LLM (Ollama gemma4:31b, temperature 0).",
            "",
        ]
    )

    # ── Methodology ──
    kappa = compute_kappa(df)
    lines.extend(
        [
            "## Méthodologie et limites",
            "",
            "### Classification",
            "",
            "Chaque avis passe par deux classifieurs indépendants :",
            "1. **Mots-clés** (~226 mots FR/EN, normalisés sans accents)",
            "2. **LLM local** (Ollama gemma4:31b, temperature 0, déterministe)",
            "",
        ]
    )
    if kappa is not None:
        interp = (
            "faible"
            if kappa < 0.4
            else "modéré"
            if kappa < 0.6
            else "substantiel"
            if kappa < 0.8
            else "excellent"
        )
        reclassified = 0
        if "Catégorie_mots_cles" in df.columns and "Catégorie_ollama" in df.columns:
            mask = df["Catégorie_ollama"].notna() & (
                df["Catégorie_ollama"].astype(str).str.strip() != ""
            )
            reclassified = (
                df.loc[mask, "Catégorie_mots_cles"] != df.loc[mask, "Catégorie_ollama"]
            ).sum()
        lines.extend(
            [
                f"**Accord inter-annotateurs (Cohen's κ) : {kappa:.3f}** ({interp})",
                "",
                f"Le LLM a reclassifié **{reclassified}** avis par rapport aux mots-clés "
                f"({reclassified / total * 100:.0f}% du corpus). "
                f"Un κ {interp} indique que les deux méthodes convergent "
                f"{'fortement' if kappa >= 0.6 else 'partiellement'}, "
                f"les désaccords portant principalement sur les cas ambigus multi-catégories.",
                "",
            ]
        )

    # ── Source bias ──
    lines.extend(
        [
            "### Biais de source",
            "",
            "| Source | Total | Négatifs | % négatifs | Positifs | % positifs |",
            "|--------|-------|----------|------------|----------|------------|",
        ]
    )
    for src in df["source"].value_counts().index:
        src_df = df[df["source"] == src]
        src_neg = len(src_df[src_df["type_avis"] == "négatif"])
        src_pos = len(src_df[src_df["type_avis"] == "positif"])
        lines.append(
            f"| {src} | {len(src_df)} | {src_neg} | {src_neg / len(src_df) * 100:.0f}% "
            f"| {src_pos} | {src_pos / len(src_df) * 100:.0f}% |"
        )
    lines.extend(
        [
            "",
            "> **Avertissement** : Trustpilot contient quasi exclusivement des avis négatifs "
            "(population auto-sélectionnée de plaignants). Le taux global de "
            f"{neg_total / total * 100:.0f}% d'avis négatifs est un artefact du mix de sources, "
            "pas une mesure du sentiment réel des utilisateurs. "
            "Les analyses ci-dessous portent sur les **thématiques** des plaintes, "
            "pas sur leur prévalence dans la base d'utilisateurs.",
            "",
        ]
    )

    # ── Gravité_texte explanation ──
    col_grav = "Gravité_texte" if "Gravité_texte" in df.columns else "Gravité"
    if col_grav == "Gravité_texte":
        lines.extend(
            [
                "### Indicateur de gravité",
                "",
                "Ce rapport utilise la **Gravité_texte** (analyse lexicale du texte seul) "
                "et non la Gravité standard (liée à la note). Ceci évite la tautologie "
                "note 1★ → gravité Haute qui rendrait le croisement catégorie × gravité "
                "circulaire. La Gravité_texte détecte les mots-clés émotionnels forts "
                "(arnaque, scandale, tribunal…) indépendamment de la note donnée.",
                "",
            ]
        )

    # ── Temporal trends ──
    neg_df = df[df["type_avis"] == "négatif"]
    trends = analyse_temporelle(neg_df)
    if trends:
        # Get unique categories from trends
        all_cats_in_trends = set()
        for t in trends:
            for k in t:
                if k not in ("mois", "total"):
                    all_cats_in_trends.add(k)
        sorted_cats = [
            c
            for c, _ in [
                ("Financier", 0),
                ("Annulation / Réservation", 0),
                ("Bug Technique", 0),
                ("Service Client", 0),
                ("Localisation / Langue", 0),
                ("UX / Ergonomie", 0),
                ("Qualité du bien", 0),
                ("Autre", 0),
            ]
            if c in all_cats_in_trends
        ]

        lines.extend(
            [
                "## Évolution temporelle (avis négatifs par mois)",
                "",
                _format_temporal(trends, sorted_cats),
            ]
        )

    # ── Per-persona analysis ──
    for persona_name in ["Locataire", "Propriétaire"]:
        quanti = personas[persona_name]
        persona_df_neg = df[(df["profil_auteur"] == persona_name) & (df["type_avis"] == "négatif")]
        real_total = len(persona_df_neg)

        lines.append(f"## Persona : {persona_name} ({real_total} avis négatifs)")
        lines.append("")

        if persona_name == "Propriétaire":
            lines.extend(
                [
                    f"> **ATTENTION — Échantillon insuffisant (n={real_total}).**",
                    "> Les résultats ci-dessous sont des **signaux exploratoires**, "
                    "pas des conclusions statistiquement généralisables. ",
                    "> Un sondage NPS ciblé auprès des propriétaires est recommandé "
                    "pour valider ces tendances avant toute décision d'investissement produit.",
                    "",
                ]
            )

        lines.append("| # | Problème | N | % | Gravité Haute (texte) |")
        lines.append("|---|----------|---|---|----------------------|")
        for i, cat in enumerate(quanti, 1):
            lines.append(
                f"| {i} | {cat['categorie']} | {cat['count']} | {cat['pct']}% "
                f"| {cat['haute_pct']}% |"
            )
        lines.append("")

        quali_persona = quali_results.get(persona_name, {})
        for i, cat in enumerate(quanti, 1):
            quali = quali_persona.get(cat["categorie"])
            lines.append(_format_problem(i, cat, quali))

    # ── Opportunities ──
    lines.extend(
        [
            "## Synthèse : Problèmes → Opportunités",
            "",
            "| Problème | Persona(s) | Fréquence | Recommandations |",
            "|----------|------------|-----------|-----------------|",
        ]
    )

    seen = set()
    for persona_name in ["Locataire", "Propriétaire"]:
        for cat in personas[persona_name][:5]:
            c = cat["categorie"]
            if c == "Autre" or c in seen:
                continue
            seen.add(c)
            affected = []
            for pn in ["Locataire", "Propriétaire"]:
                for pc in personas[pn]:
                    if pc["categorie"] == c:
                        affected.append(f"{pn} ({pc['count']})")
            opp = OPPORTUNITES.get(c, "—")
            lines.append(f"| {c} | {', '.join(affected)} | {cat['pct']}% | {opp} |")
    lines.append("")

    # ── Limitations & next steps ──
    lines.extend(
        [
            "## Limites et prochaines étapes",
            "",
            "### Limites connues",
            "",
            "1. **Pas de benchmark concurrentiel** : les taux de plaintes ne sont pas "
            "comparés à Airbnb, Booking.com ou d'autres plateformes.",
            "2. **Pas de données transactionnelles** : impossible de chiffrer le coût "
            "en churn ou en LTV perdu par catégorie de problème.",
            "3. **Biais de sélection** : les avis publics surreprésentent les expériences "
            "extrêmes (très négatives ou très positives). Les utilisateurs satisfaits "
            "sans enthousiasme sont silencieux.",
            "4. **Échantillon Propriétaire** : n={} — insuffisant pour des conclusions "
            "fermes, utile uniquement comme signal d'alerte qualitatif.".format(
                len(df[(df["profil_auteur"] == "Propriétaire") & (df["type_avis"] == "négatif")])
            ),
            f"5. **Classification hybride** : κ = {kappa:.3f} — "
            "les désaccords mots-clés ↔ LLM ne sont pas arbitrés par un humain."
            if kappa is not None
            else "5. **Classification** : pas de mesure d'accord inter-annotateurs disponible.",
            "",
            "### Prochaines étapes recommandées",
            "",
            "1. **Sondage NPS ciblé Propriétaires** (n ≥ 200) pour valider les signaux.",
            "2. **Benchmark concurrentiel** : scraper les avis Airbnb/Booking sur la même période "
            "pour contextualiser les taux.",
            "3. **Croisement avec les données internes** : tickets support, taux de churn, "
            "LTV par cohorte — pour monétiser chaque catégorie de problème.",
            "4. **Analyse de tendance** : automatiser le suivi mensuel pour détecter "
            "l'impact des correctifs déployés.",
            "",
        ]
    )

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────
def main():
    df = load_data()
    neg = df[df["type_avis"] == "négatif"]

    personas_quanti: dict[str, list[dict]] = {}
    quali_results: dict[str, dict[str, dict | None]] = {}

    for persona in ["Locataire", "Propriétaire"]:
        LOG.info("\n═══ %s ═══", persona.upper())
        persona_neg = neg[neg["profil_auteur"] == persona]
        LOG.info("  %d avis négatifs", len(persona_neg))

        quanti = analyse_quanti(persona_neg)
        personas_quanti[persona] = quanti
        quali_results[persona] = {}

        for cat in quanti:
            if cat["categorie"] == "Autre":
                continue
            LOG.info("  Catégorie: %s (%d avis)", cat["categorie"], cat["count"])
            result = synthese_ollama(cat["textes"], cat["categorie"], persona)
            quali_results[persona][cat["categorie"]] = result
            if result:
                n_sp = len(result.get("sous_problemes", []))
                LOG.info("  ✓ %d sous-problèmes identifiés", n_sp)
            else:
                LOG.warning("  ✗ Pas de synthèse Ollama pour %s", cat["categorie"])

    LOG.info("\n═══ GÉNÉRATION DU RAPPORT ═══")
    report = generate_report(df, personas_quanti, quali_results)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    LOG.info("Rapport écrit dans %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()
