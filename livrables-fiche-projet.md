# Livrables Fiche Projet — Abritel

> Document de synthèse regroupant les livrables manquants identifiés lors de l'audit.
> Tous les chiffres proviennent du corpus de 726 avis Abritel (01/2025 — 04/2026).

---

## 1. Personas

### Persona 1 : Marie, Locataire occasionnelle

| Attribut | Valeur |
|----------|--------|
| **Profil** | Locataire (94% du corpus, n=682) |
| **Contexte** | Réserve 1-2 séjours/an pour les vacances familiales |
| **Canal principal** | Mobile (Google Play = 65% des avis locataires) |
| **Note moyenne** | 2.3/5 dans le corpus |
| **Frustrations principales** | Financier (18%), Localisation/Langue (11%), Annulation (9%) |

**Parcours type** : Marie cherche un logement, compare les prix, réserve. Au moment du paiement, le prix est affiché dans une devise étrangère ou ne correspond pas à ce qui était annoncé. En cas de problème, le remboursement est difficile à obtenir.

**Verbatims** :

> *"Site pas sérieux, lorsque vous annuler votre séjour c'est tout un bins, au final sur la totalité de la réservation on ne vous rembourse qu'une partie"*

> *"Avant le site abritel était en français, maintenant il est en anglais. Serait-il possible de le mettre en français car il m'est difficile de comprendre."*

> *"Impossible d'aller sur le site normalement... je tombe sur la version néo-zélandaise (!)"*

**Objectif** : Réserver un logement de vacances simplement, en français, avec un prix clair et une annulation sans frais cachés.

---

### Persona 2 : Pierre, Propriétaire multi-plateformes

| Attribut | Valeur |
|----------|--------|
| **Profil** | Propriétaire (6% du corpus, n=44) |
| **Contexte** | Gère 1-3 biens, présent sur Abritel + Airbnb + Booking |
| **Canal principal** | Trustpilot (sur-représenté dans les plaintes propriétaires) |
| **Note moyenne** | 1.0/5 dans le corpus (100% négatifs) |
| **Frustrations principales** | Service Client (25%), Bug Technique (20%), Qualité du bien/annonce (20%) |

**Parcours type** : Pierre publie son annonce, gère les réservations. Depuis la migration vers VRBO, il perd l'accès à son espace propriétaire, ne peut plus modifier ses annonces, et le service client est injoignable.

**Verbatims** :

> *"Ne faites pas confiance à Abritel ils sont terribles. Depuis la transition au site VRBO qui les a rachetés c'est une catastrophe."*

> *"Application affligeante, site internet plus lent qu'une tortue. Je suis hôte depuis plusieurs mois sur Abritel, Airbnb et Booking... Je n'ai JAMAIS eu de réservation avec Abritel."*

> *"Catastrophique, suppression de l'ancienne application propriétaire abritel. Plus d'accès à mon annonce et la gestion des réservations."*

**Objectif** : Gérer ses biens efficacement, recevoir des réservations, et avoir un interlocuteur fiable en cas de problème.

> **Limite méthodologique** : le persona Propriétaire est construit sur n=44 avis, tous négatifs (biais d'auto-sélection Trustpilot). Ce profil reflète les *plaignants*, pas l'ensemble des propriétaires Abritel. Un sondage dédié (n >= 200, source mixte) serait nécessaire pour un persona équilibré.

---

## 2. Experience Maps

### Experience Map — Locataire (Marie)

```
RECHERCHE          RÉSERVATION          PAIEMENT          SÉJOUR          POST-SÉJOUR
   │                   │                   │                 │                 │
   ▼                   ▼                   ▼                 ▼                 ▼
Recherche un     Sélectionne un      Procède au        Arrive sur        Laisse un
logement sur     logement, vérifie   paiement          place             avis
l'app/site       les dates                                               
   │                   │                   │                 │                 │
   ▼                   ▼                   ▼                 ▼                 ▼
PAIN POINTS :    PAIN POINTS :       PAIN POINTS :     PAIN POINTS :     PAIN POINTS :
                                                                         
• Site en        • Logement déjà     • Prix en          • Logement ne     • Pas de suivi
  anglais ou       loué affiché        devise             correspond        du signalement
  NZ (11%)         comme dispo         étrangère          pas aux photos  
• Filtres qui    • Annulation          (Localisation    • Annulation       • Remboursement
  ne persistent    opaque              /Langue 11%)       J-0 sans          long et partiel
  pas (UX 8%)     (Annulation 9%)   • Frais cachés       relogement        (Financier 18%)
                                      (Financier 18%)                    
   │                   │                   │                 │                 │
ÉMOTION :        ÉMOTION :           ÉMOTION :         ÉMOTION :         ÉMOTION :
Frustrée mais    Méfiante            En colère         Désemparée        Résignée
cherche encore                                                           → part sur
                                                                           Airbnb
```

**Catégories mappées par étape** :

| Étape | Catégorie | % corpus | Gravité texte Haute |
|-------|-----------|----------|---------------------|
| Recherche | Localisation/Langue | 10.5% | 3% |
| Recherche | UX/Ergonomie | 7.7% | 5% |
| Réservation | Annulation/Réservation | 9.1% | 8% |
| Paiement | Financier | 17.8% | 44% |
| Séjour | Qualité du bien | 12.7% | 3% |
| Post-séjour | Service Client | 10.2% | 11% |
| Transversal | Bug Technique | 8.4% | 5% |

### Experience Map — Propriétaire (Pierre)

```
INSCRIPTION      MISE EN LIGNE       RÉSERVATION REÇUE    GESTION           SUPPORT
   │                   │                   │                  │                 │
   ▼                   ▼                   ▼                  ▼                 ▼
Crée son         Publie son          Reçoit une          Gère le           Contacte le
compte hôte      annonce             demande de          calendrier        service client
                                     réservation                           
   │                   │                   │                  │                 │
   ▼                   ▼                   ▼                  ▼                 ▼
PAIN POINTS :    PAIN POINTS :       PAIN POINTS :       PAIN POINTS :     PAIN POINTS :
                                                                           
• Migration      • Perte d'accès     • Aucune            • Synchro         • Injoignable
  VRBO = perte     à l'annonce         réservation         impossible        ou non
  de compte        existante           malgré bonne        avec autres       francophone
  (Bug 20%)        (Bug 20%)           annonce             plateformes       (SC 25%)
                 • Interface                             • Calendrier      
                   affligeante                             désynchronisé    
   │                   │                   │                  │                 │
ÉMOTION :        ÉMOTION :           ÉMOTION :           ÉMOTION :         ÉMOTION :
Perdu            Frustré             Déçu                Épuisé            En colère
                                                                           → quitte
                                                                             Abritel
```

---

## 3. KPIs post-déploiement

| # | KPI | Baseline actuelle | Cible M+3 | Cible M+6 | Méthode de mesure |
|---|-----|-------------------|-----------|-----------|-------------------|
| 1 | **Note moyenne App Store** | ~2.0/5 (51 avis) | +0.3 (2.3/5) | +0.5 (2.5/5) | Pipeline automatisé (scraping mensuel) |
| 2 | **% avis Localisation/Langue** | 10.5% du corpus | -30% (7.3%) | -50% (5.2%) | Pipeline : ratio catégorie sur fenêtre glissante 3 mois |
| 3 | **% avis Gravité_texte Haute** | 18% du corpus | -20% (14.4%) | -30% (12.6%) | Pipeline : comptage automatique |
| 4 | **Disparition du spike Annulation** | Spike détecté (>2σ) | Pas de spike sur 4 semaines | Stable | Détection automatique (pipeline existant) |
| 5 | **Taux de reclassification Ollama** | 29% (210/726 avis) | Stable ±5% | Stable | κ Cohen sur chaque run |

> Ces KPIs sont mesurables automatiquement via le pipeline existant (`1_pipeline.py`), sans intervention manuelle. La valeur ajoutée du pipeline est précisément cette capacité de monitoring continu.

---

## 4. Scope MVP

### Problématique retenue

**Localisation/Langue** — Quick win, impact maximal, ratio 53x vs Airbnb (statistiquement significatif, test de Fisher p < 0.001).

### Solution proposée : Pipeline de monitoring i18n + Dashboard alertes

**Type de produit data** : Data Engineering + BI

| Inclus dans le MVP | Exclu (v2+) |
|---------------------|-------------|
| Pipeline de scraping automatisé (existant) | Détection automatique de la langue via NLP |
| Catégorisation hybride mots-clés + LLM (existant) | Intégration avec le backlog produit Abritel |
| Dashboard Power BI avec alertes par catégorie | A/B testing sur les corrections i18n |
| Détection de spikes temporels (existant) | Sondage propriétaires (n >= 200) |
| Rapport benchmark automatisé (existant) | Analyse de churn corrélée aux catégories |
| Export CSV pour équipes produit | API temps réel pour les équipes dev |

### Fonctionnalités clés

1. **Collecte continue** : scraping incrémental 3 sources, fusion + déduplication, export CSV
2. **Classification automatique** : double catégorisation (mots-clés + LLM local) avec validation croisée (κ = 0.66)
3. **Alertes** : détection de spikes par catégorie (>2σ + 5pp), circuit breaker si source indisponible
4. **Benchmark** : positionnement vs Airbnb/Booking avec tests statistiques (Fisher exact + Bonferroni)
5. **Dashboard** : visualisation Power BI avec filtres source/catégorie/période/gravité

### Critères go/no-go

| Critère | Go | No-go |
|---------|-----|-------|
| Pipeline stable | 3 runs consécutifs sans erreur | Scraper cassé > 7 jours |
| Qualité classification | κ > 0.6 | κ < 0.4 |
| Couverture | 3 sources actives | < 2 sources |
| Data freshness | CSV < 7 jours | CSV > 30 jours |

### User Stories

| # | Story | Priorité |
|---|-------|----------|
| US1 | En tant que PM, je veux voir le top 5 des problèmes par catégorie ce mois-ci pour prioriser le backlog | Haute |
| US2 | En tant que PM, je veux comparer nos taux de problèmes à Airbnb/Booking pour identifier nos faiblesses spécifiques | Haute |
| US3 | En tant que dev lead, je veux recevoir une alerte si une catégorie spike (>2σ) pour réagir rapidement | Moyenne |
| US4 | En tant que data analyst, je veux un export CSV avec toutes les colonnes enrichies pour faire mes propres analyses | Moyenne |
| US5 | En tant que directeur produit, je veux un rapport mensuel automatisé avec benchmark et recommandations | Basse |

---

## 5. Risques et Conformité

### Risques liés aux données

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|------------|
| **Trustpilot change sa structure HTML** (`__NEXT_DATA__` disparaît) | Moyenne | Haute — perte d'une source (28% corpus) | Test contractuel hebdomadaire (lundi 8h), fallback CSS selectors à implémenter |
| **Google Play bloque le scraping** (API non officielle) | Faible | Haute — perte source principale (65%) | Version épinglée (`>=1.2.7,<2`), monitoring circuit breaker |
| **Biais d'auto-sélection Trustpilot** | Certaine | Moyenne — sur-estimation des négatifs | Documenté, analyses stratifiées par source, caveat méthodologique |
| **Avis courts non classifiables** (24% "Autre") | Certaine | Faible — bruit, pas de signal perdu | Décomposition Autre en 4 sous-types, LLM pour avis courts |
| **Dérive du modèle LLM** (changement de version Ollama) | Faible | Moyenne — perte de reproductibilité | Temperature 0, version modèle documentée, hash mots-clés |

### Conformité réglementaire (RGPD)

| Point | Statut | Justification |
|-------|--------|---------------|
| **Données personnelles** | Conforme | Aucun pseudo, nom ou identifiant stocké. CSV contient uniquement : date, note, texte, source |
| **Données publiques** | Conforme | Tous les avis sont publiquement accessibles sur Google Play, App Store et Trustpilot |
| **Traitement local** | Conforme | Ollama tourne en local — aucune donnée transmise à un tiers |
| **CGU plateformes** | Risque accepté | Le scraping automatisé peut violer les CGU de Google, Apple et Trustpilot. Risque accepté dans le cadre d'un projet académique |
| **Droit à l'oubli** | Non applicable | Pas de base de données utilisateurs, pas de collecte de données personnelles |

### Considérations éthiques

- **Biais algorithmique** : les mots-clés sont optimisés sur le vocabulaire Abritel, sous-estimant potentiellement les problèmes chez les concurrents. Ce biais est documenté et conservateur (renforce les conclusions si Abritel est pire malgré ce biais).
- **Représentativité** : le corpus (726 avis) ne représente pas l'ensemble des utilisateurs Abritel. Les pourcentages reflètent la distribution des *avis publics scrapés*, pas la prévalence réelle dans la base utilisateurs.
- **Manipulation potentielle** : les avis publics peuvent être faux (astroturfing). Aucune détection de faux avis n'est implémentée.

---

## 6. Estimation d'impact financier (proxy)

### Hypothèses

| Paramètre | Valeur | Source |
|-----------|--------|--------|
| Facteur multiplicateur silencieux | ×26 | Lee Resources International : pour 1 plainte publique, 26 clients insatisfaits ne disent rien |
| Panier moyen Abritel | ~800 EUR/réservation | Estimation marché location vacances France |
| Taux de churn post-insatisfaction | 50% | Étude Zendesk : 50% des clients quittent après 1 mauvaise expérience |

### Estimation par catégorie (Abritel, corpus 726 avis)

| Catégorie | N avis négatifs | Clients silencieux estimés (×26) | Churn estimé (50%) | Revenus perdus/an (×800 EUR) |
|-----------|----------------|----------------------------------|--------------------|-----------------------------|
| **Financier** | 129 | 3 354 | 1 677 | ~1.3M EUR |
| **Qualité du bien** | 92 | 2 392 | 1 196 | ~957K EUR |
| **Localisation/Langue** | 76 | 1 976 | 988 | ~790K EUR |
| **Service Client** | 74 | 1 924 | 962 | ~770K EUR |
| **Annulation/Réservation** | 66 | 1 716 | 858 | ~686K EUR |
| **Bug Technique** | 61 | 1 586 | 793 | ~634K EUR |
| **UX/Ergonomie** | 56 | 1 456 | 728 | ~582K EUR |

> **Avertissement** : ces chiffres sont des *ordres de grandeur* basés sur des hypothèses documentées, pas des mesures exactes. Le facteur ×26 est une moyenne sectorielle, le panier moyen et le taux de churn sont des estimations. L'objectif est de donner un ordre d'idée au CODIR pour arbitrer les priorités, pas de fournir un P&L précis. Un croisement avec les données internes (tickets support, churn réel, LTV) affinerait considérablement ces estimations.

---

## 7. Matrice d'impact croisée Locataire / Propriétaire

| Recommandation | Impact Locataire | Impact Propriétaire | Trade-off |
|----------------|-----------------|---------------------|-----------|
| **Fix Localisation/Langue** (i18n) | Positif : navigation en français, prix en EUR | Positif : plus de locataires français = plus de réservations | Aucun conflit |
| **Annulation flexible** | Positif : annulation sans frais cachés | **Négatif** : annulations tardives = logement vide | Mitigation : assurance annulation, politique dégressive (J-30 gratuit, J-7 50%, J-0 100%) |
| **Remboursement 7j garanti** | Positif : confiance accrue | **Négatif** : cash-flow propriétaire impacté | Mitigation : Abritel avance le remboursement, récupère sur le propriétaire si litige |
| **Stabilité app (bugs)** | Positif : moins de crashes | Positif : accès fiable à l'espace propriétaire | Aucun conflit |
| **Service Client francophone** | Positif : résolution plus rapide | Positif : interlocuteur compétent | Aucun conflit |
| **Vérification photos** | Positif : logement conforme aux photos | **Négatif** : charge admin supplémentaire | Mitigation : checklist simplifiée, IA de vérification photo |

> Les recommandations Localisation, Bug Technique et Service Client sont **win-win**. Les recommandations Annulation et Financier nécessitent un arbitrage avec mitigation explicite pour le propriétaire.

---

## 8. Stratégie de lancement

### Phase 1 — Immédiat (Sprint Q2, semaines 1-4)

| Action | Responsable | Livrable |
|--------|-------------|----------|
| Audit i18n complet (devise, langue, géolocalisation) | Équipe backend | Liste des endpoints retournant du contenu non localisé |
| Fix détection automatique de la locale | Équipe frontend | Config navigateur → devise EUR + langue FR |
| Sprint stabilité (login, auth, crashes) | Équipe mobile | Crash rate < 1%, temps de connexion < 3s |
| Activation monitoring pipeline | Data team | Dashboard Power BI + alertes Slack sur spikes |

### Phase 2 — Roadmap Q3 (semaines 5-12)

| Action | Responsable | Livrable |
|--------|-------------|----------|
| Refonte processus annulation | Product + Legal | Politique annulation claire, dégressive, communiquée avant réservation |
| SLA remboursement 7 jours | Finance + Product | Process automatisé, tracking visible pour le locataire |
| Routage service client francophone | Support ops | Temps de réponse < 5 min pour FR, escalade humaine garantie |

### Phase 3 — Roadmap Q4 (semaines 13-24)

| Action | Responsable | Livrable |
|--------|-------------|----------|
| Vérification qualité des annonces | Trust & Safety | Score fraîcheur, checklist photo, alertes annonces obsolètes |
| Deep linking sans téléchargement forcé | Équipe mobile + web | Lien web → contenu sans redirect app obligatoire |

### Déploiement

- **Approche progressive** : canary release (5% → 25% → 100%) pour les changements app
- **Feature flags** pour les corrections i18n (rollback rapide si régression)
- **Monitoring continu** via le pipeline existant : comparaison avant/après par catégorie
