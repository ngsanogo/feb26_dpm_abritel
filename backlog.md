# Backlog — Projet Abritel

Priorisé par impact sur la crédibilité CODIR. Les items "Critique" sont des bloquants de présentation.

---

## CRITIQUE — Bloquants CODIR

| # | Tâche | Pourquoi | Effort |
|---|-------|----------|--------|
| **C1** | **Estimer l'impact financier par catégorie** — Calculer un proxy de revenus perdus (nb avis négatifs × facteur multiplicateur silencieux × panier moyen Abritel) pour chaque problème. Ajouter une colonne "€/mois estimé" à la matrice de priorisation | Le CEO demande "combien ça coûte", pas "quel %" | M |
| **C2** | **Recadrer les pourcentages** — Partout remplacer "25% des utilisateurs" par "25% des avis négatifs". Ajouter un encadré méthodologique explicite sur le biais de sélection (Trustpilot 100% négatif, corpus ≠ base utilisateurs) | Évite la question 1 du CODIR qui démonte toute la crédibilité | S |
| **C3** | **Validation externe de la taxonomie** — Faire annoter 50-100 avis par 2-3 personnes du groupe (sans accès aux mots-clés), calculer le Fleiss' Kappa inter-annotateurs, comparer avec le pipeline | Répond à la question 3 : "un expert externe a validé ?" | L |
| **C4** | **Formaliser les personas** — 2 personas (Locataire type, Propriétaire type) avec données du corpus : parcours, frustrations, verbatims. Livrable manquant de la Fiche Projet | Requis par la Fiche Projet, actuellement absent | M |
| **C5** | **Rédiger le scope MVP** — Décrire la fonctionnalité proposée (scope, périmètre, critères go/no-go), pas juste "fixer Localisation". Livrable manquant de la Fiche Projet | Requis par la Fiche Projet, actuellement absent | M |

---

## HAUTE — Renforce significativement la présentation

| # | Tâche | Pourquoi | Effort |
|---|-------|----------|--------|
| **H1** | **Articuler la valeur ajoutée du pipeline vs lecture manuelle** — Ajouter un slide/section "Pourquoi cette approche ?" : quantification, benchmark concurrentiel reproductible, signal temporel, détection automatique de dégradation | Répond à la question 5 du CODIR | S |
| **H2** | **Corriger le Chi² persona** — Soit retirer le test (n=44, effectifs attendus < 5), soit le présenter comme "exploratoire, non conclusif" avec un warning explicite. Ne plus écrire "satisfait Bonferroni" (p=0.031 > α_corrigé=0.0125) | Un statisticien dans le jury le verra | S |
| **H3** | **Ajouter des tests de significativité sur les gaps benchmark** — Bootstrap CI 95% sur les ratios Abritel/concurrent par catégorie. Un gap de 2.1× avec CI [0.8, 3.4] n'est pas la même chose qu'un gap de 53× | Les gaps à 2-3× sont peut-être du bruit | M |
| **H4** | **Séparer le hint mots-clés du prompt Ollama** — Tester une variante du prompt SANS `Catégorie suggérée par mots-clés : {cat}` pour mesurer le vrai κ indépendant. Rapporter les deux scores | Neutralise l'objection du biais de confirmation circulaire | M |
| **H5** | **Rédiger les experience maps** — Journey locataire (recherche → réservation → séjour → post-séjour) avec les pain points issus des catégories. Livrable manquant Fiche Projet | Requis par la Fiche Projet | M |
| **H6** | **Définir 3-5 KPIs de succès post-déploiement** — Ex : note moyenne App Store à M+3, % avis Localisation/Langue à M+3, taux de complétion réservation. Livrable manquant Fiche Projet | Requis par la Fiche Projet | S |
| **H7** | **Ajouter l'analyse risques/conformité** — RGPD (scraping avis publics, stockage, pas de données personnelles directes mais pseudos possibles), dépendance aux APIs tierces, maintenabilité post-projet | Livrable manquant Fiche Projet | S |

---

## MOYENNE — Améliore la robustesse technique

| # | Tâche | Pourquoi | Effort |
|---|-------|----------|--------|
| **M1** | **Épingler les dépendances** — `pandas>=2.2,<3`, `playwright>=1.58,<2`, etc. dans `pyproject.toml` | Évite la casse silencieuse à la prochaine `uv sync` | S |
| **M2** | **Déplacer Playwright en dépendance optionnelle** — `[project.optional-dependencies] trustpilot = ["playwright>=1.58"]` | 50 MB de Chromium inutiles si on ne scrape pas Trustpilot | S |
| **M3** | **Ajouter 10 tests sur données réelles annotées** — Prendre 10 avis réels, les annoter manuellement, vérifier que le pipeline est d'accord. Premier vrai test de qualité (pas tautologique) | Les 151 tests actuels ne valident pas la justesse métier | M |
| **M4** | **Paralléliser le benchmark** — `ThreadPoolExecutor` dans `1_benchmark.py` pour scraper les 3 marques en parallèle | Passe de 15-90 min à 5-30 min | S |
| **M5** | **Documenter le facteur multiplicateur silencieux** — Citer une source (ex : pour 1 plainte publique, X utilisateurs partent sans rien dire). Hypothèse explicite plutôt qu'implicite | Rend l'estimation financière C1 défendable | S |
| **M6** | **Corriger le circuit breaker CI** — Retirer `ABRITEL_SOFT_CIRCUIT_BREAKER` ou le rendre bruyant (warning → error) pour que le monitoring détecte les pannes de scraper | Un scraper meurt → personne ne le sait → données périmées | S |
| **M7** | **Lever le plafond App Store** — Ajouter un paramètre `max_pages` configurable ou documenter la limite de 500 avis comme limitation connue | Perte silencieuse de données si volume augmente | S |

---

## BASSE — Si le temps le permet

| # | Tâche | Pourquoi | Effort |
|---|-------|----------|--------|
| **B1** | **Ajouter un flag `--full-rescrape`** à `1_pipeline.py` pour forcer `date_debut = DATE_DEBUT_INCLUSIVE` sans cache | La marge de 7 jours peut rater des avis retardés | S |
| **B2** | **Découper `pipeline.py`** — Extraire `_detect_spikes()`, `_enrichir_version()`, `_exporter_csv()` dans des modules séparés | 700+ lignes = God module, maintenance difficile | L |
| **B3** | **Améliorer la négation** — Gérer "arnaque ? Non c'est pire", "definitely not a scam", négation post-posée | Cas rares mais embarrassants si montrés en démo | M |
| **B4** | **Ajouter des tests de performance** — 10k avis synthétiques à travers `enrichir()`, mesurer temps + mémoire | Prouver que le pipeline scale si un jury demande | M |
| **B5** | **Stratégie de lancement** — Go-to-market du MVP, plan de déploiement, timeline. Livrable Fiche Projet | Dernier livrable manquant, le moins critique pour un projet data | M |

---

## Légende effort

- **S** = Small (< 2h)
- **M** = Medium (2-4h)
- **L** = Large (> 4h)

## Ordre de bataille suggéré

**Sprint 1 (urgence CODIR)** : C2 → C1 → H1 → H2 → H6 → H7
**Sprint 2 (livrables Fiche)** : C4 → C5 → H5 → M5
**Sprint 3 (crédibilité méthodologique)** : C3 → H3 → H4 → M3
**Sprint 4 (robustesse technique)** : M1 → M2 → M4 → M6 → M7

Les items B* sont du "si on a le temps la veille de la soutenance".
