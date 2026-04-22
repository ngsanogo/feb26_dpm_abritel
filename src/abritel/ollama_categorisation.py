"""Validation et raffinement des catégories via Ollama (LLM local).

**Auto-détection** : si ``ollama serve`` tourne sur la machine, le pipeline
l'utilise automatiquement — aucune variable d'environnement requise.
Pour forcer la désactivation : ``ABRITEL_OLLAMA=0``.
Jamais actif en CI (runners GitHub sans service Ollama).

Configuration recommandée :
    ollama serve &
    ollama pull qwen3.5
    uv run python 1_pipeline.py   # Ollama détecté et utilisé automatiquement

Mode par défaut : « all » — chaque avis est validé par le LLM, qu'il soit
classé par mots-clés ou non. Les avis déjà traités lors d'un run précédent
sont ignorés (cache incrémental sur la colonne Catégorie_ollama du CSV).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
import requests

from abritel.categorisation import CATEGORIES_ABRITEL, evaluer_gravite, sous_cat_autre

LOG = logging.getLogger(__name__)

_ENV_ENABLED = "ABRITEL_OLLAMA"
_ENV_URL = "ABRITEL_OLLAMA_URL"
_ENV_MODEL = "ABRITEL_OLLAMA_MODEL"
_ENV_MODE = "ABRITEL_OLLAMA_MODE"
_ENV_TIMEOUT = "ABRITEL_OLLAMA_TIMEOUT"

_CATEGORIES_SET = frozenset(CATEGORIES_ABRITEL)
_OLLAMA_MAX_WORKERS = 4
_OLLAMA_MAX_RETRIES = 3
_CHECKPOINT_BATCH_SIZE = 25


def ollama_actif() -> bool:
    """Vrai si Ollama est accessible et doit s'exécuter.

    Auto-détection : ping sur ``/api/tags`` (timeout 2 s).
    - Si Ollama répond → True (pas de variable d'environnement requise).
    - Si Ollama ne répond pas → False (keywords seuls, sans erreur).
    - ``ABRITEL_OLLAMA=0`` → False forcé même si Ollama tourne.
    - En CI (``CI=true`` ou ``GITHUB_ACTIONS=true``) → toujours False.
    """
    # Opt-out explicite
    v = (os.getenv(_ENV_ENABLED) or "").strip().lower()
    if v in {"0", "false", "no", "off"}:
        return False
    # Les runners GitHub n'ont pas Ollama.
    if os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true":
        return False
    # Auto-détection : le service répond-il ?
    base = (os.getenv(_ENV_URL) or "http://127.0.0.1:11434").rstrip("/")
    try:
        r = requests.get(f"{base}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _liste_categories_prompt() -> str:
    return "\n".join(f"- {c}" for c in CATEGORIES_ABRITEL)


def _extraire_json_message(content: str) -> dict[str, Any] | None:
    """Parse la sortie modèle (JSON pur ou bloc markdown)."""
    t = content.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*\n?", "", t)
        t = re.sub(r"\n?```\s*$", "", t).strip()
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r'"categorie"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
        if not m:
            return None
        cat_val = json.loads(f'"{m.group(1)}"')
        return {"categorie": cat_val} if isinstance(cat_val, str) else None
    if isinstance(obj, dict):
        return obj
    return None


def _normaliser_categorie(raw: str) -> str | None:
    s = raw.strip()
    if s in _CATEGORIES_SET:
        return s
    for c in CATEGORIES_ABRITEL:
        if c.lower() == s.lower():
            return c
    return None


def categoriser_texte_ollama(
    texte: str,
    *,
    note: int = 0,
    cat_mots_cles: str = "Autre",
    base_url: str | None = None,
    model: str | None = None,
    timeout_s: float | None = None,
) -> str | None:
    """Appelle l'API chat Ollama et retourne une catégorie valide, ou ``None``.

    Paramètres enrichis vs la version précédente :
    - ``note`` : note /5 de l'avis → contexte émotionnel pour le LLM
    - ``cat_mots_cles`` : catégorie suggérée par les mots-clés → hint pour le LLM
    - Temperature 0 (déterministe) pour la reproductibilité
    - 3 tentatives avec backoff si la réponse est invalide ou le service indisponible
    """
    if not isinstance(texte, str) or not texte.strip():
        return None

    base = (base_url or os.getenv(_ENV_URL) or "http://127.0.0.1:11434").rstrip("/")
    mod = model or os.getenv(_ENV_MODEL) or "qwen3.5"
    timeout = timeout_s if timeout_s is not None else float(os.getenv(_ENV_TIMEOUT) or "300")

    system = (
        "Tu es un expert en analyse de satisfaction client pour Abritel/VRBO "
        "(plateforme de location de vacances en France).\n\n"
        "Classe l'avis dans la catégorie la plus pertinente.\n"
        'Réponds UNIQUEMENT en JSON : {"categorie": "<libellé exact>"}\n\n'
        "Catégories :\n"
        "- Localisation / Langue : traduction, devise ($, €), pays, langue d'affichage\n"
        "- Annulation / Réservation : annulation, indisponibilité, calendrier, "
        "check-in/out, confirmation\n"
        "- Financier : paiement, remboursement, caution, frais cachés, "
        "tarification, arnaque\n"
        "- Bug Technique : crash, bug, lenteur, problème de connexion, "
        "mise à jour, app bloquée\n"
        "- UX / Ergonomie : interface confuse, navigation difficile, filtres, "
        "parcours compliqué, obligation de télécharger\n"
        "- Service Client : SAV injoignable, aucune réponse, attente, chatbot, hotline\n"
        "- Qualité du bien : logement sale, non conforme, photos trompeuses, "
        "équipement, ménage\n"
        "- Autre : avis positif générique, commentaire hors catégorie, trop vague\n\n"
        "Règles :\n"
        "• La note /5 donne le contexte émotionnel (1-2★ = négatif, 4-5★ = positif)\n"
        "• Choisis le problème PRINCIPAL si l'avis touche plusieurs thèmes\n"
        "• « Autre » = dernier recours quand aucune catégorie ne colle\n"
        "• Utilise le libellé EXACT de la liste ci-dessus (accents inclus)\n"
        "• Ne jamais inventer de catégorie\n\n"
        "Exemples :\n"
        '• "L\'appli bug constamment, impossible de se connecter" → Bug Technique\n'
        '• "Tout est en dollars au lieu d\'euros" → Localisation / Langue\n'
        '• "Super appli, fonctionne très bien" → Autre'
    )

    max_chars = 6000
    user = (
        f"Note : {note}/5 étoiles\n"
        f"Catégorie suggérée par mots-clés : {cat_mots_cles}\n\n"
        f"Avis :\n{texte.strip()[:max_chars]}"
    )

    payload = {
        "model": mod,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": False,  # Désactive le raisonnement interne (gemma4) — 18x plus rapide
        "options": {"temperature": 0},  # Déterministe : meilleure reproductibilité
        "format": "json",
    }

    last_err: Exception | None = None
    for attempt in range(_OLLAMA_MAX_RETRIES):
        try:
            r = requests.post(f"{base}/api/chat", json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            content = data.get("message", {}).get("content")
            if not content or not isinstance(content, str):
                last_err = ValueError("Réponse Ollama vide")
                time.sleep(1)
                continue
            obj = _extraire_json_message(content)
            if not obj:
                last_err = ValueError(f"JSON non parseable : {content[:100]!r}")
                time.sleep(1)
                continue
            cat = obj.get("categorie")
            if not isinstance(cat, str):
                last_err = ValueError(f"Clé 'categorie' absente ou non-string : {obj}")
                time.sleep(1)
                continue
            result = _normaliser_categorie(cat)
            if result is None:
                last_err = ValueError(f"Catégorie inconnue retournée : {cat!r}")
                time.sleep(1)
                continue
            return result
        except Exception as e:
            last_err = e
            if attempt < _OLLAMA_MAX_RETRIES - 1:
                time.sleep(2**attempt)

    LOG.warning("ollama: échec après %s tentatives (%s)", _OLLAMA_MAX_RETRIES, last_err)
    return None


def appliquer_categorisation_ollama(
    df: pd.DataFrame,
    *,
    force_rerun: bool = False,
    on_progress: Callable[[pd.DataFrame, int, int], None] | None = None,
) -> pd.DataFrame:
    """Valide et corrige les catégories de TOUS les avis via Ollama.

    Stratégie incrémentale :
    - Les avis ayant déjà une ``Catégorie_ollama`` valide (runs précédents) sont
      réutilisés sans nouvel appel API, sauf si ``force_rerun=True`` (keywords changés).
    - Les nouveaux avis (pas de cache) sont toujours envoyés au modèle.

    ``on_progress(df, done, total)`` est appelé tous les ``_CHECKPOINT_BATCH_SIZE``
    avis traités pour permettre une sauvegarde intermédiaire (crash recovery).

    ``ABRITEL_OLLAMA_MODE`` :
    - ``all`` (défaut) : valide tous les avis, nouveaux ou non
    - ``autre``         : ne valide que les avis encore classés « Autre » après mots-clés

    Le LLM reçoit pour chaque avis : le texte + la note /5 + la catégorie mots-clés.
    Temperature 0 → résultats déterministes et reproductibles.
    """
    out = df.copy()
    out["Catégorie_mots_cles"] = out["Catégorie"]

    # Initialiser Catégorie_ollama si absente (premier run)
    if "Catégorie_ollama" not in out.columns:
        out["Catégorie_ollama"] = ""

    mode = (os.getenv(_ENV_MODE) or "all").strip().lower()
    if mode not in {"autre", "all"}:
        LOG.warning("ollama: mode inconnu %r — utilisation de 'all'", mode)
        mode = "all"

    # Cache incrémental : restaurer les catégories Ollama des runs précédents
    if not force_rerun:
        cached_mask = out["Catégorie_ollama"].isin(_CATEGORIES_SET)
        n_cached = int(cached_mask.sum())
        if n_cached > 0:
            LOG.info("   Ollama : %s avis restaurés depuis le cache (pas de rappel API)", n_cached)
            for idx in out.index[cached_mask]:
                cat_cached = str(out.at[idx, "Catégorie_ollama"])
                out.at[idx, "Catégorie"] = cat_cached
                # Éviter doublon : si secondaire == nouveau primaire, permuter
                if (
                    "Catégorie_secondaire" in out.columns
                    and out.at[idx, "Catégorie_secondaire"] == cat_cached
                ):
                    out.at[idx, "Catégorie_secondaire"] = out.at[idx, "Catégorie_mots_cles"]
                note_raw = out.at[idx, "note"]
                note_int = int(note_raw) if pd.notna(note_raw) else 0
                out.at[idx, "Gravité"] = evaluer_gravite(
                    str(out.at[idx, "texte"]), note_int, cat_cached
                )
                # Recalcul de Autre_type cohérent avec la catégorie restaurée
                if "Autre_type" in out.columns:
                    if cat_cached == "Autre":
                        lng = (
                            int(out.at[idx, "longueur_texte"])
                            if "longueur_texte" in out.columns
                            else 0
                        )
                        out.at[idx, "Autre_type"] = sous_cat_autre(note_int, lng)
                    else:
                        out.at[idx, "Autre_type"] = ""
        # Seuls les avis sans cache valide ont besoin d'être traités
        needs_llm = ~cached_mask
    else:
        LOG.info("   Ollama : force_rerun=True — tous les avis repassent par le LLM")
        needs_llm = pd.Series(True, index=out.index)

    # Appliquer le filtre de mode
    if mode == "autre":
        needs_llm = needs_llm & (out["Catégorie"] == "Autre")

    cible = out.loc[needs_llm]
    n = len(cible)
    LOG.info(
        "   Ollama : %s avis à traiter (mode=%s, force_rerun=%s, workers=%s)",
        n,
        mode,
        force_rerun,
        _OLLAMA_MAX_WORKERS,
    )

    if n == 0:
        return out

    modif = 0
    done = 0
    with ThreadPoolExecutor(max_workers=_OLLAMA_MAX_WORKERS) as executor:
        future_to_idx = {
            executor.submit(
                categoriser_texte_ollama,
                str(out.at[idx, "texte"]),
                note=int(out.at[idx, "note"]) if pd.notna(out.at[idx, "note"]) else 0,
                cat_mots_cles=str(out.at[idx, "Catégorie_mots_cles"]),
            ): idx
            for idx in cible.index
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                cat_llm = future.result()
            except Exception as e:
                LOG.warning("ollama: erreur inattendue idx=%s: %s", idx, e)
                done += 1
                continue
            if cat_llm is None:
                done += 1
                continue
            out.at[idx, "Catégorie_ollama"] = cat_llm
            prev = out.at[idx, "Catégorie_mots_cles"]
            if cat_llm != prev:
                out.at[idx, "Catégorie"] = cat_llm
                # Éviter doublon : si secondaire == nouveau primaire, permuter
                if (
                    "Catégorie_secondaire" in out.columns
                    and out.at[idx, "Catégorie_secondaire"] == cat_llm
                ):
                    out.at[idx, "Catégorie_secondaire"] = prev
                note_raw = out.at[idx, "note"]
                note = int(note_raw) if pd.notna(note_raw) else 0
                out.at[idx, "Gravité"] = evaluer_gravite(str(out.at[idx, "texte"]), note, cat_llm)
                if "Autre_type" in out.columns:
                    if cat_llm == "Autre":
                        lng = (
                            int(out.at[idx, "longueur_texte"])
                            if "longueur_texte" in out.columns
                            else 0
                        )
                        out.at[idx, "Autre_type"] = sous_cat_autre(note, lng)
                    else:
                        out.at[idx, "Autre_type"] = ""
                modif += 1

            done += 1
            if done % _CHECKPOINT_BATCH_SIZE == 0:
                LOG.info("   Ollama : %d/%d traités (%d modifiés)…", done, n, modif)
                if on_progress:
                    on_progress(out, done, n)

    # Checkpoint final pour les avis restants après le dernier batch
    if on_progress and done > 0 and done % _CHECKPOINT_BATCH_SIZE != 0:
        on_progress(out, done, n)

    LOG.info(
        "   Ollama : %s/%s catégories modifiées (le reste confirmé ou inchangé)",
        modif,
        n,
    )
    return out
