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
