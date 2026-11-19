# Tâches et agenda personnels + Copilote — dossier de la fonctionnalité

## Ce que c'est (en 8 lignes)

1. Une nouvelle application de l'ERP, « Tâches », pour que chaque personne gère SES tâches et SON agenda, en privé.
2. L'écran du jour s'appelle **Aujourd'hui** : ce qu'il faut faire, ce qui est proposé, les rendez-vous, un bilan le soir.
3. Les tâches se rangent par **projets** ; on colle ou on dicte une liste, le logiciel propose le rangement, on valide.
4. Les visites, activités et suggestions de l'ERP apparaissent dans la journée, sans rien recopier.
5. Le **Copilote** (l'assistant de l'ERP) sait planifier, prioriser et ranger ; tout marche aussi sans clé d'IA.
6. Sur iPhone : icône, pastille, notifications, calendrier abonné, dictée Siri, grande tuile Scriptable.
7. Personne d'autre ne voit vos tâches : espace privé, pas de projet partagé dans cette première construction.
8. Le module s'allume par étapes : d'abord l'Administrateur seul, le Directeur depuis le 18/11/2026, puis plus largement sur votre parole.

Plan de construction : `docs/plans/PLAN_TACHES.md` (tâches `TCH1` à `TCH179`).
Décisions de Reda : `docs/claude-memory/taches-decisions-fondateur.md`.

## Ce que contient chaque sous-dossier

- **`reference/`** — la vérité. Données (`donnees.md`), routes d'API (`api.md`), règles et algorithmes (`regles.md`),
  mots affichés à l'écran (`textes.md`). En cas de doute, c'est ce dossier qui fait foi.
- **`conception/`** — le pourquoi. `socle.md` (décisions de Reda et architecture), `arbitrages.md` (les 18 choix
  tranchés pendant la conception), `spec-2` à `spec-8` (saisie, journée et agenda, projets, rythme, assistant, ERP,
  iPhone, écrans, langage visuel), `consignes-construction.md` (comment construire sous Windows).
- **`maquettes/`** — le contrat visuel : les écrans dessinés en HTML, avec leurs feuilles de style et `SCENARIO.md`
  (la journée d'exemple et ses chiffres).

### Ouvrir une maquette

Double-cliquez sur un fichier `.html` de `docs/taches/maquettes/` (par exemple `ecran-aujourdhui-matin.html`) : il
s'ouvre dans le navigateur, sans serveur. Ajoutez `?vue=iphone` ou `?vue=bureau` à la fin de l'adresse pour choisir la
taille, et `?theme=sombre` pour le mode sombre.

### Relancer les outils des maquettes

Ils sont dans `docs/taches/maquettes/outils/` et utilisent Playwright du dossier `frontend/node_modules` du dépôt
principal (variable `PLAYWRIGHT_DIR` pour pointer ailleurs). Depuis la racine du dépôt :

- `node docs/taches/maquettes/outils/capturer.cjs docs/taches/maquettes/<fichier>.html` — fabrique les captures PNG
  (iPhone et bureau, clair et sombre) ; sans second argument elles vont dans un dossier `captures/` à côté de la
  maquette. Ce dossier n'est jamais versionné.
- `node docs/taches/maquettes/outils/verifier.cjs` — contrôle toutes les maquettes (icônes, contraste, cibles de 44 px,
  éléments recouverts, mots interdits) ; il échoue au premier défaut. On peut lui donner un seul fichier.

## Les quatre fusions et ce que chacune rend utilisable

- **F1 — le socle, invisible.** Modèles, contrats, moteurs de calcul. Rien n'est visible : personne n'a le droit
  d'ouvrir l'app, sauf les comptes techniques.
- **F2 — le cœur complet.** Saisie, Aujourd'hui, agenda, projets, rythme, réglages, liens ERP, hors ligne. Activé à
  la fin pour le SEUL rôle Administrateur ; depuis le 18/11/2026 le rôle Directeur l'a aussi (voir « Vous ne voyez
  pas la tuile Tâches ? »).
- **F3 — iPhone et Copilote.** Pastille, notifications, calendrier abonné, Siri, tuile, écran « Mon iPhone », Copilote
  qui planifie et range.
- **F4 — l'avancé replié.** Étiquettes, vues enregistrées, planification de projets avancée ; puis l'ouverture aux
  autres rôles (le Directeur d'office depuis le 18/11/2026, tâche `TCH168` ; les autres par votre geste).

## Essayer le cœur (après la fusion F2)

1. Lancer la pile locale (`docker compose up`, voir le fichier `CLAUDE.md` à la racine).
2. Charger la journée d'exemple : `python manage.py seed_taches_demo` (commande créée par la tâche `TCH169`, absente
   avant F2) ; elle crée le compte de démonstration `demo_taches`.
3. Se connecter avec un compte au rôle **Directeur** ou **Administrateur** (ou `demo_taches`) : la tuile **Tâches** apparaît dans le
   menu Applications (⊞) ; elle ouvre Aujourd'hui, avec les quatre onglets Aujourd'hui · À trier · Projets · Agenda.
   On peut aussi taper `/taches/aujourdhui` dans la barre d'adresse.
4. Après un déploiement sur un serveur existant, `python manage.py init_roles` (lancé par le déploiement) donne le
   droit aux rôles Directeur et Administrateur de chaque société.

Les autres rôles ne voient ni la tuile ni les onglets : pour ouvrir Tâches à un autre rôle, Paramètres → Rôles, cocher
la case « Tâches ».

### Vous ne voyez pas la tuile Tâches ?

- **Votre compte est le propriétaire de la société (ou un superutilisateur).** Chaque déploiement range ce compte sur
  le rôle **Directeur**. Jusqu'au 18/11/2026 ce rôle n'avait pas le droit de voir Tâches (seul l'Administrateur
  l'avait) : vous ne pouviez donc pas voir votre propre module, et changer votre rôle à la main était défait au
  déploiement suivant. Corrigé le 18/11/2026 : il faut un déploiement (`powershell -File scripts\deploy-prod.ps1`),
  puis recharger la page (ou fermer et rouvrir l'application installée).
- **Votre compte a un autre rôle** (Commercial, Technicien…) : c'est voulu ; voir « Ouvrir Tâches à d'autres
  personnes » plus bas.

## L'avancé (après la fusion F4) — où le trouver

Rien de tout cela n'encombre l'écran du jour : c'est rangé un cran plus loin, pour le jour où vous en avez besoin.

- **Étiquettes** — dans la fiche d'une tâche → « Plus » → Étiquettes ; la Recherche filtre ensuite par étiquette.
- **Vues enregistrées** — dans la Recherche : régler les filtres, enregistrer la vue, la rouvrir d'un toucher.
- **Un projet en Tableau ou en Chronologie** — dans un projet, le choix Liste · Tableau · Chronologie ; le projet se
  rouvre dans la dernière vue utilisée.
- **Modèles de projet** — le ⋯ d'un projet : « Enregistrer comme modèle », « Dupliquer » ; Projets → Modèles pour en
  utiliser un, avec l'aperçu des dates avant de créer. Une tâche confidentielle n'est jamais reprise dans un modèle
  ni dans une copie : l'écran le dit.
- **Suggéré par l'ERP** — en tête d'À trier : quand un devis est accepté, un chantier réceptionné ou annulé, l'ERP
  propose la tâche qui suit (« Ajouter » ou « Pas utile »). Réglages → « L'ERP me suggère » choisit lesquelles
  (« Visite validée : préparer le devis » est éteinte au départ).
- **Au bureau** — sur un grand écran, Aujourd'hui montre l'agenda du jour à droite : on glisse une tâche sur une heure.
- **Depuis n'importe quel écran de l'ERP** — les touches `c` puis `t` ouvrent la saisie d'une tâche ; le bouton ✓+ de
  l'en-tête montre les tâches liées à la fiche ouverte (lead, devis, chantier…) et en crée une déjà liée ; le cockpit
  porte une carte « Tâches · Aujourd'hui » ; le bouton « + À faire » de l'écran Activités ouvre la même saisie.

## Ouvrir Tâches à d'autres personnes — seulement quand vous le dites

Aujourd'hui les rôles **Directeur** et **Administrateur** voient Tâches (le Directeur depuis le 18/11/2026 : la tâche
`TCH168` a été construite sans attendre, parce que le compte du propriétaire est toujours rangé « Directeur » et ne
voyait donc pas le module). Pour ouvrir à quelqu'un d'autre :

- **Un rôle à la fois, sans rien construire.** Paramètres → Rôles → cocher la case « Tâches » du rôle voulu ; on
  revient en arrière en décochant. Chacun n'y voit que SES tâches : ouvrir le module ne montre les vôtres à personne.
  Un rôle du portail client ne peut jamais le recevoir.
- **Revenir à « Administrateur seul »** se demande en une phrase (c'est une ligne de code) ; mais le propriétaire de
  la société ne verrait alors plus le module.

**Une question à trancher AVANT d'ouvrir à un commercial.** Un lead qui a une date de relance apparaît deux fois dans
sa journée : comme activité « Relance commerciale » et dans la ligne « Suivi des relances : n ». Rien n'est faux, mais
c'est en double. Tant que seuls le Directeur et l'Administrateur voient Tâches, cela ne se voit que si l'un d'eux
porte lui-même des leads à relancer. Dites laquelle des deux lignes garder ; la correction se fait avant l'ouverture.

## À essayer par Reda sur son iPhone

Aucune tâche du plan ne prouve ces points : ils demandent votre vrai téléphone, vos comptes ou la production. Dans
l'ordre d'arrivée :

- **Essayer le cœur** (après F2) — utiliser Aujourd'hui quelques jours, au bureau et sur l'iPhone. C'est vous seul qui
  savez si cela vous convient.
- **Activer les notifications** — l'iPhone doit autoriser les notifications de l'ERP installé sur l'écran d'accueil ;
  seul votre téléphone peut accepter cette demande. Côté production, vérifier aussi que la clé `VITE_VAPID_PUBLIC_KEY`
  est présente au montage du front et que `NOTIFICATIONS_TOUJOURS_IMMEDIATES` contient `taches_rappel` : ce sont des
  réglages du serveur que Claude ne touche pas.
- **S'abonner au calendrier « Tâches Taqinor »** — ajoute vos tâches au Calendrier d'Apple par un lien d'abonnement ;
  l'abonnement se fait dans les réglages de VOTRE compte iCloud. À vérifier sur votre téléphone : que le bouton
  d'abonnement (une adresse `webcal://`) ouvre bien Calendrier.
- **Créer le raccourci Siri « Nouvelle tâche »** — suivre la recette de l'écran « Mon iPhone », le partager par iCloud
  et coller son lien dans `TACHES_RACCOURCI_SIRI_URL` du `.env` de production : le raccourci vit dans votre compte
  Apple, et le `.env` de production est un geste de serveur qui vous revient.
- **Installer Scriptable et la grande tuile** — Scriptable est une application gratuite de l'App Store ; l'installer
  et poser la tuile sur l'écran d'accueil demande votre appareil et votre identifiant Apple.
- **Choisir Aujourd'hui comme accueil** — réglage personnel de l'ERP sur votre téléphone : c'est votre goût qui tranche.
- **Régler le fournisseur et la clé d'IA de production** — pour que le Copilote réponde en production ; c'est un secret
  et un abonnement payant qui ne passent jamais par Claude.
- **Dire si vous ouvrez Tâches aux autres rôles** (F4) — le plan attend votre parole.

## Vos gestes sur le serveur

- **Déployer après chaque fusion.** Depuis le 17/11 plus rien ne se met en ligne tout seul : une fusion n'est visible
  qu'après votre `scripts/deploy-prod.ps1` (environ 2 minutes). Le déploiement lance `init_roles`, qui donne le droit
  « Tâches » au rôle Administrateur.
- **Notifications** — `VITE_VAPID_PUBLIC_KEY` présente au montage du front ; `NOTIFICATIONS_TOUJOURS_IMMEDIATES` du
  `.env` contient `taches_rappel` (si la ligne existe dans le `.env`, elle remplace la valeur par défaut).
- **Raccourci Siri** — coller le lien iCloud du raccourci dans `TACHES_RACCOURCI_SIRI_URL` du `.env` ; vide, l'écran
  « Mon iPhone » ne le propose pas.
- **Copilote** — il suffit que la clé d'IA de production soit posée. Les réglages par défaut conviennent
  (`ASSISTANT_COPILOTE=admins`, `ASSISTANT_MOTEUR=langchain`) : c'est avec eux que l'essai en vrai a été joué. Sans
  clé, les quatre demandes prêtes (planifier, prioriser, coller une liste, faire le point) répondent quand même.
- **Journal du serveur web** — l'adresse du calendrier abonné contient son jeton (l'iPhone l'impose). Django et Sentry
  le masquent ; le journal d'accès de nginx, lui, écrit encore l'adresse entière. Ce fichier appartient au
  déploiement et une erreur y coupe le site : la correction est proposée à part, à lancer quand vous voulez. En
  attendant, « Régénérer » dans Mon iPhone remplace le jeton à tout moment.

## Ce que les tours de revue du 19/11 ont changé

Deux tours de revue ont relu chaque écran sur la vraie pile. Voici ce que vous verrez de différent :

- **Un chiffre, une seule source.** « Essentiel », « faites cette semaine » et les totaux disent pareil sur Aujourd'hui,
  le bilan du soir, Mon rythme, la Revue, la Recherche et l'Agenda. Le second chiffre « x des y gardées » a disparu.
- **Un matin moins encombré.** Au plus une carte de conseil par jour, et aucune statistique le matin si elle ne
  propose pas un geste.
- **Reporter une tâche qui est due aujourd'hui** ne la fait plus revenir en silence : elle reste visible, le dit, et
  « Repousser l'échéance » est à un toucher.
- **La fiche d'une tâche s'ouvre tout de suite**, avec son titre, son jour, son projet et son étoile, sans « Chargement… ».
- **Au bureau, les largeurs sont posées.** L'en-tête et les actions sont au même endroit partout, la lecture reste sur
  une colonne étroite, la Semaine de l'Agenda est lisible (deux tâches à la même heure se mettent côte à côte).
- **Les mots du système sont remplacés** : « Plus tard », « Aujourd'hui », « Découper en sous-tâches »,
  « Supprimées », « Continuer » dans la Revue, « Télécharger mes données ».
- **Un refus du serveur est dit sous le bon champ** (un nom de projet déjà pris, par exemple), sans message d'erreur général.
- **L'étoile ne change plus d'avis** entre la liste et la fiche.
- **Une journée trop pleine est dite honnêtement** : le Copilote ne répond plus « Objectif atteint » quand ce n'est pas
  vrai, et propose d'alléger.
- **Sur un réseau lent**, une tâche qu'on vient de saisir est déjà là, grisée « envoi… ».

## Ce que la construction a choisi seule — vous pouvez inverser

Vous aviez demandé de ne poser aucune question. Voici les choix qui touchent ce que vous voyez. Chacun dit ce qui a
été choisi, pourquoi, et que vous pouvez l'inverser (dites-le : c'est une ligne de code).

**Choix C-1 à C-12 (premier tour)**

- **C-1 — Une tâche ajoutée depuis Aujourd'hui va dans Aujourd'hui** (pas dans À trier), comme Things et Todoist ;
  la saisie par `c t`, Siri ou hors de Tâches reste dans À trier. Vous pouvez inverser.
- **C-2 — Au bureau, la fiche est un panneau à droite** (la liste reste visible), comme la maquette ; l'iPhone garde
  sa feuille du bas. Vous pouvez inverser.
- **C-3 — Au bureau, la saisie s'ouvre en place**, sous « Ajouter une tâche », sans fenêtre centrée. Vous pouvez inverser.
- **C-4 — Au bureau, les Projets sont en liste à gauche et projet à droite** ; l'iPhone garde liste puis projet. Vous
  pouvez inverser.
- **C-5 — Mettre un projet en pause laisse en place ce qui est déjà posé aujourd'hui** (« ce que j'ai posé reste
  posé ») ; la pause arrête Proposé, À trier et les jours à venir, et la Revue le dit. Vous pouvez inverser.
- **C-6 — Sur iPhone, la barre de l'ERP est masquée dans Tâches** (une seule barre, celle du module, avec ☰ et la
  cloche). Vous pouvez inverser.
- **C-7 — Dans Mon rythme, revenir à « En faire plus » après « Sans objectif » rend le dernier palier** : essayer les
  modes ne fait plus perdre l'objectif. Vous pouvez inverser.
- **C-8 — « Apps » dans la barre du bas est laissé tel quel** : c'est le modèle de toute l'ERP, hors de Tâches.
- **C-9 — Cocher une activité de l'ERP se défait pendant le toast** : la clôture n'est envoyée qu'à la fin du toast.
  Vous pouvez inverser.
- **C-10 — `j` et `k` parcourent aussi À trier, la Recherche et la liste des Projets** (pas l'Agenda, où ce sont les
  flèches), comme Linear et Todoist. Vous pouvez inverser.
- **C-12 — « Faites » un jour donné = les tâches finies ce jour-là**, partout (Agenda, Mon rythme, Revue), parce que
  c'est ce que vous avez fait ce jour-là. Vous pouvez inverser.

**Choix C-13 à C-24 (second tour)**

- **C-13 — Une tâche due aujourd'hui, reportée, reste dans la journée et le dit**, avec « Repousser l'échéance » :
  une échéance n'est jamais déplacée en silence. Vous pouvez inverser.
- **C-14 — « Essentiel » = les ★ de la section Essentiel affichée**, une seule règle ; « x des y gardées » est supprimé.
  Vous pouvez inverser.
- **C-15 — « Garder ce rythme » part de la moyenne réelle dès 5 jours évalués**, et dit franchement qu'il garde le
  palier avant (c'est votre phrase : « that is enough… keep the same pace »). Vous pouvez inverser.
- **C-16 — « Cette semaine » = tout ce qui est fini du lundi à maintenant**, week-end et aujourd'hui compris,
  partout ; « Objectif atteint X jours sur N » quitte la tête de la Revue. Vous pouvez inverser.
- **C-17 — Au plus une carte de conseil par jour, aucune statistique sans geste le matin** : les chiffres sans
  question vivent dans Mon rythme et le bilan du soir. Vous pouvez inverser.
- **C-18 — Largeurs au bureau : colonne de lecture pour les listes, pleine largeur pour l'Agenda, le Tableau et
  la Chronologie**, avec un en-tête toujours sur la même largeur. Vous pouvez inverser.
- **C-19 — Les projets sont groupés par priorité par défaut**, ordre manuel dans chaque groupe : une Haute ne passe
  plus sous une Moyenne. Vous pouvez inverser.
- **C-20 — Les mots du système sont remplacés** : « Plus tard », « Aujourd'hui » (la puce), « Continuer »,
  « Découper en sous-tâches » ; « Garder ces N » et « Garder ce rythme » restent, ce sont vos mots. Vous pouvez inverser.
- **C-21 — Le samedi travaillé est montré** (Agenda, Mon rythme « hors objectif ») **sans changer les jours
  travaillés** : le calendrier de la société fait foi. Vous pouvez inverser.
- **C-22 — Une seule tuile « Demain »** (plus de « Reporter à {jour} » le même jour), comme Things. Vous pouvez inverser.
- **C-23 — L'appui long sur iPhone ouvre une feuille du bas** titrée de la tâche (rangées de 48 px), plus un menu de
  bureau. Vous pouvez inverser.
- **C-24 — Au premier jour, on lit « 1 faite », jamais « 0 sur 5 »** : le chiffre d'objectif vient quand il dit
  quelque chose de vous. Vous pouvez inverser.

**Autres choix, encore vrais**

- **Le Copilote demande un toucher dès qu'il a lu quelque chose.** Après une lecture dans la conversation, ou un texte
  collé, il n'écrit plus directement : il montre une carte « à valider ». « Mets la priorité haute à telle tâche »
  arrive donc toujours en carte (il doit d'abord la chercher). C'est plus strict que prévu ; c'est le seul réglage
  dont la sûreté a pu être prouvée.
- **Les tâches faites se replient dans « Faites »**, alors que la maquette de 15 h les montrait barrées à leur place.
  Seule l'essentielle faite reste visible dans Essentiel.
- **Trois conseils de « Mon rythme » sur huit sont allumés** : le jour de la semaine à alléger, l'heure à laquelle vous
  finissez vos tâches, les tâches reportées trois fois. Quatre ont été retirés pendant la construction : deux dont le
  « Oui » ne changeait rien (« garder moins de tâches », « reprendre un projet négligé »), deux qui lisaient des
  données que rien n'écrit encore (le matin contre l'après-midi). Le cinquième attend la durée réelle des tâches. Ils
  reviendront quand ils auront un effet.
- **Les raccourcis clavier** `d` et `m` ne marchent que sur Aujourd'hui ; `j` et `k` marchent aussi dans À trier, la
  Recherche et la liste des Projets (voir C-10).
- **Au bureau, la ligne « Ajouter une tâche » reste sur une journée vide.** La maquette de l'état vide ne la dessine
  pas ; l'iPhone, lui, garde son bouton « + » : on ne retire jamais le moyen d'ajouter une tâche.

Le détail et les raisons sont dans `docs/claude-memory/taches-decisions-fondateur.md`.

## Écarts d'apparence connus avec les maquettes — à toi de trancher

Une passe complète a comparé chaque écran aux maquettes (65 écarts relevés, corrigés pour la plupart) ; les tours du
19/11 en ont encore réglé : Projets en liste et projet côte à côte au bureau, deux tâches à la même heure côte à côte
dans la Semaine, un seul signal « hors ligne ». Ceux-ci restent, parce que la maquette et les textes de référence se
contredisent, ou parce qu'il manque une donnée :

- **Ligne de « Proposé »** : la raison écrite (« prochaine action de Chantier Benali ») répète le nom du projet, la
  ligne tient sur trois étages. Les textes de référence exigent la raison ; la maquette ne la montre pas.
- **Saisie** : la maquette montre un bouton micro ; la conception dit « micro du clavier ». Le bouton de dictée de
  l'ERP envoie l'audio à Google : il n'a pas été ajouté.
- **À trier et Recherche** : « Dicté · hier 19:12 », « Noté · lun. 23 » — le serveur ne sert ni la date de création
  ni la façon dont la tâche est entrée.
- **Revue de la semaine** : une phrase de bilan au lieu des trois tuiles chiffrées (le serveur ne sert pas ces
  nombres) ; le champ « Intention de la semaine » est gardé.
- **Mon rythme** : les boutons Moins · Plus · Choisir sont gardés (les textes les exigent ; la maquette ne les montre
  pas).
- **Agenda** : la carte « Ajoute ton agenda… » reste tant qu'aucun agenda n'est ajouté.
- **Copilote ouvert depuis Tâches** : « Signaler un bug », « Nouvelle conversation » et l'avertissement de l'assistant
  de l'ERP restent ; pas de micro dans le panneau.
- **Sur iPhone**, le bouton « + » reste visible pendant le défilement (la maquette le cache quand on descend) ; en
  bas de page, rien n'est recouvert.
- **Données de la journée d'exemple** : quelques chiffres diffèrent des maquettes (« 4 h 45 » au lieu de « 4 h 15 »,
  « 3 faites » au lieu de 4 le lundi) : c'est le jeu de démonstration, pas l'écran.
- **Tableau d'un projet** : il commence à 332 px du haut au lieu de 472, mais la cible (260 px ou moins) n'est pas
  atteinte.
- **La cloche** de Tâches est passée à gauche, près de ☰ (écart assumé : le titre centré la recouvrait).
- **« Ajoutées récemment »** (Recherche) montre les 10 dernières tâches ouvertes, pas celles des 7 derniers jours :
  le serveur ne sert pas la date de création.
- **Hors de Tâches**, le panneau de notifications de l'ERP reste blanc en mode sombre, et affiche « Rien à signaler
  ici » sous une notification non lue.
- **Échap** est avalé quelques millisecondes juste après un choix dans un menu ⋯ (même comportement que sur l'ERP).
- **Le champ de saisie qui grandit avec le texte** n'a pas été vérifié sur un vrai Safari : à regarder sur votre iPhone.


## Une précision honnête

Les rapports de vérification (`verif-*.md`), les recherches (`recherche-*.md`) et les autres pièces de travail de la
phase de conception ne sont PAS sur `main` : ils restent sur la branche de travail `claude/erp-task-manager-ai-f8db1b`.
Certains documents de `conception/` citent donc des fichiers `verif-*.md` ou `recherche-*.md` absents d'ici ; leurs
conclusions utiles sont reprises dans `arbitrages.md` et dans `reference/`.
