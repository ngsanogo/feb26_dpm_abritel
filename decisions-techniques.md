# Décisions techniques — Justification

> Document créé le 2026-04-18, mis à jour le 2026-04-20.  
> Chaque section suit le format : **Décision → Pourquoi**.

---

## Résumé

Notre pipeline collecte les avis utilisateurs Abritel depuis 3 sources (Google Play, App Store, Trustpilot) à partir d'une **date fixe au 01/01/2025** pour garantir la reproductibilité de nos analyses. Le scraping est **incrémental** avec une marge de 7 jours pour ne pas manquer d'avis publiés en retard, et nous scrapons les 3 sources en parallèle pour réduire le temps d'exécution. Nous catégorisons chaque avis par un système à deux niveaux : d'abord par **mots-clés** (~300 mots FR/EN, normalisés sans accents via NFD) dans 7 catégories + « Autre », puis nous le validons par un **LLM local** (Ollama gemma4:31b, temperature 0) qui corrige les erreurs de classification. Nous avons choisi un LLM local pour des raisons de confidentialité (RGPD) et nous utilisons un cache incrémental avec sauvegarde progressive tous les 25 avis pour éviter la perte de travail en cas d'interruption. Nous évaluons la gravité selon deux axes indépendants : l'un combine note + catégorie + mots-clés forts (3 niveaux), l'autre analyse uniquement le texte pour casser la tautologie note→gravité. Nous décomposons les avis « Autre » en 4 sous-catégories (positif court, positif thématique, négatif non catégorisé, neutre) pour distinguer le bruit du signal. Un **circuit breaker** nous protège contre la perte de données si une source cesse de répondre. Nous exportons le CSV de manière atomique (écriture temp + rename) en UTF-8-SIG pour la compatibilité Power BI, et nous rattachons chaque avis à la version de l'app active à sa date de publication. Le pipeline tourne quotidiennement via GitHub Actions, avec détection automatique de spikes par catégorie et traçabilité des changements de mots-clés via hash MD5.

---

## 1. Date fixe au 01/01/2025

Nous avons choisi une date de début fixe plutôt qu'une fenêtre glissante parce que nous avions besoin d'une base stable pour nos analyses. "Depuis le 1er janvier 2025, combien d'avis Bug Technique ?" — avec une fenêtre glissante, la réponse changerait chaque semaine et rendrait toute comparaison temporelle non reproductible. Notre pipeline est incrémental : le premier run collecte tout depuis le 01/01/2025, les runs suivants ne scrapent que les nouveaux avis.

---

## 2. Marge de 7 jours en scraping incrémental

En mode incrémental, nous rescrapons à partir de 7 jours avant la dernière date du CSV. Nous avons choisi cette marge parce que les avis peuvent apparaître avec retard sur les stores (modération, cache CDN, décalage de fuseau). La déduplication sur `(source, date, note, texte)` garantit qu'aucun doublon n'est introduit malgré cette marge. 7 jours est un bon compromis : assez large pour ne rien manquer, assez court pour limiter les appels réseau inutiles, et assez long pour que le circuit breaker ne déclenche pas de faux positifs (une source à faible volume peut légitimement n'avoir aucun nouvel avis sur 1-2 jours).

---

## 3. Normalisation NFD pour les mots-clés

Nous avons choisi la décomposition Unicode NFD (qui sépare "é" en "e" + accent, puis nous retirons l'accent) parce que les avis mélangent du français accentué, du français sans accents (clavier mobile), et de l'anglais. En stockant tous les mots-clés sans accents et en normalisant le texte de la même façon, le matching est robuste à toutes ces variantes sans avoir besoin de regex complexes. C'est la méthode Unicode standard pour ce cas d'usage, et ça nous simplifie la maintenance : nous écrivons simplement "rembourse" sans nous demander s'il faut un accent.

---

## 4. Catégorisation par comptage de mots-clés

Nous comptons le nombre de mots-clés de chaque catégorie présents dans le texte, et la catégorie avec le score le plus élevé l'emporte. Nous avons choisi cette approche parce qu'elle est simple à comprendre, à déboguer et à maintenir. Elle est robuste à la longueur variable des avis et permet naturellement la multi-catégorisation (si un avis parle de remboursement ET de bug, les deux catégories sont capturées dans `Catégorie` et `Catégorie_secondaire`). En cas d'égalité de score, l'ordre de la liste de mots-clés sert de tie-breaking déterministe.

---

## 5. Ordre de priorité des catégories

L'ordre est : Localisation/Langue → Annulation/Réservation → Financier → Bug Technique → UX/Ergonomie → Service Client → Qualité du bien. Cet ordre sert de tie-breaking quand deux catégories ont le même score de mots-clés. Nous l'avons choisi selon la logique métier :

- **Localisation/Langue** en premier car ses mots-clés (devises, noms de pays) sont très spécifiques et ne se retrouvent presque jamais ailleurs.
- **Annulation avant Financier** car une annulation est la cause originelle, le problème financier (remboursement) en est la conséquence.
- **Financier avant Bug Technique** car un bug de paiement a un impact direct sur le portefeuille de l'utilisateur.
- **Bug Technique avant UX** car une app qui plante est plus grave qu'une interface mal pensée.
- **Service Client** après UX car il est souvent mentionné en réaction à un autre problème — la catégorie primaire doit refléter la cause.
- **Qualité du bien** en dernier car ses mots-clés (logement, appartement, photo) sont larges et risquent de matcher des avis qui décrivent simplement le logement sans problème.

---

## 6. Décomposition des avis « Autre »

Les avis sans aucun mot-clé sont classés « Autre », puis décomposés en 4 sous-catégories. Nous avons fait cette décomposition parce que les avis « Autre » sont hétérogènes : ~80% sont des "Super !" non actionnables, mais ~20% contiennent de vrais retours négatifs dont les mots-clés manquent au modèle.

- **Positif court** (note ≥ 4, ≤ 15 mots) : avis du type "Super !", "Très bien !" — non actionnable.
- **Positif thématique** (note ≥ 4, contient des marqueurs de satisfaction comme « génial », « parfait », « recommande ») : avis positif plus développé, utile pour mesurer la satisfaction globale.
- **Négatif non catégorisé** (note ≤ 2, ≥ 30 mots) : avis négatif détaillé dont les mots-clés manquent — c'est le signal le plus précieux pour enrichir le modèle de catégorisation.
- **Neutre** : tout le reste.

Les seuils (15 mots, 30 mots) ont été déterminés empiriquement : en dessous de 15 mots un avis positif est rarement actionnable, et au-dessus de 30 mots un avis négatif contient suffisamment d'information pour être analysé. Power BI peut filtrer sur `Autre_type = "négatif non catégorisé"` pour constituer un backlog de mots-clés à ajouter.

---

## 7. Évaluation de la gravité (note + texte)

Nous avons choisi 3 niveaux (Haute / Moyenne / Basse) parce que c'est le minimum pour un tri actionnable en backlog : Haute = urgence, Moyenne = à planifier, Basse = monitoring.

Les règles combinent la note, le texte et la catégorie :
1. Si le texte contient des mots-clés forts (arnaque, escroc, tribunal, fraude...) non niés → **Haute**.
2. Note 1 étoile → **Haute** (mauvaise expérience par définition).
3. Note 2 étoiles + catégorie à impact direct (Bug Technique, Financier, Annulation) → **Haute** (impact financier ou perte de service).
4. Note 2 étoiles, autre catégorie → **Moyenne**.
5. Note ≥ 3 → **Basse**.

La détection de négation (« pas d'arnaque », « aucune escroquerie ») évite les faux positifs sur les avis qui utilisent ces termes positivement.

### Gravité indépendante du texte (Gravité_texte)

Nous avons ajouté une deuxième colonne de gravité basée uniquement sur le texte, indépendamment de la note et de la catégorie. Nous l'avons fait parce que le champ `Gravité` principal est tautologiquement corrélé à la note (note 1 → Haute, note ≥ 3 → Basse), ce qui biaise les analyses statistiques (chi², corrélation). `Gravité_texte` casse cette tautologie : un avis noté 3/5 mais contenant « arnaque » ou « catastrophique » sera Haute en Gravité_texte, révélant un décalage entre la note donnée et l'émotion exprimée. Le notebook d'analyse utilise ce champ pour des croisements statistiques non circulaires.

---

## 8. Validation par LLM local (Ollama)

### Pourquoi un LLM en plus des mots-clés

Nous avons ajouté une validation LLM parce que les mots-clés sont efficaces sur les cas clairs mais échouent sur l'ironie ("super, encore un bug !"), les synonymes non listés et les avis ambigus multi-thèmes. Un LLM comprend le sens et peut distinguer "l'annulation de ma réservation m'a coûté cher" (Financier ou Annulation ?) selon le contexte. La qualité des données downstream (Power BI, priorisation produit) justifie l'investissement en temps de calcul.

### Pourquoi Ollama (local) et non une API cloud

Nous avons choisi un LLM local parce que les avis contiennent des données potentiellement sensibles (montants, noms de propriétaires). Les envoyer à une API tierce créerait un risque RGPD. En plus, le coût est fixe (pas de facturation à l'appel) et le modèle ne change pas entre deux runs sans action explicite, ce qui garantit la reproductibilité.

### Pourquoi gemma4:31b

Nous avons choisi ce modèle parce que ses 31 milliards de paramètres sont suffisants pour de la classification de texte court, avec une qualité supérieure aux modèles 7-8B sur les cas ambigus. Gemma 4 (Google) est particulièrement bon en classification structurée avec sortie JSON et tourne en local sur un Mac M-series avec 64 GB de RAM.

### Pourquoi temperature 0

Nous avons mis la temperature à 0 parce que nous voulons un comportement déterministe : le même avis doit toujours produire la même catégorie entre deux runs. La tâche (classification dans une liste fermée de 8 catégories) ne bénéficie pas de la créativité qu'apporte une temperature élevée, et l'aléatoire rendrait les comparaisons temporelles invalides.

### Pourquoi think = False

Nous avons désactivé le raisonnement interne de Gemma4 parce que ça rend le traitement ~18x plus rapide (mesuré en pratique : ~15 min vs ~4h sur 700+ avis). La tâche de classification ne bénéficie pas du chain-of-thought interne car le prompt fournit déjà tout le contexte nécessaire (catégories, descriptions, note, hint mots-clés). La qualité de classification n'est pas dégradée.

### Pourquoi 4 workers et 3 tentatives

Nous utilisons 4 appels Ollama simultanés parce que c'est le sweet-spot sur un Mac M-series : au-delà, la mémoire GPU sature et les temps de réponse augmentent. 3 tentatives avec backoff exponentiel (1s, 2s, 4s) parce qu'Ollama peut retourner une réponse mal formée sur le premier essai, surtout sur des avis courts ou ambigus.

### Conception du prompt

Le prompt système liste les catégories avec leurs descriptions et les règles d'arbitrage. Le message utilisateur inclut la note /5 (contexte émotionnel), la catégorie mots-clés comme hint (point de départ à valider/corriger plutôt qu'une classification ex-nihilo), et le texte tronqué à 6000 caractères. Le format JSON est forcé au niveau du tokenizer Ollama pour réduire les erreurs de parsing.

---

## 9. Cache incrémental Ollama

Nous avons mis en place un cache incrémental parce que la temperature 0 garantit que repasser le même avis par le même modèle donnerait le même résultat. Les avis déjà validés par Ollama (colonne `Catégorie_ollama` non vide dans le CSV) ne repassent pas par le LLM lors des runs suivants. Sur 700 avis, si 698 ont déjà été validés, nous n'appelons Ollama que pour les 2 nouveaux — le temps de run passe de ~15 min à quelques secondes.

Si les mots-clés changent entre deux runs (détecté par un hash MD5 stocké dans `pipeline_meta.json`), tous les avis repassent automatiquement par Ollama parce que les suggestions mots-clés envoyées au LLM ont changé et la cohérence l'exige.

### Sauvegarde progressive (checkpoint)

Nous sauvegardons le CSV tous les 25 avis traités par Ollama parce que le traitement peut durer longtemps (1h+ sur un gros volume). En cas d'interruption (Ctrl+C, crash Ollama, OOM), le run suivant récupère automatiquement le cache partiel et continue sans perdre les avis déjà validés. 25 avis est un bon compromis entre sécurité (~28 sauvegardes pour 700 avis) et charge I/O (pas une sauvegarde par avis).

---

## 10. Traçabilité des mots-clés (hash MD5)

Nous stockons un hash MD5 tronqué à 8 caractères des mots-clés dans `pipeline_meta.json` parce que ça permet de détecter automatiquement si nous avons modifié la liste de mots-clés entre deux runs. Si le hash change, un warning apparaît dans les logs et Ollama retraite tous les avis pour maintenir la cohérence. Le hash inclut l'ordre ET le contenu des mots-clés, ce qui est correct car un réordonnancement change le tie-breaking.

---

## 11. Circuit breaker

Nous avons mis en place un circuit breaker parce qu'une source qui retourne subitement 0 avis signale probablement un problème (structure HTML changée, API dépréciée, timeout réseau). Sans cette protection, le pipeline écraserait le CSV en perdant les données historiques de cette source.

En CI (GitHub Actions), le circuit breaker fait échouer le job (exit code 1) pour déclencher une alerte visible. Le mode `ABRITEL_SOFT_CIRCUIT_BREAKER=1` permet au workflow quotidien de continuer (commit du CSV, exit 0) tout en loggant un warning — utile pour ne pas bloquer le pipeline si une source est temporairement indisponible. En local, c'est un simple avertissement.

---

## 12. Export CSV atomique

Nous écrivons d'abord dans un fichier temporaire puis nous faisons un `os.replace()` atomique vers le chemin final. Nous avons choisi cette approche parce que si le process est tué pendant l'écriture (Ctrl+C, OOM, coupure), le CSV existant reste intact. `os.replace()` est un rename atomique au niveau du filesystem : un lecteur concurrent (Power BI, script d'analyse) ne verra jamais un état intermédiaire.

---

## 13. Déduplication sur (source, date, note, texte)

Nous dédupliquons sur cette combinaison de 4 champs parce que les 3 sources n'ont pas d'identifiant universel partageable (Google Play a un `reviewId`, mais App Store et Trustpilot n'en exposent pas). En pratique, cette combinaison est unique pour un avis réel. `keep="first"` donne la priorité à l'avis déjà présent dans le CSV (avec son cache Ollama), ce qui est cohérent avec le mode incrémental.

---

## 14. Collecte en parallèle

Nous scrapons les 3 sources en parallèle (3 threads) parce qu'elles sont I/O-bound (attente réseau) et indépendantes. Le temps total passe de ~8-12 min en séquentiel à ~3-5 min en parallèle. Chaque thread a sa propre session HTTP pour éviter les problèmes de concurrence.

---

## 15. Détection des spikes temporels

Nous comparons la proportion d'une catégorie cette semaine vs la moyenne des 4 semaines précédentes. Nous alertons si elle dépasse 2 écarts-types ET 5 points de pourcentage au-dessus de la moyenne. Nous avons choisi cette double condition parce qu'un écart statistiquement significatif mais pratiquement négligeable (passer de 1% à 2.5%) ne mérite pas une alerte. Il faut au moins 5 semaines d'historique, 5 avis la semaine courante et 3 avis par semaine historique pour que le calcul soit fiable.

---

## 16. Scraping Trustpilot par filtre d'étoiles

Nous scrapons Trustpilot 5 fois (une fois par note de 1 à 5 étoiles) parce que sans filtre, Trustpilot retourne les avis dans un ordre de pertinence opaque qui sous-représente systématiquement les avis négatifs. En filtrant par étoiles, nous obtenons une représentation équilibrée de toutes les notes.

---

## 17. Google Play : 5 tentatives avec backoff

Nous avons choisi 5 tentatives avec backoff exponentiel parce que l'API non officielle `google-play-scraper` est fragile (timeouts aléatoires, rate-limiting non documenté). La borne de 2000 pages est une sécurité contre les boucles infinies — en pratique, le token de pagination et le filtre de date interrompent la boucle bien avant.

---

## 18. Sauvegarde d'urgence du CSV corrompu

Si le CSV existant est illisible au chargement, nous créons une copie `.bak` et nous relançons un scraping complet. Nous avons fait ce choix parce qu'un CSV corrompu ne doit pas bloquer le pipeline, et la copie `.bak` permet une récupération manuelle si nécessaire.

---

## 19. Encodage UTF-8-SIG

Nous exportons en UTF-8-SIG (UTF-8 avec BOM) parce que c'est la variante reconnue nativement par Excel et Power BI pour les fichiers CSV français. Sans BOM, ces outils interprètent souvent le fichier en Windows-1252 et corrompent les accents. Le BOM est transparent pour les outils non-Microsoft (pandas, Python) qui l'ignorent silencieusement.

---

## 20. CI/CD quotidien via GitHub Actions

Nous avons choisi un run quotidien (chaque jour à 20h UTC) parce que les avis sont publiés en continu et qu'un run hebdomadaire créerait des fenêtres de données manquantes et ralentirait la détection de spikes. Ollama est désactivé en CI parce que les runners GitHub n'ont pas de GPU — seule la catégorisation par mots-clés est utilisée. Pas de notification Slack : le circuit breaker (exit code 1) crée une alerte visible dans l'onglet Actions.

---

## 21. Attribution de version release

Chaque avis est rattaché à la version de l'app active au moment de sa publication, avec un **délai de grâce de 2 jours**. Nous avons choisi ce délai parce que les stores mettent 24-48h pour déployer une mise à jour à tous les utilisateurs (staged rollout Google Play, propagation CDN App Store). Un avis publié le jour même d'une release concerne presque certainement l'ancienne version. Au-delà de 2 jours, la majorité des utilisateurs actifs ont reçu la mise à jour.

---

## 22. Structure en 4 modules

Nous avons séparé le code en 4 fichiers (`scraping.py`, `categorisation.py`, `ollama_categorisation.py`, `pipeline.py`) parce que ça sépare les responsabilités (réseau, NLP, LLM, orchestration), permet de tester chaque module indépendamment, et rend Ollama optionnel (jamais appelé si le service n'est pas actif). `pipeline.py` ré-exporte les symboles publics via `__all__` pour la compatibilité des imports.

---

## Synthèse des paramètres

| Paramètre | Valeur | Pourquoi |
|---|---|---|
| Date de début | 01/01/2025 | Reproductibilité analytique |
| Marge incrémentale | 7 jours | Couvre les retards de publication + évite les faux positifs du circuit breaker |
| Lot Google Play | 200 avis/page | Maximum supporté par l'API |
| Pages Trustpilot | 10 par filtre | Équilibre couverture/charge réseau |
| Workers Ollama | 4 | Sweet-spot GPU local (Mac M-series 64 GB) |
| Retries Ollama | 3 | Résilience sans multiplier le temps |
| Temperature | 0 | Déterminisme pour reproductibilité |
| Think | False | 18x plus rapide, même qualité de classification |
| Timeout Ollama | 300s | Suffisant pour gemma4:31b en local |
| Troncature prompt | 6000 chars | Sous les limites de contexte Gemma4 |
| Checkpoint | 25 avis | Compromis sécurité / charge I/O |
| Seuil positif court | ≤ 15 mots, note ≥ 4 | 1 phrase courte = non actionnable |
| Seuil négatif non catégorisé | ≥ 30 mots, note ≤ 2 | Feedback détaillé = à analyser |
| Spike | 2σ + 5pp | Significativité statistique + pertinence pratique |
| Spike baseline | 4 semaines | Historique suffisant |
| Hash keywords | MD5 8 chars | Traçabilité légère |
| Délai de grâce version | 2 jours | Temps de déploiement stores |
