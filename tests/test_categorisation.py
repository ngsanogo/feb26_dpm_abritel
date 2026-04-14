from abritel.pipeline import categoriser_avis, evaluer_gravite


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
