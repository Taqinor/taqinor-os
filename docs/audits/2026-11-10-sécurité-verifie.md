# Vérifie ASEC — contre-visite des correctifs de l'unité X1 « sécurité », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 04/11 (`docs/audits/2026-11-04-sécurité-verifie.md`) avait trouvé 6 écarts
S1-S2 ; les 19 tâches d'écart ASEC66-84 ont été construites et cochées depuis, sans jamais être relues. Contre-visite des
correctifs (METHODE §C.4 point 6). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot3-1011`.
- **Registre.** X1 `sécurité`, groupe ASEC, 84 tâches cochées sur 84.
- **Échantillon.** 14 des 19 tâches d'écart du 04/11 : les 10 qui fermaient un écart S1-S2 (ASEC66 à 73, 77, 78) et 4 des 9
  autres (ASEC74, 75, 76, 79). Non relues : ASEC80, 81, 82, 83, 84.
- **Pile locale.** Celle de la machine sert un code antérieur aux correctifs visés : aucune sonde rejouée. Verdicts par
  lecture des commits et du code sur `origin/main`, calculs en mémoire sur le registre vivant des rôles, une garde rejouée.
  **Production lue en lecture seule** (un comptage de comptes par rôle).

## 1. Vérificateur et seconde lentille (opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **11** | ASEC66, 67, 68, 69, 70, 72, 73, 76, 77, 78, 79 |
| partiel | **3** | ASEC71, ASEC74, ASEC75 (la garde n'est posée que sur une partie des portes) |
| non-fait / faux / régression | **0** | — |

Écarts S1-S2 du 04/11 : **4 fermés sur 6**. Fermés : un gestionnaire de comptes ne peut plus gérer un compte aux droits plus
larges que les siens (ASEC66, vérifié en mémoire avec les rôles vivants) ; générer ou consolider une facture exige le droit
d'encaisser (ASEC67) ; une demande d'accès déjà décidée ne se modifie plus (ASEC69) ; le lien de partage public d'un document
fonctionne et son mot de passe se saisit (ASEC77, ASEC78). Deux restent ouverts par une porte voisine : voir §4.

Une seconde lentille indépendante, chargée de réfuter les deux écarts jugés les plus graves, a **confirmé** le premier et
l'a classé S1, et a ramené le second (droits créer / modifier un devis) à S3 : aucun rôle livré n'est touché. À la
rédaction, l'écart de l'export de stock a été relevé à S2 : il touche, lui, des rôles livrés.

## 2. Tests nommés

Tous présents et comportementaux, sur de vrais rôles du registre. Un commit « tests alignés » a été relu : il ajoute un code
à un rôle de test sans affaiblir une garde. La matrice de permissions des devis FIGE aujourd'hui la porte de l'avoir de
révision sans le droit d'encaisser : c'est l'assertion à réaligner. Aucun test Django lancé (CI d'abord).

## 3. Sondes

Les sondes de la contre-visite du 04/11 demandent Django : lues, non rejouées. Une sonde neuve du constat S1 est écrite au
dépôt (`docs/audits/sondes/ASEC/C-ASEC-VER5-068.py`, vrai rôle « Admin Ventes », témoin sur la porte sœur) mais **n'a pas pu
être jouée** : la pile locale sert un code du 04/11, antérieur à la porte visée. Elle est à rejouer par l'orchestrateur d'une
session dont la pile sert `main` (attendu avant correctif : reproduit ; après : non).

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ASEC-VER5-068 | ASEC68 | **S1** | la confirmation de l'avoir de révision d'un devis, ajoutée seize minutes après ASEC68, ÉMET un avoir numéroté sans exiger le droit d'encaisser, contre la décision D-ASEC-VER-1 ; les rôles « Admin Ventes » et « Responsable » y arrivent seuls (réviser, modifier la nouvelle version, l'accepter, confirmer) ; le montant est calculé par le système. **Production le 10/11 : aucun compte actif ne porte ces deux rôles** (5 comptes actifs) — non exploitable aujourd'hui | STATIQUE — deux lectures indépendantes concordantes ; sonde écrite, non rejouée (§3) | ASEC85 |
| C-ASEC-VER5-071 | ASEC71 | S3 | le droit « modifier un devis » n'est exigé que sur une route que l'écran n'utilise pas pour les lignes : décocher la case dans la grille d'un rôle ne retire pas la modification ; aucun rôle livré n'est touché | STATIQUE (lecture) | ASEC86 |
| C-ASEC-VER5-074 | ASEC74 | S3 | même chose pour « créer un devis » : la création réelle passe par deux routes qui n'exigent pas ce droit | STATIQUE (lecture) | ASEC87 |
| C-ASEC-VER5-070 | ASEC70 | S2 | l'export en tableur de l'agrégation des mouvements de stock n'exige pas le droit d'export : six rôles livrés qui voient le stock sans droit d'export (dont Commercial, Technicien et le rôle de consultation) le téléchargent aujourd'hui, contre la décision D-ASEC-VER4-1 ; un test existant fige ce comportement | STATIQUE (lecture) | ASEC88 |
| C-ASEC-VER5-075 | ASEC75 | S3 | quatre actions d'écriture d'un chantier (recette, recette de pompage, réserves, dossier de remise) n'exigent pas le droit de gérer les chantiers | STATIQUE (lecture) | ASEC89 |

Un écart S1 confirmé par la seconde lentille et un écart S2 ; la critique finale est celle de l'orchestrateur (modèle de
session), sans appel supplémentaire.

## 5. Optionnel (non déposé)

- Depuis ASEC66, le rôle « Admin RH » ne peut plus gérer aucun compte d'un rôle du registre (conforme au constat d'origine,
  à faire confirmer par le fondateur).
- Le rôle « Commercial » porte le droit d'encaisser mais reste refusé par le palier sur la porte de l'avoir (effet inverse).
- Le retour d'outillage d'une intervention n'exige pas le droit de gérer les interventions.
- Le « Commercial responsable » a perdu les écritures d'intervention et de chantier (c'est la grille ; non annoncé).
- Le fichier de référence des rôles est un plancher daté : pour un rôle, lire le registre vivant.
- Après ASEC85, l'écran proposera encore le bouton « Confirmer l'avoir » à un rôle qui recevra un refus (l'état de la
  vente ne lit pas le droit d'encaisser).
- Deux autres exports de stock (conformité des fournisseurs, négoce) ne lisent pas le droit d'export : non tranchés.

## 6. Couverture et sortie de cycle

- **Couvert.** 14 tâches d'écart sur 19 ; lecture du code, des commits et des tests ; calculs sur les rôles vivants.
- **Non couvert.** ASEC80 à ASEC84 ; les 65 autres tâches cochées ; aucune sonde ni test rejoué ; la chaîne complète de
  l'avoir n'a pas été jouée ; un seuil d'approbation de remise pourrait bloquer l'acceptation d'une version moins chère
  (non vérifié).
- **Statut.** Un écart S1 et un écart S2 ⇒ ASEC reste « construit » ; contre-visite due quand ASEC85 et ASEC88 seront
  cochées.

## 7. Coût

- 1 vérificateur + 1 seconde lentille + 1 rédacteur (opus, effort élevé) ≈ 0,9 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ASEC | pct: 100 | ecarts_s1_s2: 2 -->
