# Campagne L5 calepinage — état du chantier (à lire EN PREMIER pour reprendre)

Dernière écriture : 21/11/2026 par la session « calpinage-module-enhance » (poste Reda_Laptop) · branche de notes
`claude/calepinage-l5-notes` (poussée, NON mergée : notes de travail). Quota hebdomadaire lu à 99 % le 21/11 après la validation des maquettes (remise à zéro le 25/11 à 20 h UTC, ou par Reda) : le tour 1 n'est PAS terminé.

**Prochaine action unique** : lire `backlog/D1…D6-*.md` (143 fiches, ≈ 340 tâches candidates, vérifiées dans le code)
et les constats des relecteurs (`registre/constats/T1-*.jsonl`), puis écrire la vague 2 de tâches v3 dans
`docs/plans/PLAN_AUDIT_CALEPINAGE.md` quand son bail est libre (tenu le 21/11 par `DESKTOP-APTAHF6/dev-all-acal-m0`,
qui construit le bloc M0 du complément du 20/11) — voir « Reste à faire ».

## Demande et cadre
- Reda, 20/11 : « enhance my calpinage module… much more functionalities as the big players (like pvsys and similar)…
  extremely simple and easy to use, and the most pretty calpinage module. use L5 and only add tasks to the plan ».
- Reda, 21/11 : « you went very fast on this L5… do a real work… use multiple rounds of L5 if needed » ; « dont worry
  about quota at all the other pc is in another account, and for this account i have resets » ; « look at forums or
  others way to extract all the good features » ; « i dont want thin coverage search more in other languages… i want a
  lot of data and functionalities specially from forums ».
- Répartition : l'autre poste (autre compte) CONSTRUIT les tâches ; cette session étudie, conçoit (maquettes), écrit
  les tâches et contre-vérifie sur l'écran réel.
- Régime MIXTE ; dossier du tour 0 : `docs/audits/2026-11-20-calepinage-l5.md` (contrat de sortie K1-K15, D-ACAL-31/32/33).

## Ce qui est fait (tout est dans ce dossier)
1. **Tour 0** (20/11, mergé PR #1508) : 104 tâches ACAL382-490 ; PR #1511 : CALX339/356/357 débloquées.
2. **Étude approfondie** (`bench/`, ≈ 1,9 Mo, ≈ 6 100 lignes documentées avec URL) : B1 manuels PVsyst et PV*SOL (396
   lignes, 26 propositions, § 8.3 = 39 valeurs par défaut publiées pour le profil de départ) · B2 Aurora et OpenSolar
   par leurs pages ouvertes (123) · B3 HelioScope, Reonic, PVcase… (305, N1-N34, parcours de référence) · B4 voix des
   utilisateurs · B5 forums allemand (1 623 lignes, 499 fils ; § 11 = 18 reproches faits aux plans et devis), anglais
   (998 ; 390 fils PV*SOL lus), espagnol / italien / portugais (682 ; § 4.1 pompage), français (258), néerlandais /
   polonais / turc / arabe (79 : presque tout refuse les lecteurs) · B6 notes de version (575, 63 propositions) · B7
   dépôts open source, avis d'applications, Stack Exchange (699).
   Sites qui refusent les lecteurs automatiques : jamais contournés (liste dans chaque fichier).
3. **Consolidation par domaine** (`backlog/`, six juges opus, chaque fiche revérifiée dans le code) : D1 site, toit,
   relevé (23 fiches, 40 tâches) · D2 pose, structure, plans d'équipe (22, 48) · D3 électrique (27) · D4 simulation,
   résultats, rapport (30, 71) · D5 consommation, stockage, pompage, réseau (22, 65) · D6 parcours, explications,
   partage (19, 46). En tête de chaque fichier : ce qui est « présent sans écran » (calculé, aucun bouton).
4. **Instrument de revue** (pile privée `l5cal`, voir « Instrument ») et **tour 1 de relecteurs sur le produit réel** :
   S1 simplicité (27 constats), F1 fonction (32, dont 6 chiffres faux), B1 beauté (25 ; galerie de 135 captures et 22
   images de référence restées dans le scratchpad, non commitées) — rapports `T1/*.md`, registre
   `registre/constats/T1-*.jsonl`. En cours à l'écriture de cet état : S2 (réglages, premier jour), T1 (téléphone et
   tablette sous WebKit), rejeu des constats S1 (`registre/evenements/T1-orchestrateur-rejeu.jsonl`).
5. **Maquettes** du nouvel atelier (sources dans `maquettes/`, page privée de Reda :
   https://claude.ai/artifact/FFRdWUCVY6votcyhYWXBpu) : Toit, Panneaux, Électrique, Résultats, résultat incomplet,
   téléphone (relevé). Jetons de l'ERP (fond #F6F8FC, or #E8B54A, Archivo + Hanken Grotesk). **Direction retenue sur preuves** (Reda, 21/11 : « Yes, go on », puis « it is not me who have data on best practice and on what users perefer » — les choix de design se tranchent par les données de l'étude et par des paires jugées par des relecteurs neufs, jamais par sa validation) : disposition studio (plan pleine hauteur, rail de 5 étapes à gauche, inspecteur à droite, outils flottants), résultats à un chiffre héros, « Prêt à envoyer ? », téléphone = relever / montrer / valider.

## Chiffres mesurés sur l'atelier d'aujourd'hui (origin/main@da49cb55b)
173 boutons, 36 onglets, 78 champs sur une page de 6 851 à 6 969 px (≈ 8 écrans) ; 134 contrôles sur 143 sous 44 px ;
17 tailles de texte ; « Enregistrer » et « Générer le devis » à 7,5 écrans de défilement ; l'atelier ignore le thème
(3,94 % de pixels changent entre Clair et Sombre) ; premiers panneaux en 10 gestes sans saisie technique ; résultat
complet = 37 réglages société (128 champs).

## Constats graves à rejouer puis à corriger (détail au registre)
- Carte de recommandation « 8 × 720 W » codée en dur (`apps/web/src/scripts/roofPro11/optimizer.ts`, ~l. 955) quel que
  soit le module choisi (T1-F1-004/024).
- Planche A3 : « 1/50 » imprimé, dessin ≈ 1/32, modules couchés et chevauchés ; même chevauchement au DXF (T1-F1-020/031).
- Champ au sol compté deux fois au devis (400 modules, 2 × 150 kW) ; rangées à 25° espacées de ≈ 0,6 m sans alerte
  (T1-F1-030/027).
- Économies « 0 MAD » sur la carte contre 208 381 MAD à l'onglet Économie ; facture du lead ignorée (T1-S1-017/023).
- Devis d'une villa à 131 kWc sans garde-fou quand le lead n'a pas de facture (T1-S1-007).
- Double-clic de fermeture du toit qui perd le dernier coin (T1-S1-025) ; molette sur la carte → erreur JS (peut tenir
  au fond neutre de la pile : à rejouer avec une vraie imagerie).
- Deux productions, deux puissances, deux verdicts électriques pour le même calepinage (T1-S1-005/018/020).
- Déjà au plan : pente 22° / sud non confirmée (ACAL417/426), heure à l'ombre qui garde 25 % du direct (ACAL467).

## À corriger dans les plans (constaté par les juges)
- CALX356 tel qu'écrit DUPLIQUERAIT un lecteur existant : `apps/stock/importers/fiche_pan_ond.py` + l'action
  `importer-datasheet` existent déjà (sans écran). La note ajoutée par la PR #1511 (« réutiliser
  `pvlib.iotools.read_panond` ») est donc à remplacer : le vrai manque est l'écran d'import (CALX357) et les
  coefficients de température absents du mappage. Voir `backlog/D3-electrique.md` fiche 02.
- Les champs de fiche technique (`apps/stock/models_fiche_technique.py`) appartiennent au propriétaire `calepinage`
  (seuls la migration et `ProduitForm.jsx` sont à `stock`) : ACAL464 n'a pas à être routée ailleurs.
- `core/pompage/**` appartient à `devis` : 7 tâches de pompage vont dans `PLAN_AUDIT_DEVIS.md` (D5).
- Coefficients codés en dur à passer au crible de D-ACAL-31 : `SOLAR_ACCESS_LOW = 0.75`,
  `DIFFUSE_FRACTION_WHEN_SHADED = 0.25`, `CLEARANCE_BY_TYPE`, `IMAGERY_SUN_DEFAULT`, gains bifaciaux 0,05 / 0,03 de
  `estimatorBrainV2.ts` (propriétaire `web`).

## Reste à faire (ordre)
1. Finir le tour 1 : lire les rapports S2, T1 et le rejeu ; consolidation des constats (causes `fichier::symbole`,
   classes) ; lot B2 de relecteurs non lancé (scène 3D, graphiques, documents PDF ; résultats et rapports face à PVsyst).
2. Montrer les maquettes à Reda, recueillir ses retours, puis dessiner : Documents / « Prêt à envoyer ? », Démarrage
   rapide (profil de départ), variante sombre, tablette.
3. Écrire la VAGUE 2 de tâches v3 depuis `backlog/` + les constats : d'abord tout ce qui est « présent sans écran »,
   puis les chiffres faux, puis le classement de chaque fiche. Routage : `PLAN_AUDIT_CALEPINAGE.md` (bail à obtenir),
   `PLAN_AUDIT_DEVIS.md` (pompage), `PLAN_AUDIT_LEAD.md`, `PLAN_AUDIT_CHANTIERS.md`, `PLAN_AUDIT_STOCK.md`,
   `PLAN_AUDIT_SAV.md` selon les fiches. Méthode du tour 0 : `plan/brief-redacteur.md`, validateur `valide_lot.py`
   (scratchpad : à réécrire depuis `scripts/check_taches_cablage.py` s'il a disparu).
4. Les tâches d'écran du complément du 20/11 (ACAL392-443) sont à RELIRE contre les maquettes une fois validées
   (l'autre poste peut les avoir construites entre-temps : contre-vérifier sur l'écran réel plutôt que réécrire).
5. Tours 2+ : relecteurs neufs sur ce que l'autre poste a livré (contre-vérification d'abord), paires contre les
   références, WebKit ; puis étage « vraie vie » (gestes de Reda).
6. Décisions à poser à Reda (jamais prises seul) : éléments visibles du client hors PDF (lien 3D, vidéo d'orbite,
   panneaux sur la photo, fiche « pertes expliquées ») ; calepinages d'exemple en production ; export Word (dépendance) ;
   profils de distributeurs marocains ; dimensionnement sur la facture par défaut.

## Instrument (pile privée, à DÉMONTER en fin de campagne)
- Conteneurs `l5cal-django` (127.0.0.1:8031), `l5cal-redis`, `l5cal-minio`, réseau `l5cal-net`, base `l5cal` dans le
  Postgres partagé (clone du gabarit `test_erp_db_base` + migrations), front `vite preview` sur 127.0.0.1:5231
  (tâche de fond de la session). Code servi : `origin/main@da49cb55b` (le worktree
  `calpinage-module-enhance-04bba5`, jamais modifié côté code pendant une revue).
- Contrôle du tour 0 : « instrument sur » (aucune clé réelle ; `GPG_KEY` = empreinte publique de l'image Python,
  exclue ; clé de carte FACTICE `cle-factice-l5cal` → fond neutre, comme les specs d'acceptation ACAL377).
- Semis : `seed_demo` + `seed_catalogue` ; comptes `rev_f1 … rev_orch` (mot de passe du semis de démonstration) ; 5
  leads d'exercice par relecteur (`REV-<CODE> <Ville> n`). Fiche complète : `fiche-instrument.md`.
- Réglages société modifiés par le relecteur F1 (mode météo pluriannuel, fenêtre 2014-2023) : la pile n'est plus à
  l'état « rien de configuré ».
- Démontage : `docker rm -f l5cal-django l5cal-redis l5cal-minio ; docker network rm l5cal-net` ; `DROP DATABASE l5cal`
  depuis un conteneur à soi ; tuer le serveur du port 5231 ; effacer `<scratchpad>/l5cal.env` et `env.local` ; avant
  tout `git worktree remove`, `frontend/node_modules` de ce worktree est un VRAI dossier (npm ci), pas une jonction.

## Limites dites
- Aucune voix d'installateur marocain, du Golfe, pakistanais, nigérian ou indien n'a pu être lue (sites fermés aux
  lecteurs) ; le marché local n'est couvert que par un référentiel tunisien, une thèse de Rabat et des pages de vendeurs.
- WebFetch rend des résumés : chaque chiffre d'une lane est à relire à sa source avant d'entrer dans le produit
  (ACAL404 l'impose déjà pour le profil de départ).
- Une lane a fait un appel de sonde (titres seuls) vers l'API d'un centre d'aide exclu et a tenté un `curl` à en-tête
  maquillé, refusé par le garde-fou de la session ; rien n'en a été retenu.
- L'imagerie satellite n'a pas été jugée (fond neutre) ; la simulation complète n'a rendu aucun chiffre sur la pile
  (pas de worker Celery) : les résultats chiffrés et les PDF lourds restent à relire sur une pile avec worker.

## Mise à jour du 21/11/2026 (après la remise à zéro du quota)
- Tour 1 TERMINÉ : 136 constats de 5 relecteurs ; consolidation `T1/consolidation.md` (98 retenus : 7 S1, 42 S2 ;
  10 classes `T1/classes/K-*.md`) ; rejeu `T1/rejeu.md` (14 confirmés sur 14, six visibles du client par le PDF du
  devis) ; corrections non couvertes : `backlog/D7-constats-tour1.md` (22 fiches).
- 13 maquettes publiées (7 nouvelles : Documents / Prêt à envoyer, Démarrage rapide, Toit sombre, Tablette,
  Téléphone client, Liste, Schéma) ; règle de Reda : les choix de design se tranchent par la preuve, pas par lui.
- PR #1514 mergée : note de CALX339/356/357 rectifiée (le lecteur PAN/OND existe déjà, sans écran).
- L'autre poste a mergé le bloc M0 (ACAL382, 383, 386-391 cochées) ; ce worktree est à jour de `origin/main@207c7a70e`
  (la pile `l5cal` sert donc un code plus récent que sa base : `migrate` + reconstruction du front avant le tour 2).
- EN COURS à cette écriture : 7 rédacteurs de la VAGUE 2 (lots `lots2/lot-D1…D7.md`, ids ACAL491-990, brief
  `brief-redacteur-vague2.md`) ; un architecte sur la question de Reda du 21/11 (« in the CRM module i already have a
  lot of stuff… maybe a hiden module used by both ? search the best and decide ») → `architecture/DECISION-moteur-partage.md`
  + `backlog/D8-moteur-partage.md`.
- ENSUITE : assembler les lots, lancer les gardes, une critique finale (modèle de pointe) sur la décision d'architecture
  et sur le lot, puis insérer dans `PLAN_AUDIT_CALEPINAGE.md` (bail à obtenir) et dans les plans des autres
  propriétaires ; écrire les tâches du lot D8.
