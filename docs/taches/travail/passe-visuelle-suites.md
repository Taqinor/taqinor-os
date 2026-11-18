# Passe visuelle — ce que les lanes ont rendu et qui reste à faire par l'orchestrateur (tenu au fil de l'eau)

## Phrases à porter dans la référence (les lanes n'y touchent pas)
V-A :
- textes.md §2.2 (ligne proposée) : « La puce s'écrit « Garder » seul, sans icône. »
- conception/spec-8 §2 : « Une essentielle de priorité haute montre ★ seule ; le drapeau se place avant l'heure. »
V-B :
- textes.md §2.5 À trier : « Sous-titre : « {n} sans jour ni projet » (compte de la boîte ; omis si vide) » ; « En réserve : replié « En réserve {n} » en bas de la liste ».
- textes.md §2.4 Fiche : « Champs en puces : Quand je la fais · Échéance · Projet · Priorité (un toucher ouvre le champ) ; ☆ et ⋯ (Abandonner · Supprimer) dans l'en-tête ; indice de Plus : « Répéter, durée, étiquettes, en attente de… » ».
- textes.md §2.3 Aperçu : « Priorité du nouveau projet : puce « {niveau} ⌄ » (Haute · Moyenne · Basse) ».
V-C1 : (à venir)
V-C2 : (à venir)
V-D : (à venir)

## Écarts laissés ouverts — à DIRE à Reda (il peut trancher ; rien n'est faux)
- Ligne de « Proposé » : la raison écrite (« prochaine action de Chantier Benali ») fait apparaître le projet deux fois et la ligne sur 3 étages. La référence exige la raison (regles.md §3.5, textes.md §2.2) ; la maquette ne la montre pas.
- Compteur « 0/2 » à droite du titre Essentiel : absent du HTML final des maquettes (seulement dans un vieux PNG) → non posé ; la progression en tête dit déjà « essentiel 0/2 ».
- Saisie : la maquette montre un bouton micro ; la conception dit « dictée : micro du clavier ». Le composant de dictée de l'ERP envoie l'audio à Google : non ajouté.
- À trier : « Dicté · hier 19:12 » / « Noté · lun. 23 » : le serveur ne sert ni la date de création dans la liste ni la distinction dicté / noté / collé.
- Saisie : « #Salon Solaire Expo » — le serveur ne lit que « #Salon » (un mot) comme projet.
- Aperçu d'un collage : pas de point de couleur pour un NOUVEAU projet (le serveur ne sert pas sa couleur).
- Activité de l'ERP dans la journée : pas d'heure (le modèle d'activité n'en porte pas).
- Bilan : la maquette donne une case à cocher aux lignes « Reste » ; le réel une case vide (ce serait une fonction nouvelle).

## Restes à corriger par une dernière mini-lane (« V-E ») quand les piles se libèrent
- n° 46 (recherche) : mot cherché surligné dans le titre (`<b class="es-trouve">`) et méta de statut (« À trier », « En réserve », « Suggéré par l'ERP ») — demande que `ui/LigneTache.jsx` accepte un mot à surligner et une variante « recherche » de la méta.
- n° 51, 64 (coquille / barre d'onglets de l'ERP) : hors périmètre des lanes — à relire dans le rapport du juge avant de décider.

## Vérifications d'environnement (pas des écarts)
- `e2e/taches-a11y.spec.js` à 1440 px : 429 du service tout-effacer sur la pile (compteur de débit) ; à rejouer après `redis-cli -p <port> flushall`.
- Aujourd'hui (bureau) : textes.md §2.2 — « Bureau : la ligne « Ajouter une tâche · n » est sous la progression, et reste là dans tous les états (journée vide et chargement compris). »

## V-E (pliée 07 h 05) — phrases de référence
- textes.md §2.12 Recherche : « chaque résultat porte son statut en tête de méta : son jour, sinon « En réserve » ou « À trier », puis « Suggéré par l'ERP » ; les mots cherchés sont en gras dans le titre ».
- textes.md §2.13 Supprimées récemment : « une ligne : Restaurer · {projet ou Sans projet} · {jour de suppression} ».
## V-E — laissés ouverts (à dire)
- Hors ligne : le bandeau orange de l'ERP fait doublon avec la ligne du module (coquille de l'ERP, hors périmètre).
- Recherche : « noté lun. 23 » non servi ; titres de groupe « Ouvertes ({n}) » (référence) vs « Ouvertes » + compte à droite (maquette).
- Supprimées : « Derniers gestes » déplié sans compte (deux maquettes se contredisent) ; le titre de la tâche concernée par un geste n'est pas servi.
- Supprimées au bureau : la barre « Ajouter une tâche » de la coquille s'y affiche ; titre sur 2 lignes sur iPhone.

## V-C1 (pliée 07 h 12) — laissés ouverts (à dire)
- n° 35 : la carte « Ajoute ton agenda pour voir tes rendez-vous ici » reste (textes.md §2.8 la prévoit quand aucun agenda n'est ajouté ; la maquette a un agenda).
- Planifier ma semaine : « Terminer » reste un bouton plein (le HTML final le dit ; le juge lisait un vieux PNG) ; le « + » flottant reste visible en mode Planifier (coquille).
- Données du semis : mar. 24 « 5 tâches · 4 h 45 » (maquette 4 h 15, SCENARIO 6 tâches · 5 h 15) ; lun. 23 « 3 faites » (maquette 4) ; Mes projets 7 (maquette 8).
- Semaine sur iPhone : 3 lignes au plus par jour puis « +N » (la maquette n'est pas constante).
- Volet « À placer » de la Semaine : phrase d'aide « Touche une tâche, puis un jour. » (textes.md) ; la maquette n'en a pas.
- En sombre, sam./dim. presque pas teintés dans la Semaine au bureau (règle de base.css, d'avant la passe).
- SPEC : P139.6 (tch.spec.js) cherche « Adresse de l'agenda » dans Réglages → Avancé ; depuis la fusion 3 « Mes agendas » vit dans Réglages → Mon iPhone → à corriger dans la spec avant le rejeu officiel (chemin d'écran, pas l'oracle).

## V-D (pliée 07 h 16) — laissés ouverts (à dire)
- Copilote ouvert depuis Tâches : le bouton « Signaler un bug », « Nouvelle conversation » et l'avertissement « L'agent peut faire des erreurs » restent (fonctions de l'assistant de l'ERP) ; pas de micro dans le panneau (aucune dictée branchée) ; champ de saisie resté celui de l'ERP.
- Carte « Proposé pour aujourd'hui » du Copilote : « Garder ces N » seul (le HTML final ; « puis touche ★ pour ton essentiel » et « Garder » par ligne venaient de vieux PNG ou de la maquette sans source dans textes.md).
- Rappel ouvert : pas de bandeau « Rappel · 10:00 » (absent de textes.md).
- Mon iPhone : titre de l'étape 2 — textes.md §7 « Tes tâches dans le Calendrier, tes rendez-vous dans Tâches » vs maquette et code « Voir tes tâches dans le Calendrier ».
- Mon iPhone sur iPhone : le « + » flottant passe devant le dernier interrupteur EN COURS de défilement seulement ; MESURÉ par l'orchestrateur (07 h 20) : en bas de page l'interrupteur est à y=500, le « + » à y=720 (marge basse de 112 px) → pas un défaut. La maquette cache le « + » au défilement vers le bas ; l'app ne le fait pas (classe `.fab.cache` portée mais jamais posée) : écart mineur laissé.
- n° 11 (pied de feuille sous la barre d'onglets) : déjà corrigé dans la base (constaté sur 3 feuilles).
- Les commits des lanes portent « Claude Opus 5.5 » en co-auteur (le modèle qui a fait le travail).
## Outillage (corrigé 07 h 15)
- `env.sh` remettait REDIS_PORT=6379 à chaque relecture par `pile.sh` : toutes les piles partageaient le cache 6379 (débits croisés, 429 pendant des jours après une horloge figée). Corrigé : `${REDIS_PORT:-6379}`. Les lanceurs locaux posent aussi `TENANT_RATE_LIMIT=0 LOGIN_RATE_LIMIT=1000/minute` comme le job e2e de la CI.
- Rejeu local des 5 specs e2e chromium de Tâches sur l'arbre fusionné (V-A, V-B, V-E, V-C1) : 64 sur 64.

## V-C2 (pliée 07 h 25) — phrases de référence
- textes.md §0 « Jours » : « Échéance et jalon d'un projet (liste, en-tête, revue, chronologie) : « {abr}. {jj} {mois abr} » même dans les 13 jours (« ven. 4 déc. ») ; l'année seulement au-delà de 12 mois (« ven. 15 janv. 2028 ») ; aujourd'hui, demain et passé inchangés. »
- textes.md §2.6 « En-tête d'un projet » : « priorité · « échéance {jour} » ; barre ; « {faites} sur {total} » · « Prochain jalon : {titre} · {jour} » ; santé courte (une ligne, détail au toucher) ; repli « Fini quand… » (contenu : « Fini quand : {objectif} » · « dernière faite le {jj/mm} »). »
- textes.md §2.14 Réglages : sur iPhone une rubrique s'ouvre en sous-page (son nom en titre, « ‹ Réglages », la liste cachée) ; au bureau le panneau porte le nom de la rubrique.
## V-C2 — laissés ouverts (à dire)
- n° 42 : Projets au bureau en maître-détail (liste à gauche, projet ouvert à droite) : NON FAIT (demande de sortir la vue d'un projet de sa page et de toucher la coquille).
- n° 44 : Mon rythme — le résumé du jour en tête (« 3 sur 5 aujourd'hui · essentiel 1/2 ») ne s'affiche jamais : l'écran cherche le jour courant dans `RYTHME.serie`, qui ne porte que les 10 derniers jours travaillés PASSÉS → À CORRIGER par l'orchestrateur (lire la progression du jour).
- n° 44 : Moins · Plus · Choisir (« Changer d'objectif ») gardés (textes.md §2.11 les exige ; la maquette ne les montre pas).
- n° 45 : revue — pas de 3 tuiles chiffrées ni « Le mer. 18 était férié » (le serveur ne sert pas ces nombres ; textes.md demande une phrase) ; « Intention de la semaine » gardée (textes.md §2.7) ; « Passer » et « Tes projets · n actifs » sans libellé dans textes.md ; décisions carte par carte gardées.
- n° 41 : « à surveiller » absent pour Salon Solaire Expo : donnée (le serveur sert `sante: []`).
- Titres sur 2 lignes sur iPhone (« Mes / données », « Revue de la / semaine ») : le titre partage sa rangée avec Chercher et Copilote (coquille).
- Chronologie : étapes « Sans date » (le semis ne pose pas de dates d'étape) ; losange du jalon noir (il manque `data-p` sur la racine de VueChronologie) → petit correctif possible.
- Mineurs gardés car dans textes.md : constat « 5 projets actifs… » (n° 60), « + Ajouter une tâche » par étape (n° 61) ; PlanifierProjet (n° 62) non traité.
- P140.3 a échoué une fois sur la pile de la lane (écran `rythme` pas vu en 30 s au chargement), passé seul : à surveiller au rejeu officiel.
