# Tour 3 du test utilisateur — consolidation (en cours, 25/11/2026)

Instrument : pile privée `l5t`, code `main` après la PR #1554 + lanes de correctifs du tour 2 (`agri-2`, `devis-2`,
`calepinage-2`), SANS les étapes 5 et 6 du moteur. Deux relecteurs à la fois. Rapports : `X1.md`, `X4.md`, … ; constats :
`registre/constats/T4-X*.jsonl` ; rejeux : `rejeu-X*.json` ; couverture : `couverture-X*.json`.

## X1 — agricole de bout en bout, fenêtre des PDF, onglet devis de la fiche (terminé)

**Ce qui marche.** Le scénario i (pompe neuve sur forage, prix d'essai) va du lead au devis automatique, à l'éditeur, aux
trois tailles, à tous les formats de PDF, à l'envoi, à l'acceptation, au chantier, au bon de commande et à la révision V2,
avec UN chiffre par valeur partout (m³/jour, débit à la HMT, kWc, panneaux, prix). Le scénario j (pompe gardée) arrive
jusqu'au chantier, « débit déclaré par vous » partout. Rejeux : 7 corrigés sur 10.

**Tri des 16 constats.**

| Constat | Gravité | Tri de l'orchestrateur | Suite |
|---|---|---|---|
| T4-X1-001 | S1 | VRAI, lu par un client : le prix par kWc de l'option 1 est divisé par la taille de l'en-tête (3,55) et non par la sienne (2,75) ; l'en-tête de la page 2 annonce le module et la taille d'une seule option pour les deux. Se produit quand les deux options n'ont ni la même taille ni le même module (taille imposée + module remplacé « pour compatibilité électrique »). | correctif du rendu, nouveaux rendus seulement (niveau de règles) — à dire au fondateur |
| T4-X1-002 | S1 | VRAI, lu par un client : la page « Confiance, garanties » du PDF avec étude imprime « Onduleur 10 ans » et « onduleurs Huawei » en dur, alors que l'option recommandée porte un hybride Deye garanti 5 ans (page 2 du même PDF). | même chemin que 001 |
| T4-X1-003 | S2 | REJOUÉ par l'orchestrateur : sur un autre devis la demande « Devis final » aboutit en 33 s par la même route. Le défaut est à l'écran : quand un appel de suivi dépasse 20 s, l'écran n'affiche plus rien, pour toujours (ni fichier, ni message, ni « Réessayer »). | lane de correctifs (écran) |
| T4-X1-004 | S3 | VRAI (mots) : 3 kWc tapés deviennent 3,55 puis 2,75 sans que l'écran dise le passage de l'un à l'autre. | lane de correctifs |
| T4-X1-005 | S3 | CONNU : 10 814 / 10 813 sur le même PDF — l'arrondi attend le niveau de règles 15. | décision 2 du rapport |
| T4-X1-006 | S3 | CONNU : « 3 pages » annoncées, 4 produites. | décision 12 du rapport |
| T4-X1-007 | S3 | VRAI : « Inclure la planche cotée » sans calepinage ne fait rien et ne dit rien. | lane de correctifs |
| T4-X1-008 | S3 | VRAI, lu par un client : après un enregistrement dans l'éditeur, le PDF agricole imprime « déclaré par vous » pour un débit « donné par le foreur » et l'ajoute à « À confirmer par la visite ». | lane de correctifs (l'enregistrement perd l'origine) |
| T4-X1-009 | S3 | VRAI : pompe monophasée sans courbe proposée sous la puissance minimale dite par le même écran. | lane de correctifs ; lié à la décision 20 |
| T4-X1-010 | S3 | À VÉRIFIER : variante Darija = texte français (texte approuvé absent, ou réglage de la copie ?). | lecture du code |
| T4-X1-011 | S3 | INSTRUMENT pour l'erreur 500 (connexion à la base perdue sous charge, journal du serveur) ; VRAI pour le message, qui accuse la fiche du lead d'une panne du serveur. | lane de correctifs (message) |
| T4-X1-012 | S3 | VRAI : validité « — » dans la liste, « jusqu'au 25/12/2026 » sur le PDF du même brouillon. | lane de correctifs |
| T4-X1-013 | S3 | Fondateur : « prix sur devis » imprimé pour une option dont le prix est au catalogue. | décision 16 du rapport |
| T4-X1-014 | S4 | VRAI : deux alertes gardent une formule. | lane de correctifs |
| T4-X1-015 | S4 | CONNU : note automatique « — par ? » (écart 7 de l'acceptation ACAL2027). | lane de correctifs |
| T4-X1-016 | S4 | VRAI : fil d'Ariane « Nouveau devis solaire » sur une révision ; validité de la V2 vide. | lane de correctifs |

Rejeux non confirmés : T4-V2-003 — la taille supérieure garde moins de panneaux que la recommandée (22 contre 23) : la
lane l'avait CONTESTÉ (une pompe plus puissante monte le même volume avec moins d'énergie) ; reste à le DIRE sur la carte.
T4-V2-010 — côté client, décision 18 du rapport. T4-U3-013 — l'atelier n'a plus d'onglet Pompage (« autre »).

Couverture X1 : 21 lignes jouées sur 30 ; PDF-023 à PDF-028 n'ont aucun contrôle à l'écran (réglages passés par
l'adresse seulement) ; PDF-032 bloquée (la pile n'envoie aucun e-mail) ; PDF-006 et PDF-031 non atteintes.

## X4 — correctifs devis du tour 2, générateur (terminé)

**Ce qui marche.** Les 14 correctifs du tour 2 rejoués sont confirmés (0 « pas corrigé »). La chaîne complète passe sur
un lead d'essai : envoyé → accepté → chantier → acompte émis → ticket après-vente. Les nombres tapés dans le générateur
(3.7, 0, une longue décimale, 12,5) restent tels quels partout. Brouillon retouché à l'ÉCRAN puis facture changée : il est
gardé ; brouillon intact : il suit (5 → 7 et 8 → 11 panneaux) — même résultat que l'acceptation ACAL2027.

**Tri des 22 constats** (aucun S1 ; 9 S2).

| Constat | Gravité | Tri de l'orchestrateur | Suite |
|---|---|---|---|
| T4-X4-005 | S2 | VRAI et MESURÉ au calme : la liste des devis sert de 52 à 82 Ko PAR devis (10 devis = 523 Ko, 25 = 2,0 Mo) et l'écran les charge TOUS par pages de 200 (590 devis pour ce rôle ≈ 48 Mo) ; une page de 200 a fait tuer un processus du serveur de la pile (mémoire). Une seule page lente vide l'écran entier. | lane de correctifs, PRIORITÉ : liste légère côté serveur |
| T4-X4-001 | S2 | VRAI : panneaux retouchés de 5 à 7, « Structures acier » et « Socles » restent pour 5 : ≈ 1 300 MAD de pose en moins que le devis automatique de même taille, sans avertissement. | lane de correctifs |
| T4-X4-011, 016, 019, 020 | S2 / S3 | UNE cause probable : des totaux ADDITIONNENT les lignes des deux options (total « villas » 82 800 pour 65 800 ; retour C&I 21 ans à l'écran contre 5,7 ans au bandeau et au PDF ; registre des surcharges 18 panneaux = 7 + 11 ; marge indicative négative). | lane de correctifs : une fonction « lignes de l'option », lue partout |
| T4-X4-004 | S2 | VRAI : carte « Tailles », onglet Sans batterie : « Recommandé » montre la composition AVEC batterie à 36 900 MAD (moins que l'« Éco » à 5 panneaux). | lane de correctifs |
| T4-X4-018 | S2 | VRAI : la simulation dit « option batterie non livrable » pour chaque taille alors que le devis la vend ; retours écrits « 5.74 ans ». | lane de correctifs |
| T4-X4-021 | S2 | VRAI : devis ENVOYÉ ouvert dans deux onglets, le second enregistrement écrase le premier sans bandeau. | lane de correctifs |
| T4-X4-008 | S2 | CONNU (étape 7) : le brouillon retouché gardé imprime l'ancienne facture et aucun écran ne dit qu'il est en retard sur la fiche ni ne propose « Mettre à jour » (AGEN12). | étape 7 du moteur |
| T4-X4-003 | S3 | INSTRUMENT : erreur 500 = connexion à la base perdue sous charge. | — |
| T4-X4-002 | S3 | CONNU : note « — par ? ». | lane de correctifs |
| T4-X4-006, 009, 010, 012, 013, 014, 015, 017, 022 | S3 | VRAIS, petits : compteur « 1 bon de commande » sur des brouillons ; « Numéro invalide » quand il n'y en a aucun ; carte « À échoir » ; fenêtre coupée ; validité déjà passée acceptée ; « Devis enregistré » sans dire l'option ; « Renommer sur ce devis seulement » n'enregistre pas ; « Jui / Jui » pour juin et juillet ; « Réinitialiser » n'efface rien. | lane de correctifs |
| T4-X4-007 | S3 | CONNU : 4 pages pour 3 annoncées. | décision 12 du rapport |

Couverture X4 : 48 lignes jouées sur 57 ; 6 introuvables (MKT-003, TEC-006, SAV-005, SIM-004, RES-005, ADM-002, condition
notée) ; 1 bloquée par la liste des devis ; 2 non atteintes.

## X2 — outil de dessin, étapes Toit, Panneaux, Électrique (terminé)

**Ce qui marche.** Les 10 correctifs calepinage rejoués sont confirmés (0 « pas corrigé ») : toit tracé au niveau du
pays = site non localisé, « + Ajouter un panneau », vue client qui tourne sur elle-même, client créé par un Commercial
retrouvé, carte de la variante posée, « Enregistré à » identique après rechargement. 43 lignes jouées sur 53.

**Tri des 11 constats** (aucun S1 ; 4 S2).

| Constat | Gravité | Tri de l'orchestrateur | Suite |
|---|---|---|---|
| T4-X2-010 | S2 | À ISOLER D'ABORD : sur un calepinage à plusieurs zones (toit + champ au sol + ombrière + parcelle), le toit perd ses 24 panneaux après enregistrement et rechargement, et trois compteurs donnent trois totaux (46 / 22 / 6). Non reproduit avec une seule zone au sol. Perte silencieuse d'une saisie. | lane dédiée : reproduire, puis corriger |
| T4-X2-001 | S2 | VRAI : la carte « Couvrir la facture » écrit « 5 panneaux 2,75 kWc » (le besoin d'après la facture) à côté de « 5 panneaux · 3,55 kWc » (la pose). | lane atelier |
| T4-X2-007 | S2 | VRAI : « Montrer au client » dit « 35 % de votre consommation », l'atelier « ≈ 60 % », pour la même pose et la même production. | lane atelier (deux bases de consommation) |
| T4-X2-009 | S2 | VRAI : avec un champ au sol, la bande de l'étape Panneaux ne compte que le toit (5 · 3,55 kWc) sans le dire ; la barre du projet et le tableau du site disent 23 · 16,33. | lane atelier |
| T4-X2-003 | S3 | DÉJÀ CORRIGÉ dans le lot 3 (lane de relecture : le bandeau imprime le lieu que le serveur utilisera). | à rejouer |
| T4-X2-005 | S3 | VRAI : le pas entre rangées est calé sur la latitude de l'épingle brute (centre du pays) quand la simulation se fait sur la ville de référence. Même classe que les températures électriques, corrigées dans le lot 3 ; ce lecteur-ci reste. | lane atelier |
| T4-X2-002 | S3 | VRAI : la même pose passe de 5 310 à 5 623 kWh/an après rechargement (ombre de la cheminée comptée avant, plus après, avec une carte « ombre pas encore comptée »). | lane atelier |
| T4-X2-006 | S3 | VRAI : en Expert, « estimation de l'atelier » 21 797 et « simulation » 27 197 kWh/an sur le même écran, une fois la simulation faite. | étape 7 du moteur (ACAL2022) |
| T4-X2-004 | S3 | VRAI : l'onduleur « proposé pour 5 panneaux » + « Raccorder automatiquement » donnent d'emblée un dossier bloquant. | lane atelier |
| T4-X2-008 | S3 | VRAI : en Expert, un toit en pente montre les réglages du toit plat ; le bloc de pente reste caché. | lane atelier |
| T4-X2-011 | S4 | VRAI : deux boutons de la carte en anglais. | lane atelier |

## Lanes de correctifs du tour 3 (à lancer dès qu'une place se libère ; trois agents de fond au plus sur ce poste)

1. **Liste des devis légère** (T4-X4-005) — serveur `ventes` + écran de la liste.
2. **Éditeur du devis** — « lignes de l'option » lues partout (T4-X4-011, 016, 019, 020), kit qui suit les panneaux
   retouchés (001), carte Tailles (004), simulation (018), deux onglets (021), petits (012 à 015, 017, 022 ; T4-X1-004, 016).
3. **Listes, envoi, PDF à l'écran** — attente d'un PDF qui se tait (T4-X1-003), validité (T4-X1-012), planche cotée sans
   calepinage (T4-X1-007), Darija (T4-X1-010), message du devis automatique (T4-X1-011), T4-X4-006, 009, 010.
4. **Pompage et rendu des PDF** — origine du débit perdue à l'enregistrement (T4-X1-008), pompe monophasée sous la
   puissance minimale (T4-X1-009), formules dans deux alertes (T4-X1-014) ; PDF client au niveau de règles 15 :
   prix par kWc de chaque option (T4-X1-001), garantie de l'onduleur lue sur la fiche du produit (T4-X1-002).
5. **Fiche du lead** — note automatique « par ? », responsable « Non assigné » (T4-V1-001), et les écarts 4, 5, 6, 8 de
   l'acceptation ACAL2027 (brouillon dupliqué sans pointeur, champ de l'heure de fin, phrases de « Mettre à jour »,
   deux libellés pour un brouillon jamais envoyé).
6. **Atelier du calepinage** — perte des panneaux d'un toit à plusieurs zones (T4-X2-010, à reproduire d'abord), carte
   « Couvrir la facture » (001), couverture de la vue client (007), compteurs avec un champ au sol (009), pas entre
   rangées au bon lieu (005), production avant / après rechargement (002), raccordement automatique bloquant (004),
   réglages de pente en Expert (008), boutons en anglais (011).

## État des corrections du tour 3 (25/11, 05 h 55 UTC)

- **Corrigé, à rejouer par un relecteur neuf** : T4-X4-005 (liste des devis : 25 devis = 78 Ko au lieu de 1,8 Mo, une
  page à la fois, total et cartes par statut servis à part — lane `t3-liste`) ; T4-X4-016 et T4-X4-008 (l'écran devis
  lit la conception servie, bandeau « La conception a changé » et « Mettre à jour », avis sur la carte du devis de la
  fiche — lane `moteur-e7b`) ; T4-X2-003 (bandeau du site : lieu servi par le serveur — lot 3, fusionné).
- **En cours** : T4-V1-001, note « par ? », libellé du brouillon jamais envoyé (lane `moteur-e7a`) ; T4-X2-001, 006,
  007, 009 (lane `moteur-e7c`).
- **Pas encore de lane** : lanes 2 (reste de l'éditeur : 001, 004, 011, 018, 019, 020, 021, petits), 3, 4, 5 (restes),
  6 (atelier : 010 d'abord, 002, 004, 005, 008, 011).

## X5 — atelier après le toit, Résultats, Documents, « Générer le devis » (terminé, 25/11 vers 07 h UTC)

Chromium 1440 × 900, thème sombre, pile `22e6aa81ae` (lot 3). 48 lignes notées sur 48 (41 jouées, 3 bloquées, 2
introuvables, 2 non atteintes). 17 constats : 1 S1, 8 S2, 6 S3, 2 S4 (`registre/constats/T4-X5.jsonl`, rapport `X5.md`).
Valeurs à plusieurs nombres relevées pour un même calepinage : kWc 5,68 (pose) / 4,40 puis 2,13 (cible) / 2,2 et 4,4
(devis) ; production 9 228 (simulation de la pose) / 3 414 (conception) / 3 527 et 7 053 (devis) ; couverture 40 %
(Résultats) / ≈ 123 % (bande) / 74 % (devis) ; économies 6 310 (atelier) / 5 490 et 8 884 MAD par an (devis).

Tri (cause à prouver par la lane avant de corriger) :
- **S1 T4-X5-009** réimporter la conception que l'atelier vient d'exporter vide le toit → lane F6b (en vol), en premier.
- **S2 001** deux productions à l'étape Résultats sans dire leurs tailles → F6b. **S3 005** pourcentage calculé sur une
  ancienne estimation → lane `moteur-e7e` (même composant). **S3 006, 008, 013, 014, 016, S4 007** → F6b. **S4 017**
  commandes de la carte en plein écran → F6a (outil de toit).
- **S2 002** consommation du calepinage plate malgré « été différent », **S2 012** « Simulé » dix fois trop petit,
  **S2 004** écart avec le devis envoyé du lead jamais nommé quand le devis n'est pas lié au calepinage, **S3 015**
  synthèse qui marie la puissance d'une pose et la production d'un autre devis → lane `moteur-e8` (mêmes fonctions).
- **S2 010** le devis né de l'atelier chiffre un autre onduleur que celui désigné, « Resynchroniser » en impasse ;
  **S2 011** « Réviser le devis » reprend l'ancienne pose (6 panneaux) au lieu de la conception (7) ; **S2 003** la
  cible « Couvrir la facture » change (8 panneaux → 3) sans le dire après une désignation → lane à écrire
  (« devis né de l'atelier »), APRÈS e6d et e8 (mêmes fichiers) ; liée à la décision 28 du rapport (effets d'une
  désignation à la main) : dire à l'écran ce que le moteur a fait d'une désignation, ne jamais laisser d'impasse ;
  le choix de fond reste au fondateur.

État des lanes du tour 3 au 25/11, 07 h 05 UTC : F6b en vol ; F6a, F3, F4, F2a, F2b prêtes (consignes dans le bloc-notes
de session, `tour3/msg-lane-*.md`) ; relecteurs X3, X6, X7, X8 à lancer sur la pile mise à jour au lot 4 corrigé.

## État des corrections du tour 3 (25/11, 08 h 05 UTC) — remplace l'état de 05 h 55

**Corrigé dans `dev-lot4`, à REJOUER par un relecteur neuf sur la pile mise à jour** (chaque lane : test rouge d'abord,
cause lue ; rien n'a encore été regardé à l'écran) :
- Liste des devis : T4-X4-005 (lane `t3-liste`).
- Écran devis, étape 7 : T4-X4-016, T4-X4-008 (lane `moteur-e7b`) — puis la relecture du lot 4 a trouvé B2, M1 à M4
  sur ce même écran : lane `moteur-e7d` EN VOL.
- Fiche du lead : T4-V1-001, note « — automatique », libellé du brouillon jamais envoyé (lane `moteur-e7a`) ; carte
  Conception : recalcul non terminé dit, option retenue marquée (lane `moteur-e7e`).
- Atelier, valeurs servies : T4-X2-001, 006, 007, 009 (lane `moteur-e7c`) ; vue client et bande Panneaux quand la pose
  n'a pas la taille de la conception (B1, M5 de la relecture ; lane `moteur-e7e`).
- Atelier, écrans (lane F6b `t3-atelier-ecrans`) : **T4-X5-009 (S1)** — cause : l'import enregistrait l'enveloppe du
  fichier exporté comme conception (`views/io_layout.py`) ; un import sans toit par-dessus un toit demande maintenant
  confirmation ; T4-X5-001, 014, 008, 013, 016, 006, 007.
- Atelier, outil de toit (lane F6a `t3-atelier`) : **T4-X2-010 (S2)** — cause : au rechargement, les zones non actives
  perdaient leur rendu (`result` et `renderPlan` nuls) : compteurs à 0 et toit vide à l'écran alors que le document
  gardait ses panneaux ; l'ombrière laissait une zone fantôme ; T4-X2-004 (la ligne de l'onduleur lit les mêmes
  contrôles que le verdict), 005 (un seul lieu : `site_de_repli_point` servi), 008, 011, T4-X5-017.
  T4-X2-002 CONTESTÉ par la lane (l'atelier ERP ne montre plus l'estimation du navigateur) : à vérifier à l'écran.
- Pompage et PDF (lane F4 `t3-pompage-pdf`) : T4-X1-008 (origine du débit gardée à l'enregistrement), 009 (une taille
  sous la puissance minimale le dit), 014 (alertes sans formule) ; T4-X1-001 et 002 (PDF client) corrigés DERRIÈRE le
  niveau de règles 15, dormant — niveau 14 inchangé (références figées vertes sans retouche).
- T4-X5-005 : non reproduit dans le code du lot 4 (garde ajoutée) ; T4-X2-003 : lot 3.

**En vol** : `moteur-e7d` (écran devis), `moteur-e8` (T4-X5-002, 012, 004, 015 + étape 8), `moteur-e6e` (T4-X5-003,
010, 011), F3 `t3-listes-envoi` (T4-X1-003, 007, 010, 011, 012, T4-X4-006, 009, 010 + M6 de la relecture).
**Pas encore lancées** (même écran que `moteur-e7d`, après son retour) : F2a (T4-X4-001, 004, 011, 018, 019, 020, 021,
T4-X1-004), F2b (T4-X4-012, 013, 014, 015, 017, 022, T4-X1-016).
**Restent sans lane** : aucun constat S1 ou S2 du tour 3.
