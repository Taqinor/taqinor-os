# Vérifie ACHT — contre-visite de clôture du groupe chantiers (J2), 30/10/2026

Commande `vérifie ACHT` (METHODE §C.4.2, skill audit §5), lancée par `loop audit`. `audit_registre.py --du` liste cinq
groupes dus en clôture (≥ 95 %) : ACHT 97/97, AMOT 96/100, ASEC 54/54, AGNR 47/48, ATOT 35/35. Les dus se jouent par
nombre de tâches cochées décroissant : ACHT passe en premier. La contre-visite précédente, du 11/10
(`docs/audits/2026-10-11-chantiers-verifie.md`), était à mi-parcours ; la revue L3 du 26-27/10
(`docs/audits/2026-10-26-chantiers-revue.md`) a ajouté ACHT104-112.

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test nommé et le code de `main` avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde exécutée en
transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `db8ca9670` (PR #1176), re-fetch en début d'itération. Branche de claim : `verifie-acht-cloture`
  (commit vide, poussé).
- **Registre.** J2 `chantiers`, groupe ACHT, dossier `docs/audits/2026-10-08-chantiers.md`, 97/97 tâches constructibles
  cochées, aucun `vérifie` de clôture.
- **Inventaire (déterministe).** 97 tâches ACHT `[x]` : 89 dans `PLAN_AUDIT_CHANTIERS.md`, 3 dans `PLAN_AUDIT_SAV.md`,
  2 dans `PLAN_AUDIT_STOCK.md`, 1 chacune dans `PLAN_AUDIT_LEAD.md`, `PLAN_AUDIT_DEPLOY.md`, `PLAN_AUDIT_TRANSVERSE.md`.
- **Échantillon (graine = SHA `db8ca9670424f43ae123c55c801a6a76e733063a`).** Toutes les S1/P0 cochées (ACHT1, 2, 3, 44,
  52, 53, 99, 110), plus 25 % du reste tirées par `random.Random(int(sha, 16)).sample` sur les ids triés (22 sur 89) :
  ACHT5, 6, 7, 13, 18, 20, 23, 25, 26, 30, 36, 41, 55, 60, 61, 62, 66, 68, 71, 72, 95, 106. Total : **30 tâches**.
- **Pile des sondes.** Conteneur jetable `sonde-verifie-acht` sur l'image `erp-agentique-django_core`, avec le code de
  `main` copié par `git archive` (le conteneur de la pile locale monte le checkout principal, sur la branche d'une autre
  session ; il n'a pas été touché). Base de démo partagée : 0 migration en attente. Chaque sonde tourne dans une
  transaction annulée : 0 mail, 0 tâche Celery. Pour C-ACHT-VER-007 et -008, le lanceur a vu le compte de lignes varier
  pendant l'exécution ; la pile d'une autre session (beat Celery) écrivait au même moment dans la base partagée. Les sondes
  écrivent dans une société neuve dont rien ne survit au rollback.

## 1. Vérificateurs (10 agents frais, opus, effort élevé, lecture seule, même répertoire, 3 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **16** | ACHT1, 5, 6, 13, 18, 20, 23, 30, 44, 52, 55, 62, 68, 71, 95, 110 |
| partiel | **13** | ACHT2 (S3), ACHT3 (S2 + S3), ACHT7 (S2), ACHT25 (S3 ×2), ACHT26 (S2), ACHT36 (S2), ACHT41 (S2 + S3), ACHT53 (S3 + S4), ACHT61 (S3), ACHT66 (S3 + S4), ACHT72 (S3), ACHT99 (S3 ×2 + S4), ACHT106 (S3 + S4) |
| régression | **1** | ACHT60 (S2, même cause que l'écart S2 d'ACHT3) |
| non-fait / faux / déjà-présent | 0 | — |

Changements postérieurs jugés voulus, pas des régressions : refus passés de 400 à 409 (ERR-ENF11 : ACHT2, ACHT20, ACHT25) ;
id inconnu ou d'une autre société → 404 sans distinguer (fuzz #997 : ACHT23, ACHT44, ACHT52) ; tests de FK bornées
déplacés (ENF17) ; ACHT66 garde `forme_serveur: "partielle"`, avec la raison écrite (`check_api_shapes.py` refuserait
`complete` pour un ModelViewSet).

## 2. Sondes (5 REPRO)

| Sonde | Tâche | Observé (code de `main`, transaction annulée) |
|---|---|---|
| `docs/audits/sondes/ACHT/C-ACHT-VER-004.py` | ACHT3 × ACHT60 | chantier Réceptionné : POST `mise-en-service` **200**, date 01/10 → 05/10 ; l'écran masque ce bouton (`canMoveStatus('receptionne','receptionne')` = false) |
| `docs/audits/sondes/ACHT/C-ACHT-VER-005.py` | ACHT7 | V1 acceptée (PAN 10) → lead sorti de « Signé » (chantier annulé) → ligne corrigée à 14 → ré-acceptée 200 : 1 chantier actif, nomenclature **PAN 10** |
| `docs/audits/sondes/ACHT/C-ACHT-VER-006.py` | ACHT26 | charge d'Ateliers `{resultat: 'conforme'}` **400** ; résultat resté `en_attente` ; blocage écran faux ; `terminer` sans forcer **400** (clôture impossible depuis l'écran) |
| `docs/audits/sondes/ACHT/C-ACHT-VER-007.py` | ACHT36 | PATCH terminee → sur_site → terminee (200 ×3) : **2** `ApiEvent` `intervention.completed` (1 attendu) |
| `docs/audits/sondes/ACHT/C-ACHT-VER-008.py` | ACHT41 | corps de l'écran `{photo}` sur intervention terminée : **409** « indiquez le motif », photo intacte ; l'écran n'envoie jamais de motif |

Les constats C-ACHT-VER-001 à -003 appartiennent à la contre-visite du 11/10 ; la numérotation continue à -004.

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu | Sonde |
|---|---|---|---|---|---|---|---|
| C-ACHT-VER-004 | ACHT113 | ACHT3, ACHT60 | C10 | S2 | `frontend/src/pages/installations/InstallationDetail.jsx` (section Mise en service) | bouton gardé par `canMoveStatus` dont ACHT60 a changé la règle : masqué sur Réceptionné (accepté par le serveur), offert sur Clôturé (refusé sans motif) → offert dès Installé, non annulé, non clôturé | `docs/audits/sondes/ACHT/C-ACHT-VER-004.py` |
| C-ACHT-VER-005 | ACHT114 | ACHT7 | C17 | S2 | `apps/installations/services.py::_reactiver_chantier_reaccepte` | réservations réamorcées sur l'ancienne nomenclature à la ré-acceptation → `realigner_nomenclature_si_divergente` avant `seed_reservations` | `docs/audits/sondes/ACHT/C-ACHT-VER-005.py` |
| C-ACHT-VER-006 | ACHT115 | ACHT26 | C10 | S2 | `frontend/src/pages/installations/AteliersPage.jsx` | l'écran envoie conforme/echec (refusés) et calcule mal le blocage : clôture impossible → pass/fail, blocage = tout sauf pass | `docs/audits/sondes/ACHT/C-ACHT-VER-006.py` |
| C-ACHT-VER-007 | ACHT116 | ACHT36 | C17 | S2 | `apps/publicapi/signals.py::intervention_post_save` | webhook + flux `intervention.completed` rejoués à chaque re-clôture → un seul événement externe par clôture | `docs/audits/sondes/ACHT/C-ACHT-VER-007.py` |
| C-ACHT-VER-008 | ACHT117 | ACHT41 | C10 | S2 | `frontend/src/api/installationsApi.js` (`supprimerPhoto` & co) | aucun motif envoyé, 409 affiché « Suppression impossible. » → refus lisible puis motif saisi et transmis | `docs/audits/sondes/ACHT/C-ACHT-VER-008.py` |
| C-ACHT-VER-009 | ACHT118 | ACHT2 | C7 | S3 | `apps/installations/services.py::raison_machine_etats` | recul de plus d'un rang accepté (réceptionné → signé 200) → refusé comme à l'écran | STATIQUE |
| C-ACHT-VER-010 | ACHT119 | ACHT25 | C6 | S3 | `apps/installations/views/kitting.py::OrdreAssemblageViewSet.depuis_devis` | garde « Nomenclature vide » absente de `depuis_devis` et ignorant les lignes réellement consommées à `terminer` | STATIQUE |
| C-ACHT-VER-011 | ACHT120 | ACHT53 | C5 | S3 | `apps/installations/serializers.py::InterventionSerializer` | `devis_upsell_id`, `ventes_recette_id` inscriptibles sans borne de société → lecture seule | STATIQUE |
| C-ACHT-VER-012 | ACHT121 | ACHT72 | C7 | S3 | `apps/installations/field_services.py::cocher_outil_ligne` | outil sorti garde `emplacement=Dépôt` → emplacement vidé à la sortie, restauré au retour | STATIQUE |
| C-ACHT-VER-013 | ACHT122 | ACHT106 | C3 | S3 | `frontend/src/features/stock/procurement.js::buildReceptionPayload` | réception rapide de la fiche BCF sans séries ni lot → saisissables sur les deux portes | STATIQUE |

**Constats S1-S2 : 5** (0 S1, 5 S2), tous reproduits. ACHT123 clôt la section (acceptation en direct, jamais confiée à une
lane). Routage : ACHT113-115, 117-121, 123 dans `PLAN_AUDIT_CHANTIERS.md` ; ACHT116 dans `PLAN_AUDIT_ANALYSE.md`
(`apps/publicapi` appartient à `analyse`) ; ACHT122 dans `PLAN_AUDIT_STOCK.md`.

C-ACHT-VER-004 réunit deux verdicts : l'écart S2 d'ACHT3 et la « régression » d'ACHT60. Les deux tâches ont été
construites en parallèle le 08/10 : ACHT3 garde le bouton par `canMoveStatus`, ACHT60 a changé la règle de `canMoveStatus`.
Aucune n'est l'ancêtre de l'autre ; la cause est la couture entre les deux, d'où une seule tâche.

## 4. Critique de complétude

Aucun écart S1 ne subsiste : pas de critique Fable (METHODE §C.4.2), pas de seconde lentille (§B.5, réservée aux S1).

## 5. Optionnel (non déposé)

- ACHT1 : le test passe à « Installé » par `queryset.update` + `_apply_stock_statut_effects`, pas par le PATCH ; une F11
  partielle (8/10) libère le reliquat, que la V2 suivante re-réserve.
- ACHT2 : `avancer-etape` fait avancer un chantier annulé quand la cible garde le même statut canonique (seulement pour une
  société à étapes CH2 : aucune aujourd'hui) ; désactiver les deux étapes INSTALLE rendrait en_cours → réceptionné « un
  pas » sans sortie de stock (hypothétique, S1 potentiel à surveiller).
- ACHT3 : glisser un chantier annulé dans le kanban ne vérifie pas `annule` (le serveur refuse en 409).
- ACHT5 : le menu de la liste Ventes (`DevisRow.jsx`) propose « Créer le chantier » sur une version remplacée ; la garde
  serveur ACHT4 renvoie le bon chantier (libellé trompeur).
- ACHT6 : `test_patch_annule_cloture_ignore` accepte 200 ou 400.
- ACHT18 / ACHT20 : contrôles de `demarrer`, `annuler` et `expedier` hors verrou ; `contre_transferer_stock_livraison`
  garde `except ValueError: continue` et la vue `annuler` avale l'exception (retour partiel sans signal).
- ACHT23 : aucun écran n'appelle `ordres-assemblage/depuis-devis` (pas de bouton « Assembler à la commande »).
- ACHT26 : la garde de `cocher_etape` n'a aucun test ; un « pass » sans valeur mesurée sur un item à tolérance est accepté.
- ACHT30 : `ajouter-serial` et `ajouter-reserve` en ligne acceptent une intervention validée (la synchro refuse).
- ACHT36 : `test_date_realisee_remise_a_vide` ne vérifie que « différente du 01/10 ».
- ACHT41 : `DELETE /api/django/records/attachments/<id>/` (admin) supprime une photo d'intervention validée sans motif ni
  trace (API sans écran ; `apps/records` appartient à `securite`, et une règle d'installations n'y entre pas sans
  inverser la dépendance fondation → domaine).
- ACHT53 : le test vérifie le type des champs d'une liste figée, sans rejeu en base, et simule `Outillage.objects` pour
  `instrument_id` (le rejeu réel est fait par `tests_acht44` et `tests_acht52`).
- ACHT60 : la moitié « stepper » (motif d'acompte via `avancerEtape`) n'est prouvée par aucun test (`ChantierGateTimeline`
  remplacé par un composant nul).
- ACHT61 : le test mocke `installationsApi` et `ui/Toaster` ; ni l'appel automatique (« Départ dépôt ») ni le kanban ne
  sont joués.
- ACHT66 : aucun cas de devis à deux options (une version qui comparerait toutes les lignes passerait).
- ACHT68 : la route photo publique sert toute pièce `image/*` de l'intervention (SVG inclus, servi inline).
- ACHT72 : pas de verrou dans `cocher_outil_ligne` ; changer le kit après une sortie supprime la ligne et laisse l'outil
  « En intervention ».
- ACHT99 : `audit_coherence` jamais joué (oracle 10 NA sur toutes les étapes) ; l'enregistrement `2026-10-30-e9e8593e5`
  cite 16 captures absentes du dépôt (ACHT99 reste couvert par `2026-10-29-5f102e3f2`, dont les traces existent) ;
  `check_acceptation.py` ne contrôle pas l'existence des traces. ACHT123 exige les captures commitées et la sortie liée.
- ACHT106 : la saisie séries/lot à la réception n'a jamais été rejouée en direct ; le serveur ne borne pas le nombre de
  séries à la quantité.
- ACHT110 : la Pose de démo garde sa date du premier `seed_demo` (« Ma journée » vide les jours suivants, nightly QA
  compris).

## 6. Couverture et non-couvert

- **Couvert.** 30 tâches sur 97 cochées (toutes les S1/P0 + 25 %), commits, tests nommés (lus, non exécutés), code de
  `main`, décisions D-ACHT-*. Cinq sondes jouées sur le code de `main`.
- **Non couvert.** Les 67 autres tâches cochées ; aucun aller-retour en direct à l'écran (ACHT123 ouverte) ; aucun vitest
  ni test Django exécuté par les vérificateurs (worktree sans `node_modules`, docker réservé à l'orchestrateur).
- **Statut du registre.** Après ce dépôt : 97 cochées sur 108 constructibles (90 %, ACHT113-123 ajoutées), contre-visite de
  clôture **avec 5 écarts S1-S2** → statut calculé `audité` ; le cycle n'est pas sorti (il faut deux contre-visites
  consécutives à zéro S1-S2).

## 7. Coût

- 10 vérificateurs opus (effort élevé) : ≈ 1,80 M de jetons, 437 appels d'outil. 1 rédacteur opus : 11 tâches v3,
  clauses calculées par `audit_tache.py`.
- Orchestrateur : échantillon déterministe, triage des 30 verdicts, 5 sondes écrites et jouées, routage, rédaction de ce
  dossier.
- H0 S0 O11 F0 · jetons sous-agents ≈ 2,0 M

<!-- verifie | groupe: ACHT | pct: 100 | ecarts_s1_s2: 5 -->
