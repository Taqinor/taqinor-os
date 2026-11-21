# Calepinage — vague 2 du complément L5 (21/11/2026) : table des constats et réserve

Dossier de la vague 2 de la campagne go-deep L5 calepinage (demandes de Reda des 20 et 21/11/2026 : « much more functionalities as the big players… extremely simple… the most pretty calpinage module… only add tasks to the plan » ; « do a real work… multiple rounds of L5 »). Rien n'est construit : ce dossier accompagne les tâches entrées aux plans. Dossier du tour 0 et contrat de sortie K1-K15 : `docs/audits/2026-11-20-calepinage-l5.md`. Notes de travail (étude, maquettes, relecteurs, architecture) : `docs/audits/l5-calepinage/`.

## Où vivent les tâches

- 482 tâches v3 (constat `C-ACAL-L5-<numéro de la tâche>`), plus ACAL487 du groupe du 20/11, sortie de GATED par D-ACAL-38 et rangée dans ce groupe.
- Groupe principal : `docs/plans/PLAN_AUDIT_CALEPINAGE.md`, `## Groupe ACAL — complément du 2026-11-21 (vague 2)` (423 tâches de la vague) : en-tête, ordre de construction (dont la « vague 0 »), gestes du fondateur.
- Moitiés des autres propriétaires : même titre de groupe dans `PLAN_AUDIT_DEVIS`, `PLAN_AUDIT_MOTEUR`, `PLAN_AUDIT_LEAD`, `PLAN_AUDIT_CHANTIERS`, `PLAN_AUDIT_STOCK`, `PLAN_AUDIT_SAV`, `PLAN_AUDIT_PARAMETRES`, `PLAN_AUDIT_DEPLOY`, `PLAN_AUDIT_SECURITE`, `PLAN_AUDIT_TRANSVERSE` (tâches atomiques à deux propriétaires), `PLAN_AUDIT_GENERATEUR` et `docs/WEB_PLAN.md`.
- Décisions de Reda du 21/11 : D-ACAL-36 à D-ACAL-46 (D-ACAL-44 à 46 le soir, après la vérification ; `docs/audits/decisions.yml`, `docs/claude-memory/calepinage-decisions-fondateur.md`).
- Tâches GATED (ne pas auto-construire) : ACAL765 (PLAN_AUDIT_CALEPINAGE) — attend un facteur d'émission du réseau marocain daté et sourcé — recherche documentaire à mener par une session ultérieure, pas une question au fondateur ; ACAL1001 (PLAN_AUDIT_DEVIS) — attend que Reda ait lu la liste des écarts sortie par ACAL1000 sur une copie de ses devis, produite sur un commit qui contient ACAL999, ACAL1195, ACAL1169, ACAL1170, ACAL973, ACAL927, ACAL1033, ACAL1008, ACAL1196, ACAL1171 et ACAL1197 à ACAL1203 (la sortie agricole d'ACAL1203 est collée dans la PR à côté de celle d'ACAL1000) — condition écrite de D-ACAL-36 et D-ACAL-39 ; ACAL921 (PLAN_AUDIT_TRANSVERSE) — attend que Reda ait lu la liste sortie par ACAL1194 (`acal_dryrun_azimut_surfaces --dry-run`) sur une copie de ses calepinages — la lecture de chaque surface de pose déjà enregistrée change.

## Comptes (les tâches de la vague, sans ACAL487)

- Par domaine : D1 46, D2 64, D3 58, D4 80, D5 76, D6 56, D7 72, D8 29, acceptation 1.
- Par priorité : P0 17, P1 135, P2 200, P3 129, — 1.
- Par plan : PLAN_AUDIT_CALEPINAGE 423, PLAN_AUDIT_CHANTIERS 7, PLAN_AUDIT_DEPLOY 2, PLAN_AUDIT_DEVIS 25, PLAN_AUDIT_GENERATEUR 1, PLAN_AUDIT_LEAD 2, PLAN_AUDIT_MOTEUR 6, PLAN_AUDIT_PARAMETRES 3, PLAN_AUDIT_SAV 1, PLAN_AUDIT_SECURITE 1, PLAN_AUDIT_STOCK 3, PLAN_AUDIT_TRANSVERSE 5, WEB_PLAN 3.
- Par section : Acceptation en direct (orchestrateur, jamais une lane) 1, GATED (ne PAS auto-construire) 3, M1 bloquant-fondateur 154, M2 324.
- Par gravité : S1 18, S2 147, S3 275, S4 9, — 33.

## Table des constats (générée depuis les plans)

| Constat | Critère, gravité | Tâche | Plan | Section | Titre abrégé |
|---|---|---|---|---|---|
| C-ACAL-L5-487 | C1, S3 | ACAL487 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à la visionneuse 3D en lecture seule un soleil animé (heure et mois) sans aucun chiffre calculé |
| C-ACAL-L5-492 | C3, S3 | ACAL492 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Dire dans l'aide des raccourcis ce que fait Ctrl + D (« Dupliquer l'obstacle sélectionné ») et le faire parler |
| C-ACAL-L5-493 | C4, S2 | ACAL493 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Monter dans la carte « Obstacle sélectionné » la saisie de HAUTEUR et le bandeau « Compte NON engageable » que |
| C-ACAL-L5-494 | C4, S2 | ACAL494 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ajouter à Réglages › Calepinage la section « Gabarits d'obstacle » (voir, créer, modifier, supprimer ; rectang |
| C-ACAL-L5-495 | C4, S2 | ACAL495 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ajouter à la même section les « gabarits de ZONE » de la société (bande coupe-feu, servitude) |
| C-ACAL-L5-496 | C1, S2 | ACAL496 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Remplacer le soleil de prise de vue SUPPOSÉ (jour 80, 10 h 30) par une date et une heure solaire SAISIES |
| C-ACAL-L5-497 | C4, S2 | ACAL497 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Monter dans l'atelier ERP l'outil « Mesurer une hauteur par son ombre » (bouton, heure solaire de l'image, not |
| C-ACAL-L5-498 | C4, S3 | ACAL498 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Étendre le menu « Type d'obstacle » de six types (lanterneau, exutoire de fumée, climatiseur, citerne, garde-c |
| C-ACAL-L5-499 | C1, S2 | ACAL499 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire lire le dégagement d'un NOUVEAU type d'obstacle dans les réglages de la société, et dire « recul de base |
| C-ACAL-L5-500 | C4, S3 | ACAL500 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter le genre « poteau » aux objets d'environnement (pose au clic, hauteur et diamètre saisis) |
| C-ACAL-L5-501 | C4, S3 | ACAL501 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter le genre « ligne » (haie, mur) tracée en polyligne avec hauteur et épaisseur saisies |
| C-ACAL-L5-502 | C4, S3 | ACAL502 | PLAN_AUDIT_CALEPINAGE | M2 | Ranger pour chaque arbre une hauteur future saisie (« dans N ans : H m ») et une case « Supposer coupé » |
| C-ACAL-L5-503 | C3, S3 | ACAL503 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Donner une apparence aux boutons et champs que l'atelier crée à la volée (`rp9-btn`, `rp9-input`) |
| C-ACAL-L5-504 | C4, S2 | ACAL504 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Monter la saisie de HAUTEUR du bâtiment et sa note pour que le panneau « Bâtiment » (étages, hauteur d'étage,  |
| C-ACAL-L5-505 | C10, S3 | ACAL505 | PLAN_AUDIT_CALEPINAGE | M2 | Étendre le contrat `environmentObject` (genres `poteau` et `ligne`, diamètre, trace, épaisseur, hauteur future |
| C-ACAL-L5-506 | C4, S3 | ACAL506 | PLAN_AUDIT_CALEPINAGE | M2 | Reconnaître des coordonnées ou un lien de carte collés dans le champ d'adresse et centrer la carte dessus sans |
| C-ACAL-L5-507 | C4, S3 | ACAL507 | PLAN_AUDIT_CALEPINAGE | M2 | Proposer « Vouliez-vous dire … ? » quand des coordonnées collées tombent hors du pays du projet et que leur in |
| C-ACAL-L5-508 | C1, S3 | ACAL508 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher sous la carte d'où vient l'image : fournisseur, puis la résolution PUBLIÉE avec sa source ou « date e |
| C-ACAL-L5-509 | C4, S3 | ACAL509 | PLAN_AUDIT_CALEPINAGE | M2 | Ranger dans le document une date de prise de vue de l'image saisie (date + source) sous la clé racine `imageCa |
| C-ACAL-L5-510 | C4, S3 | ACAL510 | PLAN_AUDIT_CALEPINAGE | M2 | Marquer un pan « Pan existant » (modules déjà en place) avec une année de mise en service SAISIE |
| C-ACAL-L5-511 | C4, S3 | ACAL511 | PLAN_AUDIT_CALEPINAGE | M2 | Faire reconnaître un pan « déjà en place » : étiquette « Existant 2019 » dans la liste des pans et plan 2D hac |
| C-ACAL-L5-512 | C1, S3 | ACAL512 | PLAN_AUDIT_CALEPINAGE | M2 | Servir, avec un calage de plan, la longueur A–B en mètres selon l'unité que le DXF déclare |
| C-ACAL-L5-513 | C4, S3 | ACAL513 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher dans l'écran d'import de plan le contrôle d'échelle « selon l'unité du fichier (mm), A–B mesure 9,84  |
| C-ACAL-L5-514 | C4, S3 | ACAL514 | PLAN_AUDIT_CALEPINAGE | M2 | Écrire la rotation de tout le site autour de son barycentre (pans, obstacles, objets d'environnement, zones d' |
| C-ACAL-L5-515 | C4, S3 | ACAL515 | PLAN_AUDIT_CALEPINAGE | M2 | Monter « Pivoter le site » (angle saisi + bouton) dans le panneau de géométrie des pans |
| C-ACAL-L5-516 | C4, S2 | ACAL516 | PLAN_AUDIT_CALEPINAGE | M2 | Lire la boussole et l'inclinaison du téléphone dans une petite couche partagée, avec la permission iOS et une  |
| C-ACAL-L5-517 | C4, S3 | ACAL517 | PLAN_AUDIT_CALEPINAGE | M2 | Faire porter au profil d'horizon sa provenance « relevé téléphone » (mode, date, précision déclarée) de bout e |
| C-ACAL-L5-518 | C4, S2 | ACAL518 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à l'onglet Horizon un mode « Relever au téléphone » : 8 à 12 visées guidées autour du site, un point p |
| C-ACAL-L5-519 | C4, S2 | ACAL519 | PLAN_AUDIT_CALEPINAGE | M2 | Proposer la pente et l'orientation d'un pan mesurées en posant le téléphone sur le toit, « à confirmer » par u |
| C-ACAL-L5-520 | C4, S3 | ACAL520 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter un cadenas par pan : verrouillé, ses sommets, son glissé et sa suppression refusent en nommant le pan |
| C-ACAL-L5-521 | C13, S2 | ACAL521 | PLAN_AUDIT_CALEPINAGE | M2 | Jouer le relevé de l'horizon au téléphone sous WebKit avec des capteurs simulés dans `frontend/e2e/calepinage- |
| C-ACAL-L5-526 | C4, S2 | ACAL526 | PLAN_AUDIT_CALEPINAGE | M2 | Calculer côté serveur les écarts entre la visite technique validée et le toit dessiné (pente, longueur, largeu |
| C-ACAL-L5-527 | C4, S2 | ACAL527 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher dans l'onglet « Reprise de la visite » un bandeau « n écarts avec la visite » qui ouvre le tableau Vi |
| C-ACAL-L5-528 | C4, S3 | ACAL528 | PLAN_AUDIT_CALEPINAGE | M2 | Tirer des rectangles de modules en longitude/latitude depuis le seul document enregistré (centres, origine, az |
| C-ACAL-L5-529 | C4, S3 | ACAL529 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher les modules posés SUR la photo du site calée (« Voir sur la photo ») avec un export PNG interne |
| C-ACAL-L5-530 | C4, S3 | ACAL530 | PLAN_AUDIT_CALEPINAGE | M2 | Étendre le contrat `calepinage_detection_toit.json` aux obstacles proposés (type, contour, confiance), la clé  |
| C-ACAL-L5-531 | C4, S3 | ACAL531 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher et cocher les obstacles proposés sous le contour dans l'onglet « Détection du toit » |
| C-ACAL-L5-533 | C4, S3 | ACAL533 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher un tableau replié « Objets du site » (type, cotes, hauteur, provenance, pan) où un clic sélectionne l |
| C-ACAL-L5-534 | C4, S3 | ACAL534 | PLAN_AUDIT_CALEPINAGE | M2 | Écrire un altimètre qui lit un relief GeoTIFF fourni par l'installateur (projection en degrés seulement) sans  |
| C-ACAL-L5-535 | C4, S3 | ACAL535 | PLAN_AUDIT_CALEPINAGE | M2 | Offrir « Lire la pente sur un relief de drone » : un dépôt de GeoTIFF produit une suggestion de pente et d'ori |
| C-ACAL-L5-536 | C4, S3 | ACAL536 | PLAN_AUDIT_CALEPINAGE | M2 | Exporter les pans, zones et rangées en KML pour Google Earth depuis les Documents |
| C-ACAL-L5-537 | C4, S3 | ACAL537 | PLAN_AUDIT_CALEPINAGE | M2 | Exporter la scène 3D de l'atelier en glTF pour un architecte |
| C-ACAL-L5-546 | C4, S3 | ACAL546 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Monter dans l'atelier ERP le tableau comparatif des poses du toit plat (configuration, panneaux, kWc, kWh/an,  |
| C-ACAL-L5-547 | C15, S3 | ACAL547 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter aux cartes de variantes de l'atelier la carte « Couvre le besoin » (le plus petit nombre de panneaux q |
| C-ACAL-L5-548 | C18, S3 | ACAL548 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ajouter dans l'atelier ERP le champ « Accès solaire minimal (%) » qui écrit `optimisation.seuilAccesSolaire`,  |
| C-ACAL-L5-549 | C18, S3 | ACAL549 | PLAN_AUDIT_CALEPINAGE | M2 | Nommer, sous le champ « Panneaux nécessaires », la cause mesurée d'un pan où aucun module ne tient, et la rang |
| C-ACAL-L5-550 | C15, S3 | ACAL550 | PLAN_AUDIT_CALEPINAGE | M2 | Imprimer sur le plan de pose, sous chaque pan sans module, la cause rangée au document |
| C-ACAL-L5-551 | C15, S4 | ACAL551 | PLAN_AUDIT_CALEPINAGE | M2 | Peindre à la position visée la silhouette du panneau (ou du lot) glissé, rouge quand une contrainte dure l'int |
| C-ACAL-L5-552 | C15, S3 | ACAL552 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher, sous les puces Portrait / Paysage d'un toit plat ombré, les deux poses chiffrées (panneaux posés, ac |
| C-ACAL-L5-553 | C15, S3 | ACAL553 | PLAN_AUDIT_CALEPINAGE | M2 | Copier la sélection libre (Ctrl+C) et la coller au curseur (Ctrl+V) dans le pan actif, y compris un autre pan, |
| C-ACAL-L5-554 | C2, S3 | ACAL554 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter « Appliquer ces réglages à… » sur la ligne d'un pan : le module, le type de toit, la pente et la face  |
| C-ACAL-L5-555 | C10, S3 | ACAL555 | PLAN_AUDIT_CALEPINAGE | M2 | Poser SEUL le contrat `motifsPansVides` (clé racine du document : par identifiant de pan, la cause mesurée d'u |
| C-ACAL-L5-557 | C10, S2 | ACAL557 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Poser le contrat `calepinage_systemes_fixation.json` (liste, création, modification, suppression et refus nomm |
| C-ACAL-L5-558 | C4, S2 | ACAL558 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Servir les systèmes de fixation de la société (`GET` et `POST calepinages/systemes-fixation/`, `GET`, `PATCH`  |
| C-ACAL-L5-559 | C18, S2 | ACAL559 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ajouter l'écran Réglages « Systèmes de fixation » (liste, création, modification et désactivation d'un système |
| C-ACAL-L5-560 | C18, S2 | ACAL560 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Remplacer le champ « identifiant » de l'onglet Fixation par la liste des systèmes actifs de la société |
| C-ACAL-L5-561 | C9, S3 | ACAL561 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à la section `degagements` la table « retrait supplémentaire par type d'arête » (faîtage, égout, rive, |
| C-ACAL-L5-562 | C16, S3 | ACAL562 | PLAN_AUDIT_CALEPINAGE | M2 | Poser d'office, à la fermeture d'un pan, le retrait de la table société sur chaque arête typée sans retrait sa |
| C-ACAL-L5-563 | C9, S3 | ACAL563 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à la section `lestage` les paramètres de zones de pose (largeur de la bande de rive, largeur de coin,  |
| C-ACAL-L5-564 | C18, S3 | ACAL564 | PLAN_AUDIT_CALEPINAGE | M2 | Ranger chaque module posé en centre, rive ou coin d'après sa distance au contour de son pan et publier le lest |
| C-ACAL-L5-565 | C18, S3 | ACAL565 | PLAN_AUDIT_CALEPINAGE | M2 | Dessiner la feuille « Plan de lestage » (modules teintés centre, rive, coin, lest inscrit par module, mention  |
| C-ACAL-L5-566 | C9, S3 | ACAL566 | PLAN_AUDIT_CALEPINAGE | M2 | Déclarer sur chaque système de fixation les couvertures qu'il sert (vocabulaire du lead) et proposer le systèm |
| C-ACAL-L5-567 | C6, S3 | ACAL567 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à la fiche technique d'un module la zone de serrage fabricant (minimum et maximum en mm, source) et la |
| C-ACAL-L5-568 | C7, S3 | ACAL568 | PLAN_AUDIT_CALEPINAGE | M2 | Contrôler, sur les valeurs de pose déclarées par le système, la distance rail-bord contre la zone de serrage d |
| C-ACAL-L5-569 | C7, S3 | ACAL569 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter aux règles de quantité de fixation les bases « rangées en portrait », « rangées en paysage », « module |
| C-ACAL-L5-571 | C18, S3 | ACAL571 | PLAN_AUDIT_PARAMETRES | M2 | Ajouter à l'écran Fiches techniques les champs de la zone de serrage d'un module (minimum mm, maximum mm, sour |
| C-ACAL-L5-572 | C18, S2 | ACAL572 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter l'UNIQUE écran Réglages « Lestage » (les paramètres de la feuille de lestage et les quatre de zones de |
| C-ACAL-L5-573 | —, — | ACAL573 | PLAN_AUDIT_CALEPINAGE | M2 | Poser SEUL sur main la clé de pan `zones[].existant` (booléen) et `zones[].anneeMiseEnService` (entier ou null |
| C-ACAL-L5-574 | —, — | ACAL574 | PLAN_AUDIT_CALEPINAGE | M2 | Rendre un pan « existant » intouchable dans l'atelier : pivoter, redimensionner, changer de module, re-paver e |
| C-ACAL-L5-575 | —, — | ACAL575 | PLAN_AUDIT_CALEPINAGE | M2 | Exclure les modules d'un pan « existant » de la nomenclature de fixation et les marquer « existant » sur la pl |
| C-ACAL-L5-576 | —, — | ACAL576 | PLAN_AUDIT_CALEPINAGE | M2 | Générer, depuis `zones[].coupuresPavage`, des bandes INTERDITES du pan que le pavage évite (une coupure tous l |
| C-ACAL-L5-577 | —, — | ACAL577 | PLAN_AUDIT_CALEPINAGE | M2 | Faire lire `zones[].coupuresPavage` par le traducteur serveur : les bandes de coupure deviennent des zones INT |
| C-ACAL-L5-578 | —, — | ACAL578 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à la nomenclature de fixation les bases `tables` (champ au sol, ombrière), `poteaux` (ombrière à entra |
| C-ACAL-L5-579 | —, — | ACAL579 | PLAN_AUDIT_CALEPINAGE | M2 | Dessiner les triangles de pied du châssis de toit plat à la portée saisie (`zones[].porteeEntrePieds`) au lieu |
| C-ACAL-L5-580 | —, — | ACAL580 | PLAN_AUDIT_CALEPINAGE | M2 | Imprimer sur le plan de pose les poteaux d'ombrière (repères P1…Pn, nombre, entraxe saisi) et le nombre de pie |
| C-ACAL-L5-581 | —, — | ACAL581 | PLAN_AUDIT_CALEPINAGE | M2 | Poser SEUL sur main le contrat du châssis N × M : au kit du moteur `rangs_par_table`, `modules_par_rang`, `jeu |
| C-ACAL-L5-582 | —, — | ACAL582 | PLAN_AUDIT_CALEPINAGE | M2 | Faire poser par le serveur des tables N × M : emprise, pas de pose et compte généralisés au châssis, et lectur |
| C-ACAL-L5-583 | —, — | ACAL583 | WEB_PLAN | M2 | Faire accepter à `packConfig` une option `chassis` {rangs, modulesParRang, jeuEntreRangsM} : le pavage pose de |
| C-ACAL-L5-584 | —, — | ACAL584 | PLAN_AUDIT_CALEPINAGE | M2 | Aligner les rangées d'un pan à gauche, au centre, à droite ou justifiées, par post-traitement du pavage (sans  |
| C-ACAL-L5-585 | —, — | ACAL585 | PLAN_AUDIT_CALEPINAGE | M2 | Faire paver l'atelier en châssis N × M : lire et écrire `zones[].chassis`, le passer à `packConfig` et saisir  |
| C-ACAL-L5-586 | —, — | ACAL586 | PLAN_AUDIT_CALEPINAGE | M2 | Poser SEUL sur main la clé de pan `zones[].coupuresPavage` {tousLesNModules, largeurCoupureM, source} et la rè |
| C-ACAL-L5-587 | —, — | ACAL587 | PLAN_AUDIT_CALEPINAGE | M2 | Poser SEUL sur main la clé de pan `zones[].porteeEntrePieds` {valeurM, source} (portée maximale entre deux pie |
| C-ACAL-L5-588 | C10, S3 | ACAL588 | PLAN_AUDIT_CALEPINAGE | M2 | Servir par un sélecteur le plan de pose (SVG) du calepinage retenu d'un devis, avec son empreinte et sans mont |
| C-ACAL-L5-589 | C10, S3 | ACAL589 | PLAN_AUDIT_CHANTIERS | M2 | Faire lire le plan de pose du chantier dans « Ma journée », y compris réseau coupé : une route le sert, un ong |
| C-ACAL-L5-590 | C1, S3 | ACAL590 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au plan de pose une feuille A4 par pan : modules teintés par chaîne, numéro de chaque module et repère |
| C-ACAL-L5-591 | C1, S3 | ACAL591 | PLAN_AUDIT_CALEPINAGE | M2 | Coter sur la feuille A4 de chaque pan les quatre distances du champ aux rives et chaque zone interdite |
| C-ACAL-L5-592 | C7, S3 | ACAL592 | PLAN_AUDIT_CALEPINAGE | M2 | Publier la nomenclature de fixation PAR PAN et l'imprimer en encart sur la feuille A4 du pan |
| C-ACAL-L5-593 | C2, S3 | ACAL593 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à l'atelier une couche « Repères de chantier » (ancre antichute, accès, passage de câble : type, texte |
| C-ACAL-L5-594 | C3, S3 | ACAL594 | PLAN_AUDIT_CALEPINAGE | M2 | Créer une variante par module coché du stock sur la même implantation |
| C-ACAL-L5-595 | C10, S3 | ACAL595 | PLAN_AUDIT_CALEPINAGE | M2 | Servir le module de chaque variante dans le comparatif (`lignes[].module`) |
| C-ACAL-L5-596 | C10, S3 | ACAL596 | PLAN_AUDIT_CALEPINAGE | M2 | Servir par un sélecteur les points de contrôle de pose d'un calepinage retenu (système de fixation, chaînes da |
| C-ACAL-L5-597 | C10, S3 | ACAL597 | PLAN_AUDIT_CHANTIERS | M2 | Ajouter à la check-list d'un chantier, à sa première matérialisation, les points de contrôle de pose du calepi |
| C-ACAL-L5-598 | C7, S3 | ACAL598 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter l'échafaudage à la nomenclature de fixation : bases `longueur_egouts_m` et `facade_egouts_m2` lues sur |
| C-ACAL-L5-599 | C10, S3 | ACAL599 | PLAN_AUDIT_CALEPINAGE | M2 | Poser SEUL le contrat de la couche « Repères de chantier » : clé racine optionnelle `reperesChantier` de `roof |
| C-ACAL-L5-600 | C15, S3 | ACAL600 | PLAN_AUDIT_CALEPINAGE | M2 | Ouvrir « Comparer d'autres modules » depuis l'étape Panneaux (niveau expert) : cocher 2 à 3 modules du stock,  |
| C-ACAL-L5-601 | C10, S1 | ACAL601 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Dessiner chaque module de la planche A3 dans son vrai sens : emprise lue de `geometry.panelOrientation` (et de |
| C-ACAL-L5-602 | C10, S2 | ACAL602 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Imprimer l'échelle réellement dessinée : `_echelle_nommee` rend l'entier le plus proche de 1 000 ÷ (mm de feui |
| C-ACAL-L5-603 | C10, S2 | ACAL603 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Coter la planche (et le DXF) avec les dimensions du TOIT seul, contour et pans, jamais la boîte toit + obstacl |
| C-ACAL-L5-604 | C10, S1 | ACAL604 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Écrire dans le DXF l'emprise vraie de chaque module (rectangle de `coins_du_module`, sans recouvrement) et un  |
| C-ACAL-L5-605 | C10, S1 | ACAL605 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Dessiner le plan de câblage et le calque CHAINES du DXF avec l'emprise vraie des modules (`coins_du_module`) a |
| C-ACAL-L5-606 | C10, S1 | ACAL606 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Poser un champ au sol à l'entraxe anti-ombrage CALCULÉ par `SurfaceSol` (latitude de l'épingle) quand aucune a |
| C-ACAL-L5-607 | C10, S2 | ACAL607 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Calculer le kWc d'une surface de pose du tableau Site (champ au sol, ombrière) avec la puissance SAISIE `modul |
| C-ACAL-L5-608 | C10, S1 | ACAL608 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Écrire `geometry.panelOrientation` (et `panels[].orient` en pose mixte) quand l'atelier enregistre un pan posé |
| C-ACAL-L5-609 | C10, S2 | ACAL609 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Envoyer la latitude de l'épingle avec la pose d'un champ au sol, dire l'entraxe calculé et alerter quand l'all |
| C-ACAL-L5-610 | C10, S2 | ACAL610 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Afficher le kWc du champ au sol dans l'onglet Terrain (modules posés × puissance saisie : `kwc` de la réponse  |
| C-ACAL-L5-611 | C6, S3 | ACAL611 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Poser SEUL le contrat `calepinage_evaluation_electrique.json` (POST `evaluer-electrique` : requête avec `entre |
| C-ACAL-L5-612 | C6, S3 | ACAL612 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Composer côté serveur le `titre` et la `phrase` de `publication` à partir de l'`etat` et des `points` d'ACAL93 |
| C-ACAL-L5-613 | C6, S3 | ACAL613 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire dire à l'onglet « Verdict électrique » ce que dit le serveur : le titre et la phrase de `publication`, a |
| C-ACAL-L5-614 | C10, S3 | ACAL614 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Poser le contrat `calepinage_configurations_onduleur.json` (2 à 3 configurations d'onduleur comparables : nomb |
| C-ACAL-L5-615 | C6, S3 | ACAL615 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Valider les produits désignés (`module_produit`, `onduleur_produit`, `optimiseur_produit`) de `entree_electriq |
| C-ACAL-L5-616 | C10, S3 | ACAL616 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Servir `GET calepinages/<pk>/configurations-onduleur/` : l'onduleur retenu et ses deux voisins de puissance du |
| C-ACAL-L5-617 | C15, S3 | ACAL617 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ajouter à l'étape Électrique (niveau expert) le lien « Comparer avec d'autres onduleurs » sous le champ Ondule |
| C-ACAL-L5-618 | C7, S3 | ACAL618 | PLAN_AUDIT_CALEPINAGE | M2 | Servir `chaines[]` dans la réponse de `POST evaluer-electrique` : par chaîne (automatique ou imposée à la main |
| C-ACAL-L5-619 | C15, S3 | ACAL619 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher la tension de chaque chaîne : une bulle sous « Affecter la sélection » pour les chaînes qui viennent  |
| C-ACAL-L5-620 | C10, S3 | ACAL620 | PLAN_AUDIT_CALEPINAGE | M2 | Étendre SEUL le contrat `calepinage_evaluation_electrique.json` (posé par ACAL611) d'une clé `chaines[]` : une |
| C-ACAL-L5-626 | C18, S3 | ACAL626 | PLAN_AUDIT_CALEPINAGE | M2 | Poser SEUL le contrat `calepinage_controle_chaine.json` (POST `calepinage/controle-chaine/` : module, onduleur |
| C-ACAL-L5-627 | C10, S3 | ACAL627 | PLAN_AUDIT_CALEPINAGE | M2 | Servir `POST calepinages/controle-chaine/` : le verdict d'une chaîne (module, onduleur, N modules, température |
| C-ACAL-L5-628 | C18, S3 | ACAL628 | PLAN_AUDIT_CALEPINAGE | M2 | Offrir le « Contrôle rapide d'une chaîne » : choisir un module et un onduleur, taper N et la température, lire |
| C-ACAL-L5-629 | C18, S3 | ACAL629 | PLAN_AUDIT_CALEPINAGE | M2 | Poser SEUL le contrat `calepinage_import_affectation.json` (POST d'un plan de chaînes CSV `module;chaine;mppt; |
| C-ACAL-L5-630 | C10, S3 | ACAL630 | PLAN_AUDIT_CALEPINAGE | M2 | Lire un plan de chaînes CSV (`module;chaine;mppt;onduleur`), valider chaque ligne, puis passer les seules lign |
| C-ACAL-L5-631 | C18, S3 | ACAL631 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter dans « Affectation des chaînes » un bouton « Importer un plan de chaînes (CSV) » qui montre les refus  |
| C-ACAL-L5-632 | C10, S3 | ACAL632 | PLAN_AUDIT_CALEPINAGE | M2 | Calculer le plus petit nombre d'onduleurs du modèle retenu pour lequel plus aucun pan ne dépasse les entrées M |
| C-ACAL-L5-633 | C10, S3 | ACAL633 | PLAN_AUDIT_CALEPINAGE | M2 | Accepter un nombre d'onduleurs dans l'entrée électrique, le faire lire par TOUS les calculs (conception des ch |
| C-ACAL-L5-634 | C18, S3 | ACAL634 | PLAN_AUDIT_CALEPINAGE | M2 | Dire à l'utilisateur « 2 onduleurs sont nécessaires pour câbler les 26 modules » et lui laisser l'accepter d'u |
| C-ACAL-L5-635 | C10, S3 | ACAL635 | PLAN_AUDIT_CALEPINAGE | M2 | Calculer la chute de tension avec la résistivité du cuivre à une température de service SAISIE par la société  |
| C-ACAL-L5-636 | C10, S3 | ACAL636 | PLAN_AUDIT_CALEPINAGE | M2 | Appliquer un facteur de regroupement saisi par la société (valeur + source) au courant admissible d'un tronçon |
| C-ACAL-L5-641 | C18, S3 | ACAL641 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Saisir, pour chaque pan, le motif de parcours du câble et le point de collecte (aujourd'hui aucun écran ne les |
| C-ACAL-L5-642 | C18, S3 | ACAL642 | PLAN_AUDIT_CALEPINAGE | M2 | Ordonner l'affectation des modules aux chaînes selon un motif par pan (« le long de la rangée » ou « aller-ret |
| C-ACAL-L5-643 | C18, S3 | ACAL643 | PLAN_AUDIT_CALEPINAGE | M2 | Dessiner sur le plan de câblage le sens de numérotation des modules de chaque chaîne (flèche et légende) |
| C-ACAL-L5-645 | C18, S3 | ACAL645 | PLAN_AUDIT_CALEPINAGE | M2 | Compter les optimiseurs sur les seuls modules marqués quand le marquage existe |
| C-ACAL-L5-646 | C10, S3 | ACAL646 | PLAN_AUDIT_CALEPINAGE | M2 | Contrôler l'entrée de l'optimiseur sur la somme de ses modules (modules par optimiseur × valeur de fiche) |
| C-ACAL-L5-647 | C18, S3 | ACAL647 | PLAN_AUDIT_CALEPINAGE | M2 | Proposer les modules ombrés pour un optimiseur dans l'affectation des chaînes (liste calculée par le serveur d |
| C-ACAL-L5-648 | C10, S3 | ACAL648 | PLAN_AUDIT_CALEPINAGE | M2 | Écrire les deux tests de comportement des chaînes manuelles (retrait d'un module d'un document non numéroté ;  |
| C-ACAL-L5-649 | C10, S3 | ACAL649 | PLAN_AUDIT_CALEPINAGE | M2 | Ré-ancrer par la position une affectation manuelle dont le module n'est plus retrouvé par son numéro, et nomme |
| C-ACAL-L5-650 | C18, S3 | ACAL650 | PLAN_AUDIT_CALEPINAGE | M2 | Autoriser une chaîne sur deux pans de même orientation (azimut et inclinaison égaux à une tolérance saisie par |
| C-ACAL-L5-657 | C10, S3 | ACAL657 | PLAN_AUDIT_CALEPINAGE | M2 | Refuser dans l'aperçu d'import une fiche module incohérente (Vmp ≥ Voc, Imp ≥ Isc, Pmax qui s'écarte de Vmp ×  |
| C-ACAL-L5-658 | C10, S3 | ACAL658 | PLAN_AUDIT_CALEPINAGE | M2 | Reprendre à l'import le nombre de cellules en série (`NCelS`) et le coefficient de température de Isc (`muISC` |
| C-ACAL-L5-659 | C18, S3 | ACAL659 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à la fiche technique les champs optionnels que les modèles électriques lisent (cellules en série, coef |
| C-ACAL-L5-661 | C10, S3 | ACAL661 | PLAN_AUDIT_CALEPINAGE | M2 | Traiter comme UNE seule entrée logique les entrées MPPT d'un onduleur dont la fiche dit qu'elles ne sont pas i |
| C-ACAL-L5-662 | C10, S3 | ACAL662 | PLAN_AUDIT_CALEPINAGE | M2 | Contrôler que l'onduleur retenu figure dans la liste des onduleurs compatibles de l'optimiseur désigné |
| C-ACAL-L5-663 | C18, S3 | ACAL663 | PLAN_AUDIT_STOCK | M2 | Saisir dans le formulaire produit les nouveaux champs de fiche (cellules en série, coefficient de Isc, début e |
| C-ACAL-L5-664 | C10, S3 | ACAL664 | PLAN_AUDIT_CALEPINAGE | M2 | Publier la puissance AC disponible de l'onduleur à la température d'AIR maximale du site d'après la réduction  |
| C-ACAL-L5-665 | C18, S3 | ACAL665 | PLAN_AUDIT_CALEPINAGE | M2 | Servir, par chaîne du calepinage retenu d'un chantier, le nombre de modules et les Voc, Isc et Pmax attendus à |
| C-ACAL-L5-666 | C18, S3 | ACAL666 | PLAN_AUDIT_CHANTIERS | M2 | Poser SEUL le contrat `recette_valeurs_attendues.json` (GET `recettes-commissioning/<id>/valeurs-attendues/` : |
| C-ACAL-L5-667 | C18, S3 | ACAL667 | PLAN_AUDIT_CHANTIERS | M2 | Servir, sur la fiche de recette d'un chantier, les valeurs attendues par chaîne lues sur le calepinage retenu |
| C-ACAL-L5-668 | C18, S3 | ACAL668 | PLAN_AUDIT_CHANTIERS | M2 | Offrir, dans le relevé I-V de la recette, un bouton « Reprendre les valeurs du calepinage » qui remplit Voc, I |
| C-ACAL-L5-669 | C18, S3 | ACAL669 | PLAN_AUDIT_PARAMETRES | M2 | Ajouter le réglage société « résistance d'isolement minimale à la recette » (valeur saisie, vide par défaut) |
| C-ACAL-L5-670 | C10, S3 | ACAL670 | PLAN_AUDIT_CHANTIERS | M2 | Juger `isolement_ok` d'après la résistance mesurée et le seuil société quand il est saisi |
| C-ACAL-L5-671 | C18, S3 | ACAL671 | PLAN_AUDIT_CALEPINAGE | M2 | Publier une ligne « plutôt onduleur de chaîne, micro-onduleurs ou optimiseurs » d'après le nombre d'orientatio |
| C-ACAL-L5-672 | C18, S3 | ACAL672 | PLAN_AUDIT_CALEPINAGE | M2 | Imprimer sur le plan de câblage, pour chaque chaîne, sa tension à froid avec la température citée et son coura |
| C-ACAL-L5-673 | C18, S3 | ACAL673 | PLAN_AUDIT_CALEPINAGE | M2 | Imprimer sur le plan de câblage la consigne DC de la société (texte saisi une fois dans les réglages, avec sa  |
| C-ACAL-L5-674 | C18, S3 | ACAL674 | PLAN_AUDIT_CALEPINAGE | M2 | Écrire dans le DXF un bloc `MODULE` défini une fois et inséré par module avec les attributs CHAINE, MPPT, ONDU |
| C-ACAL-L5-675 | C18, S3 | ACAL675 | PLAN_AUDIT_CALEPINAGE | M2 | Poser dans la check-list des protections la question « coupure d'urgence DC / arrêt rapide exigé ? » (oui, non |
| C-ACAL-L5-676 | C10, S3 | ACAL676 | PLAN_AUDIT_CALEPINAGE | M2 | Comparer la distance de séparation foudre saisie à la valeur minimale saisie par la société (avec sa source) q |
| C-ACAL-L5-677 | C18, S3 | ACAL677 | PLAN_AUDIT_CALEPINAGE | M2 | Mesurer la surface de la boucle de chaque chaîne (centres des modules dans l'ordre de l'affectation, puis les  |
| C-ACAL-L5-678 | C9, S3 | ACAL678 | PLAN_AUDIT_CALEPINAGE | M2 | Avertir, sans bloquer, quand la boucle d'une chaîne dépasse une surface maximale SAISIE par la société (valeur |
| C-ACAL-L5-685 | C18, S3 | ACAL685 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher dans le verdict électrique (niveau expert) la surface de boucle de chaque chaîne, sa limite société e |
| C-ACAL-L5-686 | C6, S3 | ACAL686 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire dire au bandeau du schéma unifilaire sans norme ce qui n'est pas dessiné après l'onduleur (disjoncteur A |
| C-ACAL-L5-687 | C6, S3 | ACAL687 | PLAN_AUDIT_CALEPINAGE | M2 | Faire lire par le verdict de raccordement les phases saisies dans « Saisies électriques » quand le raccordemen |
| C-ACAL-L5-692 | C10, S2 | ACAL692 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Nommer, dans `validation`, le plus gros poste de pertes de la cascade quand la chaîne perd plus que PVGIS et p |
| C-ACAL-L5-693 | C10, S2 | ACAL693 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Servir `production.duree_de_vie` (horizon, motif d'omission du tableau pluriannuel et garantie de production d |
| C-ACAL-L5-694 | C10, S2 | ACAL694 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Imprimer le tableau pluriannuel (année, production, facteur, garantie du fabricant) dans la section « Producti |
| C-ACAL-L5-695 | C10, S2 | ACAL695 | PLAN_AUDIT_CALEPINAGE | M2 | Servir `cascade.postes_lisibles` : la cascade regroupée en cinq postes lisibles (Ombres proches, Poussière, Ch |
| C-ACAL-L5-696 | C18, S3 | ACAL696 | PLAN_AUDIT_CALEPINAGE | M2 | Monter dans l'étape Résultats la carte « Du soleil au réseau » : cinq postes en barres lus dans `cascade.poste |
| C-ACAL-L5-697 | C10, S3 | ACAL697 | PLAN_AUDIT_CALEPINAGE | M2 | Rendre la fiche « les pertes expliquées en 5 postes » (une page, une phrase-gabarit par poste, étape omise « n |
| C-ACAL-L5-698 | C18, S3 | ACAL698 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher sous la carte « Du soleil au réseau » la ligne « n réglages utilisent des valeurs publiées, non mesur |
| C-ACAL-L5-699 | C10, S2 | ACAL699 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Servir `cascade.a_renseigner` : pour chaque étape omise faute de réglage société ou de champ de fiche, la clé  |
| C-ACAL-L5-700 | —, — | ACAL700 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Monter l'état « résultat incomplet » de la maquette : « Production la première année · au plus », « C'est un p |
| C-ACAL-L5-701 | C3, S2 | ACAL701 | PLAN_AUDIT_CALEPINAGE | M2 | Compiler `plages_usuelles` (données) : pour chaque étape de la cascade, la bande de perte imprimée par une pag |
| C-ACAL-L5-702 | C10, S2 | ACAL702 | PLAN_AUDIT_CALEPINAGE | M2 | Publier `cascade.plages` : pour chaque étape appliquée qui a une bande sourcée, « dans la plage » ou « inhabit |
| C-ACAL-L5-703 | C18, S3 | ACAL703 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher la pastille « inhabituel » sur chaque ligne de perte hors bande et « Dans la plage habituelle » sous  |
| C-ACAL-L5-704 | C10, S2 | ACAL704 | PLAN_AUDIT_CALEPINAGE | M2 | Remplacer la borne codée en dur du rendement spécifique (600 ; 2 400 kWh/kWc) par deux réglages société sourcé |
| C-ACAL-L5-705 | C10, S2 | ACAL705 | PLAN_AUDIT_CALEPINAGE | M2 | Servir `production.bilan_mensuel` : température ambiante moyenne et indice de performance (PR) par mois, à côt |
| C-ACAL-L5-706 | C10, S2 | ACAL706 | PLAN_AUDIT_CALEPINAGE | M2 | Servir `production.gain_inclinaison` : l'irradiation horizontale par mois (une requête PVGIS à 0°, même base e |
| C-ACAL-L5-707 | C18, S3 | ACAL707 | PLAN_AUDIT_CALEPINAGE | M2 | Étendre « Mois par mois » de l'onglet Production en tableau complet derrière « Mode expert » : irradiation hor |
| C-ACAL-L5-708 | C10, S2 | ACAL708 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au tableau mensuel du rapport d'étude interne les colonnes irradiation horizontale, température ambian |
| C-ACAL-L5-709 | C18, S3 | ACAL709 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Afficher la tuile « De la consommation » (couverture : part de la consommation couverte par le solaire) dans l |
| C-ACAL-L5-710 | C18, S3 | ACAL710 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ajouter à l'onglet Production la ligne « Année basse (9 fois sur 10 au-dessus) : x kWh · Dans N ans : y kWh (g |
| C-ACAL-L5-711 | C4, S3 | ACAL711 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Servir, pour chaque chaîne touchée par l'ombre, ses deux bornes de perte, leur écart et ses modules ombrés, et |
| C-ACAL-L5-712 | C4, S3 | ACAL712 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Afficher, dans l'étape Électrique, une carte « chaîne touchée par l'ombre » par chaîne dont les deux bornes di |
| C-ACAL-L5-713 | C4, S3 | ACAL713 | PLAN_AUDIT_CALEPINAGE | M2 | Écrire l'hypothèse portrait/paysage comme HYPOTHÈSE NOMMÉE dans l'entrée de l'étape `mismatch_ombrage`, selon  |
| C-ACAL-L5-714 | C4, S3 | ACAL714 | PLAN_AUDIT_CALEPINAGE | M2 | Remplacer le seuil codé en dur `SOLAR_ACCESS_LOW = 0.75` par le réglage société `seuil_acces_retrait`, lu au d |
| C-ACAL-L5-715 | C4, S3 | ACAL715 | PLAN_AUDIT_CALEPINAGE | M2 | Publier sous l'accès solaire d'un pan UNE phrase de verdict (« Ombrage du pan : x % de l'énergie, n modules so |
| C-ACAL-L5-716 | C9, S3 | ACAL716 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au registre des réglages société, SANS valeur, trois clés d'ombrage — le seuil de retrait d'un module  |
| C-ACAL-L5-717 | C4, S3 | ACAL717 | PLAN_AUDIT_CALEPINAGE | M2 | Tracer sous la barre du soleil la courbe « direct perdu » heure par heure du mois de la date choisie, avec une |
| C-ACAL-L5-718 | C4, S3 | ACAL718 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au noyau pur `core/calepinage/soleil.py` la correspondance entre l'heure solaire vraie et l'heure léga |
| C-ACAL-L5-719 | C4, S3 | ACAL719 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher l'heure LÉGALE à côté de l'heure solaire sur le curseur d'heure de la barre du soleil et sur le repèr |
| C-ACAL-L5-720 | C1, S3 | ACAL720 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à la fiche technique d'un MODULE le champ optionnel « sous-chaînes par module » (le nombre de brins pr |
| C-ACAL-L5-721 | C4, S3 | ACAL721 | PLAN_AUDIT_CALEPINAGE | M2 | Faire calculer par l'atelier l'accès solaire de chaque BANDE d'un module (autant de bandes que de sous-chaînes |
| C-ACAL-L5-722 | C4, S3 | ACAL722 | PLAN_AUDIT_CALEPINAGE | M2 | Calculer l'étape `diodes` par sous-chaînes : le champ de fiche et les accès par bande affinent la dispersion d |
| C-ACAL-L5-723 | C4, S3 | ACAL723 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter l'étape « optimiseur » qui applique le rendement publié sur la fiche de l'optimiseur aux SEULS modules |
| C-ACAL-L5-724 | C4, S3 | ACAL724 | PLAN_AUDIT_CALEPINAGE | M2 | Exempter de la contrainte de chaîne les SEULS modules équipés d'un optimiseur (ou micro-onduleur) au lieu de t |
| C-ACAL-L5-725 | C4, S3 | ACAL725 | PLAN_AUDIT_CALEPINAGE | M2 | Poser et montrer le drapeau « optimiseur » par module à l'écran d'affectation des chaînes |
| C-ACAL-L5-726 | C4, S3 | ACAL726 | PLAN_AUDIT_CALEPINAGE | M2 | Faire que « Joindre la carte de chaleur » de Documents rende réellement la carte d'accès solaire du pan actif  |
| C-ACAL-L5-727 | C13, S3 | ACAL727 | PLAN_AUDIT_CALEPINAGE | M2 | Imprimer sous la carte de chaleur du rapport d'ombrage une légende à échelle FIXE 0-100 % (rampe rouge, jaune, |
| C-ACAL-L5-728 | C4, S2 | ACAL728 | PLAN_AUDIT_CALEPINAGE | M2 | Trier la liste des pans de l'étape Panneaux par accès solaire moyen décroissant, à la demande, avec l'accès de |
| C-ACAL-L5-729 | C4, S2 | ACAL729 | PLAN_AUDIT_CALEPINAGE | M2 | Faire dire à l'info-bulle d'un module son accès solaire annuel et sa chaîne, en plus des heures masquées |
| C-ACAL-L5-730 | C4, S3 | ACAL730 | PLAN_AUDIT_CALEPINAGE | M2 | Servir `GET calepinages/<pk>/soleil-legal/?date=AAAA-MM-JJ` : la correspondance heure solaire vraie / heure lé |
| C-ACAL-L5-731 | C1, S3 | ACAL731 | PLAN_AUDIT_CALEPINAGE | M2 | Déclarer au contrat du document les accès solaires PAR BANDE de module et le nombre de sous-chaînes du module, |
| C-ACAL-L5-732 | C15, S2 | ACAL732 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Remplacer, dans le manque « accès solaire par module » de Documents, la consigne « Calculer l'ombrage dans l'a |
| C-ACAL-L5-733 | C4, S3 | ACAL733 | PLAN_AUDIT_CALEPINAGE | M2 | Accepter et conserver un drapeau « optimiseur » PAR MODULE dans l'affectation manuelle, et le servir dans la t |
| C-ACAL-L5-734 | —, — | ACAL734 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Publier dans l'entrée de l'étape `mppt` l'énergie des heures sous la tension de démarrage de l'onduleur, SANS  |
| C-ACAL-L5-735 | —, — | ACAL735 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Afficher, dans la ligne dépliée de l'étape « Fenêtre MPPT » du diagramme de pertes, le nombre d'heures et l'én |
| C-ACAL-L5-736 | C11, — | ACAL736 | PLAN_AUDIT_CALEPINAGE | M2 | Servir l'histogramme de l'énergie par classe de puissance dans l'entrée de l'étape `ecretage` (`entree.distrib |
| C-ACAL-L5-737 | —, — | ACAL737 | PLAN_AUDIT_CALEPINAGE | M2 | Tracer l'histogramme de puissance de l'écrêtage dans l'étape Électrique (carte « Panneaux pour l'onduleur », n |
| C-ACAL-L5-738 | —, — | ACAL738 | PLAN_AUDIT_CALEPINAGE | M2 | Tracer la puissance des panneaux (P_DC) et la borne de l'onduleur dans la journée type d'un mois, à côté de la |
| C-ACAL-L5-740 | C03, — | ACAL740 | PLAN_AUDIT_CALEPINAGE | M2 | Appliquer le déclassement thermique de l'onduleur à la borne d'écrêtage heure par heure avec la température d' |
| C-ACAL-L5-742 | —, — | ACAL742 | PLAN_AUDIT_CALEPINAGE | M2 | Déclarer au registre des réglages société deux clés sans valeur, « nettoyages par an » et « inclinaison d'auto |
| C-ACAL-L5-743 | —, — | ACAL743 | PLAN_AUDIT_CALEPINAGE | M2 | Publier dans l'entrée de l'étape `salissure` la fréquence de nettoyage saisie et un avertissement quand l'incl |
| C-ACAL-L5-744 | C06, — | ACAL744 | PLAN_AUDIT_CALEPINAGE | M2 | Comparer l'irradiation incidente de la base PVGIS utilisée avec celle de l'AUTRE base (SARAH3 / ERA5) sur le m |
| C-ACAL-L5-745 | —, — | ACAL745 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher sous le bandeau de provenance de l'onglet Production la ligne « Deuxième source météo : écart de x %  |
| C-ACAL-L5-746 | —, — | ACAL746 | PLAN_AUDIT_CALEPINAGE | M2 | Écrire un client NASA POWER (série horaire, gratuite) qui rend une série horizontale au format d'ACAL454, SEUL |
| C-ACAL-L5-747 | —, — | ACAL747 | PLAN_AUDIT_CALEPINAGE | M2 | Compiler la table des albédos par type de surface : seules les surfaces dont la page PVsyst imprime UNE valeur |
| C-ACAL-L5-748 | —, — | ACAL748 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à la ligne « albédo » de Réglages simulation un choix « Remplir depuis une surface » qui met la valeur |
| C-ACAL-L5-749 | —, — | ACAL749 | PLAN_AUDIT_CALEPINAGE | M2 | Servir la liste « ce que cette simulation ne modélise pas » (`cascade.limites_connues`, texte sans chiffre) |
| C-ACAL-L5-750 | —, — | ACAL750 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher l'encadré replié « Limites connues » en bas de l'onglet Pertes : la liste servie, plus les étapes non |
| C-ACAL-L5-751 | —, — | ACAL751 | PLAN_AUDIT_CALEPINAGE | M2 | Imprimer les limites connues et les étapes non comptées à l'annexe « Hypothèses » du rapport d'étude interne |
| C-ACAL-L5-752 | —, — | ACAL752 | PLAN_AUDIT_CALEPINAGE | M2 | Écrire la colonne `p_dc_kw` (puissance continue à l'entrée de l'onduleur) sur chaque point de la série à l'éta |
| C-ACAL-L5-753 | C6, S2 | ACAL753 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Laisser choisir, dans l'onglet Séries, les colonnes de la série horaire (cases à cocher, onglet expert) et les |
| C-ACAL-L5-754 | C6, S2 | ACAL754 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter l'export « Ombrage module par module » : une ligne par module (module, accès solaire annuel) avec l'en |
| C-ACAL-L5-755 | C6, S2 | ACAL755 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter le pas « jour » à l'export horaire (un menu « Pas : heure / jour » dans l'onglet Séries) |
| C-ACAL-L5-756 | C18, S2 | ACAL756 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au rapport d'étude interne la section « Synthèse », une page de chiffres clés lus dans le résultat ser |
| C-ACAL-L5-757 | C18, S2 | ACAL757 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au rapport d'étude interne la section « Autoconsommation et batterie » : taux, bilan d'énergie, plafon |
| C-ACAL-L5-758 | C18, S2 | ACAL758 | PLAN_AUDIT_CALEPINAGE | M2 | Faire servir par l'étape IAM sa table « angle d'incidence, facteur » (0 à 90°, pas de 10°) calculée par la loi |
| C-ACAL-L5-759 | C18, S2 | ACAL759 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au rapport d'étude interne la section « Photos du site » : les photos déposées, légendées et datées, l |
| C-ACAL-L5-760 | C18, S2 | ACAL760 | PLAN_AUDIT_CALEPINAGE | M2 | Faire dire à la section « Site et source météo » du rapport les modèles employés (incidence, température de ce |
| C-ACAL-L5-761 | C19, S2 | ACAL761 | PLAN_AUDIT_CALEPINAGE | M2 | Dessiner côté serveur le schéma « où va l'énergie » (du soleil aux usages) en SVG autonome, alimenté par la ca |
| C-ACAL-L5-762 | C19, S2 | ACAL762 | PLAN_AUDIT_CALEPINAGE | M2 | Montrer dans l'étape Résultats, derrière « Mode expert », la carte repliable « Où va l'énergie » : le schéma s |
| C-ACAL-L5-763 | C27, S3 | ACAL763 | PLAN_AUDIT_CALEPINAGE | M2 | Produire à chaque dépôt d'un fichier météo un rapport de qualité en quatre lignes (couverture, décalage horair |
| C-ACAL-L5-764 | C27, S3 | ACAL764 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher à l'import d'un fichier météo ses quatre lignes de qualité en mots simples, sans verdict |
| C-ACAL-L5-765 | C19, S3 | ACAL765 | PLAN_AUDIT_CALEPINAGE | GATED (ne PAS auto-construire) | Imprimer en Production, avec sa source, le bilan carbone évité (énergie produite × facteur d'émission du résea |
| C-ACAL-L5-767 | C6, S4 | ACAL767 | PLAN_AUDIT_CALEPINAGE | M2 | Ne jamais lever de toast pour la lecture AUTOMATIQUE de la série horaire : un refus (409 d'état ou 400) reste  |
| C-ACAL-L5-768 | C27, S4 | ACAL768 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Laisser jusqu'à 2 minutes au téléchargement d'un document du module (rapport d'étude PDF compris) au lieu de l |
| C-ACAL-L5-769 | C27, S4 | ACAL769 | PLAN_AUDIT_CALEPINAGE | M2 | Dire quoi faire quand le téléchargement d'un document dépasse son délai : un message sur la carte (plus de toa |
| C-ACAL-L5-770 | C27, S4 | ACAL770 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ne proposer dans Réglages simulation que les valeurs d'une liste que le serveur sait honorer : le serveur publ |
| C-ACAL-L5-771 | C27, S4 | ACAL771 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à la liste `manquants[]` d'ACAL940 le seul refus HORS réglages qu'elle ne porte pas, « aucun pan équip |
| C-ACAL-L5-772 | C18, S2 | ACAL772 | PLAN_AUDIT_CALEPINAGE | M2 | Imprimer au rapport d'étude, section « pertes », la table IAM de l'étape (angle, facteur) avec le modèle et l' |
| C-ACAL-L5-773 | C19, S2 | ACAL773 | PLAN_AUDIT_CALEPINAGE | M2 | Imprimer au rapport d'étude, section « pertes », le schéma « où va l'énergie » sous le diagramme de la cascade |
| C-ACAL-L5-774 | C27, S4 | ACAL774 | PLAN_AUDIT_CALEPINAGE | M2 | Faire lier, dans la liste des refus d'une simulation, les lignes SANS champ de réglage (`plans`, épingle `site |
| C-ACAL-L5-776 | C4, S1 | ACAL776 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Servir la facture mensuelle moyenne du lead dans le contexte de conception (`consommation_lead`) |
| C-ACAL-L5-777 | C4, S1 | ACAL777 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire lire la facture du lead par l'atelier en mode calepinage |
| C-ACAL-L5-778 | C4, S1 | ACAL778 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Nommer l'origine du chiffre « Économies estimées » de la carte Recommandation et renvoyer vers l'onglet Économ |
| C-ACAL-L5-779 | C4, S3 | ACAL779 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ignorer une charge à venir marquée « déjà dans les factures » et le dire par un avertissement qui la nomme |
| C-ACAL-L5-780 | C4, S3 | ACAL780 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Écrire `consumption.charges[]` depuis l'atelier : ajouter une charge à venir (voiture électrique, pompe à chal |
| C-ACAL-L5-781 | C4, S3 | ACAL781 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Afficher « charges ajoutées : X kWh/an » avec le détail par charge sous la courbe journalière de l'onglet Prod |
| C-ACAL-L5-782 | C4, S3 | ACAL782 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Publier le régime loi 82-21 du site dans le bloc raccordement |
| C-ACAL-L5-783 | C4, S3 | ACAL783 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Comparer la part injectée simulée au plafond légal de 20 % de la production annuelle (loi 82-21 art. 12) et la |
| C-ACAL-L5-784 | C4, S3 | ACAL784 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Afficher le régime 82-21 et la part injectée face au plafond en deux lignes de l'onglet Raccordement |
| C-ACAL-L5-786 | C18, S2 | ACAL786 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Admettre à l'enregistrement les réglages de secours et de commande que la simulation lit déjà (`appareils`, `d |
| C-ACAL-L5-787 | C10, S3 | ACAL787 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Servir dans `batterie.total` ce que le dispatch calcule déjà : pointe avant/après effacement, dépassements res |
| C-ACAL-L5-788 | C18, S2 | ACAL788 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ajouter à l'onglet Batterie la saisie des appareils à tenir pendant une coupure et de la durée à tenir (étape  |
| C-ACAL-L5-789 | C18, S2 | ACAL789 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Afficher dans un bloc « Mode expert » de l'onglet Batterie les cycles par an, le vieillissement année par anné |
| C-ACAL-L5-790 | C6, S2 | ACAL790 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Refuser à l'enregistrement un seuil de protection hors réseau mal formé en nommant `hors_reseau.seuils.<seuil> |
| C-ACAL-L5-791 | C18, S2 | ACAL791 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Saisir en mode expert les trois seuils de protection de la batterie d'un site hors réseau (veille, recharge d' |
| C-ACAL-L5-792 | C18, S2 | ACAL792 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Saisir en mode expert les réglages propres à la stratégie : fenêtres de charge et de décharge à état de charge |
| C-ACAL-L5-793 | C10, S3 | ACAL793 | PLAN_AUDIT_CALEPINAGE | M2 | Publier dans `batterie.total` quatre faits tirés de la série horaire — jours où la batterie atteint 100 %, nui |
| C-ACAL-L5-794 | C7, S3 | ACAL794 | PLAN_AUDIT_CALEPINAGE | M2 | Dire « adaptée », « trop petite » ou « trop grande » seulement quand la société a saisi ses deux seuils sourcé |
| C-ACAL-L5-795 | C18, S3 | ACAL795 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher en tête de l'onglet Batterie le garde-fou « votre production est déjà consommée à N % sans batterie » |
| C-ACAL-L5-796 | C6, S3 | ACAL796 | PLAN_AUDIT_CALEPINAGE | M2 | Admettre à l'enregistrement les coupures de réseau déclarées (`batterie.coupures` : combien par an, de combien |
| C-ACAL-L5-797 | C7, S3 | ACAL797 | PLAN_AUDIT_CALEPINAGE | M2 | Rejouer les coupures déclarées sur chaque jour de l'année type et publier l'énergie non fournie (`batterie.tot |
| C-ACAL-L5-798 | C7, S3 | ACAL798 | PLAN_AUDIT_CALEPINAGE | M2 | Publier les heures que tient chaque appareil secouru (`batterie.total.secours.appareils`) |
| C-ACAL-L5-799 | C18, S3 | ACAL799 | PLAN_AUDIT_CALEPINAGE | M2 | Poser sous « Secours » de l'onglet Batterie les trois questions sur les coupures et lire l'énergie non fournie |
| C-ACAL-L5-800 | C6, S3 | ACAL800 | PLAN_AUDIT_CALEPINAGE | M2 | Admettre à l'enregistrement un groupe électrogène d'appoint pour un site hors réseau (`hors_reseau.groupe` : p |
| C-ACAL-L5-801 | C7, S3 | ACAL801 | PLAN_AUDIT_CALEPINAGE | M2 | Simuler le groupe électrogène d'appoint d'un site hors réseau et publier ses heures de marche et l'énergie fou |
| C-ACAL-L5-802 | C7, S3 | ACAL802 | PLAN_AUDIT_CALEPINAGE | M2 | Publier à côté de la banque moyenne la banque dimensionnée sur le mois de plus forte consommation (`hors_resea |
| C-ACAL-L5-803 | C18, S3 | ACAL803 | PLAN_AUDIT_CALEPINAGE | M2 | Saisir et lire le groupe d'appoint d'un site hors réseau dans l'onglet Batterie (interrupteur « Il y a un grou |
| C-ACAL-L5-804 | C7, S3 | ACAL804 | PLAN_AUDIT_DEVIS | M2 | Écrire `bilan_reservoir_journalier` (fonction pure) : le niveau du réservoir jour par jour sur l'année type, a |
| C-ACAL-L5-805 | C7, S3 | ACAL805 | PLAN_AUDIT_DEVIS | M2 | Faire suivre à la production d'eau de chaque mois la HMT de ce mois : `hmt_mensuelle` (niveau statique de chaq |
| C-ACAL-L5-806 | C10, S3 | ACAL806 | PLAN_AUDIT_CALEPINAGE | M2 | Faire suivre la HMT et les volumes du pompage au niveau d'eau de chaque mois : la porte `pompage/` accepte un  |
| C-ACAL-L5-807 | C18, S3 | ACAL807 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher dans l'onglet Pompage la carte « Réservoir jour par jour », les saisies du niveau d'eau et les alerte |
| C-ACAL-L5-808 | C7, S3 | ACAL808 | PLAN_AUDIT_DEVIS | M2 | Avertir dans le kit de pompage quand ni la sonde de niveau n'est cochée ni la protection marche à sec du varia |
| C-ACAL-L5-809 | C10, S3 | ACAL809 | PLAN_AUDIT_DEVIS | M2 | Exposer `controle_chaine_variateur` (fonction publique du noyau de pompage) : vérifier une longueur de chaîne  |
| C-ACAL-L5-810 | C10, S3 | ACAL810 | PLAN_AUDIT_CALEPINAGE | M2 | Contrôler les chaînes du champ posé contre la fenêtre du variateur retenu : la porte du pompage rend `chaines_ |
| C-ACAL-L5-811 | C18, S3 | ACAL811 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher dans l'onglet Pompage une ligne de verdict « N modules en série : Voc à froid X V, le variateur accep |
| C-ACAL-L5-812 | C7, S3 | ACAL812 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au balayage d'orientation le critère « mois choisi » : chaque point porte l'énergie de ce mois et la r |
| C-ACAL-L5-813 | C18, S3 | ACAL813 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à l'onglet « Optimiser » le choix « Optimiser pour le mois de » (12 mois ou « toute l'année ») |
| C-ACAL-L5-814 | C7, S3 | ACAL814 | PLAN_AUDIT_DEVIS | M2 | Comparer « pompage direct » et « avec le réservoir déclaré » : `comparaison_direct_reservoir` rend, pour chacu |
| C-ACAL-L5-815 | C10, S3 | ACAL815 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher dans l'onglet Pompage deux cartes côte à côte « Pompage direct » et « Avec le réservoir » : débit de  |
| C-ACAL-L5-816 | C10, S3 | ACAL816 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à la fiche du variateur de pompage le champ « tension redressée du bus DC » (`var_bus_dc_redresse_v`,  |
| C-ACAL-L5-817 | C10, S3 | ACAL817 | PLAN_AUDIT_STOCK | M2 | Saisir et servir la tension redressée du bus DC d'un variateur de pompage : champ `var_bus_dc_redresse_v` dans |
| C-ACAL-L5-818 | C7, S3 | ACAL818 | PLAN_AUDIT_DEVIS | M2 | Contrôler l'appoint réseau ou groupe sur le bus DC du variateur : `controle_appoint` compare la tension du cha |
| C-ACAL-L5-819 | C7, S3 | ACAL819 | PLAN_AUDIT_DEVIS | M2 | Contrôler plusieurs pompes sur un même variateur : `controle_pompes_par_variateur` compare la puissance de pla |
| C-ACAL-L5-820 | C10, S3 | ACAL820 | PLAN_AUDIT_CALEPINAGE | M2 | Contrôler l'appoint réseau ou groupe sur l'écran Pompage : choix « Appoint » et ligne de verdict |
| C-ACAL-L5-821 | C10, S3 | ACAL821 | PLAN_AUDIT_CALEPINAGE | M2 | Contrôler plusieurs pompes sur un même variateur dans l'écran Pompage : liste de pompes (nom, kW de plaque), c |
| C-ACAL-L5-822 | C13, S3 | ACAL822 | PLAN_AUDIT_CALEPINAGE | M2 | Faire porter au gabarit de dossier réglementaire une date « vérifié le » et des limites saisies `{code, valeur |
| C-ACAL-L5-824 | C13, S3 | ACAL824 | PLAN_AUDIT_CALEPINAGE | M2 | Dire sur chaque dossier « vérifié le … » et avertir « vérifié il y a plus de N jours » quand la société a régl |
| C-ACAL-L5-827 | C13, S3 | ACAL827 | PLAN_AUDIT_CALEPINAGE | M2 | Saisir le plafond d'injection en ampères et publier sa conversion en kW |
| C-ACAL-L5-828 | C13, S3 | ACAL828 | PLAN_AUDIT_CALEPINAGE | M2 | Admettre jusqu'à trois plages horaires de plafond d'injection et les appliquer heure par heure |
| C-ACAL-L5-829 | C13, S3 | ACAL829 | PLAN_AUDIT_CALEPINAGE | M2 | Admettre un plafond de soutirage (kW) et publier les heures où l'import réseau le dépasse |
| C-ACAL-L5-830 | C13, S3 | ACAL830 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au bloc « Raccordement » (étape Électrique, niveau expert, replié) le plafond en ampères, trois plages |
| C-ACAL-L5-831 | C13, S3 | ACAL831 | PLAN_AUDIT_CALEPINAGE | M2 | Enregistrer le dernier dimensionnement de pompage rendu, pour que le rapport d'étude puisse l'imprimer |
| C-ACAL-L5-832 | C13, S3 | ACAL832 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au rapport d'étude interne la section « Consommation et hypothèses », omise quand aucune consommation  |
| C-ACAL-L5-833 | C13, S3 | ACAL833 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au rapport d'étude interne la section « Hors réseau » (défaillance par mois, pire mois, banque), omise |
| C-ACAL-L5-834 | C13, S3 | ACAL834 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au rapport d'étude interne la section « Pompage » lue sur le dernier dimensionnement enregistré (HMT e |
| C-ACAL-L5-835 | C13, S3 | ACAL835 | PLAN_AUDIT_CALEPINAGE | M2 | Chercher le plus petit nombre de panneaux qui atteint une couverture visée (% de la consommation) sur le bilan |
| C-ACAL-L5-836 | C15, S3 | ACAL836 | PLAN_AUDIT_CALEPINAGE | M2 | Accepter 1 à 12 factures (MAD ou kWh) dans la source « factures » de `consommation/proposer/` et compléter les |
| C-ACAL-L5-837 | C15, S3 | ACAL837 | PLAN_AUDIT_CALEPINAGE | M2 | Monter dans « Affiner ma consommation » une grille repliable « Mes factures (1 à 12 mois) » (un mois par ligne |
| C-ACAL-L5-838 | C15, S3 | ACAL838 | PLAN_AUDIT_LEAD | M2 | Rendre, sans rien écrire sur un lead, une PROPOSITION de kWh lus sur une photo de facture (`lire_photo_facture |
| C-ACAL-L5-839 | C15, S3 | ACAL839 | PLAN_AUDIT_CALEPINAGE | M2 | Servir `GET`/`POST calepinages/<pk>/consommation/lire-facture/` : le GET dit si la lecture d'une photo est dis |
| C-ACAL-L5-840 | C15, S3 | ACAL840 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher « Lire une photo de facture » seulement quand le serveur la dit disponible, puis proposer les kWh lus |
| C-ACAL-L5-842 | C15, S2 | ACAL842 | PLAN_AUDIT_CALEPINAGE | M2 | Décaler le vieillissement de l'âge des pans existants : l'année N d'un pan posé il y a `âge` ans vaut sa produ |
| C-ACAL-L5-843 | C15, S2 | ACAL843 | PLAN_AUDIT_CALEPINAGE | M2 | Publier `production.parties {existant, ajoute, total}` (kWc, P50 neuf, P50 avec âge) quand au moins un pan est |
| C-ACAL-L5-845 | C15, S2 | ACAL845 | PLAN_AUDIT_SAV | M2 | Servir les volumes d'eau mensuels mesurés d'un chantier depuis les index m³ du SAV (`volumes_mensuels_mesures` |
| C-ACAL-L5-846 | C15, S2 | ACAL846 | PLAN_AUDIT_CALEPINAGE | M2 | Servir `POST calepinages/<pk>/ecart-mesures/` : comparer 12 consommations mensuelles mesurées (saisies) à la c |
| C-ACAL-L5-847 | C15, S2 | ACAL847 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à l'étape Résultats (niveau expert) un onglet « Consommation mesurée » réservé aux porteurs de `calepi |
| C-ACAL-L5-848 | C15, S2 | ACAL848 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher dans l'onglet Production (étape Résultats) un tableau « Existant / Ajouté / Total » quand le serveur  |
| C-ACAL-L5-851 | C10, S1 | ACAL851 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire dire aux cartes « Recommandation » et « Total — toutes les zones » la puissance du module réellement pos |
| C-ACAL-L5-852 | C1, S2 | ACAL852 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ne plus afficher « 0 MAD – 0 MAD/an » ni « ≈ 0 % de la facture » quand la facture est inconnue : l'atelier dit |
| C-ACAL-L5-853 | C10, S2 | ACAL853 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire lire la même production aux cartes « Recommandation » et « Total — toutes les zones » d'un toit à un seu |
| C-ACAL-L5-854 | C5, S2 | ACAL854 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Montrer sous le chiffre de production l'écart à PVGIS que la simulation calcule déjà (« Comparé à PVGIS au mêm |
| C-ACAL-L5-855 | C5, S2 | ACAL855 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Donner un voyant à l'écart PVGIS : vert « dans la tolérance de la société », orange « hors tolérance », rien d |
| C-ACAL-L5-856 | C5, S2 | ACAL856 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Poser le contrat `calepinage_pret_a_envoyer.json` (les contrôles avant l'envoi du devis : code, état ok / info |
| C-ACAL-L5-857 | C5, S2 | ACAL857 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Calculer les contrôles de PORTE du « prêt à envoyer ? » sans lever d'erreur (visite validée, approbation à jou |
| C-ACAL-L5-858 | C5, S2 | ACAL858 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Calculer les contrôles ÉLECTRIQUES du « prêt à envoyer ? » en LISANT l'état à trois valeurs servi par ACAL934  |
| C-ACAL-L5-859 | C5, S3 | ACAL859 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Calculer les contrôles de RÉSULTAT et de DOSSIER du « prêt à envoyer ? » (écart PVGIS, ombrage chiffré, pièces |
| C-ACAL-L5-860 | C15, S2 | ACAL860 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Servir l'agrégat `GET calepinages/<pk>/pret-a-envoyer/` (les contrôles des services, plus les pentes jamais co |
| C-ACAL-L5-861 | C6, S2 | ACAL861 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Avertir avant le devis quand rien ne dimensionne le système (ni facture ni taille souhaitée) : « le toit est r |
| C-ACAL-L5-862 | C10, S1 | ACAL862 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Contrôler que la puissance annoncée par le document égale « modules × Wc de la fiche » |
| C-ACAL-L5-863 | C3, S2 | ACAL863 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Signaler avant le devis un obstacle qui dépasse de son pan |
| C-ACAL-L5-864 | C13, S3 | ACAL864 | PLAN_AUDIT_CALEPINAGE | M2 | Dire avant le devis quel pan reste vide |
| C-ACAL-L5-865 | C15, S2 | ACAL865 | PLAN_AUDIT_TRANSVERSE | M1 bloquant-fondateur | Monter en tête de l'étape Électrique du parcours guidé le panneau « Prêt à envoyer ? » (maquette `Electrique.d |
| C-ACAL-L5-866 | C15, S2 | ACAL866 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Remplacer le cadre jaune de 14 lignes techniques de « Générer le devis » par une carte de succès « Devis DEV-… |
| C-ACAL-L5-867 | C15, S2 | ACAL867 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire de l'étape Documents guidée un écran de FIN de parcours (maquette `Documents.dc.html`) : « Prêt à envoye |
| C-ACAL-L5-868 | C15, S2 | ACAL868 | PLAN_AUDIT_CALEPINAGE | M2 | Faire porter par la barre fixe le bouton de l'étape suivante du parcours guidé (« Poser les panneaux », « Racc |
| C-ACAL-L5-869 | C15, S3 | ACAL869 | PLAN_AUDIT_CALEPINAGE | M2 | Réduire en mode guidé le panneau « Personnaliser la disposition » à ses gestes de base (Remplir, Sélectionner, |
| C-ACAL-L5-870 | C18, S3 | ACAL870 | PLAN_AUDIT_CALEPINAGE | M2 | Poser le contrat `calepinage_explications.json` (une entrée par grandeur affichée : clé servie, famille, phras |
| C-ACAL-L5-871 | C18, S3 | ACAL871 | PLAN_AUDIT_CALEPINAGE | M2 | Tenir UN registre des explications en données (`data/explications.json`, clé = clé servie), le servir par `GET |
| C-ACAL-L5-872 | C18, S3 | ACAL872 | PLAN_AUDIT_CALEPINAGE | M2 | Écrire le composant « ? » UNIQUE (`Pourquoi`) lu dans le registre, et la garde qui échoue quand un chiffre d'u |
| C-ACAL-L5-873 | C18, S3 | ACAL873 | PLAN_AUDIT_CALEPINAGE | M2 | Brancher le « ? » sur la famille PRODUCTION : P50, P75/P90/P95, variabilité, productible, puissance, pertes to |
| C-ACAL-L5-874 | C18, S3 | ACAL874 | PLAN_AUDIT_CALEPINAGE | M2 | Brancher le « ? » sur les grandeurs ÉLECTRIQUES affichées : élévation de tension, marge à la limite, puissance |
| C-ACAL-L5-875 | C18, S3 | ACAL875 | PLAN_AUDIT_CALEPINAGE | M2 | Brancher le « ? » sur la famille ÉNERGIE : capacité utile, énergie stockée et restituée, les six flux, hors-ré |
| C-ACAL-L5-876 | C18, S3 | ACAL876 | PLAN_AUDIT_CALEPINAGE | M2 | Brancher le « ? » sur la famille TOIT et CARTES DE L'ATELIER : inclinaison, pas, hauteur hors-tout, longueur d |
| C-ACAL-L5-877 | C18, S3 | ACAL877 | PLAN_AUDIT_CALEPINAGE | M2 | Brancher le « ? » sur la famille POMPAGE : débit à la HMT, pompe retenue, variateur, autonomie du réservoir, m |
| C-ACAL-L5-878 | C18, S3 | ACAL878 | PLAN_AUDIT_CALEPINAGE | M2 | Brancher le « ? » sur la famille COMPARATIF et DOCUMENTS : modules, kWc, P50 et écarts du comparatif des varia |
| C-ACAL-L5-879 | C18, S3 | ACAL879 | PLAN_AUDIT_CALEPINAGE | M2 | Dire en mots du métier les motifs serveur qui montrent un chemin de code, et un seul vocabulaire pour le statu |
| C-ACAL-L5-880 | C18, S3 | ACAL880 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter sous le chiffre de production le bouton « Pourquoi ce chiffre ? » (maquette `Resultats.dc.html`) : les |
| C-ACAL-L5-883 | C10, S3 | ACAL883 | PLAN_AUDIT_CALEPINAGE | M2 | Faire dire au comparatif des variantes « mêmes hypothèses de pertes et de météo » ou NOMMER ce qui diffère |
| C-ACAL-L5-884 | C10, S3 | ACAL884 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher sous le tableau des variantes la ligne « mêmes hypothèses de pertes et de météo » ou la liste de ce q |
| C-ACAL-L5-885 | C9, S3 | ACAL885 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter à l'export tableur une feuille « Vérification » qui écrit EN TEXTE les formules de la Voc à froid et d |
| C-ACAL-L5-886 | C9, S3 | ACAL886 | PLAN_AUDIT_CALEPINAGE | M2 | Poser le contrat `calepinage_production_mesuree.json` (douze valeurs mensuelles mesurées, l'écart au P50 mensu |
| C-ACAL-L5-887 | C9, S3 | ACAL887 | PLAN_AUDIT_CALEPINAGE | M2 | Enregistrer douze valeurs mensuelles de production MESURÉE par calepinage et servir leur écart au P50 mensuel  |
| C-ACAL-L5-888 | C9, S3 | ACAL888 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter le panneau « Livré et prévu » (douze valeurs mesurées collées, écart au P50) à l'étape Résultats, en m |
| C-ACAL-L5-889 | C3, S3 | ACAL889 | PLAN_AUDIT_CALEPINAGE | M2 | Imprimer sur le plan de pose la tension DC maxi à froid de chaque chaîne et, si la société en a saisi une, sa  |
| C-ACAL-L5-890 | C13, S3 | ACAL890 | PLAN_AUDIT_CALEPINAGE | M2 | Mesurer UNE fois la fluidité de l'atelier à trois tailles (2 000, 5 000, 10 000 modules) et committer la limit |
| C-ACAL-L5-891 | C13, S3 | ACAL891 | PLAN_AUDIT_CALEPINAGE | M2 | Refuser en le disant un pavage au-delà de la limite mesurée de modules : « Au-delà de N modules l'atelier n'es |
| C-ACAL-L5-892 | C12, S3 | ACAL892 | PLAN_AUDIT_CALEPINAGE | M2 | Mettre en file hors ligne les photos du site déposées sans réseau et les envoyer à la reconnexion (maquette `T |
| C-ACAL-L5-893 | C3, S3 | ACAL893 | PLAN_AUDIT_CALEPINAGE | M2 | Sortir « Défaut de la société » (allée technique, allées de circulation par pays) de l'atelier vers les Réglag |
| C-ACAL-L5-894 | C9, S3 | ACAL894 | PLAN_AUDIT_CALEPINAGE | M2 | Ne nommer PVGIS dans la mention « Estimation rapide » que si PVGIS a répondu, et n'écrire que la perte réellem |
| C-ACAL-L5-895 | C1, S3 | ACAL895 | PLAN_AUDIT_CALEPINAGE | M2 | Semer, de façon IDEMPOTENTE, trois MODÈLES de bibliothèque marqués « Exemple » (villa à toit incliné, toit pla |
| C-ACAL-L5-896 | C1, S3 | ACAL896 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter le bouton « Vidéo 10 s » à l'atelier : une orbite de la scène enregistrée et téléchargée, que la comme |
| C-ACAL-L5-897 | C1, S3 | ACAL897 | PLAN_AUDIT_CALEPINAGE | M2 | Offrir, sur la page « Photos du site », « Image pour le client » : la même projection des modules sur la photo |
| C-ACAL-L5-901 | C5, S3 | ACAL901 | PLAN_AUDIT_TRANSVERSE | M2 | Offrir au calepinage un sélecteur de ventes qui rend la compatibilité du matériel désigné (module, onduleur, b |
| C-ACAL-L5-902 | C18, S3 | ACAL902 | PLAN_AUDIT_DEPLOY | M2 | Ajouter au lexique les termes du solaire qu'une commerciale rencontre dans l'atelier : Voc, Vmp, Isc, ratio DC |
| C-ACAL-L5-903 | C12, S3 | ACAL903 | PLAN_AUDIT_CHANTIERS | M2 | Ajouter à la carte « Calepinage retenu » de la fiche chantier un bouton « Plan de pose (PDF) » qui télécharge  |
| C-ACAL-L5-904 | C15, S2 | ACAL904 | PLAN_AUDIT_LEAD | M1 bloquant-fondateur | Donner à la fiche du lead UNE porte visible « Dessiner le toit » qui ouvre le calepinage, et faire dire à « Co |
| C-ACAL-L5-906 | C5, S3 | ACAL906 | PLAN_AUDIT_CALEPINAGE | M2 | Ajouter au « prêt à envoyer ? » le contrôle de compatibilité panneau ↔ onduleur et batterie ↔ onduleur lu du s |
| C-ACAL-L5-911 | C1, S2 | ACAL911 | PLAN_AUDIT_TRANSVERSE | M1 bloquant-fondateur | Rendre, pour une pose est-ouest, l'inclinaison et l'azimut POSÉS de chaque face dans la géométrie du devis — l |
| C-ACAL-L5-912 | C1, S2 | ACAL912 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Ne plus écrire comme production du devis le `result.annualKwh` racine (toit seul) quand le document chiffre au |
| C-ACAL-L5-913 | C1, S2 | ACAL913 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Poser comme module de départ de chaque pan le premier module CHOISISSABLE du catalogue (« module de départ — à |
| C-ACAL-L5-914 | C1, S2 | ACAL914 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Refuser « Générer le devis » quand la composition chiffre un autre module que le dessin (kWc composé ≠ kWc des |
| C-ACAL-L5-915 | C1, S1 | ACAL915 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Dire, avant « Générer le devis », ce que le devis va chiffrer : « Le devis chiffre : Zone 1 (42) + Champ au so |
| C-ACAL-L5-916 | C1, S1 | ACAL916 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Composer chaque surface de pose à SA puissance (`moduleWc`) même sans `modules[]` |
| C-ACAL-L5-918 | C6, S2 | ACAL918 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire calculer par le moteur la surface créée par « Enregistrer le contour tracé » (bloc `engine` stocké, modu |
| C-ACAL-L5-921 | C10, S1 | ACAL921 | PLAN_AUDIT_TRANSVERSE | GATED (ne PAS auto-construire) | Poser UNE convention pour `rowAzimuthDeg` : l'azimut de FACE des tables (180 = sud, comme l'écran), sans + 90° |
| C-ACAL-L5-922 | C1, S2 | ACAL922 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Demander une CONFIRMATION avant de générer un devis que rien ne dimensionne (ni facture ni taille souhaitée) : |
| C-ACAL-L5-923 | C18, S2 | ACAL923 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Poser à l'écran la question de confirmation : « Aucune facture : le devis remplit le toit (34,08 kWc, 168 800, |
| C-ACAL-L5-925 | C6, S2 | ACAL925 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Garder la cible hydratée quand on clique « Effacer » : après `reset`, le nombre de panneaux voulu redevient ce |
| C-ACAL-L5-926 | C6, S2 | ACAL926 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Poser le dernier coin quand on finit un tracé par un double-clic à un NOUVEL endroit (le coin en attente est p |
| C-ACAL-L5-927 | C1, S2 | ACAL927 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Faire dépendre de la POSE les quantités « Structures acier » et « Socles » de la composition (D-ACAL-39) |
| C-ACAL-L5-928 | C3, S2 | ACAL928 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Limiter les inclinaisons essayées en Est-Ouest aux inclinaisons constructibles de V6 (10, 12, 15°) |
| C-ACAL-L5-929 | C3, S2 | ACAL929 | WEB_PLAN | M1 bloquant-fondateur | Ajouter à `estimatorBrainCommun.ts` un départage par énergie du module supplémentaire (`departageParModule`),  |
| C-ACAL-L5-934 | C3, S2 | ACAL934 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Servir un état à trois valeurs du dossier électrique (« prêt », « à compléter : N points », « bloquant : N »), |
| C-ACAL-L5-935 | C3, S2 | ACAL935 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire lire au cadre de génération du devis et au résumé de l'affectation le même état et les mêmes mots (« Prê |
| C-ACAL-L5-937 | C15, S2 | ACAL937 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ajouter à « Sources des paramètres normatifs » le lien « Choisir la norme » vers le champ de norme de Réglages |
| C-ACAL-L5-938 | C15, S2 | ACAL938 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire atterrir « Aller aux réglages de lestage » du panneau Masse et lestage sur le champ du premier paramètre |
| C-ACAL-L5-939 | C9, S3 | ACAL939 | PLAN_AUDIT_CALEPINAGE | M2 | Retirer la pesanteur et la masse volumique de l'air des paramètres de lestage à saisir : constantes fixes docu |
| C-ACAL-L5-940 | C15, S2 | ACAL940 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Refuser la simulation UNE fois en listant TOUTES les clés manquantes (`manquants[]`) et faire ouvrir à chaque  |
| C-ACAL-L5-942 | C18, S2 | ACAL942 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Dire « Conception enregistrée — il manque le calcul » après un enregistrement, pas « Aucune conception enregis |
| C-ACAL-L5-945 | C6, S2 | ACAL945 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Enregistrer hors ligne sans mentir : « Pas de réseau — enregistré sur ce téléphone, envoi au retour » ET l'env |
| C-ACAL-L5-946 | C15, S2 | ACAL946 | PLAN_AUDIT_CALEPINAGE | M2 | Remplacer « Approuver » par « La conception doit être approuvée par un autre relecteur » pour l'auteur, et n'a |
| C-ACAL-L5-947 | C6, S2 | ACAL947 | PLAN_AUDIT_CALEPINAGE | M2 | Lister d'un coup toutes les erreurs de réglage, près du bouton « Enregistrer les réglages », avec ce que le se |
| C-ACAL-L5-948 | C15, S3 | ACAL948 | PLAN_AUDIT_CALEPINAGE | M2 | Trouver un calepinage par le titre affiché « Calepinage #12 » : la recherche accepte « #12 » et « Calepinage # |
| C-ACAL-L5-949 | C13, S2 | ACAL949 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire zoomer la molette sans erreur : le gestionnaire `wheel` ne lit plus la position avant de tester Alt |
| C-ACAL-L5-950 | C15, S2 | ACAL950 | PLAN_AUDIT_CALEPINAGE | M2 | Sortir la puce « Plein écran » de la pile des boutons de zoom : en haut à gauche sous la boussole, fond opaque |
| C-ACAL-L5-951 | C15, S2 | ACAL951 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire remplir l'écran au plein écran du téléphone : une règle CSS qui l'emporte sur `position: relative` |
| C-ACAL-L5-952 | C15, S2 | ACAL952 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Au toucher, un doigt fait défiler la page et deux doigts déplacent la carte de l'atelier : `cooperativeGesture |
| C-ACAL-L5-954 | C18, S2 | ACAL954 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Poser « Terminer le tracé » sur la carte, pas sous la flottaison : bouton `#rp9-finish` remonté dans l'envelop |
| C-ACAL-L5-955 | C15, S2 | ACAL955 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire passer « Enregistrer » avant « Générer le devis » : la barre d'enregistrement se rend au-dessus du bloc  |
| C-ACAL-L5-956 | C15, S2 | ACAL956 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Cadrer le toit à la fermeture du contour : la caméra prend le zoom qui montre le contour entier, à 58° comme a |
| C-ACAL-L5-957 | C15, S3 | ACAL957 | PLAN_AUDIT_CALEPINAGE | M2 | Replier les filtres de la liste sous 768 px : la recherche seule d'abord et un bouton « Filtres » |
| C-ACAL-L5-958 | C18, S3 | ACAL958 | PLAN_AUDIT_CALEPINAGE | M2 | Montrer la fenêtre « Déplacer les panneaux » dès que le toit est fermé dans l'atelier ERP : `syncProductionWin |
| C-ACAL-L5-959 | C6, S2 | ACAL959 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire porter le matériel au modèle : « Partir d'un modèle » recopie le module, l'onduleur et les décisions de  |
| C-ACAL-L5-960 | C6, S2 | ACAL960 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Choisir les favoris de matériel dans deux listes du catalogue (Modules, Onduleurs), pas par des identifiants t |
| C-ACAL-L5-961 | C15, S3 | ACAL961 | PLAN_AUDIT_CALEPINAGE | M2 | Proposer les champs admis d'un préréglage, avec leur unité, au lieu d'un texte « champ = valeur » libre |
| C-ACAL-L5-962 | C15, S3 | ACAL962 | PLAN_AUDIT_CALEPINAGE | M2 | Dire sans clé technique pourquoi l'allée de circulation est refusée et transmettre le pays réglé de la société |
| C-ACAL-L5-963 | C18, S3 | ACAL963 | PLAN_AUDIT_CALEPINAGE | M2 | Retirer des textes affichés les codes de tâche et le chemin du dépôt de la Bibliothèque |
| C-ACAL-L5-964 | C18, S3 | ACAL964 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher les options des réglages de simulation en mots français servis avec le registre |
| C-ACAL-L5-965 | C18, S3 | ACAL965 | PLAN_AUDIT_CALEPINAGE | M2 | Dire une seule fois que la cible de puissance n'est pas calculée, avec un lien vers la fiche du lead |
| C-ACAL-L5-966 | C18, S3 | ACAL966 | PLAN_AUDIT_CALEPINAGE | M2 | Retirer de la fiche d'un calepinage l'identifiant technique et le code de statut |
| C-ACAL-L5-967 | C18, S4 | ACAL967 | PLAN_AUDIT_CALEPINAGE | M2 | Ne plus écrire « Calepinage Calepinage … chargé » et raccourcir à 8 caractères les empreintes de la comparaiso |
| C-ACAL-L5-968 | C1, S1 | ACAL968 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Ajouter, à la liste des surfaces d'ACAL915, une case par surface chiffrée, TOUTES cochées à l'ouverture, et ne |
| C-ACAL-L5-969 | C3, S3 | ACAL969 | PLAN_AUDIT_CALEPINAGE | M2 | Donner un style de l'ERP aux retraits et aux notes que le constructeur crée en JavaScript et un seul style « c |
| C-ACAL-L5-970 | C3, S3 | ACAL970 | PLAN_AUDIT_CALEPINAGE | M2 | Aligner le tableau « Par pan » de la production et donner aux listes et à la case de l'onglet Batterie le styl |
| C-ACAL-L5-971 | C18, S3 | ACAL971 | PLAN_AUDIT_CALEPINAGE | M2 | Proposer le genre et le pays d'un gabarit en mots français et un sélecteur de fichier stylé en français |
| C-ACAL-L5-972 | C18, S3 | ACAL972 | PLAN_AUDIT_CALEPINAGE | M2 | Masquer l'épingle du lead dessinée par-dessus les panneaux dès que le toit est fermé |
| C-ACAL-L5-973 | C1, S2 | ACAL973 | PLAN_AUDIT_MOTEUR | M1 bloquant-fondateur | Faire imprimer par le PDF, au niveau de règles 15 et SANS bloc horaire rangé, la production de la pose réelle  |
| C-ACAL-L5-974 | C15, S3 | ACAL974 | PLAN_AUDIT_CALEPINAGE | M2 | Proposer la température minimale et maximale du site tirées de la météo, marquées « proposée — à confirmer » |
| C-ACAL-L5-975 | C1, S3 | ACAL975 | PLAN_AUDIT_CALEPINAGE | M2 | Ne plus proposer de gain bifacial pour une pose affleurante |
| C-ACAL-L5-976 | C1, S1 | ACAL976 | PLAN_AUDIT_MOTEUR | M1 bloquant-fondateur | Ne publier ni TRI ni retour dans l'onglet Économie quand la consommation du lead est inconnue |
| C-ACAL-L5-977 | C18, S3 | ACAL977 | PLAN_AUDIT_DEPLOY | M2 | Faire suivre le thème sombre à l'icône du menu de la barre du haut |
| C-ACAL-L5-978 | C15, S3 | ACAL978 | PLAN_AUDIT_CALEPINAGE | M2 | Comparer d'office la conception courante aux variantes dans « Comparer les variantes » |
| C-ACAL-L5-979 | C7, S2 | ACAL979 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Afficher sur chaque poste de pertes la valeur HÉRITÉE du réglage de la société quand le poste n'est pas saisi |
| C-ACAL-L5-980 | C6, S3 | ACAL980 | PLAN_AUDIT_CALEPINAGE | M2 | Servir une liste « Ce qui est supposé » nommant chaque repli caché, sa valeur et le champ à renseigner |
| C-ACAL-L5-981 | C18, S3 | ACAL981 | PLAN_AUDIT_CALEPINAGE | M2 | Nommer « Bâtiment 1 » le bâtiment sans identifiant et ne plus écrire « contour du pan non tracé » quand le toi |
| C-ACAL-L5-982 | C7, S2 | ACAL982 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire échouer la CI dès qu'une grandeur d'une conception (kWc, production annuelle, état du dossier électrique |
| C-ACAL-L5-983 | C1, S2 | ACAL983 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire échouer la CI quand une valeur que personne n'a saisie fixe seule un chiffre de devis sans confirmation |
| C-ACAL-L5-984 | C1, S2 | ACAL984 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire échouer la CI dès qu'un document (planche A3, DXF, plan de câblage, devis) dessine ou compte autre chose |
| C-ACAL-L5-985 | C6, S2 | ACAL985 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire échouer la CI dès qu'une saisie n'atteint pas le calcul ou disparaît en route |
| C-ACAL-L5-986 | C15, S2 | ACAL986 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire échouer la CI dès qu'un message demande une saisie qu'aucun écran ne permet |
| C-ACAL-L5-987 | C13, S2 | ACAL987 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire échouer la CI dès qu'un écran produit une erreur sans geste de l'utilisateur ou un retour faux |
| C-ACAL-L5-988 | C13, S2 | ACAL988 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire échouer la CI dès qu'un geste de carte (molette, clic coin, double-clic, glisser, pincer, + / −, plein é |
| C-ACAL-L5-989 | C15, S3 | ACAL989 | PLAN_AUDIT_CALEPINAGE | M2 | Faire échouer la CI dès que l'action suivante ou le chiffre résultat sort de la première hauteur d'écran |
| C-ACAL-L5-990 | C1, S3 | ACAL990 | PLAN_AUDIT_CALEPINAGE | M2 | Faire échouer la CI dès qu'un texte SERVI en direct contient une clé, un chemin, un code interne ou une valeur |
| C-ACAL-L5-991 | C10, S2 | ACAL991 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Poser SEUL sur main le contrat `chiffrage_conception.json` de la porte unique de chiffrage d'`apps/ventes` (en |
| C-ACAL-L5-992 | C1, S2 | ACAL992 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Écrire la porte unique `chiffrer_conception` (module `domain/chiffrage_conception.py`, ré-exportée par `apps.v |
| C-ACAL-L5-993 | C1, S2 | ACAL993 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Servir dans le `design-context` du calepinage un bloc `chiffrage` (kWc, production année 1, économie année 1 e |
| C-ACAL-L5-994 | C1, S2 | ACAL994 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Faire afficher par l'atelier ERP la production et l'économie SERVIES par le bloc `chiffrage` (à l'ouverture et |
| C-ACAL-L5-995 | C1, S2 | ACAL995 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Montrer dans l'onglet Production du calepinage, sous le résultat de la simulation, la ligne « Le devis annonce |
| C-ACAL-L5-996 | C10, S2 | ACAL996 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Poser SEUL sur main le contrat `calepinage_productible_pose.json` : le rendement de la pose réelle servi au mo |
| C-ACAL-L5-997 | C1, S2 | ACAL997 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Servir le rendement de la pose réelle dans un module frère `apps/calepinage/selectors_devis.py` : `productible |
| C-ACAL-L5-998 | C1, S2 | ACAL998 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Déclarer le niveau de règles 15 (`REGLES_POSE_REELLE_2111`) qui porte, pour toute la vague, la production de l |
| C-ACAL-L5-999 | C1, S2 | ACAL999 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Écrire LE résolveur de la base de production d'un devis, `horaire/productible_pose.py::base_de_production(devi |
| C-ACAL-L5-1000 | C1, S2 | ACAL1000 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Paramétrer le dry-run des niveaux de règles par `--niveau N` : pour chaque devis de la société de niveau < N,  |
| C-ACAL-L5-1001 | C1, S2 | ACAL1001 | PLAN_AUDIT_DEVIS | GATED (ne PAS auto-construire) | Rendre courant le niveau de règles 15 : `REGLES_COURANTES` = 15, défaut du modèle `Devis.regles_calcul` = `REG |
| C-ACAL-L5-1002 | C2, S3 | ACAL1002 | PLAN_AUDIT_CALEPINAGE | M2 | Réunir la lecture des pans POSÉS d'un document `roof_layout` en une fonction pure `pans_poses(document)` du no |
| C-ACAL-L5-1003 | C2, S3 | ACAL1003 | PLAN_AUDIT_CALEPINAGE | M2 | Faire lire `pans_poses` par la planche A3, le DXF et le plan de câblage au lieu de leur propre lecture du docu |
| C-ACAL-L5-1004 | C2, S3 | ACAL1004 | PLAN_AUDIT_DEVIS | M2 | Marquer `origine_conception: rapide` le devis créé par le bouton « Devis automatique » de la fiche lead, clé d |
| C-ACAL-L5-1005 | C10, S3 | ACAL1005 | PLAN_AUDIT_CALEPINAGE | M2 | Poser SEUL sur main la clé `etat_conception` (`rapide` / `complet`) au contrat `calepinage_detail.json` |
| C-ACAL-L5-1006 | C2, S3 | ACAL1006 | PLAN_AUDIT_CALEPINAGE | M2 | Marquer `rapide` le calepinage créé ou adopté à l'ouverture d'un devis automatique jamais dessiné, et le passe |
| C-ACAL-L5-1007 | C10, S3 | ACAL1007 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher dans l'atelier, sur un calepinage `rapide`, le bandeau « Conception rapide — à vérifier sur place » a |
| C-ACAL-L5-1008 | C1, S2 | ACAL1008 | PLAN_AUDIT_CALEPINAGE | M2 | Refuser qu'un calepinage `rapide` sorte côté client : la planche A3 est refusée, l'annexe « paramètres du site |
| C-ACAL-L5-1009 | C15, S3 | ACAL1009 | PLAN_AUDIT_CALEPINAGE | M2 | Poser un cliquet des imports croisés entre `apps/ventes` et `apps/calepinage` : un test compte les fichiers no |
| C-ACAL-L5-1010 | C1, S2 | ACAL1010 | PLAN_AUDIT_CALEPINAGE | M2 | Étendre la garde « une grandeur, une valeur » d'ACAL982 au bloc `chiffrage` : pour un calepinage lié à un devi |
| C-ACAL-L5-1011 | C1, S2 | ACAL1011 | PLAN_AUDIT_MOTEUR | M2 | Ajouter au correcteur de nuit la règle `CAL_PRODUCTION_DEVIS_VS_CALEPINAGE` : un BROUILLON de niveau 15 dont l |
| C-ACAL-L5-1026 | C1, S3 | ACAL1026 | WEB_PLAN | M2 | Monter sous la visionneuse 3D de la page publique du devis le réglage « Heure et mois » du soleil |
| C-ACAL-L5-1027 | C13, S4 | ACAL1027 | PLAN_AUDIT_CALEPINAGE | M2 | Masquer le lien « Raccourcis clavier (?) » sur un appareil sans clavier (écran tactile principal) |
| C-ACAL-L5-1028 | C18, S3 | ACAL1028 | PLAN_AUDIT_CALEPINAGE | M2 | Montrer, sur l'onglet Schéma unifilaire quand la fiche technique est incomplète, un croquis de principe grisé  |
| C-ACAL-L5-1029 | C1, S2 | ACAL1029 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Dire combien de modules du document sont posés à plat sur un toit en pente (affleurants) |
| C-ACAL-L5-1031 | C19, S3 | ACAL1031 | PLAN_AUDIT_CALEPINAGE | Acceptation en direct (orchestrateur, jamais une lane) | Acceptation live de la vague 2 du complément ( ACAL492-521, ACAL526-531, ACAL533-537, ACAL546-555, ACAL557-569 |
| C-ACAL-L5-1032 | C4, S2 | ACAL1032 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Monter « Dupliquer » et « Poser en série » dans la carte « Obstacle sélectionné » de l'atelier ERP |
| C-ACAL-L5-1033 | C1, S1 | ACAL1033 | PLAN_AUDIT_MOTEUR | M1 bloquant-fondateur | Ne plus imprimer la vignette « Économies estimées / an » du format « une page » quand aucune donnée réelle n'a |
| C-ACAL-L5-1041 | C10, S3 | ACAL1041 | PLAN_AUDIT_CALEPINAGE | M2 | Poser SEUL sur `main` le contrat de la clé racine `imageCapture` (date de prise de vue de l'image + source) et |
| C-ACAL-L5-1049 | C4, S3 | ACAL1049 | PLAN_AUDIT_CALEPINAGE | M2 | Faire servir par la détection du toit les obstacles rendus par le fournisseur, validés côté calepinage |
| C-ACAL-L5-1050 | C4, S3 | ACAL1050 | PLAN_AUDIT_SECURITE | M2 | Faire demander les obstacles au fournisseur d'IA de détection du toit et les valider avec `valider_obstacles` |
| C-ACAL-L5-1065 | C2, S3 | ACAL1065 | PLAN_AUDIT_CALEPINAGE | M2 | Imprimer les repères de chantier saisis sur la feuille A4 du pan qui les contient, avec un symbole par type, l |
| C-ACAL-L5-1081 | C10, S3 | ACAL1081 | PLAN_AUDIT_TRANSVERSE | M2 | Poser SEUL sur main, dans le contrat de l'import PVsyst, les clés `refus` (chaîne vide) et `conversions` (list |
| C-ACAL-L5-1113 | C10, S3 | ACAL1113 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Choisir la pompe du calepinage avec `choisir_pompe` du devis, en lui passant le calage et le tubage, et rendre |
| C-ACAL-L5-1114 | C10, S3 | ACAL1114 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Plafonner le débit du pompage au débit d'exploitation du forage, alerter quand le forage ne suffit pas et rend |
| C-ACAL-L5-1145 | C1, S2 | ACAL1145 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Faire dire à `cible_depuis_lead` POURQUOI il ne dimensionne pas : clé additive `motif_code` (le motif du refus |
| C-ACAL-L5-1169 | C1, S2 | ACAL1169 | PLAN_AUDIT_MOTEUR | M1 bloquant-fondateur | Donner au moteur horaire un paramètre `base_production` (`{kwh_kwc_annuel, kwh_kwc_mensuel[12], pertes_incluse |
| C-ACAL-L5-1170 | C1, S2 | ACAL1170 | PLAN_AUDIT_MOTEUR | M1 bloquant-fondateur | Faire lire la base de production (`base_de_production`, ACAL999) par les lecteurs du MOTEUR : le bloc horaire  |
| C-ACAL-L5-1171 | C1, S2 | ACAL1171 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Calculer le contrôle `un_seul_chiffre` du « prêt à envoyer ? » : dire, pour un calepinage lié à un devis de ni |
| C-ACAL-L5-1172 | C1, S2 | ACAL1172 | PLAN_AUDIT_STOCK | M1 bloquant-fondateur | Semer au catalogue le produit « Kit de fixation toiture inclinée (crochets, rails, pinces) » SANS prix, grisé  |
| C-ACAL-L5-1173 | C2, S3 | ACAL1173 | PLAN_AUDIT_DEVIS | M2 | Étendre le dry-run `comparer_compte_moteur_calepinage` par `--calepinages` : pour chaque calepinage actif d'un |
| C-ACAL-L5-1185 | C4, S3 | ACAL1185 | PLAN_AUDIT_CALEPINAGE | M2 | Dessiner les poignées des coins à la hauteur du toit en vue 3D |
| C-ACAL-L5-1186 | C2, S2 | ACAL1186 | PLAN_AUDIT_CALEPINAGE | M2 | Poser SEUL sur `main` le contrat du sixième contrôle de raccordement « Limitation de l'injection » et du dixiè |
| C-ACAL-L5-1187 | C2, S2 | ACAL1187 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Rendre « attention — limite d'injection non garantie » quand un champ à micro-onduleurs porte un plafond d'inj |
| C-ACAL-L5-1188 | C2, S2 | ACAL1188 | PLAN_AUDIT_CALEPINAGE | M2 | Afficher dans « Raccordement » le sixième contrôle et le champ « Dispositif qui limite l'injection » |
| C-ACAL-L5-1189 | C15, S3 | ACAL1189 | PLAN_AUDIT_CALEPINAGE | M2 | Mesurer chaque étape du mode guidé, pas seulement le premier écran |
| C-ACAL-L5-1190 | C15, S3 | ACAL1190 | PLAN_AUDIT_CALEPINAGE | M2 | Réduire l'étape Toit du mode guidé au panneau de la maquette |
| C-ACAL-L5-1191 | C15, S3 | ACAL1191 | PLAN_AUDIT_CALEPINAGE | M2 | Réduire l'écran guidé de l'étape Électrique à la maquette : Verdict et Équipements ouverts, les cinq autres se |
| C-ACAL-L5-1192 | C15, S3 | ACAL1192 | PLAN_AUDIT_CALEPINAGE | M2 | Réduire l'étape Résultats du mode guidé à la production et à ses pertes |
| C-ACAL-L5-1193 | C15, S3 | ACAL1193 | PLAN_AUDIT_CALEPINAGE | M2 | Réduire l'étape Documents du mode guidé à l'écran de fin de la maquette |
| C-ACAL-L5-1194 | C10, S1 | ACAL1194 | PLAN_AUDIT_CALEPINAGE | M1 bloquant-fondateur | Lister en lecture seule les calepinages dont l'orientation lue des surfaces de pose changera avec ACAL921 |
| C-ACAL-L5-1195 | C1, S1 | ACAL1195 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Faire calculer l'étude commerciale et industrielle d'un NOUVEAU devis de niveau 15 lié à un calepinage simulé  |
| C-ACAL-L5-1196 | C1, S2 | ACAL1196 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Ne plus servir la vue 3D publique d'un devis dont le calepinage est une conception « rapide » non vérifiée |
| C-ACAL-L5-1197 | C1, S2 | ACAL1197 | PLAN_AUDIT_PARAMETRES | M1 bloquant-fondateur | Permettre de lire PVGIS en direct à un plan donné : `productible_mensuel_live` et `profil_horaire_live` accept |
| C-ACAL-L5-1198 | C10, S2 | ACAL1198 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Poser SEUL sur main la clé `production.plan_irradiation` du contrat `etude_pompage_preview.json` — `{source: ' |
| C-ACAL-L5-1199 | C1, S2 | ACAL1199 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Écrire le résolveur du plan des panneaux d'un devis agricole, `domain/pompage_pose.py::plan_pose_pompage(devis |
| C-ACAL-L5-1200 | C1, S2 | ACAL1200 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Construire les 12 journées types d'irradiance du pompage au plan RÉEL des panneaux, `domain/pompage_pose.py::p |
| C-ACAL-L5-1201 | C1, S2 | ACAL1201 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Faire calculer la production d'eau d'un NOUVEAU devis agricole de niveau 15 sur le plan réel des panneaux : `e |
| C-ACAL-L5-1202 | C1, S2 | ACAL1202 | PLAN_AUDIT_GENERATEUR | M1 bloquant-fondateur | Dire dans le résultat du pompage du générateur sur quel plan la production d'eau a été calculée : une ligne «  |
| C-ACAL-L5-1203 | C1, S2 | ACAL1203 | PLAN_AUDIT_DEVIS | M1 bloquant-fondateur | Étendre la liste des écarts `regles_calcul_ecarts_dryrun --niveau 15` aux devis agricoles : pour chacun, recal |

## Vérification du 21/11

Après la première intégration (472 tâches, PR #1517), la vague a été relue en entier contre le code de `main` (worktree de vérification à jour de `main` le 21/11), puis corrigée hors dépôt dans des copies d'édition, et réassemblée ici.

- **17 vérificateurs neufs, un par lot**, ont relu chaque tâche de leur lot contre le code (rapports `rapport-<lot>.md` du dossier de travail) : 449 verdicts. Le lot D8 (moteur partagé, 22 tâches) a été relu en entier par la relecture adverse finale. Verdicts comptés dans les rapports :

| Lot | Tâches relues | OK | À corriger | Doublon | Déjà construit (sans objet) | À scinder |
|---|---|---|---|---|---|---|
| AUTRES-PLANS | 32 | 15 | 17 | 0 | 0 | 0 |
| D1-a | 22 | 10 | 12 | 0 | 0 | 0 |
| D1-b | 21 | 7 | 12 | 1 | 0 | 1 |
| D2-a | 30 | 22 | 7 | 1 | 0 | 0 |
| D2-b | 29 | 12 | 11 | 6 | 0 | 0 |
| D3-a | 27 | 9 | 16 | 2 | 0 | 0 |
| D3-b | 27 | 7 | 15 | 4 | 1 | 0 |
| D4-a | 28 | 15 | 13 | 0 | 0 | 0 |
| D4-b | 28 | 14 | 13 | 1 | 0 | 0 |
| D4-c | 26 | 14 | 11 | 0 | 1 | 0 |
| D5-a | 29 | 24 | 4 | 0 | 0 | 1 |
| D5-b | 28 | 19 | 9 | 0 | 0 | 0 |
| D6-a | 24 | 2 | 22 | 0 | 0 | 0 |
| D6-b | 24 | 10 | 13 | 1 | 0 | 0 |
| D7-a | 25 | 10 | 5 | 8 | 1 | 1 |
| D7-b | 25 | 19 | 3 | 2 | 1 | 0 |
| D7-c | 24 | 16 | 8 | 0 | 0 | 0 |
| **total** | **449** | **225** | **191** | **26** | **4** | **3** |

- **Deux passes de correction par lot**, puis **une passe de cohérence** de toute la vague (aucun cycle de `@after`, aucun renvoi vers une tâche retirée, aucun id inconnu ; seules les neuf tâches de la vague 0 déclarent `apps/calepinage/selectors.py`).
- **Deux relectures adverses au modèle le plus fort** : l'architecture du moteur partagé (D8), puis la vague entière — 8 bloquants, dont la chaîne D-ACAL-36 réécrite (production de la pose réelle atteignable au PDF, porte fondateur qui ne se contourne plus, liste des écarts produite après le code qu'elle montre), les migrations rangées avec leur modèle, 32 dépendances entre plans passées en vrais `@after`, et les tâches qui déclaraient `selectors.py` ramenées à la vague 0.
- **Ce qui a changé** : 23 tâches retirées (doublons, déjà construites ou migrations remises avec leur modèle — liste ci-dessous) ; 33 créées (ACAL1033, ACAL1041, ACAL1049, ACAL1050, ACAL1065, ACAL1081, ACAL1113, ACAL1114, ACAL1145, ACAL1169, ACAL1170, ACAL1171, ACAL1172, ACAL1173, ACAL1185, ACAL1186, ACAL1187, ACAL1188, ACAL1189, ACAL1190, ACAL1191, ACAL1192, ACAL1193, ACAL1194, ACAL1195, ACAL1196, ACAL1197, ACAL1198, ACAL1199, ACAL1200, ACAL1201, ACAL1202, ACAL1203), dont les moitiés des trois scissions (ACAL530, ACAL806, ACAL938) et les douze tâches des manques de la relecture finale (ACAL1185 à ACAL1196) et les sept du lot pompage (ACAL1197 à ACAL1203, D-ACAL-46, écrites après la vérification) ; les autres corrigées clause par clause. Décompte final : 482 tâches.
- Couverture : 427 des 482 tâches vivantes portent un verdict de vérificateur ; les 22 tâches du lot D8 ont été relues par la relecture adverse ; les 33 tâches créées pendant les corrections n'ont eu que la passe de cohérence.

## Tâches retirées

### À la première réconciliation (doublons ou décisions)

- ACAL679 — D-ACAL-43 : gabarit de schéma choisi par distributeur du lead = profils par distributeur (réserve)
- ACAL680 — D-ACAL-43 : affichage du gabarit par distributeur, suit ACAL679 (réserve)
- ACAL691 — doublon d'ACAL854 + ACAL855 (écart PVGIS sous le chiffre de production, avec voyant)
- ACAL739 — doublon d'ACAL659 (mêmes champs de déclassement thermique de l'onduleur, sous deux noms) ; ACAL740-741 lisent ceux d'ACAL659
- ACAL785 — D-ACAL-43 : rien de prérempli ni deviné ; semis de gabarits par distributeur en réserve (sortie A)
- ACAL823 — D-ACAL-43 : choix des gabarits par distributeur du lead = profils par distributeur (réserve)
- ACAL825 — D-ACAL-43 : saisie d'un distributeur sur un gabarit = profils par distributeur (réserve)
- ACAL826 — D-ACAL-43 : limite du profil du distributeur (réserve)
- ACAL841 — second contrat de `zones[].existant` : ACAL573 (D2) est le seul propriétaire de la clé (forme booléen + `anneeMiseEnService`)
- ACAL844 — doublon d'ACAL510 (case « Modules déjà en place » et année de mise en service à l'atelier)
- ACAL849 — D-ACAL-41 : le bilan du réservoir reste interne ; ACAL807 le montre déjà à l'écran (sortie A)
- ACAL882 — couvert par ACAL719 (heure solaire ET heure légale sur la barre du soleil et la course du soleil)
- ACAL898 — doublon d'ACAL697 (même fiche « pertes en mots simples ») — D-ACAL-38(d) la rend remettable au client (sortie A)
- ACAL899 — D-ACAL-43 : profils par distributeur en réserve ; dossier générique déjà servi par `GabaritDossierReglementaire` (sortie A)
- ACAL900 — export Word : réserve (preuve mince : deux fils de forum ; dépendance gratuite, donc pas une porte fondateur) — choix pris seul
- ACAL905 — doublon d'ACAL976 sur `apps/ventes/economie.py` ; D-ACAL-40 tranche (ni économie, ni TRI, ni retour sans consommation)
- ACAL930 — doublon d'ACAL608 (clé de pose des modules : `geometry.panelOrientation` d'ACAL573/601/608 est la seule clé)
- ACAL931 — doublon d'ACAL601 + ACAL605 (emprise orientée des modules à la planche et au plan de câblage)
- ACAL932 — doublon d'ACAL604 (emprise vraie des modules et tracé unique du toit au DXF)

### À la vérification du 21/11

- ACAL532 — doublon de ACAL593 (et du contrat ACAL599, des types ACAL1065)
- ACAL570 — la migration est portée par la tâche qui ajoute le champ — ACAL567
- ACAL644 — doublon de ACAL733
- ACAL656 — déjà construit — `backend/django_core/apps/stock/importers/fiche_pan_ond.py:90` (`'muVocSpec': ('temp_coeff_voc_pct_c', 'mv_par_c_relatif_voc')`) et `:184-188` (÷ (Voc × 10), refus si Voc ≤ 0), assertions `backend/django_core/apps/stock/test_cal_import_pan_ond.py:100-106` (CALX356 cochée, `docs/PLAN2.md`) ; la seule part restante (nommer la conversion dans l'aperçu) est reprise par ACAL658.
- ACAL660 — la migration est portée par la tâche qui ajoute le champ — ACAL659 (six colonnes), ACAL720 (`sous_chaines_par_module`), ACAL816 (`var_bus_dc_redresse_v`)
- ACAL681 — doublon de ACAL752
- ACAL682 — doublon de ACAL736
- ACAL683 — doublon de ACAL736
- ACAL684 — doublon de ACAL737
- ACAL741 — sans objet — le `.OND` réel du dépôt (`backend/django_core/apps/stock/contract_samples/pvsyst/CPS_SCH275KTL-DO-US-800-250kW_275kVA_1.OND`, lignes 29 et 51-56) publie TROIS points de déclassement (`TPNom=45.0`/`PNomConv=250`, `TPLim1=50.0`/`PLim1=225`, `TPLimAbs=60.0`/`PLimAbs=90`, soit 2 % puis 5,4 % de la puissance nominale par °C) : une paire unique (début, pente) ne s'en déduit pas sans extrapolation, et la fiche d'ACAL659 n'a qu'une pente ; lire la courbe par points exigerait un champ de fiche par segments (ACAL659, avec sa migration) et une étape qui l'interpole (ACAL740) — décision de plan, non d'une tâche d'import ; l'appelant de l'import est d'ailleurs `parse_pan_ond_bytes` (`apps/stock/views/fiche_technique.py`), non `propose_mapping`.
- ACAL766 — déjà construit — `frontend/src/features/calepinage/production/PanneauProduction.jsx:346` (`geometriePresente = (data?.pose?.total_modules ?? 0) > 0 && data?.simule === true`, transmis à `TapisHoraire`) et `frontend/src/features/calepinage/production/TapisHoraire.jsx:232-239` (si `!geometriePresente`, aucune requête `export-csv`, `setRefus(SANS_SERIE)`)
- ACAL881 — doublon de ACAL549 (lot D2-a ; contrat ACAL555, impression ACAL550) : même objet (nommer la cause d'un pan où aucun module ne tient, mêmes quatre causes dans le même ordre, source HelioScope N28) ; prémisse fausse : `layoutEditor.ts:1444` désactive « Remplir » quand `free <= 0`, la lattice est celle du plan gagnant (`ensureLayoutState`, l. 1345), `count` 0 ne sort donc pas d'un clic.
- ACAL917 — doublon de ACAL607
- ACAL919 — doublon de ACAL606 (pas anti-ombrage du Terrain, contrat `sol` de `pose.json`) et d'ACAL609 (écran)
- ACAL920 — doublon de ACAL609 (alerte « l'allée imposée ombre la rangée suivante »)
- ACAL924 — doublon de ACAL776 + ACAL777 (lot D5-a : facture du lead servie par `design-context` puis lue par l'atelier, même exemple 900 MAD ; reprise écrite dans les deux)
- ACAL933 — doublon de ACAL602 (échelle réelle imprimée) et d'ACAL603 (cotes du toit seul, DXF)
- ACAL936 — doublon de ACAL687 (phases du raccordement lues de l'entrée électrique)
- ACAL941 — doublon de ACAL770 (désactiver « tmy » dans Réglages, motif piloté par le serveur)
- ACAL943 — déjà construit — `frontend/src/features/calepinage/production/PanneauProduction.jsx:346` (`geometriePresente = total_modules > 0 && data?.simule === true`) et `production/TapisHoraire.jsx:232` (`!geometriePresente` ⇒ aucune requête `export-csv`), livré par ACAL490.
- ACAL944 — doublon de ACAL768
- ACAL953 — doublon de ACAL493
- ACAL1030 — fondue dans ACAL901, devenue tâche atomique à deux propriétaires

## Réserve (capacités non écrites, une ligne chacune)

### Réserve — cartes du backlog qui n'ont pas donné de tâche (vague 2)

#### D1 — Site, toit, relevé
- CAP-D1-20 — Aide « hauteur d'un bâtiment voisin » (étages × hauteur d'étage) — preuve mince (1 fil, 2 lignes), effort S, score 3 (rang 20) ; la hauteur d'un voisin reste saisissable.
- CAP-D1-23 — Toit en sheds (dents de scie) — preuve mince (2 fils 2008-2009, inférence « halls marocains » non vérifiée), effort M, score 1,5 (rang 23).

#### D2 — Pose, structure, plans
- CAP-D2-22 — Numéros de série posés rattachés au module et à la chaîne — une seule lane (avis d'applis), score 2 (rang 22) ; liste des modules posés et rattachement chantier non repris.

#### D3 — Électrique
- CAP-D3-17 — Micro-onduleurs ≠ injection zéro, place et sens de la pince CT — aucune tâche finale ; raison non écrite dans les lots (score 6, rang 10) ; à confirmer.
- CAP-D3-23 — Réserver une entrée MPPT et des modules pour une extension — preuve mince (2 fils, 1 lane), score 2 (rang 27).
- CAP-D3-17 (seconde moitié : pince de mesure au schéma et à la nomenclature) — non écrite : `core/electrique/schema.py` ne dessine le limiteur que sur le chemin C&I moyenne tension ; un champ `micro_seul` n'a pas de fiche onduleur : reprendre après ACAL1187.

#### D4 — Simulation, résultats, rapport
- CAP-D4-25 — Rapport éditable : variables de texte et export DOCX — jumelle de CAP-D6-18, écartée d'office pour D4 ; variables non reprises, DOCX = dépendance neuve (voir ligne fondateur Word).
- CAP-D4-29 — Ombre de cadre, de pinces ou de différence de hauteur de châssis — une seule lane (3 fils), score 2 (rang 29), avertissement sans chiffre ; écartée d'office pour D4.

#### D5 — Consommation, stockage, pompage, réseau
- CAP-D5-19 — Énergie réactive (kVArh) et cos φ par mois — preuve de « notes de version » seule, aucun fil de forum ; attend la position écrite ONEE/SRM (CIQM4).
- CAP-D5-20 — Batterie hors de sa plage de température au site — preuve mince (1 fil), effort S, score 4,5 (rang 20).
- CAP-D5-21 — Gabarits de profils de consommation nommés, vides — score 4 (rang 21) ; aucune valeur livrée, profils société éditables existent déjà.
- CAP-D5-22 — Règles de batterie par saison (une stratégie par mois) — score 1 (rang 22), « à ne construire qu'à la demande » ; dépend de CAP-D5-01.

#### D6 — Parcours, simplicité, explications
- CAP-D6-11 — Dossier par distributeur (pièces exigées, version du formulaire) — D-ACAL-43 : dossier générique d'abord ; seule la date « vérifié le » reprise (ACAL822, ACAL824) ; liste des distributeurs à fournir.
- CAP-D6-15 — File de demandes « calepinage à faire » commerciale → technicien — preuve d'éditeur seule, score 4 (rang 15) ; moitié bouton fiche lead (PLAN_AUDIT_LEAD) non reprise.
- CAP-D6-18 — Documents éditables (Word) et textes à variables du modèle société — variables non reprises ; DOCX gated fondateur (nouvelle dépendance), voir ligne fondateur Word ; jumelle de CAP-D4-25.
- CAP-D6-19 — Pouce haut / bas sur le remplissage automatique, avec un motif — un seul éditeur (OpenSolar), score 2 (rang 17).

#### D7 — Constats du tour 1
- (aucune carte en réserve : CAP-D7-07 est portée par ACAL927, qui ne cite pas son id)

#### D8 — Moteur partagé
- CAP-D8-01 t2 — Propriété `core/conception` dans `ownership.yml` — coupé : `core/conception` non créé, la lecture des pans posés va dans `core/calepinage` (critique d, B3).
- CAP-D8-01 t3 — Contrat import-linter `conception-est-un-noyau-pur` — coupé : même raison, pas de paquet `core/conception`.
- CAP-D8-01 t4 — Paquet `core/conception` et test de pureté — coupé : même raison, `pans_poses` vit dans `core/calepinage` (ACAL1002).
- CAP-D8-01 t5 — Section « Le moteur de conception » dans `docs/moteur-calepinage.md` — décrit adaptateur et interrupteurs non retenus ; aucune tâche finale ne la porte.
- CAP-D8-02 t3 — Garde économie année 1 : carte de l'atelier = économie du devis — ACAL982 ne garde que kWc, production et verdict ; aucune garde sur l'économie.
- CAP-D8-02 t5 — Garde du site public (`estimatorBrainV2`) bornée par le moteur — dépend de D8-07 t2 (coupé, B3) et de D8-12 (reporté, web stop-and-ask).
- CAP-D8-03 t2 — Règle de nuit `CAL_ECONOMIE_ATELIER_VS_DEVIS` — non reprise : seul `CAL_PRODUCTION_DEVIS_VS_CALEPINAGE` devient tâche (ACAL1011) ; pas de garde économie.
- CAP-D8-03 t3 — Règle de nuit `CAL_VERDICT_PUBLIABLE_SANS_MATERIEL` — non reprise ; « publiable à vide » partiellement voulu (D-ACAL-9), état « à compléter » servi par ACAL934.
- CAP-D8-04 t1 — Façade `concevoir()` / `chiffrer()` du calepinage — remplacée par la porte unique `chiffrer_conception` dans `ventes` (ACAL991, ACAL992) : l'argent ne sort pas de `ventes` (B3).
- CAP-D8-04 t3 — `design-context` du devis délègue à celui du calepinage lié — non reprise ; aucune tâche finale ne la porte.
- CAP-D8-04 t4 — `ecrire_etude_params` reçoit la `Conception` — non reprise ; la production de la pose réelle passe par le productible servi (ACAL996-ACAL999).
- CAP-D8-04 t5 — `contenance.py` (assistant) passe par la façade — sans objet : la façade n'est pas créée.
- CAP-D8-06 t1 — `kwc(pans, modules)` pur dans `core/conception` — coupé : paquet non créé ; la parité du kWc est tenue par ACAL982 et ACAL916.
- CAP-D8-07 t1 — Constat d'extraction de la production horaire — sans objet : la production reste dans `ventes` (B3).
- CAP-D8-07 t2 — Déplacement PUR de la production horaire vers `core` — coupé B3 : ≈ 10 000 lignes, I/O PVGIS, contrat import-linter, 8 `mock.patch` qui cesseraient d'agir.
- CAP-D8-07 (interrupteur) — `MOTEUR_CONCEPTION_PRODUCTION` — coupé B4 : un devis envoyé changerait de chiffre à la bascule ; un seul verrou, le niveau de règles.
- CAP-D8-08 t1 — Déplacement PUR de l'économie vers `core/conception/economie.py` — coupé B3 : l'argent reste dans `ventes`, propriétaire moteur.
- CAP-D8-08 (interrupteur) — `MOTEUR_CONCEPTION_ECONOMIE` — coupé B4 : aucun interrupteur d'environnement sur un chiffre client.
- CAP-D8-09 t2 — `electrical_service.py` délègue à la façade — non reprise ; B3/B6 : casserait les devis sans calepinage lié, façade non créée.
- CAP-D8-09 t3 — Remplacer `solar_design.string_design` par `core.electrique` — coupé B6 : peut changer onduleur, quantités et prix des nouveaux devis ; hors lot (goldens à nommer).
- CAP-D8-10 t1 — Remplisseur serveur unique `remplir` — GATED fondateur Q5 (étape 6) : lève l'interdit `USE_MOTEUR_CALEPINAGE`, décision après comparaison (B8).
- CAP-D8-10 t2 — Dry-run `comparer_compte_moteur_calepinage` étendu à tous les calepinages — étape 6 GATED Q5 ; non repris (ACAL1000 est un autre dry-run, niveaux de règles).
- CAP-D8-10 t3 — « Remplir le toit » de l'atelier appelle `remplir`, derrière `MOTEUR_CONCEPTION_POSE` — GATED Q5 (B8) ; plus aucun nouvel interrupteur d'environnement.
- CAP-D8-10 t4 — Dessins Éco / Recommandé / Max par `remplir(cible=N)` — GATED Q5 (B8), même raison.
- CAP-D8-11 t3 — `concevoir_rapide_pour_lead` (remplissage serveur) — coupé B7 : retirerait le feu vert, l'agricole et le second devis automatique, et publierait du deviné ; « rapide » = marquage (ACAL1004-ACAL1006).
- CAP-D8-11 t4 — `build_devis_auto` délègue à `concevoir_rapide_pour_lead` — coupé B7 ; plafond deviné non voulu (Q3, F2 retiré) ; le bouton reste sur `build_devis_auto`.
- CAP-D8-11 t5 — Fiche lead : kWc, production, économie servis du calepinage rapide et bouton « Affiner dans l'atelier » — non reprise ; dépend du chiffrage rapide coupé (t3).
- CAP-D8-12 t1 — Mention « estimation » sur les estimateurs du site public — reporté : touche `apps/web`, déployé seul par Cloudflare ; question web stop-and-ask pour Reda.
- CAP-D8-12 t2 — Le webhook lead n'accepte que de la géométrie du site — reporté : touche le flux de données du formulaire (stop-and-ask, CLAUDE.md).
- CAP-D8-13 t1 — Retirer l'aperçu navigateur du générateur (`computeROI`, `productibleForCity`) — non reprise : « après interrupteur levé 7 nuits », interrupteurs coupés ; brancher plutôt que retirer (D-ACAL-17..20).
- CAP-D8-13 t2 — Retirer `fallbackPerKwc` en mode ERP — non reprise ; ACAL994 le garde et le marque « estimation » ; interrupteur coupé.
- CAP-D8-13 t3 — Retirer `orientation_du_pan`, `pans_du_document` et jumeaux de `geometrie.py` — coupé B6 : les branches d'avant un niveau de règles servent à vie les devis envoyés.
- CAP-D8-13 t4 — Retirer `calepinage_options._Trame` et la prolongation de rangées — non reprise ; dépend de CAP-D8-10 t4 (GATED) et d'un interrupteur coupé.
- CAP-D8-13 t5 — Retirer l'adaptateur `electrical_service.py` et `string_design` — coupé B6 : devis sans calepinage et prix des nouveaux devis.
- CAP-D8-13 t6 — Retirer le remplissage navigateur de l'atelier en mode ERP — non reprise ; dépend de CAP-D8-10 (GATED Q5), le remplissage navigateur reste.
- CAP-D8-13 t7 — Retirer les interrupteurs `MOTEUR_CONCEPTION_*` de `settings/base.py` — coupé B4 : ces interrupteurs ne sont plus créés.

#### Décisions fondateur du 21/11/2026
- Profils par distributeur marocain (pièces, limites, choix du gabarit par distributeur du lead) — D-ACAL-43 : un dossier générique d'abord ; ex-ACAL785, ACAL823, ACAL825, ACAL826, ACAL899.
- Export Word du rapport interne — preuve mince (deux fils de forum), dépendance gratuite : choix pris seul ; ex-ACAL900.


- Gabarit de schéma choisi par distributeur du lead (ex-ACAL679, ACAL680) — D-ACAL-43 : profils par distributeur plus tard.

Total : 56 cartes ou sous-parties en réserve.

## Constats de relecteurs retenus restés sans tâche

- aucun : chaque constat retenu du tour 1 est cité par une tâche de cette vague ou couvert par une tâche existante (champ `tache` de `registre/evenements/T1-consolidation.jsonl`) ; T1-T1-013 (poignées des coins à la hauteur du toit) a maintenant sa tâche, ACAL1185.

## Limites (dites telles quelles)

- Aucun test exécuté : chaque « test rouge d'abord » est attendu, non observé ; aucune tâche n'a été construite.
- Les extractions proposées pour les fichiers de plus de 2 000 lignes (fonction déplacée dans un fichier voisin) sont des lectures du code, à confirmer à la construction.
- Le nombre de calepinages touchés par ACAL921 (orientation des surfaces de pose) est inconnu tant qu'ACAL1194 n'a pas tourné sur une copie des données.
- Le document client agricole : D-ACAL-46 (21/11 au soir) veut que le volume d'eau journalier imprimé suive la pose réelle des panneaux, derrière la liste des écarts ; ses tâches sont ACAL1197 à ACAL1203 (lot pompage, écrit le 21/11 au soir, sans vérificateur séparé). Le bilan du réservoir jour par jour reste interne (D-ACAL-41).
- Les chiffres de l'étude (valeurs publiées, forums) sont à relire à leur source par le constructeur avant d'entrer dans le produit (WebFetch rend des résumés).
- Rien n'a été vu sur une vraie image satellite (fond neutre de la pile de revue).
- Les résultats de simulation et les PDF lourds n'ont pas été observés sur la pile : pas de worker Celery au tour 1 (ACAL1031 l'exige).
- Clauses lues sur `684d77f02` ; une prémisse peut bouger avant la construction : chaque tâche se re-vérifie avant d'être construite.
