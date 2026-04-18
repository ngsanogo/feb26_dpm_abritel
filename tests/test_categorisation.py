from abritel.categorisation import categoriser_avis, evaluer_gravite


def test_categoriser_localisation_langue() -> None:
    assert (
        categoriser_avis("L'application est en anglais et les prix en dollars")
        == "Localisation / Langue"
    )


def test_categoriser_annulation_reservation() -> None:
    assert (
        categoriser_avis("Réservation annulée à 10 jours du départ") == "Annulation / Réservation"
    )


def test_categoriser_financier() -> None:
    assert categoriser_avis("Remboursement jamais reçu, frais abusifs") == "Financier"


def test_categoriser_bug_technique() -> None:
    assert categoriser_avis("Bug: impossible de me connecter, l'app plante") == "Bug Technique"


def test_categoriser_ux_ergonomie() -> None:
    assert categoriser_avis("Interface pas claire, compliqué à utiliser") == "UX / Ergonomie"


def test_categoriser_service_client() -> None:
    assert categoriser_avis("Service client injoignable, aucune réponse") == "Service Client"


def test_categoriser_qualite_bien() -> None:
    assert categoriser_avis("Logement sale, description non conforme") == "Qualité du bien"


def test_evaluer_gravite_mots_cles_prioritaires() -> None:
    assert evaluer_gravite("C'est une arnaque", 5) == "Haute"


def test_evaluer_gravite_par_note() -> None:
    assert evaluer_gravite("peu importe", 1) == "Haute"
    assert evaluer_gravite("peu importe", 2) == "Moyenne"
    assert evaluer_gravite("peu importe", 3) == "Basse"


# --- Edge cases : categoriser_avis ---


def test_categoriser_none_returns_autre() -> None:
    assert categoriser_avis(None) == "Autre"


def test_categoriser_empty_string_returns_autre() -> None:
    assert categoriser_avis("") == "Autre"


def test_categoriser_whitespace_returns_autre() -> None:
    assert categoriser_avis("   \n\t  ") == "Autre"


def test_categoriser_integer_returns_autre() -> None:
    assert categoriser_avis(42) == "Autre"  # type: ignore[arg-type]


def test_categoriser_multi_keyword_first_wins() -> None:
    result = categoriser_avis("l'app est en anglais et elle bug sans cesse")
    assert result == "Localisation / Langue"


# --- Edge cases : evaluer_gravite ---


def test_evaluer_gravite_none_texte() -> None:
    assert evaluer_gravite(None, 1) == "Haute"


def test_evaluer_gravite_note_4() -> None:
    assert evaluer_gravite("correct", 4) == "Basse"


def test_evaluer_gravite_note_5() -> None:
    assert evaluer_gravite("super", 5) == "Basse"


def test_evaluer_gravite_keyword_overrides_note() -> None:
    """Un mot-clé de gravité Haute l'emporte même avec une note de 5."""
    assert evaluer_gravite("C'est un scandale total", 5) == "Haute"


# --- Mots-clés ajoutés (enrichissement avril 2026) ---


def test_categoriser_agent_virtuel() -> None:
    assert categoriser_avis("Agent virtuel. Quel nullité cet agent !") == "Service Client"


def test_categoriser_chatbot() -> None:
    assert categoriser_avis("useless AI chatbot") == "Service Client"


def test_categoriser_impossible_reserver() -> None:
    assert (
        categoriser_avis("2 dates se cochent en même temps impossible de réserver")
        == "Bug Technique"
    )


def test_categoriser_forcer_telecharger() -> None:
    assert categoriser_avis("forcer les gens à télécharger votre application") == "UX / Ergonomie"


def test_categoriser_sans_installer() -> None:
    # Score-based : "sans installer" + "installer l'appli" → UX score=2 > Bug score=1
    # Sémantiquement correct : c'est une friction UX (obligation d'installer l'app),
    # pas un crash ou une erreur technique.
    assert (
        categoriser_avis("Impossible d'ouvrir un lien sans installer l'appli") == "UX / Ergonomie"
    )


def test_categoriser_currencies_english() -> None:
    assert (
        categoriser_avis("Prices in random currencies, properties sorted on stupid order")
        == "Localisation / Langue"
    )


def test_categoriser_loueur() -> None:
    assert categoriser_avis("Très mauvais loueur") == "Qualité du bien"


def test_categoriser_aucun_suivi() -> None:
    assert categoriser_avis("Aucun suivi en cas de plainte") == "Service Client"
