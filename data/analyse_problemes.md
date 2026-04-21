# Analyse des problèmes majeurs — Abritel

*Généré le 2026-04-21 — 725 avis analysés (janvier 2025 — avril 2026)*

## Méthodologie

**Collecte** : scraping automatisé de 3 sources complémentaires (Google Play, App Store, Trustpilot) couvrant la période depuis le 1er janvier 2025. Le choix de trianguler les sources réduit le biais de plateforme — Trustpilot ne capte que les mécontents (100% négatif), tandis que Google Play offre un échantillon plus équilibré (50% négatif).

**Catégorisation** : approche hybride en 2 passes.
1. *Mots-clés* : classification automatique par correspondance lexicale (texte normalisé NFD, sans accents) dans 8 catégories prédéfinies.
2. *Validation LLM* : chaque avis est soumis à gemma4:31b (Ollama, température 0) qui confirme ou corrige la catégorie. Le LLM reçoit le texte, la note /5, et la suggestion mots-clés.

**Analyse qualitative** : pour chaque catégorie × persona, un batch d'avis est soumis au LLM qui identifie les sous-problèmes récurrents et sélectionne les citations les plus représentatives.

**Limites** :
- Biais de sélection Trustpilot (utilisateurs mécontents surreprésentés)
- Échantillon propriétaire limité (n=44) — tendances indicatives
- Avis très courts (< 10 mots) parfois inclassables → catégorie « Autre »

## Vue d'ensemble

- **725** avis collectés (Google Play, App Store, Trustpilot)
- **487** avis négatifs (67%)
- **216** avis positifs (30%)

| Source | Total | Négatifs | % négatifs |
|--------|-------|----------|------------|
| Google Play | 468 | 233 | 50% |
| Trustpilot | 206 | 206 | 100% |
| App Store | 51 | 48 | 94% |

## Persona : Locataire (443 avis négatifs)

| # | Problème | N | % | Gravité Haute |
|---|----------|---|---|---------------|
| 1 | Financier | 111 | 25.1% | 100.0% |
| 2 | Qualité du bien | 81 | 18.3% | 95.1% |
| 3 | Localisation / Langue | 66 | 14.9% | 92.4% |
| 4 | Annulation / Réservation | 53 | 12.0% | 100.0% |
| 5 | Service Client | 48 | 10.8% | 93.8% |
| 6 | Bug Technique | 41 | 9.3% | 100.0% |
| 7 | UX / Ergonomie | 26 | 5.9% | 80.8% |

### 1. Financier — 111 avis (25.1%)

- **Gravité Haute** : 100.0% des avis de cette catégorie
- **Distribution des notes** : 1★: 106, 2★: 5

**Difficultés et délais de remboursement après annulation** (~35% des avis)

> « remboursement tous simplement impossible depuis 2 mois !! même en étant largement dans les temps sous prétexte d un bug abritel... »

> « Nous attendons le remboursement d'un voyage annulé (par l'hôte) de 450€ DEPUIS PLUS D'1 MOIS. »

> « ils ne veulent pas me rembourser et me trouve des tas d excuses »

*Impact* : Le locataire se retrouve dans une situation d'insécurité financière majeure, ayant payé pour un service non rendu sans récupération de ses fonds.

**Écarts entre prix affichés et montants réellement prélevés** (~25% des avis)

> « Montant à régler plus élevé que le devis. Dès la saisie du moyen de paiement, le montant à régler augmente sensiblement. »

> « débit en livres sterling d’un montant supérieur au montant indiqué sur la réservation. »

> « Le prix affiché était de 1980 €, les demandent de paiement portaient sur ce montant (par carte), le prix finalement demandé par le propriétaire était de 1000€ supplémentaire »

*Impact* : Une rupture totale de confiance envers la plateforme due à un manque de transparence tarifaire et un sentiment de tromperie.

**Annulations tardives sans solution de relogement** (~20% des avis)

> « Annulation de la part d'Abritel le jour même, sans relogement. »

> « A 20h à la rue avec un enfant de 5mois ! Une honte absolue ! Pas un appel d'Abritel e »

> « Abritel a annulé notre réservation et nous laisse nous débrouiller seule proposition le remboursement »

*Impact* : Le locataire se retrouve sans logement à l'arrivée, transformant les vacances en situation de crise logistique et émotionnelle.

**Erreurs de facturation et doubles prélèvements** (~12% des avis)

> « Prélevé 2 fois pour la même réservation et refus de remboursement ! »

> « une location, mais deux encaissements.. j'ai réservé un logement dit libre pour la période j'ai effectué le paiement »

> « erreur de calcul de leur part pour le paiement de la location »

*Impact* : Une frustration immédiate liée à une gestion comptable défaillante qui impacte directement le budget du voyageur.

### 2. Qualité du bien — 81 avis (18.3%)

- **Gravité Haute** : 95.1% des avis de cette catégorie
- **Distribution des notes** : 1★: 77, 2★: 4

**Non-conformité entre l'annonce (photos/description) et la réalité du bien** (~40% des avis)

> « description non conforme à la réalité »

> « Gros décalage entre les photos de l’annonce et la réalité »

> « Rien de ce qui étais décrit dans l’annonce n’étais vrais »

*Impact* : Le locataire se retrouve dans un logement qui ne répond pas à ses besoins ou attentes, créant un sentiment de tromperie.

**Annulations tardives ou indisponibilité du logement à l'arrivée** (~30% des avis)

> « Location annulée par le propriétaire, sans explication, à 10 jours du départ nous laissant sans solution ! »

> « Arrivée sur place le logement était déjà occupé »

> « le jour de l'arrivée nous apprenons par le propriétaire que le logement n'était plus à louer de puis l'année précédente »

*Impact* : Le locataire se retrouve sans hébergement juste avant ou pendant ses vacances, générant un stress majeur et une urgence logistique.

**Problèmes d'hygiène, d'insalubrité et d'équipements défectueux** (~20% des avis)

> « Gite pas propre voire crasseux »

> « Douche qui fuit.Lavabo bouché.Frigidaire fermant mal »

> « intérieur et extérieur sale de plus dés frelons la première nuit »

*Impact* : La qualité du séjour est dégradée par un environnement insalubre ou dangereux, rendant le logement parfois inhabitable.

### 3. Localisation / Langue — 66 avis (14.9%)

- **Gravité Haute** : 92.4% des avis de cette catégorie
- **Distribution des notes** : 1★: 61, 2★: 5

**Impossibilité de configurer la langue en français** (~75% des avis)

> « impossible d'avoir l'application en français. »

> « impossible de mettre l'appli en français »

> « Pas possible de mettre en français !!!!. »

*Impact* : L'utilisateur se retrouve face à une barrière linguistique majeure qui rend la navigation et la compréhension du service difficiles.

**Affichage erroné de la devise (Dollars NZ) et localisation** (~45% des avis)

> « L’application s’installe systématiquement en Anglais alors que ma langue système est le Français et en plus on m’impose une devise $NZ. »

> « Appli en anglais. Devise New zelandaise pas moyen de trouver l'application en français et en euros »

> « Ça me localise à la Nouvelle Zélande !! »

*Impact* : L'incapacité de visualiser les prix en euros crée une confusion financière et une frustration liée à l'inexactitude des informations.

**Difficultés de communication et support client inefficace** (~20% des avis)

> « Dialogue de sourd avec l'assistance automayique qui ne comprend pas les questions »

> « Service client inutile. Si vous avez un problème, le service client se dédouane et ne peut rien pour vous. »

> « Difficile de les joindre par téléphone. lorsque vous pouvez les joindre, ont vous parle Allemand. »

*Impact* : Le sentiment d'abandon de l'utilisateur face à des problèmes techniques, aggravé par l'utilisation de traducteurs ou de langues non maîtrisées.

### 4. Annulation / Réservation — 53 avis (12.0%)

- **Gravité Haute** : 100.0% des avis de cette catégorie
- **Distribution des notes** : 1★: 48, 2★: 5

**Annulations tardives ou brutales par l'hôte sans solution** (~55% des avis)

> « Annulation de la réservation le matin même, très difficile de communiquer avec Abritel.Aucune aide »

> « Location annulée par l'hôte une fois arrivé sur place après 650km de voyage »

> « Annulation à 11h45 pour le lendemain. Aucune compensation.. »

*Impact* : Le locataire se retrouve sans logement à la dernière minute, souvent après un long trajet, créant un stress majeur et une rupture de vacances.

**Inefficacité et manque d'empathie du service client** (~30% des avis)

> « le service client vous RACCROCHE littéralement au nez »

> « Lorsqu'on appel le service Abritel, aucune compassion, ne trouve pas de solution et aucun suivis du dossier »

> « On tombe sur une personne différente a chaque fois qui n'est pas au courant du dossier »

*Impact* : Le sentiment d'abandon et d'impuissance du client face à un problème critique, aggravant la frustration envers la marque.

**Désynchronisation des disponibilités et erreurs de catalogue** (~20% des avis)

> « le pavillon n'était plus en location depuis 3 ans »

> « le gîte que nous avons loué n'était plus ouvert aux voyageurs depuis 2024 et j'ai reçu une confirmation de réservation »

> « on trouve plusieurs logements qui sont affichés en tant que disponible sur cette période là or qu'en contactant le propriétaire il nous informe que non le logement n'est pas disponible »

*Impact* : Une perte de confiance totale dans la fiabilité des informations affichées sur la plateforme, rendant la planification incertaine.

**Dysfonctionnements techniques et ergonomiques du parcours d'annulation** (~15% des avis)

> « je tombe sur un agent virtuel instable et qui se bloque apres avoir proposé: " Commençons par le motif de l’annulation. Veuillez en sélectionner un" »

> « impossible de mon côté de retrouver ma réservation pour annuler »

> « je ne peux pas annuler cette resa que je n’ai jamais faite »

*Impact* : L'utilisateur est piégé dans un tunnel technique bloquant, l'empêchant d'exercer son droit d'annulation ou d'obtenir un remboursement.

### 5. Service Client — 48 avis (10.8%)

- **Gravité Haute** : 93.8% des avis de cette catégorie
- **Distribution des notes** : 1★: 44, 2★: 4

**Inaccessibilité et inefficacité du support client (humain et virtuel)** (~50% des avis)

> « il filtre via leur agent virtuel qui ne comprend pas une phrase simple comme "je veux parler à un agent humain ou conseiller" »

> « Si on pose une question au service client par le chat on fait que tourner en rond mais on obtient aucune réponse au final!!! »

> « Aucune possibilité de contacter un humain. Horrible »

*Impact* : Le locataire se retrouve totalement isolé et sans solution face à un litige ou un problème technique.

**Qualité déplorable des interactions téléphoniques et manque de professionnalisme** (~25% des avis)

> « Au téléphone, les interlocuteurs ne maîtrisent pas le français et ne comprennent pas vos questions, et quand ils sont incapables de répondre à votre question, ils vous raccrochent au nez... »

> « Répond aux questions suivant une Check list mais aucune personnalisation. Répète 3 ou 4 fois les mêmes réponses car aucune argument à donner. Et finalement raccroche au nez du client !! »

> « pas diplomate et raccroche au nez, sûrement car les étrangers au téléphone ne comprennent pas mon accent »

*Impact* : Un sentiment d'irrespect et de frustration intense qui dégrade durablement l'image de marque de la plateforme.

**Absence d'assistance concrète lors de problèmes liés au logement** (~20% des avis)

> « Logement réservé via Abritel dans un état insalubre, totalement inhabitable. Propriétaire injoignable, aucune aide concrète malgré 8 appels au service client. »

> « Suite à une location non conforme au descriptif, nous avons dû nous débrouiller seuls pour trouver un hébergement sur place »

> « aucune aide en cas de problème »

*Impact* : Le locataire assume seul le risque financier et logistique d'une location non conforme, malgré le paiement de frais de service.

**Dysfonctionnements financiers et manque de transparence sur la facturation** (~15% des avis)

> « facturation sans application de la réduction annoncée. Silence radio à mes mails.. »

> « Ils facturent sans prévenir, je cite leur support : "Puis-je savoir si vous nous avez contactés au sujet du premier versement qui a été facturé sans votre accord ? " »

> « ne rend pas les cautions, et quand ont les appellent, nous prétendent le contraire ! »

*Impact* : Une perte de confiance immédiate due à un sentiment d'arnaque ou de manque de rigueur comptable.

### 6. Bug Technique — 41 avis (9.3%)

- **Gravité Haute** : 100.0% des avis de cette catégorie
- **Distribution des notes** : 1★: 33, 2★: 8

**Échecs de connexion et d'accès au compte** (~32% des avis)

> « impossible de se connecter »

> « impossible d'ouvrir son compte, erreur interne affichée. »

> « Rare possibilité de se connecter sur son compte. A chaque fois, "désolé, une erreur s'est produite de notre côté" »

*Impact* : L'utilisateur est totalement bloqué et ne peut pas accéder à ses informations personnelles ou gérer ses réservations.

**Dysfonctionnements critiques de l'application mobile et compatibilité** (~27% des avis)

> « dommage que cette appli ne doit pas compatible avec mon telephone! »

> « Application ne marche tout simplement pas. »

> « appareil non compatible avec l'application ???????? »

*Impact* : L'expérience utilisateur est rompue dès l'installation, poussant les clients vers la concurrence ou le site web.

**Contrainte d'installation forcée de l'application pour consulter des annonces** (~15% des avis)

> « téléchargement de l'appli obligatoire nul on doit télécharger l'appli pour consulter une annonce »

> « Impossible de consulter les liens des annonces envoyées, cela renvoi systématiquement au téléchargement de l'application ! »

*Impact* : Cela crée une friction majeure dans le tunnel de conversion et dissuade les utilisateurs de réserver.

**Bugs de navigation, lenteurs et erreurs de formulaire** (~12% des avis)

> « il est impossible d'aller au bout du formulaire lors du choix du séjour.. impossible de noter l'âge des enfants ( les cases sont grisées) »

> « site impossible de complexité et d'une lenteur phénoménale. »

> « L'app dysfonctionne trop, mieux vaut utiliser le site web. Sur l'app, l'ajout de filtre sur une recherche réinitialise souvent les autres filtres. »

*Impact* : L'utilisateur éprouve une frustration cognitive élevée et abandonne son processus de recherche ou de réservation.

### 7. UX / Ergonomie — 26 avis (5.9%)

- **Gravité Haute** : 80.8% des avis de cette catégorie
- **Distribution des notes** : 1★: 21, 2★: 5

**Complexité générale et manque d'intuitivité de l'interface** (~50% des avis)

> « trop Compliqueè »

> « Pas intuitif »

> « Application trop compliqué un vrai labyrinthe »

*Impact* : L'utilisateur ressent une frustration cognitive élevée, rendant la navigation pénible et décourageant l'utilisation de la plateforme.

**Contrainte d'installation forcée de l'application pour ouvrir des liens** (~15% des avis)

> « forcer les gens à télécharger votre application pour ouvrir un lien c'est une honte »

> « Impossible d’ouvrir un lien sur un smartphone sans installer l’appli. »

*Impact* : Création d'une barrière à l'entrée majeure qui génère un sentiment d'intrusion et d'agacement lors du partage de voyages.

**Dysfonctionnements de l'expérience mobile et accès aux réservations** (~15% des avis)

> « connexion très compliqué depuis un smartphone »

> « Le chemin d'accès aux réservations en cours est contre intuitif. »

*Impact* : L'impossibilité de gérer son séjour en mobilité pousse l'utilisateur à retourner sur un PC, cassant l'usage nomade.

## Persona : Propriétaire (44 avis négatifs)

> ⚠ Échantillon limité (n=44). Les tendances sont indicatives, pas statistiquement généralisables.

| # | Problème | N | % | Gravité Haute |
|---|----------|---|---|---------------|
| 1 | Qualité du bien | 16 | 36.4% | 100.0% |
| 2 | Service Client | 9 | 20.5% | 100.0% |
| 3 | Bug Technique | 6 | 13.6% | 100.0% |
| 4 | Financier | 4 | 9.1% | 100.0% |
| 5 | Annulation / Réservation | 4 | 9.1% | 100.0% |
| 6 | Localisation / Langue | 3 | 6.8% | 100.0% |

### 1. Qualité du bien — 16 avis (36.4%)

- **Gravité Haute** : 100.0% des avis de cette catégorie
- **Distribution des notes** : 1★: 16

**Difficultés d'accès et de connexion à l'espace propriétaire** (~62% des avis)

> « je n'arrive pas à me connecter en tant qu'hôte pour modifier mes annonces et en ajouter »

> « nul, impossible d cceder a mon compte propriétaire »

> « Impossible de trouver l'espace propriétaire. »

*Impact* : Le propriétaire est totalement bloqué dans la gestion quotidienne de son activité et de ses revenus.

**Confusion et navigation complexe entre les modes voyageur et hôte** (~25% des avis)

> « je ne parviens pas à passer du mode hôte au mode propriétaire... »

> « pour quelle raison je n'arrive pas à me connecter à mon compte propriétaire je tombe sur un compte vacancière »

> « je tourne en rond sur le site internet. impossible de retrouver mon annonce, mon compte. »

*Impact* : Une frustration cognitive élevée entraînant une perte de temps et un sentiment d'impuissance face à l'interface.

**Suppression ou suspension arbitraire d'annonces actives** (~19% des avis)

> « Impossible de remettre mon annonce en ligne (alors que ca fait des années qu'elle y était) »

> « ils viennent carrément de stopper la publication de mon annonce car je ne louais pas suffisamment de semaines dans l'année alo »

*Impact* : Une perte directe de visibilité et de chiffre d'affaires pour le propriétaire sans préavis clair.

### 2. Service Client — 9 avis (20.5%)

- **Gravité Haute** : 100.0% des avis de cette catégorie
- **Distribution des notes** : 1★: 9

**Incompétence et inefficacité du support client** (~66% des avis)

> « Service client incompétent »

> « Des personnes qui ne comprennent pas nos demandes, ne connaissent pas le site et sont incapables de nous »

> « plus de 10 appels passés au service client, mais je n’ai eu affaire qu’à des interlocuteurs incompétents et impuis »

*Impact* : Le propriétaire se sent abandonné et incapable de résoudre des problèmes critiques malgré de multiples tentatives de contact.

**Problèmes de visibilité et désactivation injustifiée des annonces** (~33% des avis)

> « Cette année, mon annonce n’apparaît plus en ligne »

> « le site suspend mon a »

> « Abritel a désactivé notre annonce suite à une annulation cliente »

*Impact* : Une perte directe de revenus due à l'impossibilité pour les voyageurs de trouver et réserver le logement.

**Dysfonctionnements techniques et ergonomie défaillante de l'interface** (~22% des avis)

> « Application affligeante, site internet plus lent qu'une tortue »

> « on m'envoie un code par sms, je saisis le code "une erreur est survenue" »

> « paramétrage très compliqué »

*Impact* : Une frustration élevée et une perte de temps lors de la gestion quotidienne ou de la mise en ligne des annonces.

### 3. Bug Technique — 6 avis (13.6%)

- **Gravité Haute** : 100.0% des avis de cette catégorie
- **Distribution des notes** : 1★: 5, 2★: 1

**Difficultés d'accès et problèmes de connexion au compte propriétaire** (~50% des avis)

> « impossible de me connecter en mode proprietaire »

> « impossible de me connecter sur mon compte professionnel ! »

> « Impossible de me connecter avec mon compte hote. »

*Impact* : Le propriétaire est totalement bloqué et ne peut plus gérer son activité locative.

**Ergonomie et navigation complexes de l'interface propriétaire** (~33% des avis)

> « Appli pas du tout intuitive. Impossible de trouver l'espace propriétaire. »

> « Interface propriétaire catastrophique »

> « modifier le calendrier est très compliqué »

*Impact* : Une perte de temps considérable et une frustration accrue lors de la gestion quotidienne.

**Dysfonctionnements techniques et instabilité de la plateforme** (~33% des avis)

> « le site dysfonctionne régulièrement »

> « Application lente »

> « Nous sommes obligés d'appeler la plateforme pour toute modification »

*Impact* : Une dépendance forcée envers le support client pour des actions qui devraient être autonomes.

### 4. Financier — 4 avis (9.1%)

- **Gravité Haute** : 100.0% des avis de cette catégorie
- **Distribution des notes** : 1★: 4

**Difficultés de recouvrement et gestion des cautions/dommages** (~50% des avis)

> « si tu as une dégradation tu ne seras pas indemnisé »

> « j'ai du appeler pour réclamer la caution qui a mis 1 mois »

> « un voyageur a dégradé le plan de travail de la cuisine. J’actionne la garantie dommages »

*Impact* : Le propriétaire supporte seul le coût financier des dégradations matérielles et subit des délais de remboursement excessifs.

**Sentiment d'injustice et manque de transparence financière** (~50% des avis)

> « Hôtes, vous êtes la vache à lait! »

> « Ils appliquent des ristournes sur des réservations longtemps à l'avance sans vous demander votre avis »

> « Manque de transparence … à fuir absolument !!. Arnaque … à fuir absolument !! »

*Impact* : Une perte de confiance globale envers la plateforme due à des frais ou remises imposés sans consentement.

### 5. Annulation / Réservation — 4 avis (9.1%)

- **Gravité Haute** : 100.0% des avis de cette catégorie
- **Distribution des notes** : 1★: 3, 2★: 1

**Ergonomie et navigation du calendrier et de l'interface** (~50% des avis)

> « on ne retrouve pas le calendrier des réservations ni les personnes qui ont réservé »

> « Site propriétaire peu intuitif, difficile à trouver les rubriques.. calendrier de réservations désagréable »

*Impact* : Le propriétaire perd en efficacité opérationnelle et éprouve de la frustration lors de la gestion quotidienne de ses locations.

**Dysfonctionnements techniques et erreurs de paramétrage (tarifs/synchro)** (~50% des avis)

> « m’aider à synchroniser des calendriers avec d’autres sites »

> « les tarifs appliqués étaient ceux de la saison hivernale »

*Impact* : Cela entraîne des pertes financières directes ou des risques de surréservation (overbooking).

**Inefficacité du support client et manque de suivi** (~25% des avis)

> « Devaient m’appeler pour m’aider à synchroniser des calendriers avec d’autres sites suite à 2 réservations dont une que j’ai dû annuler. Ne m’ont pas rappelé. »

*Impact* : Le sentiment d'abandon du propriétaire augmente le risque de churn vers des plateformes concurrentes.

### 6. Localisation / Langue — 3 avis (6.8%)

- **Gravité Haute** : 100.0% des avis de cette catégorie
- **Distribution des notes** : 1★: 3

**Instabilité technique et ergonomie du site et de l'application** (~66% des avis)

> « Site anti intuitif et qui bugue »

> « le site est lent, instable, non intuitif »

*Impact* : Le propriétaire éprouve une frustration majeure et une perte de temps dans la gestion quotidienne de son annonce.

**Problèmes de langue et redirection vers des contenus anglophones** (~66% des avis)

> « les langues changent au hasard sans possibilité de changer »

> « vous envoie sur le site américain vrbo qui donne des infos inadaptées, toujours en anglais »

*Impact* : L'incompréhension des instructions peut mener à des erreurs critiques, comme la désactivation involontaire du compte.

**Absence de support client et de recours accessibles** (~66% des avis)

> « maintenant, il n’y a aucun recours possible!?? »

> « Et bien sûr pas de contact »

*Impact* : Le propriétaire se sent abandonné et impuissant face à des décisions administratives ou techniques arbitraires.

## Synthèse : Problèmes → Opportunités

| Problème | Persona(s) | Fréquence | Opportunité |
|----------|------------|-----------|-------------|
| Financier | Locataire (111), Propriétaire (4) | 25% | Transparence tarifaire : affichage du coût total dès la recherche, process de remboursement automatisé avec suivi temps réel |
| Qualité du bien | Locataire (81), Propriétaire (16) | 18% | Vérification des annonces : photos certifiées, scoring de fiabilité, signalement rapide des non-conformités |
| Localisation / Langue | Locataire (66), Propriétaire (3) | 15% | Quick win technique : forcer la locale FR et la devise EUR par défaut pour les utilisateurs français |
| Annulation / Réservation | Locataire (53), Propriétaire (4) | 12% | Politique d'engagement hôte renforcée, relogement automatique en cas d'annulation tardive |
| Service Client | Locataire (48), Propriétaire (9) | 11% | Escalade humaine garantie sous 5 min, suivi de dossier persistant, support spécialisé propriétaire |
| Bug Technique | Locataire (41), Propriétaire (6) | 9% | Stabilisation de l'app mobile, refonte de l'espace propriétaire |

## Interprétation

### Convergence des deux personas

Les problèmes **Service Client** et **Bug Technique** affectent les deux personas. Ce n'est pas un hasard : quand l'outil dysfonctionne (bugs), les utilisateurs contactent le support (service client), qui se révèle incapable de résoudre leurs problèmes. C'est un **cercle vicieux** : bugs → appels au support → support débordé/incompétent → frustration amplifiée.

### Asymétrie locataire / propriétaire

Le locataire se plaint de ce qu'il **subit** (frais cachés, annonces trompeuses, annulations). Le propriétaire se plaint de ce qu'il **ne peut pas faire** (accéder à son espace, gérer ses annonces, contacter un support compétent). Cette asymétrie révèle que la plateforme est conçue comme un tunnel de réservation pour le locataire, au détriment de l'outil de gestion pour le propriétaire.

### Les 3 quick wins

1. **Localisation FR** (15% des avis négatifs locataire) — c'est un bug de configuration, pas un problème structurel. Le corriger supprimerait d'un coup 66 sources de frustration.
2. **Escalade humaine du chatbot** — le chatbot est unanimement rejeté. Ajouter un bouton « parler à un humain » visible réduirait la frustration Service Client.
3. **Espace propriétaire dédié** — 62% des propriétaires mécontents ne trouvent même pas leur interface de gestion. Un lien direct « Espace hôte » résoudrait le problème.

### Les 2 chantiers structurels

1. **Transparence financière** — le problème n°1 (25% des locataires) nécessite une refonte du parcours de paiement : coût total affiché dès la recherche, remboursement automatisé avec tracking, alerte en cas d'écart prix affiché/prélevé.
2. **Fiabilité du catalogue** — des logements « plus en location depuis 3 ans » apparaissent encore disponibles. Un audit automatique des annonces inactives et un système de signalement rapide par les locataires sont nécessaires.

### Ce que le nuage de mots confirme

Le mot le plus fréquent dans les avis négatifs est **impossible**. Il résume l'expérience Abritel telle que perçue par ses utilisateurs : impossible de se connecter, impossible d'avoir le français, impossible de contacter un humain, impossible d'obtenir un remboursement. Chaque opportunité identifiée vise à transformer un « impossible » en une fonctionnalité qui marche.
