# Décisions techniques — Justification exhaustive

> Document créé le 2026-04-18.  
> Cible : tout lecteur qui veut comprendre **pourquoi** chaque choix a été fait, pas seulement ce qui a été fait.  
> Chaque section suit le format : **Décision → Pourquoi → Alternatives rejetées**.

---

## 1. Périmètre temporel : `DATE_DEBUT_INCLUSIVE = date(2025, 1, 1)`

**Décision** : date fixe au 01/01/2025, pas une fenêtre glissante.

**Pourquoi** :
- L'objectif de l'analyse est de comprendre les problèmes vécus par les utilisateurs depuis le début de l'exercice 2025. Une fenêtre glissante (ex. 18 mois) produirait des résultats qui changent à chaque run, rendant toute comparaison temporelle non reproductible.
- Les décideurs (PM, Direction Produit) ont besoin d'une base stable : "depuis le 1er janvier 2025, combien d'avis bug technique ?". Avec une fenêtre glissante, la réponse changerait chaque semaine.
- Le pipeline est **incrémental** : le premier run collecte depuis le 01/01/2025, les runs suivants ne scrapent que les nouveaux avis. La date fixe est donc le seul coût non-récurrent.

**Alternatives rejetées** :
- *Fenêtre glissante de 18 mois* : couramment utilisée dans les dashboards, mais nuit à la reproductibilité analytique et aux comparaisons YoY.
- *Date dynamique paramétrable par CLI* : ajouterait de la complexité et du risque d'incohérence entre runs.

---

## 2. Scraping incrémental : marge de 7 jours

**Décision** : en mode incrémental, on rescrape à partir de `date_max_csv - 7 jours`.

**Pourquoi** :
- Les avis peuvent apparaître avec retard sur les stores (modération, cache CDN, décalage de fuseau). Une marge de 0 jour manquerait des avis publiés à la dernière seconde du jour précédent.
- 7 jours est un compromis entre couverture (évite les trous) et performance (limite les appels réseau inutiles).
- La déduplication sur `(source, date, note, texte)` garantit qu'aucun doublon n'est introduit par cette marge.
- Avec une fenêtre trop courte (ex. 1 jour), le circuit breaker serait trop sensible : une source qui retourne 0 avis sur une fenêtre de 24h n'est pas forcément cassée.

**Alternatives rejetées** :
- *0 jour* : trop risqué (avis manqués sur les bords).
- *14 jours* : augmenterait inutilement la charge de scraping à chaque run.
- *Marge paramétrable* : ajouterait de la configuration sans bénéfice opérationnel réel.

---

## 3. Normalisation NFD pour le matching de mots-clés

**Décision** : `normaliser_texte()` convertit en minuscules + décompose NFD + retire les marques de combinaison (Unicode cat `Mn`). Les mots-clés dans `_CATEGORIES_KEYWORDS` sont stockés sans accents.

**Pourquoi** :
- Les avis utilisateurs mélangent français accentué, français sans accents (mobile, AZERTY sans accents), et même de l'anglais. Le matching doit être robuste à toutes ces variantes.
- NFD (Canonical Decomposition) décompose "é" en "e" + accent (U+0301). Retirer les marques de combinaison (`Mn`) donne "e". C'est la méthode Unicode standard et sans perte pour ce cas d'usage.
- Stocker les mots-clés sans accents simplifie leur maintenance : le mainteneur n'a pas à se souvenir d'écrire "remboursé" ou "rembourse".
- L'alternative NFC (composition) ou NFKD ne changerait pas le résultat pour les cas réels, mais NFD est la forme de décomposition canonique recommandée.

**Alternatives rejetées** :
- *Regex avec alternatives* (`rembours[eé]`) : fragile, non maintenable à l'échelle de 200+ mots-clés.
- *unidecode* : bibliothèque externe, translittère aussi les caractères non-latins (japonais → romaji), comportement non souhaité.
- *Fuzzy matching* : trop lent pour un passage sur tous les avis à chaque run, et introduit des faux positifs.

---

## 4. Catégorisation par score additif (count de mots-clés)

**Décision** : `categoriser_avis_multi()` compte combien de mots-clés de chaque catégorie sont présents dans le texte. La catégorie principale = score max ; en cas d'ex-æquo, l'ordre de `_CATEGORIES_KEYWORDS` prime (tri stable).

**Pourquoi** :
- Robuste à la longueur variable des avis : un avis court avec 1 mot-clé bien ciblé est correctement classé.
- Permet la multi-catégorisation (`Catégorie_secondaire`) : si un avis parle de remboursement ET de bug, les deux sont capturés.
- Le tri stable sur `_CATEGORIES_KEYWORDS` donne un tie-breaking déterministe et prévisible. L'ordre de la liste reflète la priorité métier (Financier > Bug Technique > UX plutôt que UX > Financier par exemple).
- Simple à comprendre, à déboguer et à maintenir : un PM peut lire la liste et suggérer des ajouts de mots-clés directement.

**Alternatives rejetées** :
- *TF-IDF* : nécessite un corpus de référence, résultats instables quand le volume d'avis est faible (< 100 par catégorie).
- *Embeddings sémantiques* : coûteux en calcul, overkill quand les catégories sont bien délimitées et les mots-clés suffisamment discriminants.
- *Poids différentiels par mot-clé* : ajouterait de la complexité de maintenance sans gain prouvé à ce stade du MVP.
- *Modèle de classification supervisé* : nécessite des données étiquetées que nous n'avons pas au démarrage.

---

## 5. Ordre des catégories dans `_CATEGORIES_KEYWORDS`

**Décision** : `Localisation / Langue` → `Annulation / Réservation` → `Financier` → `Bug Technique` → `UX / Ergonomie` → `Service Client` → `Qualité du bien`.

**Pourquoi** (tie-breaking en cas d'ex-æquo) :
- **Localisation / Langue** en premier : les problèmes de langue/devise ont des mots-clés très spécifiques (devises, noms de pays) qui ne se retrouvent presque jamais dans d'autres catégories. Risque de faux positifs quasi nul.
- **Annulation / Réservation** avant Financier : une annulation entraîne souvent un problème financier (remboursement). En cas de co-occurrence, le problème originel (annulation) est prioritaire pour l'action produit.
- **Financier** avant Bug Technique : un bug de paiement est classé Financier (impact direct sur l'utilisateur) plutôt que Bug Technique (problème applicatif générique).
- **Bug Technique** avant UX : un bug (application plantée) est plus grave qu'une mauvaise ergonomie.
- **Service Client** après UX : le service client est souvent mentionné en réaction à un autre problème. La catégorie primaire doit refléter la cause.
- **Qualité du bien** en dernier avant "Autre" : les mots-clés (logement, appartement, photo...) sont larges et risquent de matcher des avis qui décrivent simplement le logement sans problème.

**Alternatives rejetées** :
- *Ordre alphabétique* : arbitraire, sans lien avec la réalité métier.
- *Ordre par volume d'avis attendu* : instable, changerait à chaque run.

---

## 6. Catégorie « Autre » et `sous_cat_autre()`

**Décision** : les avis sans aucun mot-clé sont classés « Autre ». `sous_cat_autre(note, longueur_texte)` les décompose en : `positif court` / `négatif non catégorisé` / `neutre`.

**Seuils choisis** :
- `positif court` : note ≥ 4 ET longueur ≤ 15 mots → avis du type "Super !", "Très bien !", non actionnable.
- `négatif non catégorisé` : note ≤ 2 ET longueur ≥ 30 mots → avis négatif détaillé dont les mots-clés manquent au modèle.
- `neutre` : tout le reste.

**Pourquoi ces seuils** :
- 15 mots est empiriquement la limite entre un avis "court" (une phrase) et un avis qui donne du contexte. En dessous de 15 mots, un avis positif est rarement actionnable.
- 30 mots est le seuil à partir duquel un avis contient suffisamment d'information pour être analysé qualitativement. Un avis négatif long sans mots-clés connus est le signal le plus précieux pour enrichir le modèle.
- Note ≤ 2 pour les négatifs : capture les avis 1 et 2 étoiles (insatisfaits). Note 3 est ambiguë (neutre).
- Note ≥ 4 pour les positifs : capture les avis satisfaits. Note 3 est exclu.

**Pourquoi cette décomposition** :
- Les avis « Autre » sont hétérogènes : 80% sont des "Super !" non actionnables, 20% sont des plaintes sans mots-clés. Les traiter identiquement noierait les signaux importants.
- `négatif non catégorisé` est la liste des avis à relire manuellement pour enrichir `_CATEGORIES_KEYWORDS`.
- Power BI peut filtrer sur `Autre_type = "négatif non catégorisé"` pour un backlog de travail.

**Alternatives rejetées** :
- *Pas de décomposition* : « Autre » reste une boîte noire non actionnable.
- *Clustering LDA/K-means* : overkill pour le MVP, résultats difficiles à interpréter sans expertise NLP.

---

## 7. Évaluation de la gravité

**Décision** : 3 niveaux (Haute / Moyenne / Basse), déterminés par la combinaison note + mots-clés forts + catégorie.

**Règles exactes** :
1. Mots-clés de gravité haute (arnaque, escroc, tribunal, fraud...) dans le texte → `Haute` (sauf si niés par "pas arnaque", "aucune escroquerie"...).
2. Note = 1 → `Haute`.
3. Note = 2 + catégorie dans {Bug Technique, Financier, Annulation/Réservation} → `Haute` (ces catégories ont un impact direct sur l'utilisateur).
4. Note = 2 autre catégorie → `Moyenne`.
5. Note ≥ 3 → `Basse`.

**Pourquoi** :
- Un avis 1 étoile est par définition une mauvaise expérience grave, indépendamment du texte.
- Note 2 + Bug Technique / Financier / Annulation : ces catégories impliquent un impact financier ou une perte de service. Même à 2 étoiles, l'impact est Haute.
- La négation (`_NEGATION_RE`) évite de classifier Haute un avis du type "pas d'arnaque, très sérieux".
- 3 niveaux est le minimum pour un tri actionnable en backlog : Haute = urgence, Moyenne = à planifier, Basse = monitoring.

**Alternatives rejetées** :
- *5 niveaux* : trop de granularité, difficile à utiliser dans un dashboard de priorisation.
- *Gravité uniquement basée sur la note* : ignore le contenu textuel qui peut être très grave à 2 étoiles.
- *Score continu* : difficile à filtrer en Power BI et à communiquer aux parties prenantes.

---

## 8. Validation Ollama : modèle `gemma4:31b`, mode `all`, temperature 0

### 8.1 Pourquoi Ollama (LLM local) en plus des mots-clés

**Décision** : après la catégorisation par mots-clés, chaque avis passe par un LLM local (Ollama) qui valide ou corrige la catégorie.

**Pourquoi** :
- Les mots-clés sont efficaces pour les cas clairs mais échouent sur : l'ironie ("super, encore un bug !"), les synonymes non listés, les avis ambigus multi-thèmes.
- Un LLM comprend le sens, pas juste la présence de mots. Il peut distinguer "l'annulation de ma réservation m'a coûté cher" (Financier ou Annulation ?) selon le contexte.
- La qualité des données downstream (Power BI, priorisation produit) vaut l'investissement en temps de calcul (1h à 4h accepté explicitement par l'utilisateur).

**Pourquoi local (Ollama) et non une API cloud** :
- Les avis contiennent des données personnelles (mentions de montants, noms de propriétaires, textes potentiellement sensibles). Les envoyer à une API tierce (OpenAI, Anthropic) créerait un risque RGPD.
- Pas de coût variable à l'usage : 10 000 avis coûtent la même chose que 100 avis.
- Reproductibilité : le modèle local ne change pas entre deux runs sans action explicite.

### 8.2 Pourquoi `gemma4:31b`

**Décision** : modèle par défaut recommandé `gemma4:31b` (configuré par `ABRITEL_OLLAMA_MODEL`).

**Pourquoi** :
- 31 milliards de paramètres : suffisant pour la classification de texte court avec contexte, supérieur aux modèles 7-8B en précision de catégorisation.
- Gemma 4 (famille Google) : fort en classification structurée avec sortie JSON, bon suivi d'instructions.
- Tourne en local sur du matériel grand public (Mac M-series avec 64 GB RAM).
- L'utilisateur a confirmé utiliser `gemma4:31b` — ce choix est validé par la pratique.

**Alternatives mentionnées dans la config** :
- `llama3.1:8b` : plus rapide, qualité moindre sur les cas ambigus.
- `mistral:7b` : bon rapport qualité/vitesse, mais inférior à 31B pour les nuances culturelles (avis FR).

### 8.3 Pourquoi mode `all` (tous les avis, pas seulement « Autre »)

**Décision** : `ABRITEL_OLLAMA_MODE=all` — le LLM valide chaque avis, qu'il ait été classé par mots-clés ou non.

**Pourquoi** :
- Les mots-clés peuvent classer un avis Financier alors qu'il parle en réalité d'un problème de Service Client avec mention de remboursement. Le LLM corrige ces cas.
- Le mode `autre` (LLM seulement sur les avis « Autre ») laisse les avis catégorisés par mots-clés sans validation — un compromis de performance non adapté à l'objectif de qualité maximale.
- La qualité downstream (priorisation, dashboard) justifie le temps de calcul supplémentaire.

### 8.4 Pourquoi temperature 0

**Décision** : `"options": {"temperature": 0}` dans le payload Ollama.

**Pourquoi** :
- Temperature 0 = comportement déterministe. Le même avis produit toujours la même catégorie entre deux runs, ce qui est essentiel pour la reproductibilité analytique.
- Une temperature > 0 introduit de l'aléatoire : deux runs successifs sur les mêmes avis pourraient produire des catégories différentes, rendant les comparaisons temporelles invalides.
- La tâche (classification dans une liste fermée) ne bénéficie pas de la créativité qu'apporte une temperature élevée.

### 8.5 Pourquoi 3 tentatives avec backoff exponentiel

**Décision** : `_OLLAMA_MAX_RETRIES = 3`, backoff `2^attempt` secondes.

**Pourquoi** :
- Ollama peut retourner une réponse JSON mal formée ou une catégorie invalide sur le premier essai, surtout sur des avis très courts ou ambigus.
- 3 tentatives est le compromis entre résilience (donne au modèle une 2e/3e chance sur les cas difficiles) et temps total (4 tentatives multiplieraient le temps d'exécution pour les avis difficiles).
- Backoff exponentiel (1s, 2s, 4s) : évite de surcharger le service si Ollama est temporairement lent.

### 8.6 Pourquoi 4 workers parallèles (`ThreadPoolExecutor(max_workers=4)`)

**Décision** : 4 appels Ollama simultanés.

**Pourquoi** :
- Ollama expose une API HTTP et peut traiter plusieurs requêtes en parallèle (pipeline GPU).
- 4 workers est empiriquement le sweet-spot sur un Mac M-series : au-delà, la mémoire GPU est saturée et les temps de réponse augmentent.
- En dessous de 4 (ex. 1 ou 2), le temps de traitement est inutilement allongé.
- L'ordre de traitement n'est pas garanti avec `as_completed`, mais la tâche est stateless par avis.

---

## 9. Cache incrémental Ollama

**Décision** : les avis déjà validés par Ollama (colonne `Catégorie_ollama` non vide) ne repassent pas par le LLM lors des runs suivants, sauf si les mots-clés ont changé (`force_rerun=True`).

**Pourquoi** :
- Temperature 0 garantit que repasser le même avis par le même modèle donnerait le même résultat. Le cache ne sacrifie pas la qualité.
- Sur 1000 avis, si 900 ont déjà été validés, on n'appelle Ollama que pour les 100 nouveaux → temps de run réduit de 90%.
- La colonne `Catégorie_ollama` est préservée dans `_fusionner()` (côté `ancien`) : les nouvelles fusions n'écrasent pas le cache.

**Mécanisme `force_rerun`** :
- Si les mots-clés changent entre deux runs (détecté par hash MD5), les suggestions mots-clés envoyées au LLM ont changé. Pour cohérence, tous les avis repassent par Ollama (`force_rerun=True`).

---

## 9.1 Sauvegarde progressive Ollama (checkpoint CSV)

**Décision** : le callback `on_progress()` est invoqué après chaque `_CHECKPOINT_BATCH_SIZE = 25` avis traités par Ollama, permettant une sauvegarde intermédiaire du CSV (`strict=False`).

**Pourquoi** :
- Ollama peut être long (1h+ sur 700+ avis avec gemma4:31b). Une interruption (Ctrl+C, crash Ollama, OOM) perdrait tout le travail effectué.
- Le checkpoint tous les 25 avis crée un point de récupération sans surcharger l'I/O (~28 sauvegardes pour 700 avis).
- Au redémarrage, le cache incrémental (section 9) détecte les `Catégorie_ollama` déjà remplies et skip ces avis automatiquement.
- `strict=False` lors du checkpoint : la validation complète (colonnes, catégories valides) est faite une seule fois à l'export final.

**Alternatives rejetées** :
- *Pas de checkpoint* : perte totale du travail en cas d'interruption.
- *Checkpoint à chaque avis* : surcharge I/O excessive (~700 écritures CSV).
- *Checkpoint tous les 100 avis* : trop espacé, perte de ~100 avis en cas de crash.
- *Base SQLite intermédiaire* : complexité ajoutée sans bénéfice (le CSV est l'unique format de sortie).

---

## 10. Hash MD5 des mots-clés (`_keywords_hash()`)

**Décision** : hash MD5 tronqué à 8 caractères de `str(_CATEGORIES_KEYWORDS)`, stocké dans `pipeline_meta.json`.

**Pourquoi** :
- Permet de détecter automatiquement si un développeur a modifié `_CATEGORIES_KEYWORDS` entre deux runs.
- Si le hash change → warning dans les logs + `force_rerun=True` pour Ollama (recatégoriser tous les avis avec les nouveaux keywords comme hint).
- MD5 est non-cryptographique ici : on ne cherche pas la sécurité mais la détection de changements. 8 chars suffisent pour distinguer les versions.
- `str(_CATEGORIES_KEYWORDS)` inclut l'ordre ET le contenu : un réordonnancement de mots-clés change le hash (ce qui est correct, car le tie-breaking de score en dépend).

**Alternatives rejetées** :
- *SHA-256* : overkill pour un usage de traçabilité non-cryptographique.
- *Version manuelle* : erreur-prone (oubli de mise à jour).
- *Pas de détection* : risque de données incohérentes (anciens avis classés avec l'ancien modèle, nouveaux avec le nouveau).

---

## 11. Circuit breaker

**Décision** : si une source retourne 0 avis en mode incrémental alors qu'elle en avait dans le CSV existant → warning + exit code 1 en CI (ou warning seul en local avec `ABRITEL_SOFT_CIRCUIT_BREAKER=1`).

**Pourquoi** :
- Une source qui retourne subitement 0 avis signale probablement un problème : structure HTML changée (Trustpilot), API dépréciée (Google Play), timeout réseau.
- Sans circuit breaker, le pipeline écrase le CSV avec 0 avis de cette source, perdant des données historiques.
- En CI, exit code 1 déclenche une alerte visible dans GitHub Actions → intervention humaine.
- `ABRITEL_SOFT_CIRCUIT_BREAKER=1` permet au job CI de continuer (commit du CSV sans la source cassée) tout en loggant un warning — utile pour ne pas bloquer le pipeline quotidien si une source est temporairement indisponible.

**Pourquoi la marge de 7 jours est importante ici** :
- Avec une marge trop courte (1 jour), une source avec peu d'avis récents (ex. App Store avec 5 avis/semaine) pourrait retourner 0 avis sur une fenêtre de 24h sans être cassée. 7 jours limite les faux positifs.

---

## 12. Export CSV atomique (`tempfile.mkstemp` + `os.replace`)

**Décision** : écriture dans un fichier temporaire, puis `os.replace()` atomique vers le chemin final.

**Pourquoi** :
- Si le process est tué en milieu d'écriture CSV (Ctrl+C, OOM, coupure), `os.replace()` n'a pas encore eu lieu → le CSV existant est intact.
- Sans cette protection, un crash pendant `df.to_csv()` produirait un CSV tronqué ou corrompu, indétectable sans ré-exécution manuelle.
- `os.replace()` est atomique sur POSIX (macOS/Linux) : il s'agit d'un rename au niveau filesystem, garantissant qu'un lecteur concurrent (Power BI, script d'analyse) ne verra jamais un état intermédiaire.
- Le fichier temporaire est dans le même répertoire que la destination : garantit que `os.replace()` reste sur le même filesystem (cross-device rename échouerait).

**Alternatives rejetées** :
- *Écriture directe* : risque de corruption en cas d'interruption.
- *Sauvegarde `.bak` + rename* : moins atomique, deux opérations au lieu d'une.

---

## 13. Déduplication sur `(source, date, note, texte)`

**Décision** : `drop_duplicates(subset=["source", "date", "note", "texte"], keep="first")`.

**Pourquoi** :
- Les 3 sources n'ont pas d'identifiant universel partageable : Google Play a un `reviewId`, App Store n'en a pas dans l'API RSS, Trustpilot non plus dans le JSON `__NEXT_DATA__`.
- La combinaison `(source, date, note, texte)` est en pratique unique pour un avis réel : deux utilisateurs différents ne postent pas le même texte avec la même note à la même seconde sur la même plateforme.
- `keep="first"` → priorité à l'avis déjà présent dans le CSV (avec son `Catégorie_ollama` en cache). Les nouveaux avis du scraping sont écartés si déjà connus.
- La déduplication est appliquée après la fusion (ancien + nouveau) dans `_fusionner()`.

**Alternatives rejetées** :
- *Déduplication sur texte seul* : deux avis identiques sur des stores différents seraient dédupliqués à tort.
- *Hash de tous les champs* : même résultat mais moins lisible/debuggable.
- *Pas de déduplication* : la marge de 7 jours créerait des doublons systématiques.

---

## 14. Collecte en parallèle (3 scrapers simultanés)

**Décision** : `ThreadPoolExecutor(max_workers=3)` pour les 3 scrapers.

**Pourquoi** :
- Les 3 scrapers sont I/O-bound (attente réseau). Le GIL Python n'est pas un obstacle pour les threads sur du I/O.
- En parallèle : ~max(t_GP, t_AS, t_TP) ≈ 3–5 min. En séquentiel : t_GP + t_AS + t_TP ≈ 8–12 min.
- 3 workers = exactement 3 sources, pas de threads inutiles.

**Alternatives rejetées** :
- *asyncio* : nécessiterait de réécrire les scrapers avec aiohttp. Gain marginal sur I/O, complexité accrue.
- *multiprocessing* : overkill pour du I/O, overhead de sérialisation.

---

## 15. Détection des spikes temporels (`_detect_spikes`)

**Décision** : compare la proportion d'une catégorie cette semaine vs les 4 semaines précédentes. Alerte si > 2σ ET > 5 points de pourcentage au-dessus de la moyenne.

**Pourquoi** :
- Une catégorie peut augmenter mécaniquement si le volume total d'avis augmente. La proportion (%) normalise cet effet.
- Le seuil double (2σ ET +5pp) évite les alertes sur des variations statistiquement significatives mais pratiquement négligeables (ex. passer de 1% à 2.5% = 2σ mais non actionnable).
- 4 semaines d'historique donne une baseline raisonnable. Moins (2-3 semaines) serait trop sensible aux fluctuations hebdomadaires.
- Minimum 5 avis la semaine courante : évite les faux positifs sur des semaines avec peu d'avis (ex. semaine de Noël).
- Minimum 3 avis par semaine d'historique pour inclure cette semaine dans la baseline.

**Alternatives rejetées** :
- *Seuil fixe absolu* : ne s'adapte pas au volume total (un spike à 50 avis vs 500 n'a pas le même impact).
- *Comparaison YoY* : nécessite un an de données, non applicable au MVP.
- *ARIMA/Prophet* : overkill, pas assez de données au démarrage.

---

## 16. Prompt Ollama — conception

**Décision** : le prompt système liste les catégories disponibles + règles d'arbitrage. Le message utilisateur inclut la note /5, la catégorie mots-clés (hint), et le texte tronqué à 6000 chars.

**Pourquoi** :
- **Note /5 dans le prompt** : la même phrase peut avoir une signification différente selon la note. "Remboursement rapide" à 5 étoiles est Financier positif (Basse gravité) ; à 1 étoile c'est Financier négatif. La note calibre l'interprétation du LLM.
- **Catégorie mots-clés comme hint** : le LLM est plus fiable quand on lui donne un point de départ à valider/corriger plutôt qu'une classification ex-nihilo. Réduit les hallucinations.
- **Troncature à 6000 chars** : évite les dépassements de contexte sur les avis très longs (Trustpilot peut avoir des avis >1000 mots). 6000 chars ≈ 1500 tokens, bien en dessous des limites Gemma4.
- **Format JSON forcé** (`"format": "json"`) : Ollama contraint la sortie à du JSON valide au niveau du tokenizer. Réduit les erreurs de parsing.
- **Règle "Utilise « Autre » uniquement si aucune catégorie ne correspond"** : évite que le LLM surclassifie en « Autre » par prudence.
- **Règle "Ne jamais inventer un libellé"** : évite les catégories fantaisistes (ex. "Problème de connexion" au lieu de "Bug Technique").

---

## 17. Scraping Trustpilot par filtre d'étoiles (1-5)

**Décision** : Trustpilot est scrapé 5 fois, une fois par note (stars=1, stars=2, ..., stars=5), jusqu'à `TRUSTPILOT_PAGES_PAR_FILTRE=10` pages par filtre.

**Pourquoi** :
- Sans filtre, Trustpilot retourne les avis dans un ordre de pertinence opaque qui sous-représente systématiquement les avis négatifs (1-2 étoiles).
- En filtrant par étoiles, on s'assure d'avoir une représentation équilibrée de toutes les notes.
- La déduplication finale élimine les éventuels doublons entre filtres.
- 10 pages × 5 filtres = 50 pages maximum, soit ~1000 avis Trustpilot — cohérent avec le volume réel sur la période.

---

## 18. Google Play : 5 tentatives avec backoff, sans limite de pages

**Décision** : `GP_PAGES_MAX = 2000`, `tentatives=5` dans la boucle interne.

**Pourquoi** :
- L'API non officielle `google-play-scraper` est fragile : timeouts aléatoires, rate-limiting non documenté. 5 tentatives avec backoff exponentiel (1s, 2s, 4s, 8s, 10s cap) couvrent la majorité des erreurs transitoires.
- `GP_PAGES_MAX = 2000` est une borne de sécurité pour éviter une boucle infinie, pas une limite opérationnelle : en pratique, le token de pagination devient `None` bien avant 2000 pages, et le filtre de date interrompt aussi la boucle.

---

## 19. Sauvegarde d'urgence du CSV corrompu

**Décision** : si le CSV existant est illisible au chargement, une copie `.bak` est créée avant de continuer.

**Pourquoi** :
- Un CSV corrompu (mauvais encodage, tronqué) ne doit pas bloquer le pipeline : on lance un run complet (comme si c'était le premier).
- La copie `.bak` permet à un opérateur de récupérer manuellement les données si nécessaire.
- Sans cette sauvegarde, un crash pendant l'écriture + CSV corrompu = perte totale des données historiques.

---

## 20. Encodage `utf-8-sig` pour le CSV

**Décision** : `df.to_csv(..., encoding="utf-8-sig")`.

**Pourquoi** :
- UTF-8-SIG (UTF-8 avec BOM) est la variante reconnue nativement par Microsoft Excel et Power BI lors de l'import de fichiers CSV français.
- Sans BOM, Excel et Power BI interprètent souvent le fichier en Windows-1252, corrompant les accents (é → Ã©).
- Le BOM est transparent pour les outils non-Microsoft (pandas, Python open(), bash) : ils l'ignorent silencieusement.

---

## 21. CI/CD — GitHub Actions + run quotidien

**Décision** : workflow quotidien de scraping, séparé du workflow de lint/tests. Pas de notification Slack.

**Pourquoi** :
- Run quotidien : les avis sont publiés en continu. Un run hebdomadaire créerait des fenêtres de données manquantes et ralentirait la détection de spikes.
- Pas de Slack : les notifications Slack créent du bruit et ne sont pas actionnables sans contexte. Le rapport de run est dans les logs GitHub Actions, accessible à tout moment. Le circuit breaker (exit code 1) crée une alerte visible dans l'onglet Actions.
- Ollama désactivé en CI (`CI=true` → `ollama_actif()` retourne False) : les runners GitHub n'ont pas de GPU ni de service Ollama. La catégorisation par mots-clés seule est utilisée en CI.

---

## 22. Structure des modules

**Décision** : `scraping.py` / `categorisation.py` / `ollama_categorisation.py` / `pipeline.py` — 4 fichiers distincts.

**Pourquoi** :
- Séparation des responsabilités : scraping (réseau/HTTP), catégorisation (texte/NLP), LLM (Ollama), orchestration (pipeline).
- `categorisation.py` et `scraping.py` sont testables indépendamment sans pipeline ni réseau.
- `ollama_categorisation.py` est optionnel : si Ollama n'est pas actif, il n'est jamais appelé. Son import dans `pipeline.py` est conditionnel à `ollama_actif()`.
- `pipeline.py` ré-exporte les symboles publics via `__all__` pour compatibilité des imports dans `1_pipeline.py` et les tests.

---

## Synthèse des seuils et paramètres

| Paramètre | Valeur | Justification |
|---|---|---|
| `DATE_DEBUT_INCLUSIVE` | 2025-01-01 | Date fixe pour reproductibilité analytique |
| `MARGE_JOURS_INCREMENTAL` | 7 jours | Couvre retards de publication + évite faux positifs circuit breaker |
| `GP_TAILLE_LOT` | 200 | Maximum supporté par l'API google-play-scraper |
| `TRUSTPILOT_PAGES_PAR_FILTRE` | 10 | ~200 avis par note, équilibre couverture/charge |
| `_OLLAMA_MAX_WORKERS` | 4 | Sweet-spot GPU local (Mac M-series 64 GB) |
| `_OLLAMA_MAX_RETRIES` | 3 | Résilience sans sur-multiplier le temps |
| `temperature` | 0 | Déterminisme pour reproductibilité |
| `timeout` | 120s | Sufficient pour gemma4:31b en local |
| `max_chars` (prompt) | 6000 | ~1500 tokens, sous les limites Gemma4 |
| `_AUTRE_POSITIF_COURT_MOTS_MAX` | 15 | 1 phrase courte = non actionnable |
| `_AUTRE_NEGATIF_LONG_MOTS_MIN` | 30 | Feedback détaillé = à analyser |
| `_AUTRE_POSITIF_COURT_NOTE_MIN` | 4 | Avis satisfaits |
| `_AUTRE_NEGATIF_LONG_NOTE_MAX` | 2 | Avis insatisfaits |
| Spike seuil | 2σ + 5pp | Double condition : significativité statistique + pertinence pratique |
| Spike baseline | 4 semaines | Historique suffisant sans trop de données |
| Hash keywords | MD5 8 chars | Traçabilité légère, non-cryptographique |
