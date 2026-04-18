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
            "dollars",
            "devise",
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
            "nouvelle zelande",
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
            "resa ",
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
            "euros",
        ),
    ),
    (
        "Bug Technique",
        (
            "bug",
            "beug",
            "plante",
            "crash",
            "erreur",
            "ne fonctionne",
            "ne marche",
            " lent",  # espace pour éviter match dans "excellent" (e-x-c-e-**lent**)
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
            "impossible de s'inscrire",
            "inscription impossible",
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
            "peu pratique",
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
            "pas simple",
            "pas ludique",
            "mal organise",
            "galere",
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
            "contact",
            "joindre",
            "injoignable",
            "aucune reponse",
            "attente",
            "mail",
            "email",
            "telephone",
            "aucune aide",
            "reclamation",
            "interlocuteur",
            "tchat",
            "hotline",
            "relation client",
            "agent virtuel",
            "chatbot",
            "aucun suivi",
            "jamais rappele",
        ),
    ),
    (
        "Qualité du bien",
        (
            "logement",
            "appartement",
            "maison",
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
            "wifi",
            "jardin",
            "balcon",
        ),
    ),
]


def categoriser_avis_multi(texte: str) -> list[str]:
    """Retourne toutes les catégories matchées, triées par score décroissant.

    Le score est le nombre de mots-clés de la catégorie présents dans le texte.
    En cas d'égalité, l'ordre d'origine de ``_CATEGORIES_KEYWORDS`` est préservé
    (tri stable). Retourne une liste vide si aucun match (→ "Autre").
    """
    if not isinstance(texte, str) or not texte.strip():
        return []
    t = normaliser_texte(texte)
    scored = [(cat, sum(1 for mot in mots if mot in t)) for cat, mots in _CATEGORIES_KEYWORDS]
    # Tri stable par score décroissant : les égalités conservent l'ordre de la liste
    scored.sort(key=lambda x: x[1], reverse=True)
    return [cat for cat, score in scored if score > 0]


def categoriser_avis(texte: str) -> str:
    """Retourne la catégorie principale (score maximal, ex-æquo → premier dans la liste)."""
    cats = categoriser_avis_multi(texte)
    return cats[0] if cats else "Autre"


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
