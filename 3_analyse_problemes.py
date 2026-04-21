"""Analyse des problèmes majeurs par persona — synthèse quanti + quali (Ollama).

Produit : data/analyse_problemes.md
Durée : ~5-10 min (8 appels Ollama pour la synthèse qualitative).
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


# ── Quantitative analysis ──────────────────────────────────────────────
def analyse_quanti(persona_df: pd.DataFrame) -> list[dict]:
    """Retourne les catégories triées par fréquence, avec stats."""
    total = len(persona_df)
    if total == 0:
        return []
    cat_counts = persona_df["Catégorie"].value_counts()
    results = []
    for cat, count in cat_counts.items():
        pct = count / total * 100
        if pct < MIN_PCT_THRESHOLD:
            continue
        cat_df = persona_df[persona_df["Catégorie"] == cat]
        haute_pct = (cat_df["Gravité"] == "Haute").mean() * 100
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
    # Préparer les avis (tronquer, limiter)
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


# ── Report generation ───────────────────────────────────────────────────
def _format_problem(rank: int, cat: dict, quali: dict | None) -> str:
    """Formate un problème (quanti + quali) en markdown."""
    lines = []
    lines.append(f"### {rank}. {cat['categorie']} — {cat['count']} avis ({cat['pct']}%)")
    lines.append("")
    lines.append(f"- **Gravité Haute** : {cat['haute_pct']}% des avis de cette catégorie")
    notes_str = ", ".join(f"{k}★: {v}" for k, v in sorted(cat["notes_distrib"].items()))
    lines.append(f"- **Distribution des notes** : {notes_str}")
    lines.append("")

    if quali and "sous_problemes" in quali:
        for sp in quali["sous_problemes"]:
            lines.append(f"**{sp['nom']}** (~{sp['frequence_pct']}% des avis)")
            lines.append("")
            for cit in sp.get("citations", []):
                # Tronquer les citations très longues
                clean = cit.strip().replace("\n", " ")
                if len(clean) > 250:
                    clean = clean[:247] + "…"
                lines.append(f"> « {clean} »")
                lines.append("")
            if sp.get("impact"):
                lines.append(f"*Impact* : {sp['impact']}")
                lines.append("")
    else:
        # Fallback : 3 citations brutes
        lines.append("**Citations représentatives** :")
        lines.append("")
        for t in cat["textes"][:3]:
            clean = str(t).strip().replace("\n", " ")[:200]
            lines.append(f"> « {clean} »")
            lines.append("")

    return "\n".join(lines)


def generate_report(
    df: pd.DataFrame,
    personas: dict[str, list[dict]],
    quali_results: dict[str, dict[str, dict | None]],
) -> str:
    """Génère le rapport markdown complet."""
    total = len(df)
    neg_total = len(df[df["type_avis"] == "négatif"])
    pos_total = len(df[df["type_avis"] == "positif"])

    lines = [
        "# Analyse des problèmes majeurs — Abritel",
        "",
        f"*Généré le {datetime.now().strftime('%Y-%m-%d %H:%M')} — "
        f"{total} avis analysés (depuis 01/01/2025)*",
        "",
        "## Vue d'ensemble",
        "",
        f"- **{total}** avis collectés (Google Play, App Store, Trustpilot)",
        f"- **{neg_total}** avis négatifs ({neg_total / total * 100:.0f}%)",
        f"- **{pos_total}** avis positifs ({pos_total / total * 100:.0f}%)",
        "",
        "| Source | Total | Négatifs | % négatifs |",
        "|--------|-------|----------|------------|",
    ]
    for src in df["source"].value_counts().index:
        src_df = df[df["source"] == src]
        src_neg = len(src_df[src_df["type_avis"] == "négatif"])
        lines.append(f"| {src} | {len(src_df)} | {src_neg} | {src_neg / len(src_df) * 100:.0f}% |")
    lines.append("")

    for persona_name in ["Locataire", "Propriétaire"]:
        quanti = personas[persona_name]
        # Ajouter les "Autre" non listés pour le total correct
        persona_df_neg = df[(df["profil_auteur"] == persona_name) & (df["type_avis"] == "négatif")]
        real_total = len(persona_df_neg)

        lines.append(f"## Persona : {persona_name} ({real_total} avis négatifs)")
        lines.append("")

        if persona_name == "Propriétaire":
            lines.append(
                "> ⚠ Échantillon limité (n=44). Les tendances sont indicatives, "
                "pas statistiquement généralisables."
            )
            lines.append("")

        lines.append("| # | Problème | N | % | Gravité Haute |")
        lines.append("|---|----------|---|---|---------------|")
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

    # Section opportunités
    lines.append("## Synthèse : Problèmes → Opportunités")
    lines.append("")
    lines.append("| Problème | Persona(s) | Fréquence | Opportunité potentielle |")
    lines.append("|----------|------------|-----------|------------------------|")

    # Merge top problems across personas
    seen = set()
    for persona_name in ["Locataire", "Propriétaire"]:
        for cat in personas[persona_name][:5]:
            c = cat["categorie"]
            if c == "Autre" or c in seen:
                continue
            seen.add(c)
            # Check if problem affects both personas
            affected = []
            for pn in ["Locataire", "Propriétaire"]:
                for pc in personas[pn]:
                    if pc["categorie"] == c:
                        affected.append(f"{pn} ({pc['count']})")
            lines.append(
                f"| {c} | {', '.join(affected)} | "
                f"{cat['pct']}% (loc.) | *à compléter selon votre BMC* |"
            )
    lines.append("")

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
