# Brief sous-agent — lot D2 (vague 2, campagne L5 calepinage, 21/11/2026)

Tu es un rédacteur de tâches v3 (lecture seule sur le dépôt `C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5` : tu n'édites AUCUN fichier du dépôt, ni docker, ni tests ; `git grep` / Read / Grep / python seulement).
Scratchpad : `C:\Users\kasri\AppData\Local\Temp\claude\3e013d81c7d3451c\34e718a0-d494-4e8f-b5dd-46bfdf94a28e\scratchpad` (noté `SP` ci-dessous).

## À lire D'ABORD, en entier, dans cet ordre
1. `SP\l5\brief-redacteur-vague2.md` (addendum vague 2 — il MODIFIE le brief du tour 0) ;
2. `SP\plan\brief-redacteur.md` (règle de forme : 14 clauses v3, ancres, propriété, validateur, décisions qui contraignent) ;
3. un exemple de ligne v3 réelle : `docs/plans/PLAN_AUDIT_CALEPINAGE.md`, lignes 712, 714 et 716 (ACAL400-402) — c'est LE gabarit de forme ; tes lignes sont plus courtes (cible ≤ 3 500 caractères par ligne, une seule ligne physique chacune) ;
4. ta source : `SP\l5\backlog\D2-pose-structure-plans.md` — UNIQUEMENT les fiches `CAP-D2-nn` de ton groupe (numéros de lignes du fichier donnés plus bas), plus ses §« Écarté », « Déjà présent » et « Contradictions » si utiles ;
5. pour les tâches « document faux » : `SP\l5\T1\F1.md`, `SP\l5\T1\rejeu.md` et `SP\l5\registre\constats\T1-F1.jsonl` (écrire avec `PYTHONIOENCODING=utf-8`).
Les maquettes (`docs/audits/l5-calepinage/maquettes/*.dc.html` : Main, Panneaux, Electrique, Resultats, ResultatsIncomplet, Telephone) font foi pour l'écran : une tâche qui crée ou déplace de l'interface cite la maquette qu'elle réalise (chemin sans `::`) et place l'élément dans le parcours guidé (étape Toit / Panneaux / Électrique / Résultats / Documents ; niveau essentiel ou expert). Lis la maquette concernée (grep ciblé).

## Ton travail
Pour CHAQUE tâche de ta table ci-dessous : (a) RE-VÉRIFIER la prémisse dans le code (le dépôt a bougé : ACAL382/383/386-391 sont cochées ; HEAD du worktree = origin/main 207c7a70e + docs) : le manque existe-t-il AUJOURD'HUI ? chaque symbole cité par la fiche existe-t-il ? (grep). Capacité déjà construite ⇒ PAS de tâche, tu le dis avec la preuve `fichier::symbole`. (b) `git grep -n "<mot>" -- docs/plans docs/PLAN2.md docs/ERROR_PLAN.md` : aucune tâche ouverte ne la couvre déjà (sinon : tu écris `@after` ou tu fusionnes en le disant). (c) contrôle de propriété de CHAQUE fichier : `python scripts/check_ownership.py --owner-of <chemin>` (depuis la racine du worktree). Puis ÉCRIS la ligne v3.

Règles qui s'ajoutent à celles des briefs :
- **L'identifiant de chaque tâche est FIGÉ par la table** (les `@after` entre groupes s'y réfèrent). Les ids « libres » de ta plage servent aux SCISSIONS (une tâche à deux comportements) ou à un manque prouvé de la même surface (2 au plus) ; dis-le.
- Constat : `C-ACAL-L5-<id>` ; lecture `STATIQUE (lecture du 21/11 sur 207c7a70e)` ; tampon `(gen manuel 207c7a7)` ; la clause Constat cite la fiche (`CAP-D2-nn`), les ids d'origine des lanes (B3 N20, B5-de K32…) et les constats de relecteurs s'il y en a (`T1-F1-0xx`). Priorité : P0 = chiffre faux visible du client ; P1 = présent sans écran, ou geste/pièce courante cassée ; P2 = capacité du premier tiers ; P3 = le reste (mets celle que donne ta table).
- Décisions de design (libellés, disposition, ordre, essentiel/expert) : TU les tranches d'après la fiche, les rapports `SP\l5\T1\*.md` et la maquette ; jamais « à valider par Reda ». GATED seulement pour : dépense/dépendance payante, ce que voit le client hors du devis, règle légale ou commerciale, donnée propre à sa société (pièces des distributeurs marocains), création de données d'exemple en production. Forme GATED : `- [ ] ACALnnn — **[GATED : raison nommant la décision de Reda en une phrase] titre**`.
- Zéro chiffre inventé : aucune valeur par défaut codée (retrait, lest, portée, zone de serrage, allée, accès solaire minimal…) ; toute valeur vient d'une SAISIE société sourcée (provenance obligatoire) ou du « profil de départ » sourcé (D-ACAL-31) ; vide par défaut = comportement d'aujourd'hui. Les constantes trouvées en dur sont des défauts à corriger.
- L'argent ne vit que dans `apps/ventes` : aucune colonne/cellule en MAD dans un document ou un tableau du calepinage ; aucun PDF client (`/proposal`) modifié ; aucun statut de devis.
- Un fichier ≥ 2 000 lignes ne grossit pas (`RP/layoutEditor.ts` 3 223 l. ; vérifie `wc -l` de tout fichier gros que tu touches) : fichier voisin + un point d'appel (`lignes nettes ≤ N`).
- Fichiers mono-écrivain (même `@lane` pour toutes les tâches qui les touchent) : `apps/web/src/scripts/roof-tool-pro11.ts`, `roofPro11/prefill.ts`, `frontend/src/pages/ventes/ToitureDesign.jsx` (lane `calepinage/atelier-erp`), `backend/django_core/apps/calepinage/services/layout.py`, `models.py` + migrations. Surfaces en ajout seulement : `atelier/onglets.js`, `frontend/src/api/calepinageApi.js`, `views/rattachements.py`, `services/parametres_cles.py`.
- Contrat d'abord (PACT10) : toute fonctionnalité à deux moitiés (backend + frontend) a son échantillon `backend/django_core/apps/calepinage/contract_samples/<x>.json`, posé par une tâche SEULE ; la moitié frontend porte `@after` sur la tâche backend qui produit la donnée (PACT11).
- Tout fichier de `Files:` doit être au propriétaire `calepinage`. Fichiers d'AUTRES propriétaires : `apps/installations/**` et `frontend/src/features/installations/**` → `chantiers` (plan `docs/plans/PLAN_AUDIT_CHANTIERS.md`) ; `apps/web/src/lib/estimatorBrainV2.ts` → `web` (plan `docs/WEB_PLAN.md`) ; `apps/crm/**` → `lead` (`docs/plans/PLAN_AUDIT_LEAD.md`) ; `ProduitForm.jsx` et migrations stock → `stock` (`docs/plans/PLAN_AUDIT_STOCK.md`) ; `core/pompage/**` et `apps/ventes/**` (hors `roof_load.py`) → `devis`/autre (vérifie). Une tâche qui touche deux propriétaires se SCINDE en deux moitiés mono-propriétaire (contrat d'abord, la seconde `@after` la première). Les moitiés d'un autre propriétaire s'écrivent AUSSI en v3 avec le préfixe ACAL, dans ton second fichier, sous une ligne `## → <plan du propriétaire>` ; pour ces lignes lance quand même le validateur et ignore SEULEMENT ses lignes « proprietaire de … » après avoir vérifié toi-même que tous les fichiers de la tâche sont au même autre propriétaire.
- Les lecteurs d'une autre app passent par ses `selectors.py` (ex. `apps.crm.selectors`), jamais ses modèles.
- Dépendances à des tâches existantes (à vérifier par grep dans le plan avant de les citer) : ACAL470 (cible kWh/an, ouverte), ACAL421, ACAL412 (annuler/rétablir, ouverte), ACAL414 (table de raccourcis, ouverte), ACAL397 (liste « ce qui manque »), ACAL382 (goldens des 3 projets de référence, COCHÉE), ACAL269 (numéros de modules, cochée).

## Table des ids figés (tout le lot D2 ; tu n'écris QUE ceux de ton groupe, mais tu peux citer les autres en `@after`)
| id | fiche / tâche | contenu | lot/plan |
|---|---|---|---|
| 546 | D2-01 t1 | tableau comparatif toit plat monté dans l'atelier ERP, sans colonne MAD | calepinage |
| 547 | D2-01 t2 | carte « Couvre le besoin » (@after ACAL470) | calepinage |
| 548 | D2-03 | champ « accès solaire minimal » | calepinage |
| 549 | D2-05 t1 | nommer la cause d'un pan vide | calepinage |
| 550 | D2-05 t2 | raison imprimée sur le plan de pose (@after 549) | calepinage |
| 551 | D2-13 | silhouette rouge/ambre au glissé | calepinage |
| 552 | D2-15 | portrait ET paysage face à l'ombre | calepinage |
| 553 | D2-12 t1 | coller dans un autre pan | calepinage |
| 554 | D2-12 t2 | appliquer les réglages d'un pan à d'autres (@after ACAL412) | calepinage |
| 555-556 | libres (groupe A) | | |
| 557 | D2-02 t1 | contrat `calepinage_systemes_fixation.json` seul | calepinage |
| 558 | D2-02 t2 | routes société systèmes de fixation (@after 557) | calepinage |
| 559 | D2-02 t3 | écran Réglages « Systèmes de fixation » (@after 558) | calepinage |
| 560 | D2-02 t4 | onglet Fixation : liste des systèmes actifs (@after 558) | calepinage |
| 561 | D2-06 t1 | table retraits par type d'arête (réglage société sourcé) | calepinage |
| 562 | D2-06 t2 | pose d'office sur les arêtes typées (@after 561) | calepinage |
| 563 | D2-08 t1 | paramètres bande de rive / coin du lestage, sourcés | calepinage |
| 564 | D2-08 t2 | ranger chaque module centre/rive/coin (@after 563) | calepinage |
| 565 | D2-08 t3 | feuille « Plan de lestage » (@after 564) | calepinage |
| 566 | D2-14 t1 | couvertures servies par système (@after 558) | calepinage |
| 567 | D2-14 t2 | zone de serrage sur la fiche module | calepinage |
| 568 | D2-14 t3 | contrôle crochets/zone de serrage/porte-à-faux (@after 567) | calepinage |
| 569 | D2-14 t4 | bases portrait / paysage | calepinage |
| 570-572 | libres (groupe B) | | |
| 573 | D2-04 t1 | contrat `zones[].existant` seul | calepinage |
| 574 | D2-04 t2 | pan existant intouchable dans l'atelier (@after 573) | calepinage |
| 575 | D2-04 t3 | exclu de la nomenclature, marqué sur le plan de pose (@after 573) | calepinage |
| 576 | D2-09 t1 | coupures tous les N modules / allées tous les N rangs (atelier) | calepinage |
| 577 | D2-09 t2 | serveur lit les mêmes clés (@after 576) | calepinage |
| 578 | D2-10 t1 | bases `tables`, `poteaux`, `pieds` | calepinage |
| 579 | D2-10 t2 | pieds du châssis dessinés au pas saisi | calepinage |
| 580 | D2-10 t3 | pieds/poteaux/pieux imprimés sur le plan de pose (@after 558, 578) | calepinage |
| 581 | D2-16 t1 | contrat + `Kit` : rangs par table | calepinage |
| 582 | D2-16 t2 | serveur pose tables N × M (@after 581) | calepinage |
| 583 | D2-16 t3a | moitié paveur `estimatorBrainV2.ts::packConfig` (propriétaire web) (@after 581, 582) | **→ docs/WEB_PLAN.md** |
| 584 | D2-17 | alignement des rangées sans toucher `packConfig` | calepinage |
| 585 | D2-16 t3b | moitié atelier : `RP/optimizer.ts` utilise les blocs (@after 583) | calepinage |
| 586-587 | libres (groupe C) | | |
| 588 | D2-07 t1 | sélecteur `plan_pose_svg_pour_devis` | calepinage |
| 589 | D2-07 t2 | plan de pose dans la fiche chantier hors ligne (@after 588) | **→ docs/plans/PLAN_AUDIT_CHANTIERS.md** |
| 590 | D2-11 t1 | feuille A4 par pan : modules teintés par chaîne, numéros, + / − | calepinage |
| 591 | D2-11 t2 | 4 distances aux rives + zones interdites cotées | calepinage |
| 592 | D2-11 t3 | nomenclature de fixation PAR PAN | calepinage |
| 593 | D2-11 t4 | couche « Repères de chantier » | calepinage |
| 594 | D2-18 t1 | une variante par module coché | calepinage |
| 595 | D2-18 t2 | comparaison avec colonne « module » (@after 594) | calepinage |
| 596 | D2-20 t1 | sélecteur des points de contrôle de pose | calepinage |
| 597 | D2-20 t2 | check-list du chantier (@after 596) | **→ docs/plans/PLAN_AUDIT_CHANTIERS.md** |
| 598 | D2-21 | échafaudage dans la nomenclature (@after 558, 578) | calepinage |
| 599-600 | libres (groupe D) | | |
| 601 | F1-020 racine | modules dessinés dans leur vrai sens sur la planche A3 (orientation portrait/paysage enregistrée) | calepinage |
| 602 | F1-020 | échelle imprimée = échelle dessinée (arrondi au rang supérieur à corriger) | calepinage |
| 603 | F1-021 | cotes générales = toit seul | calepinage |
| 604 | F1-031 | DXF : emprise vraie, sans chevauchement, TOITURE sans doublon (@after 601) | calepinage |
| 605 | F1-020 jumeau | plan de câblage : même emprise couchée (`plan_cablage.py::_coins`) (@after 601) | calepinage |
| 606 | F1-027 | Terrain : allée AO 0,60 m en dur → pas anti-ombrage calculé + avertissement | calepinage |
| 607 | F1-029 | Terrain : puissance du module saisie/catalogue → kWc | calepinage |
| 608-610 | libres (groupe E) | | |

## Sorties (crée le dossier au besoin ; `SP\l5\lots2\parts\`)
- `D2-<lettre>.md` : tes lignes de tâches v3 pour le propriétaire `calepinage`, regroupées sous les deux titres exacts `### ACAL — M1 bloquant-fondateur` (P0 et P1) puis `### ACAL — M2` (P2, P3), plus `### ACAL — GATED (ne PAS auto-construire)` si utile. Une ligne = une tâche, rien d'autre sauf les titres.
- `D2-<lettre>-autres.md` : tes moitiés routées, sous `## → <plan du propriétaire>` (même format de ligne).
Valide : `PYTHONIOENCODING=utf-8 python "SP/valide_lot.py" "<ton fichier>"` (chemin Windows complet, séparateurs `/`) → corrige jusqu'à « 0 en echec » (hors l'exception ci-dessus pour le fichier `-autres`).

## Compte rendu (≤ 20 lignes)
Ids écrits par priorité ; cartes/tâches sans objet (déjà construites : preuve `fichier::symbole`) ; prémisses de la fiche trouvées FAUSSES ; tâches scindées / ids libres utilisés ; tâches routées (plan → ids) ; dépendances inter-groupes que tu as posées ; conflits de fichiers avec d'autres tâches de la table (même fichier mono-écrivain) ; dernière ligne du validateur (citée telle quelle).
Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.
