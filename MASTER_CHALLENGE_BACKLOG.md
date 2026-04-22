# Master Challenge Backlog — Projet Abritel

Audit complet : Code, Pipeline, Analyse Empirique, Stratégie, Livrables Fiche Projet.
Chaque item est classé par sévérité CODIR et catégorie de risque.

**Légende effort** : S = Small (< 2h) · M = Medium (2–4h) · L = Large (> 4h)

---

## 🔴 1. Risques Critiques (Bloquants CODIR)

### [CR-01] Biais Trustpilot non explicité dans les livrables

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Critique |
| **Catégorie** | Data-Integrity |
| **Effort** | S |

**Risque** : Trustpilot = 200/726 avis Abritel, **100% négatifs** (auto-sélection de plaignants). Le taux global "68% négatifs" est un artefact du mix de sources. Le CODIR lira "68% des clients Abritel sont mécontents" alors que c'est "68% des avis publics scrapés sont négatifs". Un jury statisticien démonte toute la crédibilité en une question.

**Preuve** : Google Play seul = 50% négatifs. Avec Trustpilot (100% négatifs, 28% du corpus) → 68%. L'écart vient du biais de sélection, pas du sentiment réel.

**Action** :
- Ajouter un encadré méthodologique en tête de `analyse_problemes.md` et du README : "Les pourcentages reflètent la distribution dans le corpus analysé (747 avis dont 28% Trustpilot auto-sélection), **non la prévalence réelle dans la base utilisateurs**."
- Partout remplacer "X% des utilisateurs" par "X% des avis du corpus".
- Ajouter une analyse stratifiée par source dans le notebook (avec/sans Trustpilot).

---

### [CR-02] Catégorie "Autre" = 24% du corpus — données perdues

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Critique |
| **Catégorie** | Data-Integrity |
| **Effort** | M |

**Risque** : 172 avis (23.7%) sont classés "Autre" — 1 avis sur 4 est ignoré dans l'analyse. 95% viennent de Google Play (avis courts, < 5 mots). Si ces avis étaient correctement classifiés, **le top 5 des problèmes changerait probablement**. Le CODIR demandera : "Vous avez jeté un quart de vos données ?"

**Preuve** : Distribution "Autre" : 164/172 = Google Play. Longueur médiane = 4 mots. 58% < 5 mots.

**Action** :
- Annoter manuellement 30–50 avis "Autre" pour vérifier si des catégories émergent.
- Ajouter dans le rapport la distribution "Autre" et justifier pourquoi ils ne faussent pas le classement (ou corriger si c'est le cas).
- Envisager de traiter les avis courts via Ollama (prompt spécifique pour avis < 10 mots).

---

### [CR-03] Aucun intervalle de confiance sur les ratios benchmark

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Critique |
| **Catégorie** | Data-Integrity |
| **Effort** | M |

**Risque** : Le ratio "Localisation 53×" repose sur un dénominateur de 12 avis Airbnb (0.2% de 6125). Si Airbnb avait eu 15 avis au lieu de 12, le ratio passe à 42×. Le Gap "Financier 2.1×" (IC possible [0.8, 3.4]) pourrait ne pas être significatif. Présenter des ratios sans IC donne un **faux sentiment de précision**.

**Preuve** : Abritel 10.6% ± ~3% (IC 95% binomial sur n=747), Airbnb 0.2% sur n=6125. Le ratio varie entre ~30× et ~100× selon les IC.

**Action** :
- Calculer IC 95% (bootstrap ou binomial exact) sur chaque % par catégorie et par marque.
- Calculer IC 95% sur les ratios (delta method ou bootstrap).
- Ajouter un test statistique (Fisher exact ou Chi² 2×2) par catégorie pour valider la significativité du gap.
- Appliquer correction Bonferroni sur les 7 catégories testées.

---

### [CR-04] Livrables Fiche Projet manquants (6/12)

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Critique |
| **Catégorie** | Business-Logic |
| **Effort** | L |

**Risque** : La Fiche Projet attend 12 livrables structurés. 6 sont absents ou flous : Personas, Experience Maps, KPIs post-déploiement, Scope MVP, Risques/Conformité, Stratégie de lancement. Une soutenance sans personas ni journey map est **inachevée par définition**.

**Preuve** : Audit croisé Fiche Projet vs livrables existants → 6 items manquants.

**Action** :
- Personas (C4 du backlog existant) : 2 fiches formalisées avec données corpus.
- Experience maps (H5) : Journey locataire et propriétaire avec pain points.
- KPIs (H6) : 3–5 métriques mesurables (note App Store M+3, % Localisation M+3, etc.).
- MVP scope (C5) : Périmètre fonctionnel précis, critères go/no-go.
- Risques/Conformité (H7) : RGPD, dépendances API, maintenabilité.
- Stratégie de lancement (B5) : Go-to-market, plan déploiement.

---

### [CR-05] Estimation d'impact financier absente

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Critique |
| **Catégorie** | Business-Logic |
| **Effort** | M |

**Risque** : Le CEO demandera "Combien ça coûte de ne rien faire ?". Aucune estimation de churn, LTV réduit, ou revenus perdus par catégorie de problème. La matrice de priorisation utilise "Fréquence × Gravité_texte" au lieu de "Fréquence × Impact business".

**Action** :
- Calculer un proxy : nb avis négatifs × facteur multiplicateur silencieux (citer source : "pour 1 plainte publique, X clients partent sans rien dire") × panier moyen Abritel.
- Ajouter une colonne "€/mois estimé" à la matrice de priorisation.
- Documenter le facteur multiplicateur comme hypothèse explicite.

---

### [CR-06] Validation externe de la taxonomie absente

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Critique |
| **Catégorie** | Data-Integrity |
| **Effort** | L |

**Risque** : Les 151 tests sont tautologiques — ils testent le code contre lui-même, pas contre la vérité métier. Un jury demandera : "Un expert humain a-t-il validé vos catégories ?" Réponse actuelle : non. Le Cohen's Kappa (0.663) mesure l'accord entre deux méthodes automatiques, pas la justesse.

**Preuve** : 0 tests sur données annotées par des humains. Le Kappa compare mots-clés vs Ollama, pas mots-clés vs vérité terrain.

**Action** :
- Faire annoter 50–100 avis par 2–3 personnes du groupe (sans accès aux mots-clés).
- Calculer le Fleiss' Kappa inter-annotateurs.
- Comparer avec les résultats du pipeline (Kappa pipeline vs humains).
- Documenter les désaccords et ajuster les mots-clés si besoin.

---

## 🟡 2. Dettes Techniques & Workflow

### [DT-01] Trustpilot : dépendance fragile à `__NEXT_DATA__`

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Scalability |
| **Effort** | M |

**Risque** : Le scraper Trustpilot repose sur `soup.find("script", id="__NEXT_DATA__")` (scraping.py:344). Si Trustpilot migre vers un autre framework frontend (hors Next.js), change l'ID du script, ou compresse le JSON → **0 avis Trustpilot, sans alerte claire**. Le seul filet de sécurité est un test contractuel hebdomadaire (lundi 8h).

**Action** :
- Documenter cette fragilité dans `decisions-techniques.md` comme risque connu.
- Ajouter un fallback CSS-selector alternatif (parser les `<article>` HTML directement).
- Rendre le test contractuel plus fréquent (ou l'intégrer en CI avec un flag conditionnel).

---

### [DT-02] Google Play Scraper : lib non officielle volatile

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Scalability |
| **Effort** | S |

**Risque** : `google_play_scraper@1.2.7` fait du reverse-engineering sur l'API Google Play. Google peut changer le format protobuf, ajouter de l'auth, ou bloquer le scraping à tout moment. Le code ne capture pas les exceptions custom de la lib (`PlayStoreException`) — ligne 213 ne gère que `requests.RequestException, ValueError, TypeError`.

**Action** :
- Ajouter `Exception` comme fallback de capture (ou importer les exceptions spécifiques de la lib).
- Documenter dans `decisions-techniques.md` que cette dépendance est volatile.
- Épingler la version exacte dans `pyproject.toml`.

---

### [DT-03] Déduplication sur texte exact — doublon par typo

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Mineur |
| **Catégorie** | Data-Integrity |
| **Effort** | S |

**Risque** : `drop_duplicates(subset=["source", "date", "note", "texte"])` (pipeline.py:287) : si un utilisateur re-poste avec une typo mineure ("cool" vs "cool!"), le système crée un doublon. L'ancien CSV prime (`keep="first"`) — si l'ancien avait une erreur, elle persiste.

**Action** :
- Accepter le risque (faible fréquence) mais le documenter.
- Optionnel : ajouter une similarité cosine ou Levenshtein en post-processing pour détecter les quasi-doublons (effort M si implémenté).

---

### [DT-04] Dates invalides rejetées silencieusement

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Data-Integrity |
| **Effort** | S |

**Risque** : `parse_datetime_utc` retourne `None` pour les dates invalides → l'avis est silencieusement rejeté (scraping.py:282-284, 359-361). Aucun comptage des avis perdus. Si une source change son format de date, le pipeline ne le détecte pas — les avis disparaissent sans log.

**Action** :
- Ajouter un compteur `avis_rejetes_date_invalide` dans le logging.
- Émettre un warning si > 5% des avis sont rejetés pour date invalide.
- Tester le parsing avec les formats `+XX:XX`, millisecondes, et dates sans timezone.

---

### [DT-05] Ollama : validation JSON fragile + pas de few-shot

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Mineur |
| **Catégorie** | Business-Logic |
| **Effort** | M |

**Risque** : Si le modèle génère une catégorie invalide (ex: "Financier typo"), `_normaliser_categorie` retourne `None` (ollama_categorisation.py:96-103). L'avis reste à la catégorie mots-clés, sans log explicite de la "perte silencieuse". Le prompt n'a pas de few-shot examples, ce qui augmente le risque de réponses hors format.

**Action** :
- Logger les cas où Ollama retourne une catégorie non reconnue (compteur + exemples).
- Ajouter 2–3 few-shot examples au prompt (texte + catégorie attendue).
- Tester une variante du prompt SANS hint mots-clés pour mesurer le vrai κ indépendant.

---

### [DT-06] Pipeline : pas de `pytest-cov` en CI

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Mineur |
| **Catégorie** | Scalability |
| **Effort** | S |

**Risque** : 151 tests, ~70% couverture estimée, mais aucune mesure en CI. Un refactoring peut faire tomber la couverture à 30% sans que personne ne le sache.

**Action** :
- Ajouter `pytest-cov` et `--cov-fail-under=70` (ou 75%) au CI.
- Ajouter `pytest-timeout` pour détecter les tests qui hang.

---

### [DT-07] Circuit breaker trop tolérant en CI

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Mineur |
| **Catégorie** | Scalability |
| **Effort** | S |

**Risque** : `ABRITEL_SOFT_CIRCUIT_BREAKER=1` en CI fait que le pipeline continue même si un scraper retourne 0 avis. Le circuit breaker ne détecte pas les augmentations suspectes (ex: 500 avis au lieu de 100 = faux positifs de scraping) ni les changements de note moyenne (3.5 → 1.2 = filtre cassé).

**Action** :
- Retirer `ABRITEL_SOFT_CIRCUIT_BREAKER` ou le rendre bruyant (warning → error).
- Ajouter détection d'anomalies : hausse > 3σ du volume ou variation > 1 pt de note moyenne.

---

### [DT-08] Dépendances non épinglées dans pyproject.toml

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Mineur |
| **Catégorie** | Scalability |
| **Effort** | S |

**Risque** : `pandas>=2.2` sans borne supérieure. Si pandas 3.0 sort avec breaking changes, la prochaine `uv sync` casse silencieusement le pipeline. Même risque pour playwright, beautifulsoup4, etc.

**Action** :
- Épingler avec bornes : `pandas>=2.2,<3`, `playwright>=1.58,<2`, etc.
- Déplacer Playwright en dépendance optionnelle (50 MB de Chromium inutile si pas de Trustpilot).

---

### [DT-09] `1_benchmark.py` : pas de gestion d'erreur par marque

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Mineur |
| **Catégorie** | Scalability |
| **Effort** | S |

**Risque** : Si le scraper Airbnb échoue, la boucle continue sans retry → `benchmark_complet.csv` aura 2/3 marques. `pd.concat` avec colonnes différentes ajoute NaN silencieusement. Aucun timing affiché pour 9 requêtes (3 marques × 3 sources).

**Action** :
- Ajouter un try/except par marque avec log de l'erreur et continuation.
- Valider que toutes les colonnes attendues sont présentes après concat.
- Logger le temps total par marque.

---

## 🔵 3. Alignement Stratégique & Personas

### [SP-01] Personas non formalisés

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Critique |
| **Catégorie** | Persona-Accuracy |
| **Effort** | M |

**Risque** : Le corpus identifie "Locataire" (n=682) et "Propriétaire" (n=44) via `profil_auteur`, mais aucune fiche persona formalisée. Le jury demandera : "Qui est votre utilisateur cible ? Décrivez une personne concrète." Réponse actuelle : néant.

**Action** :
- Créer 2 fiches personas (Locataire type, Propriétaire type) : âge, contexte, parcours, frustrations (avec verbatims du corpus), objectifs, canaux utilisés.
- S'appuyer sur la distribution des catégories par profil pour différencier les frustrations.
- Intégrer dans la Fiche Projet.

---

### [SP-02] Propriétaire = 100% négatif → persona incomplet

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Persona-Accuracy |
| **Effort** | M |

**Risque** : Les 44 avis propriétaires sont **tous négatifs** — artefact de collecte (Trustpilot = auto-sélection de plaintes). Impossible d'estimer un sentiment réel, un NPS, ou de construire un persona équilibré. La conclusion "Locataire ≠ Propriétaire" (Chi² p=0.031) est exploratoire au mieux, fausse au pire.

**Preuve** : n_proprio=44, 100% négatifs. IC 95% sur le % négatif = [100%, 100%] = aucune variance.

**Action** :
- Présenter le Chi² persona comme "exploratoire, non conclusif" (et retirer la mention "satisfait Bonferroni" — p=0.031 > α_corrigé=0.0125).
- Documenter explicitement : "le corpus ne permet pas de construire un persona propriétaire fiable".
- Proposer un sondage dédié propriétaires (n ≥ 200, source mixte) comme next step.

---

### [SP-03] Conflit d'intérêts Locataire / Propriétaire non analysé

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Persona-Accuracy |
| **Effort** | M |

**Risque** : Le rapport recommande de fixer "Annulation/Réservation" (Sprint Q2). Mais faciliter l'annulation pour le locataire peut **nuire à la rentabilité du propriétaire** (annulations tardives = logement vide). Aucune matrice d'impact croisée ne vérifie que les recommandations ne créent pas de perdant.

**Action** :
- Créer une matrice d'impact croisée : pour chaque recommandation, évaluer l'effet sur Locataire ET Propriétaire.
- Identifier les trade-offs explicites (ex: "annulation flexible = +satisfaction locataire, -revenus propriétaire, mitigation possible via assurance annulation").
- Intégrer dans la section recommandations du rapport.

---

### [SP-04] Experience maps absentes

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Persona-Accuracy |
| **Effort** | M |

**Risque** : Livrable Fiche Projet manquant. Les pain points du corpus (Localisation, Annulation, UX) ne sont pas cartographiés sur un parcours utilisateur. Impossible de voir à quelle étape chaque frustration se produit.

**Action** :
- Créer 1–2 journey maps (Locataire : recherche → réservation → paiement → séjour → post-séjour ; Propriétaire : inscription → mise en ligne → réservation reçue → gestion).
- Mapper les catégories de problèmes sur chaque étape.
- Sourcer avec des verbatims du corpus.

---

### [SP-05] Catégorie secondaire ignorée dans l'analyse

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Mineur |
| **Catégorie** | Business-Logic |
| **Effort** | S |

**Risque** : 43% des avis ont une `Catégorie_secondaire` remplie (312/726). Cette information est calculée par le pipeline mais **jamais utilisée** dans le notebook ni dans le rapport. Les problèmes composés (Financier + Annulation, Bug + UX) sont donc sous-estimés.

**Action** :
- Ajouter une section "problèmes composés" dans le notebook : matrice catégorie principale × secondaire.
- Identifier les associations fréquentes (ex: Annulation + Financier = frais cachés lors d'annulation).
- Intégrer dans les recommandations si pertinent.

---

### [SP-06] KPIs post-déploiement non définis

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Business-Logic |
| **Effort** | S |

**Risque** : Aucun KPI de succès pour évaluer si les recommandations fonctionnent. Le CODIR demandera : "Comment saurez-vous que c'est résolu ?"

**Action** :
- Définir 3–5 KPIs mesurables :
  - Note moyenne App Store → Cible +0.5★ à M+3
  - % avis Localisation/Langue → Cible -50% à M+6
  - Taux complétion réservation → baseline à mesurer
  - Spike Annulation/Réservation disparu → détection automatique (pipeline existant)
- Intégrer dans le rapport et la Fiche Projet.

---

### [SP-07] Scope MVP flou — pas de produit défini

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Critique |
| **Catégorie** | Business-Logic |
| **Effort** | M |

**Risque** : Le rapport dit "Audit i18n, détection auto locale" mais ne définit pas de produit. Est-ce un dashboard admin ? Un config panel utilisateur ? Un endpoint API ? Quel est le périmètre exact du Sprint Q2 ? Le jury demandera : "Qu'est-ce que vous livrez concrètement ?"

**Action** :
- Définir le scope MVP : fonctionnalité principale, périmètre (ce qui est inclus/exclu), critères go/no-go, stack technique.
- Rédiger 3–5 user stories concrètes.
- Intégrer dans la Fiche Projet.

---

## 🟠 4. Rigueur Méthodologique

### [RM-01] Gravité_texte très déséquilibrée — sous-estime certaines catégories

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Data-Integrity |
| **Effort** | M |

**Risque** : Bug Technique = 5% "Haute", Localisation/Langue = 3% "Haute" (2 avis sur 79). La Gravité_texte repose sur un lexique émotionnel qui ne capture que certains types de problèmes (Financier = 44% Haute grâce à "arnaque", "escroquerie"). Un bug bloquant l'app (100% d'impact) est classé "Basse" si le texte ne contient pas de mot-clé de gravité. La matrice de priorisation hérite de ce biais.

**Preuve** : "Application qui plante à chaque ouverture" = Bug Technique + Gravité_texte Basse (pas de mot-clé "arnaque").

**Action** :
- Envisager des métriques complémentaires : fréquence absolue, tendance temporelle, corrélation avec notes 1★.
- Documenter la limite de Gravité_texte dans le rapport : "mesure la véhémence, pas l'impact réel".
- Optionnel : pondérer par note (note 1 = multiplicateur ×2 sur la gravité).

---

### [RM-02] Matrice de priorisation sans IC — positions instables

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Data-Integrity |
| **Effort** | M |

**Risque** : L'axe Y de la matrice est "% Gravité_texte Haute". Pour Localisation/Langue, 3% Haute = 2 avis. Si un seul avis supplémentaire avait un mot-clé de gravité, le % passerait à 4.3% (+43%). Les positions sur la matrice sont **instables** et non reproductibles. Pas d'IC 95% sur les axes.

**Action** :
- Ajouter des barres d'erreur (IC 95% bootstrap) sur les deux axes de la matrice.
- Marquer les catégories avec n < 50 comme "positions approximatives".
- Ajouter une note méthodologique sur la sensibilité de la matrice.

---

### [RM-03] Seuil gap ≥ 3× arbitraire — pas de test statistique

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Data-Integrity |
| **Effort** | M |

**Risque** : Le seuil `GAP_THRESHOLD = 3.0` dans `3_analyse_problemes.py` est une règle ad hoc, pas un seuil statistique. Le gap Financier = 2.1× est exclu alors qu'il pourrait être significatif. Le gap Localisation = 53× est probablement significatif, mais aucun p-value ne le confirme. Pas de correction pour tests multiples (7 catégories testées).

**Action** :
- Remplacer le seuil fixe par un test de proportions (Fisher exact ou Chi² 2×2) par catégorie.
- Appliquer correction Bonferroni (7 tests → α = 0.05/7 = 0.0071).
- Conserver le ratio comme métrique descriptive, mais qualifier avec "significatif" / "non significatif".

---

### [RM-04] Cohen's Kappa sans IC ni analyse des désaccords

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Mineur |
| **Catégorie** | Data-Integrity |
| **Effort** | S |

**Risque** : κ = 0.663 sans intervalle de confiance (pas de bootstrap/jackknife). Les 29% reclassifiés (210 avis) ne sont pas analysés : la principale reclassification (Qualité du bien → Annulation/Réservation, 22 avis) pourrait **gonfler artificiellement** Annulation/Réservation dans le classement final.

**Action** :
- Ajouter IC 95% bootstrap sur le κ.
- Créer une matrice de confusion mots-clés × Ollama pour identifier les désaccords systématiques.
- Analyser si les reclassifications changent le top 5 des catégories.

---

### [RM-05] Confusion Cohen / Fleiss dans la documentation

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Mineur |
| **Catégorie** | Data-Integrity |
| **Effort** | S |

**Risque** : `decisions-techniques.md` justifie le choix par "reproductibilité Fleiss", mais le code implémente Cohen (comparaison 2 méthodes, pas N annotateurs). Le backlog C3 demande Fleiss' Kappa inter-annotateurs, ce qui est une chose différente. Un statisticien notera l'incohérence.

**Action** :
- Corriger `decisions-techniques.md` : clarifier "Cohen's Kappa (accord entre 2 méthodes de catégorisation)" vs "Fleiss' Kappa (à faire : accord inter-annotateurs humains)".
- Distinguer les deux métriques dans le notebook.

---

### [RM-06] Biais de confirmation Ollama — hint mots-clés dans le prompt

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Data-Integrity |
| **Effort** | M |

**Risque** : Le prompt Ollama inclut `Catégorie suggérée par mots-clés : {cat}`. Le LLM est donc **biaisé vers la catégorie mots-clés**, ce qui gonfle artificiellement le κ. Le Cohen's Kappa mesure alors l'accord entre "mots-clés" et "mots-clés validés par LLM", pas un vrai second avis.

**Preuve** : κ = 0.663 pourrait être > 0.8 si le hint est retiré (le LLM classerait indépendamment et l'accord réel serait plus informatif).

**Action** :
- Tester une variante du prompt SANS hint mots-clés.
- Rapporter les deux κ : avec hint (actuel) et sans hint (indépendant).
- Si κ sans hint < 0.5, c'est un signal que les mots-clés portent tout le travail et Ollama n'apporte rien.

---

### [RM-07] Horizons de recommandation non chiffrés

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Mineur |
| **Catégorie** | Business-Logic |
| **Effort** | S |

**Risque** : "Localisation/Langue : Sprint Q2" = 2–3 semaines. Mais l'action inclut "audit i18n + détection auto locale + test cross-devices". C'est réaliste seulement si une équipe backend i18n existe et est disponible. Pas de plan de rollout (phased, canary, etc.).

**Action** :
- Remplacer les horizons par des estimations d'effort (complexity points ou jours-homme).
- Lister les dépendances (équipe backend, accès config serveur, etc.).
- Distinguer "diagnostic" (rapide) de "correction" (dépend de l'org).

---

### [RM-08] RGPD et conformité non documentés

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Majeur |
| **Catégorie** | Business-Logic |
| **Effort** | S |

**Risque** : Le scraping d'avis publics (Google Play, App Store, Trustpilot) pose des questions RGPD : les pseudos d'utilisateurs sont potentiellement des données personnelles indirectes. Les CGU des plateformes interdisent généralement le scraping automatisé. Aucune analyse de conformité n'est documentée.

**Action** :
- Documenter que les avis scrapés sont publiquement accessibles (argument juridique).
- Vérifier que les pseudos ne sont pas stockés dans le CSV (ce n'est pas le cas — OK).
- Mentionner les CGU des plateformes comme risque connu.
- Documenter la dépendance à `google-play-scraper` (lib non officielle, reverse-engineering).

---

### [RM-09] Signal Booking : interprétation causale spéculative

| Champ | Valeur |
|-------|--------|
| **Sévérité CODIR** | Mineur |
| **Catégorie** | Business-Logic |
| **Effort** | S |

**Risque** : Le rapport conclut "fenêtre d'acquisition si Abritel corrige pendant que Booking se dégrade". C'est une **spéculation** : absence de données sur la cannibalisation réelle, pas d'analyse des causes du déclin Booking (produit, macro, saisonnalité ?). Le volume Booking augmente (354 → 593 avis/mois) ce qui peut mécaniquement diluer la note.

**Action** :
- Qualifier le signal Booking comme "observation" et non "opportunité confirmée".
- Ajouter : "corrélation ≠ causalité, analyse des causes Booking hors périmètre".
- Optionnel : vérifier si l'augmentation de volume explique la baisse de note (regression simple).

---

## Matrice de synthèse

| Priorité | Items | Effort total estimé |
|----------|-------|---------------------|
| **Sprint 1 — Urgence CODIR** | CR-01, CR-02, CR-03, CR-05, SP-06 | ~10h |
| **Sprint 2 — Livrables Fiche** | CR-04, SP-01, SP-04, SP-07, RM-08 | ~14h |
| **Sprint 3 — Crédibilité méthodo** | CR-06, RM-01, RM-02, RM-03, RM-06, SP-02 | ~16h |
| **Sprint 4 — Robustesse technique** | DT-01 à DT-09, RM-04, RM-05, RM-07, RM-09, SP-03, SP-05 | ~12h |

---

## Couverture vs backlog existant

Ce Master Backlog **absorbe et étend** le `backlog.md` existant :

| Backlog existant | Master Backlog | Ajouté |
|-----------------|----------------|--------|
| C1 (impact financier) | CR-05 | — |
| C2 (recadrer %) | CR-01 | Stratification par source |
| C3 (validation externe) | CR-06 | Détail Fleiss vs Cohen |
| C4 (personas) | SP-01 | Matrice impact croisée (SP-03) |
| C5 (MVP scope) | SP-07 | User stories |
| H1 (valeur pipeline) | — | Couvert par CR-05 |
| H2 (Chi² persona) | SP-02 | Analyse 100% négatif |
| H3 (IC gaps) | CR-03 | Fisher exact + Bonferroni |
| H4 (hint Ollama) | RM-06 | Mesure κ sans hint |
| H5 (experience maps) | SP-04 | — |
| H6 (KPIs) | SP-06 | — |
| H7 (conformité) | RM-08 | — |
| M1-M7 | DT-06 à DT-09 | — |
| B1-B5 | DT-03, RM-07 | — |
| — | CR-02 | **NOUVEAU** : Autre = 24% |
| — | DT-01 | **NOUVEAU** : Trustpilot __NEXT_DATA__ |
| — | DT-02 | **NOUVEAU** : Google Play lib |
| — | DT-04 | **NOUVEAU** : Dates invalides silencieuses |
| — | DT-05 | **NOUVEAU** : Few-shot Ollama |
| — | RM-01 | **NOUVEAU** : Gravité_texte déséquilibrée |
| — | RM-02 | **NOUVEAU** : Matrice sans IC |
| — | RM-03 | **NOUVEAU** : Seuil 3× arbitraire |
| — | RM-04 | **NOUVEAU** : Kappa sans IC |
| — | RM-05 | **NOUVEAU** : Cohen/Fleiss confusion |
| — | RM-09 | **NOUVEAU** : Signal Booking spéculatif |
| — | SP-03 | **NOUVEAU** : Conflit locataire/proprio |
| — | SP-05 | **NOUVEAU** : Catégorie secondaire ignorée |
