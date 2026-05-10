from abritel.categorisation import (
    categoriser_avis,
    detecter_sentiment_positif,
    evaluer_gravite,
    evaluer_gravite_texte,
    sous_cat_autre,
)


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


# --- Mots-clés anglais (ajout avril 2026) ---


def test_categoriser_glitch_bug_technique() -> None:
    assert categoriser_avis("The app has a glitch when I try to book") == "Bug Technique"


def test_categoriser_freeze_bug_technique() -> None:
    assert categoriser_avis("App freeze every time I open it") == "Bug Technique"


def test_categoriser_not_working_bug_technique() -> None:
    assert categoriser_avis("The search is not working at all") == "Bug Technique"


def test_categoriser_refund_financier() -> None:
    assert categoriser_avis("I never received my refund after cancellation") == "Financier"


def test_categoriser_scam_financier() -> None:
    assert categoriser_avis("Total scam, charged twice for the same booking") == "Financier"


def test_categoriser_customer_service_en() -> None:
    assert categoriser_avis("Customer service never replies to my emails") == "Service Client"


def test_categoriser_hard_to_use_ux() -> None:
    assert categoriser_avis("Hard to use and not intuitive at all") == "UX / Ergonomie"


def test_categoriser_composite_connexion_bug() -> None:
    """Connexion impossible (phrase composite) → Bug Technique."""
    assert categoriser_avis("connexion impossible depuis la mise à jour") == "Bug Technique"


def test_categoriser_panne_bug_technique() -> None:
    assert categoriser_avis("2 pannes dans la journée ça devient pénible") == "Bug Technique"


def test_categoriser_formulaire_bug_technique() -> None:
    assert categoriser_avis("impossible d'aller au bout du formulaire") == "Bug Technique"


def test_categoriser_utilisation_difficile_ux() -> None:
    assert categoriser_avis("utilisation difficile pour notre âge") == "UX / Ergonomie"


def test_categoriser_ne_publie_service_client() -> None:
    assert categoriser_avis("Abritel ne publie que les avis positifs") == "Service Client"


def test_categoriser_pas_disponible_reservation() -> None:
    assert (
        categoriser_avis("on réserve et au final ce n'est pas disponible")
        == "Annulation / Réservation"
    )


def test_categoriser_indicatif_localisation() -> None:
    assert (
        categoriser_avis("l'indicatif du Togo est le +228 merci de rectifier")
        == "Localisation / Langue"
    )


# --- Negation handling in categorisation ---


def test_categoriser_negation_arnaque_not_financier() -> None:
    """'Pas une arnaque' ne doit pas matcher Financier si c'est le seul signal."""
    assert categoriser_avis("Ce n'est pas une arnaque, juste un mauvais service") != "Financier"


def test_categoriser_negation_scam_not_financier() -> None:
    """'Not a scam' ne doit pas matcher Financier si c'est le seul signal."""
    assert categoriser_avis("Not a scam but very slow service") != "Financier"


def test_categoriser_negation_preserves_real_signal() -> None:
    """Un vrai signal Financier doit encore matcher malgré une négation à côté."""
    assert categoriser_avis("Pas une arnaque mais remboursement jamais reçu") == "Financier"


def test_categoriser_negation_pas_complique_not_ux() -> None:
    """'Pas compliqué' ne doit pas matcher UX (l'utilisateur dit que c'est simple)."""
    assert categoriser_avis("L'app n'est pas compliquée") != "UX / Ergonomie"


# --- sous_cat_autre ---


def test_sous_cat_autre_positif_court() -> None:
    assert sous_cat_autre(note=5, longueur_texte=8) == "positif court"


def test_sous_cat_autre_positif_court_note_4() -> None:
    assert sous_cat_autre(note=4, longueur_texte=15) == "positif court"


def test_sous_cat_autre_negatif_long() -> None:
    assert sous_cat_autre(note=1, longueur_texte=40) == "négatif non catégorisé"


def test_sous_cat_autre_negatif_long_note_2() -> None:
    assert sous_cat_autre(note=2, longueur_texte=30) == "négatif non catégorisé"


def test_sous_cat_autre_neutre_note_3() -> None:
    assert sous_cat_autre(note=3, longueur_texte=20) == "neutre"


def test_sous_cat_autre_neutre_positif_long() -> None:
    """Avis positif mais long → neutre (pas catégorisé comme positif court)."""
    assert sous_cat_autre(note=5, longueur_texte=50) == "neutre"


def test_sous_cat_autre_neutre_negatif_court() -> None:
    """Avis négatif court → neutre (seuil longueur non atteint)."""
    assert sous_cat_autre(note=1, longueur_texte=10) == "neutre"


def test_sous_cat_autre_positif_thematique() -> None:
    """Avis positif long avec marqueurs positifs → positif thématique."""
    assert (
        sous_cat_autre(
            note=5, longueur_texte=25, texte="Application géniale, je recommande vivement"
        )
        == "positif thématique"
    )


def test_sous_cat_autre_positif_court_priorite_sur_thematique() -> None:
    """Un avis court et positif reste 'positif court' même avec mots-clés positifs."""
    assert sous_cat_autre(note=5, longueur_texte=5, texte="Super top génial") == "positif court"


def test_sous_cat_autre_pas_thematique_si_note_basse() -> None:
    """Mots-clés positifs mais note basse → pas positif thématique."""
    assert sous_cat_autre(note=2, longueur_texte=25, texte="Super déçu") != "positif thématique"


# --- detecter_sentiment_positif ---


def test_detecter_positif_genial() -> None:
    assert detecter_sentiment_positif("Application géniale") is True


def test_detecter_positif_recommande() -> None:
    assert detecter_sentiment_positif("Je recommande vivement") is True


def test_detecter_positif_english() -> None:
    assert detecter_sentiment_positif("Amazing app, love it!") is True


def test_detecter_positif_vide() -> None:
    assert detecter_sentiment_positif("") is False


def test_detecter_positif_none() -> None:
    assert detecter_sentiment_positif(None) is False


def test_detecter_positif_negatif() -> None:
    assert detecter_sentiment_positif("horrible expérience, nul") is False


# --- evaluer_gravite_texte ---


def test_gravite_texte_haute_arnaque() -> None:
    assert evaluer_gravite_texte("C'est une arnaque totale") == "Haute"


def test_gravite_texte_haute_tribunal() -> None:
    assert evaluer_gravite_texte("Je vais porter plainte au tribunal") == "Haute"


def test_gravite_texte_moyenne_probleme() -> None:
    assert evaluer_gravite_texte("Beaucoup de problèmes avec cette app") == "Moyenne"


def test_gravite_texte_moyenne_nul() -> None:
    assert evaluer_gravite_texte("Service nul et inutile") == "Moyenne"


def test_gravite_texte_basse_neutre() -> None:
    assert evaluer_gravite_texte("Application correcte dans l'ensemble") == "Basse"


def test_gravite_texte_basse_vide() -> None:
    assert evaluer_gravite_texte("") == "Basse"


def test_gravite_texte_negation() -> None:
    """La négation 'pas une arnaque' ne doit pas déclencher Haute."""
    assert evaluer_gravite_texte("ce n'est pas une arnaque") != "Haute"
