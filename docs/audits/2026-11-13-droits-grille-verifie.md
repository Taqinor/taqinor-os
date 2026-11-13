# Vérifie ADRG — contre-visite de mi-parcours du parcours PF4 « droits de la grille », 13/11/2026

Commande `loop audit` (13/11). L'audit de parcours PF4 (10/11, dossier `2026-11-10-parcours-PF4.md`) avait déposé les tâches
ADRG. Première contre-visite du groupe, due à mi-parcours (24 tâches cochées sur 37 constructibles). Rien n'a été construit ni
déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `bbe833192`. Branche de claim : `verifie-pf-1311`.
- **Registre.** PF4 `droits-grille`, groupe ADRG, 24 tâches cochées sur 37 constructibles (64 %).
- **Échantillon.** Sur précision du fondateur (13/11), les **24 tâches cochées** sont relues, pas seulement le tirage : ADRG1,
  3, 6, 7, 8, 9, 10, 14, 33, 42, 44, 45, 65, 67, 68, 72, 74, 78, 79, 81, 83, 98, 100, 103.
- **Méthode.** Lecture des commits, du code sur `origin/main` et des tests nommés ; sondes du dossier rejouées sur l'hôte.
  Aucune pile, aucun test Django lancé, aucune production consultée.

## 1. Vérificateurs (3 lots, opus, effort élevé, frais)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **20** | ADRG1, 6, 7, 8, 9, 14, 33, 42, 65, 67, 68, 72, 74, 78, 79, 81, 83, 98, 100, 103 |
| partiel (S3) | **4** | ADRG3, 10, 44, 45 |
| non-fait / faux / régression / déjà-présent | **0** | — |

Les quatre « partiel » ont tous atteint leur « fini quand » côté API. Il leur manque un jumeau : un écran qui suit encore
l'ancienne règle (ADRG3, 44, 45) ou une seconde route du même geste (ADRG10). Un cinquième écart, hors tâche, est apparu en
relisant ADRG9.

## 2. Tests nommés

Les 24 tests nommés existent. Ils sont comportementaux : appel HTTP réel, rôles pris au registre (`init_roles` ou les
constantes `*_PERMISSIONS`), état relu en base après un refus. Aucun espion de la garde testée. Un test a été assoupli après
coup : celui d'ADRG9 accepte `403` ou `404` sur `?format=pdf` (voir §4). La CI de `bbe833192` est verte.

## 3. Sondes et preuve en direct

- **Rejouées sans écart.** Sondes 002, 003, 007, 009, 016, 021 et 056 du dossier PF4 : `repro: false`. La 007 et la 013
  exigent `PYTHONIOENCODING=utf-8` sous Windows.
- **Sonde 013 (ADRG6).** Les cinq vues réglementaires sont fermées. La sonde dit encore « repro » à cause des vues de
  mise en service (ADRG16, en attente de D-ADRG-3) et de trois vues CRM qui relèvent d'autres tâches.
- **Sonde 022 (ADRG8, ADRG9).** Pour ADRG9, la garde est trouvée. Pour ADRG8, faux positif : la garde est dans le corps
  de la vue, et la sonde ne lit que `permission_classes`. La garde de corps, rejouée rôle par rôle, refuse bien le
  Commercial terrain et l'Admin RH.
- **Sonde 054 (ADRG98).** Elle plante sur le code corrigé, à cause de son bouchon de rôle. Rejouée avec ce bouchon
  retouché : `repro: false`, les dix modifications de périmètre sont refusées.
- **Sonde 019 (ADRG68, ADRG72).** Non rejouable : elle évalue la fabrique de gardes des rapports sans son dictionnaire
  global. La correspondance chemin → garde a été relue à la main : conforme.
- **Garde d'ADRG79.** `check_palier_seul.py` passe (646 routes en dette gelée) ; ses 5 tests passent.
- **Statiques.** ADRG10, 14, 42, 44, 45, 78, 81, 83 et 103 n'ont pas de fichier de sonde.
- **Preuve en direct.** Aucune rejouée. `check_acceptation.py` passe. La tâche d'acceptation ADRG105
  (`docs/plans/PLAN_AUDIT_DEPLOY.md`) reste ouverte pour l'orchestrateur d'une session avec pile.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ADRG-VER1-044 | ADRG44 | S3 | L'API ouvre la suppression stock à `stock_supprimer`, mais cinq boutons « Supprimer » de quatre écrans restent réservés à l'administrateur ; les contacts fournisseur l'offrent à `stock_modifier` (403). | STATIQUE (lecture) | ADRG106 |
| C-ADRG-VER1-045 | ADRG45 | S3 | Le rebut exige `stock_mouvement` côté serveur ; le bouton « Mettre au rebut » suit encore `stock_modifier` : le Technicien ne l'a pas. | STATIQUE (lecture) | ADRG107 |
| C-ADRG-VER1-003 | ADRG3 | S3 | Le formulaire d'une facture émise laisse modifier l'échéance sans `encaisser` ; le serveur refuse en 403, la ligne masque déjà le geste. | STATIQUE (lecture) | ADRG108 |
| C-ADRG-VER1-010 | ADRG10 | S3 | L'action de lot `generer-pdf` des factures lance le rendu sans lire `ventes_pdf`. Aucun rôle livré n'est touché, seul un rôle personnalisé l'est. | STATIQUE (lecture) | ADRG109 |
| C-ADRG-VER1-009 | ADRG9 | S3 | `?format=pdf` de la déclaration de raccordement : DRF répond 404 avant la vue, faute de renderer « pdf » (source DRF 3.15.2 relue). Le PDF n'est servi à personne depuis FG272. 0 wrapper front, 0 écran. | STATIQUE (lecture) | sans tâche : la route est déjà vouée au retrait par ADEV66 (GATED, `docs/plans/PLAN_AUDIT_TRANSVERSE.md`) |

Gravité du cinquième écart : S3. La fonction livrée est morte pour tous, mais aucun écran ne l'appelle : le grep de
`declaration-raccordement` hors `docs/` ne trouve que l'URL, la vue et ses tests.

## 5. Optionnel (non déposé)

- **Sondes à rafraîchir.** La 019 ne résout pas le dictionnaire global des gardes de rapports. Le bouchon de rôle de la 054
  ne porte pas `values_list`. La 022 donne un faux positif sur une garde de corps et ne résout pas une classe importée.
  Plusieurs sondes du dossier, dont la 016 et la 022, n'ont pas de bloc `__main__` : lancées seules, elles sortent 0 sans
  rien jouer. La 007 et la 013 exigent `PYTHONIOENCODING=utf-8`.
- **ADRG8.** La garde est dans le corps de la vue, pas dans `permission_classes`. L'octroi `ventes_voir` y est écrit en dur,
  en double de la table des octrois de lecture, et la portée de la fiche chantier n'est pas testée.
- **ADRG3.** L'action `relancer` écrit `prochaine_relance` sans `encaisser`. C'est le geste de relance, tracé : à trancher
  s'il entre dans la règle.
- **ADRG10.** Le PDF proforma du devis reste au palier seul ; aucun rôle livré n'est touché. À trancher par le propriétaire
  devis.
- **ADRG9.** Le commit dit « rouge d'abord (raisonné) » : le test n'a pas été joué rouge avant le correctif.
- **ADRG42.** Le refus par code passe avant le court-circuit de rejeu. Une opération déjà appliquée revient donc en
  `error`, pas en `replayed`. Deux imports sont faits dans le corps de la fonction, à chaque opération.
- **ADRG81.** La fixture partagée de la classe de tests passe le « directeur » au palier administrateur pour toute la
  classe.
- **ADRG79.** La dette gelée n'est figée que par convention : `--amorcer` peut la regrossir.
- **Couverture des tests.** ADRG33 ne prouve le cas positif du Directeur que sur une route sur trois. ADRG68 ne vérifie
  l'export PDF des rapports qu'en refus. ADRG14 : `OPTIONS` exige le droit d'écriture, sans effet pratique.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 24 tâches cochées : code, commits, tests nommés, jumeaux, sondes rejouables.
- **Non couvert.** Aucun test Django ni vitest lancé (la preuve des tests est la CI de `main`). Aucun rejeu navigateur. Les
  mutants annoncés ont été raisonnés, pas joués. Les 13 tâches constructibles non cochées n'ont pas été lues.
- **Statut.** Zéro écart S1-S2 sur les tâches cochées ; quatre tâches d'écart S3 déposées chez leur propriétaire. Le
  groupe n'est pas « construit » : la contre-visite de clôture reste due à 95 %.

## 7. Coût

- 3 vérificateurs (opus, effort élevé) et 1 rédacteur ; jetons non mesurés ici ; aucun appel Fable.

<!-- verifie | groupe: ADRG | pct: 64 | ecarts_s1_s2: 0 -->
