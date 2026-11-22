# Calepinage L5 — état du chantier (à lire EN PREMIER pour reprendre, sur ce poste ou un autre)

Dernière écriture : 23/11/2026 par la session « Calpinage module L5 completion » (poste `DESKTOP-APTAHF6`) ·
branche `claude/calpinage-module-l5-aadbde`.
**Prochaine action unique** : voir la dernière ligne du § « Déroulé ».
Ce fichier vit POUSSÉ. Les états antérieurs : `docs/audits/2026-11-20-calepinage-l5.md` (tour 0 du 20/11),
`docs/audits/2026-11-21-calepinage-l5-vague2.md` (vague 2), `T1/` (tour 1 de relecteurs),
`docs/claude-memory/calepinage-decisions-fondateur.md` (recette du 22/11 et fidélité aux maquettes).

## Demande et cadre

- Demande de Reda (22/11/2026 au soir), mot pour mot : dans `contrat-de-sortie.md`. Consignes : « i am going to sleep,
  i want you to choose for me, and give me detailled report tomorrow » puis « forget about cpge go plus for now — only
  do the l5 — the l5 should take you more then 12 hours… and then the checks, and among the checks comes this lead ».
- Ordre imposé : (1) le L5 complet ; (2) les contrôles — maquettes, fonctions, « tous mes devis se calculent seuls
  avec les bonnes hypothèses », un seul moteur (celui du CRM), le lead 1742 ; (3) le rapport détaillé.
- Niveau L5 · régime MIXTE lu sur `origin/main@bfb859c90` · contrat : `contrat-de-sortie.md` (K1-K17) · registre :
  `registre/`.
- Coût annoncé : k = 3 tours × c = 21 points + réserve finale 10 ; quota au départ 3 % (« Weekly · all models », lu par
  `get_usage` le 22/11) ; L5 : coût non mesuré.
- Poste mesuré au tour 0 : 8 cœurs, 15,9 Go de mémoire (8,6 libres avant Docker), 27 Go de disque libre, 82 worktrees,
  Docker Desktop éteint au départ (démarré par cette session : 6 conteneurs de la pile `erp-agentique` sont revenus
  seuls, sans worker ni planificateur) → 2 relecteurs à navigateur à la fois, 3 agents de fond au plus.

## Inventaire du tour 0 (lu sur `origin/main@bfb859c90`)

- Plan `docs/plans/PLAN_AUDIT_CALEPINAGE.md` : 894 tâches ACAL — 436 cochées, **388 « code livré, preuve en direct
  due »** (25 S1, 120 S2, 210 S3, 9 S4, 24 sans gravité ; dues à ACAL1031 : 336, à ACAL1327 : 29, à ACAL490 : 22),
  51 ouvertes (dont 5 tâches d'acceptation), 19 retenues par une décision ouverte.
- CI (run 45077305806 de `main`, vert) : le backend et vitest lisent le module ; en PR, seules 2 specs e2e du
  calepinage tournent (`calepinage-parcours`, `calepinage-onglets`) ; 8 specs ne tournent que la nuit ; les 10 specs
  `e2e/acceptation/acal*.spec.js` ne tournent jamais en CI ; api-fuzz, a11y, visuel et perf de PR ne lisent aucun écran
  du calepinage. Nocturne du 22/11 (45014638342) ROUGE sur : `calepinage-perf` (ACAL440, 2 tests),
  `calepinage-horizon-telephone` (ACAL521), « monkey » calepinage, `test_calx389_budget_simulation` (4 échecs),
  `test_calx328_pages_documents` (rapport d'étude 19 pages, plafond 14). → Lane 0.
- Défaut d'hygiène trouvé : 13 fichiers `.whl` (80 Mo, paquets Python pour Windows) commités dans
  `backend/django_core/apps/calepinage/` par ACAL454 ; rien ne les lit ; ils entrent dans l'image Django à chaque
  deploy. → Lane 0.
- Classes ouvertes du tour 1 (`T1/classes/`) : K-ACTION-ENFOUIE, K-DEFAUT-CHOIX, K-DOC-GEOMETRIE, K-GESTE,
  K-GRANDEUR-UNIQUE, K-IMPASSE, K-JARGON, K-RETOUR-FAUX, K-SAISIE-PERDUE, K-STYLE.

## Instrument de revue (pile privée `l5cal`)

Fiche : `T2/instrument.md`. Écarts au gabarit, voulus : image à soi `l5cal-django:t0` construite depuis
`origin/main` (l'image partagée avait pvlib 0.15.2 au lieu de 0.16.1), un MinIO à soi et un worker Celery à soi sans
planificateur (l'étape Résultats et l'étape Documents en dépendent). Les scripts (lanceur, base, comptes, captures)
vivent dans le scratchpad de la session, pas sur `main`.

## Quota et contexte aux points de contrôle (ajout seulement)

| Point | Date | Quota hebdo | Contexte orchestrateur | Claims renouvelées | Décision |
|---|---|---|---|---|---|
| départ | 22/11 23 h | 3 % | 21 % | prises (`file:docs/plans/PLAN_AUDIT_CALEPINAGE.md`, `app:calepinage`) | tour 0 |

## Où sont les choses

- Notes : `docs/audits/l5-calepinage/` — `contrat-de-sortie.md`, `etat.md`, `T2/` (recherches R1-R2, listes de
  contre-vérification `T2/cv/`, rapports des relecteurs), `registre/`, `maquettes/` (v1), `maquettes-v2/`.
- Code : branche d'intégration `claude/calpinage-module-l5-aadbde` ; worktree de l'instrument
  `.claude/worktrees/l5cal-instr` (ne jamais l'éditer ; mise à jour par `git merge --ff-only`).
- Claims : `file:docs/plans/PLAN_AUDIT_CALEPINAGE.md`, `app:calepinage`, propriétaire
  `DESKTOP-APTAHF6/claude/calpinage-module-l5-aadbde` (bail 6 h, à renouveler à chaque point ; relâcher après le merge).

## Choix pris seul (aucune question — réversibles, jamais des décisions de Reda)

| # | Choix | Règle appliquée | Coût si faux |
|---|---|---|---|
| 1 | Docker Desktop démarré sur ce poste pour monter l'instrument | prérequis manquant à installer plutôt qu'à signaler | aucun (arrêt en fin de session) |
| 2 | Les deux lanes de diagnostic du lead 1742 arrêtées dès la précision de Reda ; le cas est rangé dans la phase de contrôles | consigne de Reda | à relancer à la phase de contrôles |
| 3 | Contre-vérification du tour 2 : les 388 corrections livrées, réparties sur 11 relecteurs, S1-S2 d'abord ; passage à « S1-S2 + 25 % du reste » dès que `non-fait + partiel` ≤ 10 % | `L4.md` « Cost and stop » | des corrections S3 non rejouées, dites au rapport |
| 4 | Contrôle de l'instrument : deux variables « à clé » non vides admises — `GPG_KEY` (empreinte PUBLIQUE de la clé de publication de Python 3.11, posée par l'image de base, vérifiée égale à celle de `python:3.11.11-slim-bookworm`) et `PUBLIC_MAPTILER_KEY=factice-l5cal` (sans clé l'atelier refuse de démarrer ; la vraie est limitée au domaine du site) | lecture du gabarit : aucune clé RÉELLE | aucun |
| 5 | Conteneurs inutilisés de la pile partagée `erp-agentique` arrêtés (`fastapi_ia`, `django_core`, `minio`, `redis`, `redis_cache`) pour rendre 1,7 Go ; la base, elle, reste en marche | poste à 2,7 Go libres avec deux relecteurs ; personne ne s'en servait (Docker était éteint) | `docker start` des cinq à la fin (ligne du nettoyage) |
| 6 | Lane 0 : les deux tests rouges du nocturne ont été remis au vert en RELEVANT leur borne au nombre mesuré, avec la liste des tâches qui l'expliquent écrite dans le test (3 lectures météo de plus par simulation : ACAL706, ACAL744 ×2 ; rapport d'étude à 19 pages : six sections nées depuis) | consigne de lane : jamais un plafond élargi sans nommer ce qui le consomme | si l'une des trois lectures est jugée superflue : une tâche pour la retirer |
| 7 | Maquettes v2 : même ossature que la v1 (rien ne se déplace), finition refaite — carte plein cadre, pièces flottantes, bleu nuit pour l'actif, or pour la seule action suivante, chiffres dessinés (`maquettes-v2/LANGAGE.md`) | « much prettier » sans jeter les trois tours de fidélité du 22/11 | une passe de style à défaire |

## Déroulé (un point par étape, avec ses chiffres)

1. Tour 0 (22-23/11) : état relu, claims prises, poste mesuré, CI de `main` lue (ci-dessus), recherches R1 (beauté,
   simplicité) et R2 (fonctions : 15 fonctions utiles absentes du plan, `T2/R2-fonctions.md` § B) rendues, listes de
   contre-vérification générées (`T2/cv/`, 388 corrections sur 11 relecteurs). Instrument `l5cal` monté et contrôlé
   (« instrument sûr » avec les deux exceptions du choix n° 4) : base clonée du gabarit de test `test_erp_l5w` + `migrate`
   + `seed_demo` + `seed_catalogue`, serveur gunicorn à 3 processus (127.0.0.1:8021), worker Celery à 2 processus sans
   planificateur, MinIO et Redis à soi, front construit servi sur 127.0.0.1:5241, 14 comptes de revue. PR #1527 ouverte
   en brouillon, Auto-fix allumé.
2. Lane 0 (pliée, d7bc604cc) : 13 fichiers `.whl` retirés du dépôt et ignorés ; `test_calx389_budget_simulation` et
   `test_calx328_pages_documents` verts (rejoués localement : 17 tests, 6 échecs avant, 0 après). Restent du nocturne :
   `calepinage-perf`, `calepinage-horizon-telephone`, « monkey » — à rejouer sur l'instrument au repos.
3. Maquettes v2 : langage écrit, `Main` (Toit) et `Resultats` écrites par l'orchestrateur et publiées sur le canevas
   https://claude.ai/artifact/BJ5TrpZU3QvwHE3fWAteH5 ; lot A (six écrans) confié à une lane de design.
4. Tour 2 de relecteurs : EN COURS — `S2-PARCOURS` et `F2-RESU` lancés les premiers ; ordre suivant : `F2-GESTES`,
   `F2-TOIT`, `F2-DOCS`, `F2-POSE`, `F2-ELEC`, `F2-SIMU`, `F2-CONSO`, `T2`, `B2` (deux à la fois).
   **Prochaine action** : à chaque retour de relecteur, lancer le suivant ; quand tous sont rentrés → consolidation
   (`gabarits/consolidation.md`), tâches au plan, lanes de correction.

## Phase de contrôles (APRÈS le L5 — ne pas commencer avant)

- Maquettes : chaque écran contre sa maquette v2, relecteur neuf.
- Fonctions : parcours critiques rejoués 3 fois.
- « Tous mes devis se calculent seuls, avec les bonnes hypothèses » et « un seul moteur, celui du CRM » : mesure sur
  des fiches réelles, en lecture seule.
- Lead 1742 : relu en prod (lecture seule) le 22/11 — son calepinage est resté attaché à un brouillon antérieur au
  devis envoyé, il porte le nombre de panneaux de l'option avec batterie alors que le devis recommande l'option sans,
  il juge l'onduleur hybride avec la borne 1,35 que la décision D-HYB-1 a remplacée par la fiche constructeur, deux
  calculs de chaînes ne s'accordent pas, et sa production n'est pas simulée alors que le devis porte la sienne. Causes
  à établir dans le code à ce moment-là, pas avant.

## À dire à Reda dans le rapport final

Tenu à jour au fil de l'eau dans `T2/pour-reda.md`.

## Nettoyage à la fin (cocher chaque ligne)

- [ ] dernière vague mergée par la file ; [ ] claims relâchées ; [ ] instrument démonté (conteneurs `l5cal-*`, réseau
      `l5cal-net`, serveur du front, `DROP DATABASE l5cal`, fichier d'environnement effacé, image `l5cal-django:t0`)
- [ ] worktree `l5cal-instr` et worktrees de lanes retirés ; Docker Desktop arrêté s'il n'était pas en marche
- [ ] rétro bornée
