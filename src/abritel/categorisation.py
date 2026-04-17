"""Catégorisation et évaluation de gravité des avis par mots-clés."""

from __future__ import annotations

import re
import unicodedata

# --- Normalisation du texte ---


def normaliser_texte(texte: str) -> str:
    """Minuscule + suppression des accents pour un matching robuste."""
    t = texte.lower()
    # NFD décompose les caractères accentués (é → e + accent), puis on retire les accents
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# --- Catégorisation ---

# Les mots-clés sont SANS accents (le texte est normalisé avant comparaison).
_CATEGORIES_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "Localisation / Langue",
        (
            "francais",
            "anglais",
            "allemand",
            "langue",
            "traduction",
            "traduire",
            "euros",
            "dollars",
            "devise",
            " e ",
            " $ ",
            "en anglais",
            "en allemand",
            "en francais",
            "language",
            "currency",
            "currencies",
            "nzd",
            "dollar",
            "neo-zelandais",
            "neo zelandais",
            "neo zelandaise",
            "vrbo",
        ),
    ),
    (
        "Annulation / Réservation",
        (
            "annule",
            "annulee",
            "annulation",
            "annuler",
            "reservation annul",
            "reservation non",
            "indisponible",
            "derniere minute",
            "reservation refusee",
            "non garanti",
            "non confirme",
            "confirmation de reservation",
            "calendrier",
            "disponibilite",
            "check-in",
            "check-out",
        ),
    ),
    (
        "Financier",
        (
            "caution",
            "remboursement",
            "rembourse",
            "rembours",
            "paiement",
            "payer",
            "frais",
            "facture",
            "prix",
            "tarif",
            "argent",
            "carte bancaire",
            "prelevement",
            "depot",
            "arnaque",
            "escroquerie",
            "voleur",
            "commission",
            "versement",
            "surfacturation",
            "taxe",
            "assurance",
            "supplement",
            "acompte",
            "garantie",
        ),
    ),
    (
        "Bug Technique",
        (
            "bug",
            "beug",
            "plante",
            "plante ",
            "crash",
            "erreur",
            "ne fonctionne",
            "ne marche",
            " lent",
            "lenteur",
            "connexion",
            "mot de passe",
            "login",
            "chargement",
            "mise a jour",
            "compatible",
            "figee",
            "bloque",
            "bloquer",
            "dysfonctionne",
            "dysfonctionnement",
            "impossible d'ouvrir",
            "impossible de se connecter",
            "impossible de me connecter",
            "notification",
            "page blanche",
            "ferme toute seule",
            "fonctionne pas",
            "marche pas",
            "ne charge pas",
            "ne s'ouvre",
            "probleme technique",
            "impossible d'acceder",
            "impossible a utiliser",
            "pirater",
            "pirate",
            "inscription",
            "impossible de reserver",
            "n'arrive pas a acceder",
            "impossible d'utiliser",
        ),
    ),
    (
        "UX / Ergonomie",
        (
            "intuitif",
            "ergonomique",
            "complique",
            "complexe",
            "mal fait",
            "mal pense",
            "pas pratique",
            "fastidieuse",
            "on ne comprend",
            "comprend rien",
            "pas clair",
            "difficile a utiliser",
            "labyrinthe",
            "convivial",
            "interface",
            "navigation",
            "filtre",
            "confus",
            "pas logique",
            "pas facile",
            "pas ludique",
            "obliger de telecharger",
            "oblige de telecharger",
            "forcer a telecharger",
            "force a telecharger",
            "installer l'appli",
            "telecharger l'appli",
            "telecharger votre",
            "telecharger l'application",
            "on ne trouve rien",
            "trouve rien",
            "sans installer",
        ),
    ),
    (
        "Service Client",
        (
            "service client",
            "sav",
            "support",
            "assistance",
            "conseiller",
            "reponse",
            "contact",
            "joindre",
            "injoignable",
            "aucune reponse",
            "attente",
            "mail",
            "email",
            "telephone",
            "aucune aide",
            "aide",
            "reclamation",
            "interlocuteur",
            "tchat",
            "hotline",
            "relation client",
            "agent virtuel",
            "chatbot",
            "aucun suivi",
            "suivi",
        ),
    ),
    (
        "Qualité du bien",
        (
            "logement",
            "appartement",
            "maison",
            "location",
            "annonce",
            "photo",
            "sale",
            "proprete",
            "hote",
            "proprietaire",
            "description",
            "non conforme",
            "deception",
            "insalubre",
            "odeur",
            "hebergement",
            "gite",
            "villa",
            "piscine",
            "chambre",
            "equipement",
            "menage",
            "loueur",
            "parking",
        ),
    ),
]


def categoriser_avis(texte: str) -> str:
    """Retourne la catégorie principale (premier match, texte normalisé sans accents)."""
    if not isinstance(texte, str) or not texte.strip():
        return "Autre"
    t = normaliser_texte(texte)
    for categorie, mots in _CATEGORIES_KEYWORDS:
        if any(mot in t for mot in mots):
            return categorie
    return "Autre"


def categoriser_avis_multi(texte: str) -> list[str]:
    """Retourne toutes les catégories matchées (liste vide → Autre)."""
    if not isinstance(texte, str) or not texte.strip():
        return []
    t = normaliser_texte(texte)
    return [cat for cat, mots in _CATEGORIES_KEYWORDS if any(mot in t for mot in mots)]


# --- Gravité ---

_NEGATION_RE = re.compile(
    r"\b(?:pas|plus|jamais|aucun|aucune|ni)\s+(?:une?\s+)?"
    r"(?:arnaque|escroc|escroquerie|honte|scandale|illegal)",
    re.IGNORECASE,
)

_GRAVITE_HAUTE_KEYWORDS = (
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
)


def evaluer_gravite(texte: str, note: int, categorie: str = "") -> str:
    if not isinstance(texte, str):
        texte = ""
    t = normaliser_texte(texte)

    # Retirer les expressions niées avant de chercher les mots-clés de gravité
    t_check = _NEGATION_RE.sub("", t)

    if any(mot in t_check for mot in _GRAVITE_HAUTE_KEYWORDS):
        return "Haute"

    if note == 1:
        return "Haute"
    if note == 2:
        if categorie in ("Bug Technique", "Financier", "Annulation / Réservation"):
            return "Haute"
        return "Moyenne"
    return "Basse"
