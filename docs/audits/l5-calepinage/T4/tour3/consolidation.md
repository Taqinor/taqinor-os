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

## X4 — correctifs devis du tour 2, générateur (en cours)

À consolider à son retour. Déjà noté : l'erreur 500 du devis automatique (T4-X4-003) a la même cause d'instrument que
T4-X1-011.
