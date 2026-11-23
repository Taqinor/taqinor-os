# Rapport F2-POSE-b — contre-vérification (tour 2, 23/11/2026)

Compte `rev_b5`, bureau 1440 × 900, thème clair, instrument http://127.0.0.1:5241. Captures : dossier scratchpad `T2/F2-POSE-b/cap/`.

## Comptes (17 corrections jouées sur 17)

ok 7 · partiel 9 · non-fait 1 · faux 0 · régression 0 · déjà-présent 0 · non essayé : une partie de ACAL593 (recentrage) et de ACAL568 (voir plus bas).

- ok : ACAL548, ACAL549, ACAL561, ACAL566, ACAL569, ACAL593, ACAL939.
- non-fait : ACAL547 (ni carte « Couvre le besoin » ni phrase « Aucune pose ne couvre le besoin » : la cible du balayage vaut 0).
- partiel :
  - ACAL546 — tableau monté, tri et clic OK, pas de MAD ; mais « % du besoin » = 0 % sur les 236 lignes, puces d'objectif en texte collé, kWh/an et % hors cadre.
  - ACAL551 — silhouette rouge vue (obstacle, hors toit) ; l'ambre (marge réglable) non obtenu.
  - ACAL552 — deux lignes chiffrées cliquables ; le chiffre annoncé (Portrait : 4) n'est pas celui obtenu (6) et le marquage reste sur Paysage.
  - ACAL553 — copier/coller OK dans le pan actif, refus nommé OK ; collage réussi dans un AUTRE pan non prouvé ; note « Collage refusé » affichée après un collage réussi.
  - ACAL554 — report vers 2 pans OK (module, re-pavage, confirmation en deux temps) ; « annuler » ne rend pas l'état d'avant.
  - ACAL562 — retraits posés et marqués « société » ; la pose ne s'en écarte pas ; ligne d'état « arête de type inconnu » non vue ; plantage à la réouverture (constat 006).
  - ACAL565 — PDF A3 aux zones Centre/Rive (lest 20 kg inscrit), sans MAD ; pas de bouton « Aperçu » ; zone Coin jamais obtenue.
  - ACAL568 — alerte porte-à-faux OK ; alerte de zone de serrage non obtenue (module lu depuis le devis, sans devis « Module — aucun »).
  - ACAL1296 — alerte « N panneaux à l'ombre » + « Retirer ces N panneaux » + « Garder » proche de la maquette ; obstacle non nommé ; absente à l'ouverture d'un dossier enregistré.

Cases de matrice (classes) : non jouées (hors mission — ma mission est la contre-vérification de la liste).

## Constats neufs (registre `constats/T2-F2-POSE-b.jsonl`)

- 001 S3 — Comparer les poses : % du besoin à 0 %, puces collées, colonnes hors cadre (K7).
- 002 S3 — bloc TOTAL — TOUTES LES ZONES : « kWh/an » et « MAD/an » se chevauchent (K7).
- 003 S3 — note du besoin « 6 posés / 6 cible » périmée alors que 3 panneaux sont dessinés (K10).
- 004 S4 — Retraits (m) : libellés qui chevauchent les champs (K7).
- 005 S2 — pan 3 × 1,5 m : la carte « Recommandé » annonce 6 panneaux · 4,26 kWc alors que 1 seul tient (K10).
- 006 S2 — réouverture d'un calepinage enregistré dont le pan étroit a reçu des retraits de la table société : toit rouvert en 4 points non fermés, plus de panneaux, erreur console `getPoint at closePath` (reproduit sur 2 calepinages ; 10 × 7 et même pan sans table : sans défaut) (K5).
- 007 S3 — annulation du report « Appliquer ces réglages à… » sans effet.
- 008 S3 — message « Collage refusé : il chevaucherait… » affiché après un collage réussi (K10).
- 009 S3 — « Personnaliser la disposition » disparaît dès qu'un seuil d'accès solaire écarte des emplacements.
- 010 S3 — onglet Fixation : « zone de serrage non saisie sur sa fiche » alors que la fiche la porte (le module du pan n'est pas lu sans devis).
- 011 S3 — alerte d'ombrage du guidé absente à l'ouverture du dossier, sans nom d'obstacle (K13).

## À vérifier (vu une fois, non rejoué : pas au registre)

- Calepinage B (cheminée de 3 m) : avant enregistrement la tuile du haut dit « 1 848 kWh/an · ≈ 21 % » ; après réouverture la même pose dit « 6 813 kWh/an » avec toujours « ≈ 21 % » (A, sans obstacle : 6 543 kWh/an, 74 %).
- Étiquette « 1,1 × 1,1 m » de l'obstacle très agrandie dans la vue guidée de B après saisie du seuil.
- Zone Coin du plan de lestage : le module du coin haut-gauche est rangé en Rive (définition de CALX361 à relire).
- Une erreur 401 `crm/assignable-users` et un décrochage de session ont eu lieu en cours de mission (re-connexion faite).

## Ce qui est bien

Seuil d'accès solaire (ACAL548) : message de refus clair, phrase « valeur de ce dossier / réglage de votre société », relecture après enregistrement. Phrase du pan vide (ACAL549) chiffrée et relue. Table de retraits société enregistrée et relue. Choix du système de fixation d'après le toit du lead, sans geste, avec la mention. Repères de chantier (ACAL593) posés, listés, dessinés avec leur cercle et relus. Constantes physiques de lestage avec leur référence (ACAL939). Refus de collage et de déplacement toujours nommés, jamais silencieux.

## Non essayé, et pourquoi

- ACAL593 : « recentrer sur le lead » (géocodage et fond de carte indisponibles sur la pile).
- ACAL568 : zone de serrage avec un devis lié (un devis n'a pas été généré : la carte Documents le demande, trop long).
- ACAL566 : second système « bac acier » déclarant seul (un seul déclarant créé).
- ACAL551 : cas ambre.

## Réglages remis en l'état

Table des retraits d'arête (`degagements`) remise à `{}` ; réglages de lestage remis à `{}` ; fiche du module Jinko 710 W (serrage 345-415 saisi pour l'essai) remise à vide ; système « F2-POSE-b Tuiles » (id 30, créé pour l'essai) laissé existant mais DÉSACTIVÉ. Mes calepinages et leads sont préfixés « F2-POSE-b » (A à J).

## Trois propositions fortes

1. Tableau « Comparer les poses » à la PVsyst (comparaison de variantes) : colonnes figées lisibles dans le cadre de 320 px, « % du besoin » toujours vrai ou « — », puces d'objectif en vraies puces.
2. Alerte d'ombrage permanente façon OpenSolar : « N panneaux à l'ombre de la cheminée » dès l'ouverture, avec le nom de l'obstacle et un bouton « Retirer » annulable en un geste.
3. Annulation unique pour toute opération en lot (report de réglages, collage) comme dans Figma/Illustrator : un Ctrl+Z défait toute l'opération et le dit.
