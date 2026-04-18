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
            "indicatif",
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
            "pas disponible",
            "n'est pas disponible",
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
            "refund",
            "paiement",
            "payment",
            "payer",
            "charged",
            "overcharged",
            "frais",
            "facture",
            "prix",
            "tarif",
            "argent",
            "carte bancaire",
            "credit card",
            "prelevement",
            "depot",
            "arnaque",
            "scam",
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
            "crashes",
            "glitch",
            "erreur",
            "ne fonctionne",
            "ne marche",
            " lent",  # espace pour éviter match dans "excellent" (e-x-c-e-**lent**)
            "lenteur",
            "connexion impossible",
            "perte de connexion",
            "probleme de connexion",
            "erreur de connexion",
            "mot de passe",
            "login",
            "chargement",
            "loading",
            "mise a jour",
            "compatible",
            "figee",
            "freeze",
            "frozen",
            "bloque",
            "bloquer",
            "dysfonctionne",
            "dysfonctionnement",
            "impossible d'ouvrir",
            "impossible de se connecter",
            "impossible de me connecter",
            "can't connect",
            "cannot connect",
            "notification",
            "page blanche",
            "ferme toute seule",
            "fonctionne pas",
            "marche pas",
            "not working",
            "doesn't work",
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
            "panne",
            "formulaire",
        ),
    ),
    (
        "UX / Ergonomie",
        (
            "intuitif",
            "ergonomique",
            "complique",
            "complexe",
            "confusing",
            "complicated",
            "mal fait",
            "mal pense",
            "pas pratique",
            "peu pratique",
            "fastidieuse",
            "on ne comprend",
            "comprend rien",
            "pas clair",
            "hard to use",
            "difficult to use",
            "not intuitive",
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
            "utilisation difficile",
            "captcha",
        ),
    ),
    (
        "Service Client",
        (
            "service client",
            "customer service",
            "customer support",
            "sav",
            "support",
            "assistance",
            "conseiller",
            "contact",
            "joindre",
            "injoignable",
            "aucune reponse",
            "no response",
            "no reply",
            "unanswered",
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
            "ne publie",
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

# Liste officielle (ordre des thèmes + « Autre » implicite hors mots-clés)
CATEGORIES_ABRITEL: tuple[str, ...] = tuple(cat for cat, _ in _CATEGORIES_KEYWORDS) + ("Autre",)


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


# --- Sous-catégorisation des avis « Autre » ---

_AUTRE_POSITIF_COURT_NOTE_MIN = 4
_AUTRE_POSITIF_COURT_MOTS_MAX = 15
_AUTRE_NEGATIF_LONG_NOTE_MAX = 2
_AUTRE_NEGATIF_LONG_MOTS_MIN = 30


# --- Gravité indépendante (texte seul, sans note ni catégorie) ---

_GRAVITE_TEXTE_HAUTE_KEYWORDS: tuple[str, ...] = (
    "arnaque",
    "escroquerie",
    "escroc",
    "fraude",
    "scandale",
    "honte",
    "honteux",
    "tribunal",
    "justice",
    "avocat",
    "plainte",
    "illegal",
    "voleur",
    "vol",
    "voler",
    "inadmissible",
    "inacceptable",
    "revolte",
    "revoltant",
    "degoutant",
    "furieux",
    "insupportable",
    "odieux",
    "catastrophe",
    "catastrophique",
    "danger",
    "dangereux",
    "insalubre",
)

_GRAVITE_TEXTE_MOYENNE_KEYWORDS: tuple[str, ...] = (
    "probleme",
    "galere",
    "penible",
    "nul",
    "nulle",
    "mauvais",
    "mauvaise",
    "horrible",
    "lamentable",
    "deplorable",
    "decevant",
    "deception",
    "desastreux",
    "mediocre",
    "incompetent",
    "inutile",
    "ridicule",
    "pire",
    "terrible",
    "awful",
    "worst",
    "useless",
    "disgusting",
    "pathetic",
)


def evaluer_gravite_texte(texte: str) -> str:
    """Évalue la gravité à partir du texte seul, indépendamment de la note et de la catégorie.

    Permet de casser la tautologie note→gravité en offrant un signal indépendant.
    Retourne ``"Haute"``, ``"Moyenne"`` ou ``"Basse"``.
    """
    if not isinstance(texte, str) or not texte.strip():
        return "Basse"
    t = normaliser_texte(texte)
    t_check = _NEGATION_RE.sub("", t)

    if any(mot in t_check for mot in _GRAVITE_TEXTE_HAUTE_KEYWORDS):
        return "Haute"
    if any(mot in t_check for mot in _GRAVITE_TEXTE_MOYENNE_KEYWORDS):
        return "Moyenne"
    return "Basse"


# --- Sous-catégorisation des avis « Autre » ---

_POSITIVE_KEYWORDS: tuple[str, ...] = (
    "genial",
    "excellent",
    "parfait",
    "top",
    "super",
    "formidable",
    "magnifique",
    "fantastique",
    "bravo",
    "merci",
    "satisfait",
    "recommande",
    "adore",
    "love",
    "great",
    "amazing",
    "perfect",
    "awesome",
    "wonderful",
    "best",
    "facile",
    "pratique",
    "rapide",
    "fiable",
    "impeccable",
    "nickel",
)


def detecter_sentiment_positif(texte: str) -> bool:
    """Détecte si un texte contient des marqueurs de sentiment positif."""
    if not isinstance(texte, str) or not texte.strip():
        return False
    t = normaliser_texte(texte)
    return any(mot in t for mot in _POSITIVE_KEYWORDS)


def sous_cat_autre(note: int, longueur_texte: int, texte: str = "") -> str:
    """Sous-catégorise un avis classé « Autre » selon la note, la longueur et le contenu.

    Retourne :
    - ``"positif court"``          : avis court et positif, non actionnable (bruit normal)
    - ``"positif thématique"``     : avis positif détecté par mots-clés (note >= 4 + marqueurs)
    - ``"négatif non catégorisé"`` : avis négatif long dont les mots-clés manquent dans le modèle
    - ``"neutre"``                 : tous les autres cas
    """
    if note >= _AUTRE_POSITIF_COURT_NOTE_MIN and longueur_texte <= _AUTRE_POSITIF_COURT_MOTS_MAX:
        return "positif court"
    if note >= _AUTRE_POSITIF_COURT_NOTE_MIN and detecter_sentiment_positif(texte):
        return "positif thématique"
    if note <= _AUTRE_NEGATIF_LONG_NOTE_MAX and longueur_texte >= _AUTRE_NEGATIF_LONG_MOTS_MIN:
        return "négatif non catégorisé"
    return "neutre"
