# Vérifie ADEV — contre-visite de clôture du groupe devis (J1b), 04/11/2026

Commande `vérifie ADEV` (METHODE §C.4.2, skill audit §5). `audit_registre.py --du` liste deux groupes dus en clôture
(≥ 95 %) : ADEV 97/99 et APRF 38/38. Par nombre de tâches cochées décroissant, ADEV passe en premier. La contre-visite
précédente, du 11/10 (`docs/audits/2026-10-11-devis-verifie.md`), était à mi-parcours (60/70) ; le groupe a reçu depuis
ADEV71-105 (audit moteur C&I du 23/10, revue L3 lien et PA3).

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test nommé et le code de `main` avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde exécutée en
transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `e62ca97aa` (PR #1260), re-fetch en début d'itération.
- **Registre.** J1b `devis`, groupe ADEV, dossier `docs/audits/2026-10-07-devis.md`, 97 cochées sur 99 constructibles
  (ADEV46 et ADEV66 ouvertes).
- **Inventaire (déterministe).** 97 tâches ADEV `[x]` réparties dans `PLAN_AUDIT_DEVIS.md` (52), `PLAN_AUDIT_TRANSVERSE.md`
  (29), `PLAN_AUDIT_LEAD.md` (5), `PLAN_AUDIT_DEPLOY.md` (3), `PLAN_AUDIT_CALEPINAGE.md`, `PLAN_AUDIT_FACTURATION.md`,
  `PLAN_AUDIT_MOTEUR.md` (2 chacun) et `PLAN_AUDIT_SAV.md` (1).
- **Échantillon (graine = SHA `e62ca97aa54a6d77e8eb9e2d68810226dd6e7c3d`).** Les S1/P0 cochées rattachées à un constat
  S1 des dossiers (ADEV30, 50, 51 ; ADEV89, 92 du moteur C&I ; ADEV95, 96 de la revue PA3), plus 25 % du reste tirés par
  `random.Random(int(sha, 16)).sample` sur les ids triés (23 sur 90) : ADEV1, 4, 14, 20, 23, 24, 31, 33, 35, 37, 38, 47,
  55, 56, 58, 64, 69, 70, 73, 77, 82, 88, 100. Total : **30 tâches**. C-ADEV-034 (S1) n'est cité par aucune tâche cochée
  encore active (archivée) : non échantillonné.
- **Pile.** Pile locale remise au code de `e62ca97aa` (0 migration en attente, front reconstruit) ; sondes jouées par
  `scripts/sonde.py` dans `erp-agentique-django_core-1`, transaction annulée, 0 mail.

## 1. Vérificateurs (10 agents frais, opus, effort élevé, lecture seule, même répertoire, 3 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **22** | ADEV1, 4, 14, 23, 24, 30, 31, 33, 35, 37, 38, 47, 51, 55, 56, 64, 69, 70, 73, 89, 92, 95, 96 |
| partiel | **7** | ADEV20 (S3), ADEV50 (S3), ADEV58 (S3), ADEV77 (S3), ADEV82 (S3), ADEV88 (S3 écran), ADEV100 (S2 + 2 S3 de test) |
| non-fait / faux / régression / déjà-présent | 0 | — |

ADEV70 et ADEV73 sont « ok » sur le comportement mais portent un écart S3 de test (voir §3 et §5). Changements postérieurs
jugés voulus, pas des régressions : refus passés de 400 à 409 (ERR-ENF11 : ADEV1, ADEV33) ; bascule Celery du PDF signé
(ERR-ACCEPTATION-PDF-SIGNE-SYNCHRONE, ADEV38, ADEV96) ; RWEB24 qui fixe la carte d'économies sur l'option du PDF (ADEV50) ;
choix du comptage par calibre R3.5 (ADEV82).

## 2. Sondes (1 REPRO)

| Sonde | Tâche | Observé (code de `main`, transaction annulée) |
|---|---|---|
| `docs/audits/sondes/ADEV/C-ADEV-VER-002.py` | ADEV100 | lead à 4 000 kWh/mois, corps `{kwh_mensuels: null, kwh_annuel: 96 000, lead}` : retenu **48 000 kWh**, feuille `kwh_mensuel_declare` (la saisie corrigée est ignorée) |

C-ADEV-VER-001 appartient à la contre-visite du 11/10 ; la numérotation continue à -002.

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu | Sonde |
|---|---|---|---|---|---|---|---|
| C-ADEV-VER-002 | ADEV106 | ADEV100 | C17 | S2 | `backend/django_core/apps/ventes/domain/etude_ci.py::_consommation` | le kWh semé par le lead puis corrigé à l'écran est ignoré (feuille du lead prioritaire) → la saisie du corps prime (corps > devis > lead) | `docs/audits/sondes/ADEV/C-ADEV-VER-002.py` |
| C-ADEV-VER-003 | ADEV107 | ADEV50 | C3 | S3 | `apps/web/src/pages/proposition/[...token].astro` (titre des économies) | cumul 25 ans rendu une fois pour l'option recommandée → suit l'option cochée (règles ≤ 2) | STATIQUE |
| C-ADEV-VER-004 | ADEV108 | ADEV58 | C9 | S3 | `backend/django_core/apps/ventes/views/devis_calepinage.py::DevisCalepinageActionsMixin.simuler` | simuler un ENVOYÉ réécrit l'étude sans trace → trace « corrigé après envoi — étude » | STATIQUE |
| C-ADEV-VER-005 | ADEV109 | ADEV20 | C10 | S3 | `apps/web/src/pages/proposition/[...token].astro` (bouton « Envoyer le code ») | 409 `aucun_canal` affiché « Réessayez » → message servi | STATIQUE |
| C-ADEV-VER-006 | ADEV110 | ADEV77 | C3 | S3 | `backend/django_core/apps/ventes/quote_engine/ci/mentions.py::mentions_ci` | aucune mention « estimation (n mois relevés) » → mention client | STATIQUE |
| C-ADEV-VER-007 | ADEV111 | ADEV82 | C1 | S3 | `backend/django_core/apps/ventes/moteur_ci/composition.py::composer_ci` | onduleur à paliers : ligne au prix de palier, taille au prix catalogue → même prix (théorique : aucun palier au seed) | STATIQUE |
| C-ADEV-VER-008 | ADEV112 | ADEV88 | C10 | S3 | `frontend/src/api/ventesApi.js::getProposalPdf` | corps 409 en Blob jamais décodé → « Devis commercial incomplet : motif » affiché | STATIQUE |
| C-ADEV-VER-009 | ADEV113 | ADEV73 | C11 | S3 | `frontend/src/lib/dateLocale.test.mjs` | attendu dépendant du fuseau du runner (mutant UTC vert en GMT+0) → assertion fixe | STATIQUE |

**Constats S1-S2 : 1** (0 S1, 1 S2), reproduit. Gravité de C-ADEV-VER-002 : S2 et non S1 — le chiffre imprimé est la
consommation déclarée du lead (pas un nombre inventé) ; le défaut est la correction de la commerciale non propagée (C17).
ADEV114 clôt la section (acceptation en direct, jamais confiée à une lane). Routage : ADEV106, 111, 112, 114 dans
`PLAN_AUDIT_DEVIS.md` ; ADEV108 (calepinage + devis) et ADEV110 (moteur + devis) dans `PLAN_AUDIT_TRANSVERSE.md` ;
ADEV107, 109 dans `docs/WEB_PLAN.md` (`apps/web`) ; ADEV113 dans `PLAN_AUDIT_DEPLOY.md`.

## 4. Critique de complétude

Aucun écart S1 ne subsiste : pas de critique Fable (METHODE §C.4.2), pas de seconde lentille (§B.5, réservée aux S1).

## 5. Optionnel (non déposé)

- ADEV70 (S3 de test, sans tâche : comportement livré, Paiements et Avoirs déjà couverts en comportement par AFAC63) : les
  cas FactureList et FactureForm de `paginationAdev70.test.mjs` sont des regex sur la source.
- ADEV100 (S3 de test, sans tâche : la branche sera reprise par le test d'ADEV106) : la branche « 12 mois » du garde-fou
  `kwh_incoherent_factures` n'est couverte par aucun test ; aucun test front ne fixe « `?edit=` ⇒ aucun semis ».
- S4 : ADEV24 (3 chemins sur 8 exercés, garde AST en filet) ; ADEV23 (`test_reponse_egale_base` ne distingue pas son
  mutant) ; ADEV69 (commentaire renvoyant à un test inexistant) ; ADEV1 (textes « 400 » restés dans le contrat et la vue
  après ENF11) ; ADEV55 (chemin du fichier de test).
- Hors texte des tâches : ADEV33 (`perform_destroy` hors garde T17) ; ADEV51 (parité d'empreinte C&I lecture/signature non
  testée de bout en bout) ; ADEV31 (`devis_facturation.py` sert encore « PDF indisponible : {exc} ») ; ADEV14
  (`override_credit` sans cas de test).
- Rejeu P5.2 (ADEV43) en échec sur une assertion périmée de la spec, pas sur le produit : `adev.spec.js` attend
  400 pour un motif de refus inconnu ; ERR-ENF11 (04/11) a fait passer ce refus à 409 `{motif: […]}`, voulu (contrat
  `devis_refuser.json`). La spec est à réaligner ; rien n'est déposé ici (outil d'acceptation, pas un écart de tâche).
- Leçon 7 : ADEV14, 20, 23, 24, 30, 33, 50, 51, 58 restent dans la dette gelée `docs/audits/acceptation/ADEV/_dette.yml`.

## 6. Couverture et non-couvert

- **Couvert.** 30 tâches sur 97 cochées (S1/P0 + 25 %), commits, tests nommés (lus ; quelques tests node rejoués par les
  vérificateurs), code de `main`, décisions D-ADEV-*. Une sonde jouée sur le code de `main`. Rejeu en direct des specs
  `frontend/e2e/acceptation/adev.spec.js` et `adev2.spec.js` sur la pile locale : enregistrement
  `docs/audits/acceptation/ADEV/2026-11-04-e62ca97aa.md`, 16 étapes PASS sur 17, verdict **FAIL** à cause de P5.2 seule
  (voir §5) ; aucun oracle qa-explorer en échec.
- **Non couvert.** Les 67 autres tâches cochées ; aucun test Django exécuté par les vérificateurs (docker réservé à
  l'orchestrateur).
- **Statut du registre.** Après ce dépôt : 97 cochées sur 108 constructibles (ADEV106-114 ajoutées), contre-visite de
  clôture **avec 1 écart S1-S2** → statut calculé `audité` ; le cycle n'est pas sorti.

## 7. Coût

- 10 vérificateurs opus (effort élevé) : ≈ 1,9 M de jetons. 1 rédacteur opus (tâches ADEV et APRF) : ≈ 0,34 M.
- Orchestrateur : échantillon déterministe, triage des 30 verdicts, 1 sonde écrite et jouée, rejeu des specs, dossier.
- H0 S0 O11 F0 · jetons sous-agents ≈ 2,1 M

<!-- verifie | groupe: ADEV | pct: 97 | ecarts_s1_s2: 1 -->
