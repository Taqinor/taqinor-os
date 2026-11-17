# Plan de construction — SQUELETTE (`apps/taches`, `features/taches`, plan `docs/plans/PLAN_TACHES.md`, tâches `TCH<n>`) — révision 2

Statut : squelette ARCHITECTE, révision 2 (toutes les corrections de `verif-squelette.md` appliquées, référence 2.1,
maquettes du dossier au 17/11). **152 tâches** : 4 à l'atterrissage du plan (PR docs), 139 de construction
(F1 47, F2 47, F3 45), 9 acceptations en direct (3 en F2, 6 en F3). 30 lanes de construction + `orchestrateur` +
`acceptation`. 3 fusions vers `main` après l'atterrissage. Les rédacteurs de corps lisent CE fichier + la section citée
dans la colonne « source » ; les tests d'écran reprennent les chiffres de `docs/taches/maquettes/SCENARIO.md`.

**Qui construit ce plan (B4).** Seule la session qui tient la réservation `file:docs/plans/PLAN_TACHES.md`
(`python scripts/plan_claims.py claim file:docs/plans/PLAN_TACHES.md`) le construit ; une boucle « work on all plans »
qui ne l'a pas le saute. Les tâches de F2 commencent par `— [GATED: attend la fusion F1 sur main]`, celles de F3 par
`— [GATED: attend la fusion F2 sur main]` (`plan_lanes.py:760` : non constructibles) ; l'orchestrateur TCH retire le
marqueur d'une fusion au début de celle-ci, dans le commit de cette fusion (TCH47 pour F2, TCH94 pour F3).

**Vérifié dans cette session (révision 2).** Trois essais régénérés (`docs/taches/travail/essai-plan/essai-F{1,2,3}.md` :
fusions antérieures cochées, fusion en cours ouverte, fusions suivantes `[GATED]`), passés à `python scripts/plan_lanes.py
<essai> --workers 8 --wave-size 80`, AVEC et SANS `--group "Fusion Fk"` :
- F1 : 47 tâches, 13 lanes, 14 vagues (21 en révision 1), 0 refus, « 0 lane-pair(s) merged », makespan ~25 ;
  sans `--group` : identique, « 92 gated » (F2 + F3 exclus par `[GATED]`).
- F2 : 47 tâches, 9 lanes (8 en parallèle + orchestrateur), 7 vagues, 0 refus, 0 union ; sans `--group` : « 45 gated ».
- F3 : 45 tâches, 11 lanes, 15 vagues, 0 refus, 0 union ; acceptations listées « Acceptation (orchestrateur) — jamais en
  lane » (3 en F2, 6 en F3) ; `--check` sort 0.
- `check_taches_cablage.analyse()` sur les trois essais : FORME 1 23/23, 23/23, 11/11 créations conformes, 0 constat ;
  FORME 3 : la seule tâche mixte avec un `selectors.py` (TCH132) porte la clause de contrat.
- `check_plan_taches_mixtes.taches_mixtes()` : mixtes ouvertes = TCH131, TCH132 (les deux moitiés listées et touchées).
- Script de contrôle (scratchpad) : 0 `@after` inconnu ou vers une fusion ultérieure ; seul `FT/module.config.jsx`
  (append-only) est nommé par deux lanes d'une même fusion ; les 86 maquettes `*.html|*.css` du dossier (81 pages, 5 feuilles) sont toutes
  citées par au moins une tâche, aucune maquette citée n'est absente.
- Propriété : 574 déclarations (375 chemins distincts) résolues sur une copie du registre avec le bloc du §4 : taches 479,
  deploy 35, analyse 22, securite 13, parametres 7, hors racines 18 ; 0 hors des 5 propriétaires liés. Le vérificateur
  a obtenu `check_ownership.py` « OK » sur une copie (verif-squelette §0) ; non relancé ici.

**Format d'une ligne de plan** (`plan_lanes.py`, `check_taches_cablage.py`, `check_plan_taches_mixtes.py`) :
`- [ ] TCH<n> — [GATED: attend la fusion F<n-1> sur main] <titre>. Maquette qui fait foi : … Preuve : … Source : …
[Nouveau fichier car : … (`chemin`).] [Et l'écran est ATTEIGNABLE : route déclarée dans
`frontend/src/features/taches/module.config.jsx` (TCH43), entrée de nav à l'activation (TCH131).] [Contrat partagé : …]
[Code net : …] (ROUTINE|SCHEMA|AUTH — S|M|L) (@after: TCHx, TCHy) (@lane: taches/<lane>) (@model: …) Files: \`chemin\`, …`
- `Files:` en DERNIÈRE clause, chemins complets, jamais d'accolades ; `@model:` explicite partout ; `@lane: taches/<x>`
  (`taches` n'est pas dans `KNOWN_APPS`, `plan_lanes.py:305`), jamais `apps/` dans un nom de lane.
- Toute tâche qui nomme un fichier `frontend/src/` porte `@after: TCH15` (PACT11 : `urls.py` est le seul producteur,
  `plan_lanes.py:1375-1398` ; sans ce `@after`, 29 refus mesurés sans `--group`).
- `(@acceptation)` nu, sans `@after`, dans la sous-section `### Fk — acceptation en direct` de sa fusion.
- Sections : `## Atterrissage du plan …`, `## Fusion F1 — …`, `## Fusion F2 — …`, `## Fusion F3 — …` ; jamais un titre
  qui commence par GATED, MANUEL, DONE LOG, ALREADY LIVE (`plan_lanes.py:200`).
- Test neuf : « Nouveau fichier car : » + son chemin entre backticks sur la même ligne, sans id de tâche dans le nom.
- Écran ou composant `.jsx` sous `features/`/`pages/` : `module.config.jsx` dans `Files:` + clause ATTEIGNABLE.

**Règles de construction écrites dans l'en-tête du plan.**
1. Vues : `APIView` nues seulement (aucune `@api_view`, aucun `Generic*APIView` : `check_tenant_isolation.py:23-31`,
   `:71-82`) ; permission STRICTE `user.has_erp_permission('taches_voir')`, jamais le repli `_user_has_or_legacy`
   (`core/permissions.py:239-279`).
2. Aucun modèle neuf en F2 ou F3 hors TCH121 : un besoin de schéma → `[BLOCKED: schéma]`, il part avec TCH121.
3. Lanes `pur-*` : n'écrivent aucun `__init__.py` (créés par TCH4, TCH6) ; tests en `unittest.TestCase` sans base,
   lançables par `python -m unittest` depuis `backend/django_core` avant le fold du socle.
4. Aucune lane n'écrit `docs/openapi-schema.yml`, `docs/api-contracts.md`, `docs/rbac-endpoint-inventory.md`,
   `docs/CODEMAP.md` : les régénérations (TCH47, TCH94, TCH135) attendent la dernière tâche de CHAQUE lane de la fusion.
5. **Sous-vagues (M5).** Quand une lane dépend d'une autre lane de la même fusion (F1 : 0a → 0b → 0c ; F3 : B → C),
   l'orchestrateur pousse la branche d'intégration `dev-taches-F<k>` après le fold de la sous-vague ; le prompt de chaque
   lane de la sous-vague suivante commence par `git fetch origin && git checkout -B <lane> origin/dev-taches-F<k>` et
   vérifie `git merge-base --is-ancestor <sha du dernier fold> HEAD` avant d'écrire une ligne.
6. **Réservations (M10).** Avant chaque tâche qui touche un fichier d'un autre propriétaire :
   `plan_claims.py claim file:<chemin>` pour CHAQUE fichier étranger de ses `Files:` (une clé `app:` n'a pas de sens pour
   `scripts/`, `settings/` ou `providers/`) ; refus → la lane passe à sa tâche suivante sans étranger, ou rend la main ;
   les réservations sont rendues à la fusion (D-CLAIMS-MERGE), renouvelées à chaque réveil.

## 1. Découpage en fichiers

Abréviations : `T/` = `backend/django_core/apps/taches/`, `FT/` = `frontend/src/features/taches/`, `PT/` =
`frontend/src/pages/taches/`, `ST/` = `frontend/src/styles/taches/`, `FA/` = `frontend/src/api/`, `DJ/` =
`backend/django_core/`, `E2E/` = `frontend/e2e/`.

### 1.1 Fichiers-goulots : le choix tranché

| Goulot | Choix | Raison |
|---|---|---|
| `T/urls.py` + vues | **TCH15 seule** écrit `urls.py` complet (100 couples, `<int:id>`, `<str:cle>`) et crée `views/base.py` + 11 modules d'`APIView` dont chaque méthode lève `PasEncore` (une `APIException` à 501, jamais un `return`) ; TCH145-TCH147 posent les `@extend_schema` par domaine sans rouvrir `urls.py` | un seul producteur PACT11 ; aucun `Response({...}, status=501)` que `check_api_shapes.py:321-339` lirait comme une forme ; `check_openapi_schema.py --strict` (CI, base vide) n'a aucun cliquet : chaque opération doit avoir son schéma à la fin de F1 |
| `T/views/*.py` | 11 fichiers par domaine, créés par TCH15, remplis chacun par UNE lane en F2/F3 | jamais deux lanes d'une même fusion sur un fichier |
| `__init__.py` de paquet | écrits une fois (TCH4, TCH6, TCH12, TCH14, TCH15, TCH33), SANS ré-export ; on importe le sous-module | exception : `models/__init__.py`, rouvert une seule fois par TCH121 (F3) |
| `T/selectors/erp.py` | les liens ERP (`url_de_cible`, `libelle_de_cible`, `cible_visible`) dans le socle (TCH13), nom de donnees.md §5 ; les obligations et activités du jour dans `T/selectors/obligations.py` (lane journée, F2) | min. 15 |
| `FA/tachesApi.js` | complet dans TCH42 ; rouvert une seule fois en F3 par TCH100 (file hors ligne) | — |
| `FT/module.config.jsx` | routes complètes dans TCH43, sans nav, chaque route marquée `// contextuelle: module invisible jusqu'à TCH131 (A17)` ; append-only : les écrans le NOMMENT sans l'éditer ; nav ajoutée par TCH131 | `check_ecrans_atteignables.py` classe 3 |
| Pages et coquille | 12 pages vides + `FT/coquille/CoquilleTaches.jsx` + `FT/lib/enLigne.js` (`useEnLigne()`, M7) + `FT/fiche/Fiche.jsx` + `FT/saisie/FeuilleSaisie.jsx` créés par TCH43 | les écrans de F2 griseront hors ligne dès F2 |
| Composants `FT/ui/` créés en F1 | **montés dès F1** (B1) : LigneTache, CaseRonde, Etoile dans `PT/Aujourdhui.jsx` (liste vide) ; FeuilleACrans, SelecteurProjet, BarreSelection, BoutonCopilote, BandeauConflit et les hôtes de gestes dans la coquille (TCH44-TCH46, même lane, en série) | `check_ecrans_atteignables.py:46-48, :831-838` (classe 1), base qui ne grandit pas |
| Styles | `ST/base.css` + un fichier par zone créés et importés une fois par TCH41 | règle `index.css` du registre |
| Contrats `T/contract_samples/*.json` | 47 fichiers (api.md §6 rév. 2.1) dans la lane `contrats` (TCH2-TCH3), chacun `{endpoint, exemple, pourquoi}` ; aucun export dans `contractSamples.js` (lecteur générique `exempleContrat(app, nom)`, min. 2) | B2, PACT10 |
| Étapes de la nocturne | `T/nocturne.py` (TCH37) appelle des fonctions vides de `services/{journee,rythme,erp,purge}.py`, remplies en F2 ; `taches` ajouté à la garde « service sans appelant » (TCH151) | M8a |
| `T/sweeps.py` + beats | F3 seulement (TCH99) | aucune tâche planifiée sans travail réel en production |
| Fabriques de test | `T/tests/fabriques.py` (TCH9), lecture seule ensuite | — |
| Fichiers régénérés | lane `orchestrateur`, une tâche par fusion, `api-contracts.md` compris (M3) ; `--write` d'OpenAPI demande Django : sans lui sur l'hôte, artefact CI (`ci.yml:705-712`), un cycle de plus | M3, M4, min. 14 |

### 1.2 Arbre (hors échantillons JSON et tests)

| Fichier | Créé par (lane · fusion · tâche) | Rempli ensuite par |
|---|---|---|
| `T/__init__.py` | socle · F1 · TCH4 | — |
| `T/agent_actions.py` | assistant · F3 · TCH111 | — |
| `T/apps.py` | socle · F1 · TCH4 | erp (F2), final (F3) |
| `T/auth_jeton.py` | presence · F3 · TCH95 | — |
| `T/balayage.py` | presence · F3 · TCH98 | — |
| `T/choix.py` | socle · F1 · TCH6 | — |
| `T/confidentialite.py` | socle · F1 · TCH11 | — |
| `T/dsr.py` | erp · F2 · TCH74 | — |
| `T/migrations/0001_initial.py` | socle · F1 · TCH9 | — |
| `T/migrations/0002_agendaexterne.py` | agenda-externe · F3 · TCH121 | — |
| `T/migrations/__init__.py` | socle · F1 · TCH9 | — |
| `T/models/__init__.py` | socle · F1 · TCH7 | agenda-externe (F3) |
| `T/models/agenda.py` | agenda-externe · F3 · TCH121 | — |
| `T/models/base.py` | socle · F1 · TCH6 | — |
| `T/models/erp.py` | socle · F1 · TCH8 | — |
| `T/models/gestes.py` | socle · F1 · TCH8 | — |
| `T/models/journee.py` | socle · F1 · TCH8 | — |
| `T/models/presence.py` | socle · F1 · TCH8 | — |
| `T/models/projets.py` | socle · F1 · TCH7 | — |
| `T/models/rythme.py` | socle · F1 · TCH8 | — |
| `T/models/taches.py` | socle · F1 · TCH7 | — |
| `T/moteur/__init__.py` | socle · F1 · TCH6 | — |
| `T/moteur/classement.py` | pur-classement · F1 · TCH22 | — |
| `T/moteur/decalage.py` | pur-projets · F1 · TCH32 | — |
| `T/moteur/flux.py` | pur-classement · F1 · TCH24 | — |
| `T/moteur/gabarits.py` | pur-sollicitations · F1 · TCH30 | — |
| `T/moteur/recurrence.py` | pur-saisie · F1 · TCH10 | — |
| `T/moteur/rythme.py` | pur-rythme · F1 · TCH25 | — |
| `T/moteur/sante.py` | pur-projets · F1 · TCH31 | — |
| `T/moteur/sollicitations.py` | pur-sollicitations · F1 · TCH29 | — |
| `T/nocturne.py` | socle-services · F1 · TCH37 | — |
| `T/platform.py` | socle · F1 · TCH4 | assistant (F3) |
| `T/receivers.py` | erp · F2 · TCH71 | — |
| `T/saisie/__init__.py` | socle · F1 · TCH6 | — |
| `T/saisie/analyseur.py` | pur-saisie · F1 · TCH38 | — |
| `T/saisie/collage.py` | pur-saisie · F1 · TCH40 | — |
| `T/saisie/dates_pures.py` | socle · F1 · TCH6 | — |
| `T/saisie/grammaire.py` | pur-saisie · F1 · TCH38 | — |
| `T/saisie/normalisation.py` | socle · F1 · TCH6 | — |
| `T/saisie/plan.py` | pur-saisie · F1 · TCH40 | — |
| `T/selectors/__init__.py` | socle · F1 · TCH12 | — |
| `T/selectors/base.py` | socle · F1 · TCH12 | — |
| `T/selectors/erp.py` | socle · F1 · TCH13 | — |
| `T/selectors/journee.py` | journee · F2 · TCH54 | — |
| `T/selectors/obligations.py` | journee · F2 · TCH55 | — |
| `T/selectors/projets.py` | projets · F2 · TCH60 | — |
| `T/selectors/rythme.py` | rythme · F2 · TCH66 | — |
| `T/serializers/__init__.py` | socle · F1 · TCH14 | — |
| `T/serializers/erp.py` | erp · F2 · TCH72 | — |
| `T/serializers/formes.py` | socle · F1 · TCH14 | — |
| `T/serializers/journee.py` | journee · F2 · TCH56 | — |
| `T/serializers/presence.py` | presence · F3 · TCH95 | — |
| `T/serializers/projets.py` | projets · F2 · TCH60 | — |
| `T/serializers/rythme.py` | rythme · F2 · TCH66 | — |
| `T/serializers/saisie.py` | saisie · F2 · TCH48 | — |
| `T/services/__init__.py` | socle-services · F1 · TCH33 | — |
| `T/services/agenda_externe.py` | agenda-externe · F3 · TCH121 | — |
| `T/services/creation.py` | socle-services · F1 · TCH36 | — |
| `T/services/donnees.py` | erp · F2 · TCH74 | — |
| `T/services/erp.py` | socle-services · F1 · TCH37 | erp (F2) |
| `T/services/gestes.py` | socle-services · F1 · TCH33 | — |
| `T/services/journee.py` | socle-services · F1 · TCH37 | journee (F2) |
| `T/services/planification.py` | socle-services · F1 · TCH34 | — |
| `T/services/projets.py` | projets · F2 · TCH60 | — |
| `T/services/purge.py` | socle-services · F1 · TCH37 | erp (F2) |
| `T/services/rappels.py` | socle-services · F1 · TCH35 | — |
| `T/services/revelations.py` | socle-services · F1 · TCH36 | rythme (F2) |
| `T/services/rythme.py` | socle-services · F1 · TCH37 | rythme (F2) |
| `T/services/taches.py` | saisie · F2 · TCH49 | — |
| `T/sweeps.py` | presence · F3 · TCH99 | — |
| `T/throttles.py` | presence · F3 · TCH95 | — |
| `T/urls.py` | routes · F1 · TCH15 | — |
| `T/views/__init__.py` | routes · F1 · TCH15 | — |
| `T/views/agenda.py` | routes · F1 · TCH15 | journee (F2), agenda-externe (F3) |
| `T/views/agenda_externe.py` | routes · F1 · TCH15 | agenda-externe (F3) |
| `T/views/base.py` | routes · F1 · TCH15 | — |
| `T/views/donnees.py` | routes · F1 · TCH15 | erp (F2) |
| `T/views/erp.py` | routes · F1 · TCH15 | erp (F2) |
| `T/views/journee.py` | routes · F1 · TCH15 | journee (F2) |
| `T/views/presence.py` | routes · F1 · TCH15 | presence (F3) |
| `T/views/projets.py` | routes · F1 · TCH15 | projets (F2) |
| `T/views/reglages.py` | routes · F1 · TCH15 | rythme (F2) |
| `T/views/rythme.py` | routes · F1 · TCH15 | rythme (F2) |
| `T/views/saisie.py` | routes · F1 · TCH15 | saisie (F2) |
| `T/views/taches.py` | routes · F1 · TCH15 | saisie (F2) |
| `FA/tachesApi.js` | socle-front · F1 · TCH42 | presence-front (F3) |
| `FT/agenda/PlanifierSemaine.jsx` | ecran-agenda · F3 · TCH106 | — |
| `FT/agenda/VueMois.jsx` | ecran-agenda · F3 · TCH104 | — |
| `FT/atrier/TrierUneParUne.jsx` | ecran-saisie · F2 · TCH86 | — |
| `FT/aujourdhui/ColonneBureau.jsx` | ecran-agenda · F3 · TCH152 | — |
| `FT/aujourdhui/FeuilleAlleger.jsx` | ecran-aujourdhui · F2 · TCH79 | — |
| `FT/aujourdhui/FeuilleBilan.jsx` | ecran-aujourdhui · F2 · TCH80 | — |
| `FT/aujourdhui/LignesErp.jsx` | ecran-aujourdhui · F2 · TCH81 | — |
| `FT/aujourdhui/MenuJournee.jsx` | ecran-aujourdhui · F2 · TCH79 | final (F3) |
| `FT/aujourdhui/Progression.jsx` | ecran-aujourdhui · F2 · TCH77 | — |
| `FT/aujourdhui/Propose.jsx` | ecran-aujourdhui · F2 · TCH78 | — |
| `FT/aujourdhui/Replies.jsx` | ecran-aujourdhui · F2 · TCH81 | — |
| `FT/aujourdhui/Sections.jsx` | ecran-aujourdhui · F2 · TCH76 | — |
| `FT/cartes/CartesTaches.jsx` | cartes · F3 · TCH117 | — |
| `FT/coquille/CoquilleTaches.jsx` | socle-front · F1 · TCH43 | presence-front (F3) |
| `FT/fiche/Fiche.jsx` | socle-front · F1 · TCH43 | ecran-saisie (F2) |
| `FT/fiche/FichePlus.jsx` | ecran-saisie · F2 · TCH85 | — |
| `FT/horsligne/cacheJournee.js` | presence-front · F3 · TCH100 | — |
| `FT/horsligne/captureQueue.js` | presence-front · F3 · TCH100 | — |
| `FT/iphone/MonIphone.jsx` | ecran-reglages · F3 · TCH109 | — |
| `FT/iphone/scriptTuile.js` | ecran-reglages · F3 · TCH110 | — |
| `FT/lib/clavierListe.js` | socle-front · F1 · TCH46 | — |
| `FT/lib/enLigne.js` | socle-front · F1 · TCH43 | — |
| `FT/lib/gestes.js` | socle-front · F1 · TCH46 | — |
| `FT/lib/textes.js` | socle-front · F1 · TCH46 | — |
| `FT/module.config.jsx` | socle-front · F1 · TCH43 | ecran-aujourdhui (F2), ecran-saisie (F2), ecran-projets (F2), presence-front (F3), ecran-agenda (F3), ecran-reglages (F3), cartes (F3), final (F3) |
| `FT/presence/BoutonTachesIci.jsx` | presence-front · F3 · TCH102 | — |
| `FT/presence/CarteMesTaches.jsx` | presence-front · F3 · TCH103 | — |
| `FT/presence/TachesPresence.jsx` | presence-front · F3 · TCH102 | — |
| `FT/presence/cibleEcran.js` | presence-front · F3 · TCH102 | — |
| `FT/projets/Dialogues.jsx` | ecran-projets · F2 · TCH92 | — |
| `FT/projets/LigneProjet.jsx` | ecran-projets · F2 · TCH88 | — |
| `FT/projets/PlanifierProjet.jsx` | ecran-projets · F2 · TCH91 | — |
| `FT/projets/VueChronologie.jsx` | ecran-projets · F2 · TCH90 | — |
| `FT/projets/VueListe.jsx` | ecran-projets · F2 · TCH89 | — |
| `FT/reglages/Rubriques.jsx` | ecran-reglages · F3 · TCH108 | — |
| `FT/reglages/ViePrivee.jsx` | ecran-reglages · F3 · TCH108 | — |
| `FT/rythme/MesJours.jsx` | ecran-reglages · F3 · TCH107 | — |
| `FT/saisie/ColleListes.jsx` | ecran-saisie · F2 · TCH83 | — |
| `FT/saisie/FeuilleSaisie.jsx` | socle-front · F1 · TCH43 | ecran-saisie (F2) |
| `FT/ui/AnneauProgression.jsx` | ecran-aujourdhui · F2 · TCH77 | — |
| `FT/ui/ApercuListe.jsx` | ecran-saisie · F2 · TCH83 | — |
| `FT/ui/BandeauConflit.jsx` | socle-front · F1 · TCH46 | — |
| `FT/ui/BarreSelection.jsx` | socle-front · F1 · TCH45 | — |
| `FT/ui/BoutonCopilote.jsx` | socle-front · F1 · TCH45 | — |
| `FT/ui/CarteDuMoment.jsx` | ecran-aujourdhui · F2 · TCH77 | — |
| `FT/ui/CaseRonde.jsx` | socle-front · F1 · TCH44 | — |
| `FT/ui/ChampSaisie.jsx` | ecran-saisie · F2 · TCH82 | — |
| `FT/ui/Etoile.jsx` | socle-front · F1 · TCH44 | — |
| `FT/ui/FeuilleACrans.jsx` | socle-front · F1 · TCH45 | — |
| `FT/ui/GrilleAgenda.jsx` | ecran-agenda · F3 · TCH104 | — |
| `FT/ui/LigneTache.jsx` | socle-front · F1 · TCH44 | — |
| `FT/ui/SelecteurProjet.jsx` | socle-front · F1 · TCH45 | — |
| `FT/ui/SelecteurQuand.jsx` | ecran-saisie · F2 · TCH82 | — |
| `FT/ui/Tableau.jsx` | ecran-projets · F2 · TCH90 | — |
| `FT/ui/VoletAPlacer.jsx` | ecran-agenda · F3 · TCH105 | — |
| `FT/useBadgeTaches.js` | presence-front · F3 · TCH101 | — |
| `PT/ATrier.jsx` | socle-front · F1 · TCH43 | ecran-saisie (F2) |
| `PT/Agenda.jsx` | socle-front · F1 · TCH43 | ecran-agenda (F3) |
| `PT/Aujourdhui.jsx` | socle-front · F1 · TCH43 | ecran-aujourdhui (F2), ecran-agenda (F3) |
| `PT/Projet.jsx` | socle-front · F1 · TCH43 | ecran-projets (F2) |
| `PT/Projets.jsx` | socle-front · F1 · TCH43 | ecran-projets (F2) |
| `PT/ProjetsArchive.jsx` | socle-front · F1 · TCH43 | ecran-projets (F2) |
| `PT/ProjetsModeles.jsx` | socle-front · F1 · TCH43 | ecran-projets (F2) |
| `PT/Recherche.jsx` | socle-front · F1 · TCH43 | ecran-saisie (F2) |
| `PT/Reglages.jsx` | socle-front · F1 · TCH43 | ecran-reglages (F3) |
| `PT/Revue.jsx` | socle-front · F1 · TCH43 | ecran-projets (F2) |
| `PT/Rythme.jsx` | socle-front · F1 · TCH43 | ecran-reglages (F3) |
| `PT/Supprimees.jsx` | socle-front · F1 · TCH43 | ecran-saisie (F2) |
| `ST/agenda.css` | socle-front · F1 · TCH41 | ecran-agenda (F3) |
| `ST/base.css` | socle-front · F1 · TCH41 | — |
| `ST/coeur.css` | socle-front · F1 · TCH41 | ecran-aujourdhui (F2), ecran-agenda (F3) |
| `ST/presence.css` | socle-front · F1 · TCH41 | presence-front (F3) |
| `ST/projets.css` | socle-front · F1 · TCH41 | ecran-projets (F2) |
| `ST/reglages.css` | socle-front · F1 · TCH41 | ecran-reglages (F3) |
| `ST/saisie.css` | socle-front · F1 · TCH41 | ecran-saisie (F2) |

`T/contract_samples/` : 47 JSON + `README.md` (lane `contrats`). Pas d'`admin.py`.

### 1.3 Modules de test (un par domaine ; neufs ⇒ « Nouveau fichier car : »)

| Lane (fusion) | Modules |
|---|---|
| socle (F1) | `__init__.py`, `fabriques.py`, `test_confidentialite.py`, `test_formes.py`, `test_modeles.py`, `test_normalisation.py`, `test_selecteurs.py`, `test_socle.py` |
| agenda-externe (F3) | `test_agenda_externe.py` |
| assistant (F3) | `test_agent_actions.py` |
| journee (F2) | `test_api_agenda.py`, `test_api_journee.py` |
| projets (F2) | `test_api_projets.py`, `test_api_revue.py` |
| rythme (F2) | `test_api_reglages.py`, `test_api_rythme.py`, `test_nocturne_rythme.py` |
| saisie (F2) | `test_api_saisie.py`, `test_api_taches.py` |
| presence (F3) | `test_balayage.py`, `test_capture.py`, `test_flux_tuile.py`, `test_jetons.py` |
| final (F3) | `test_canari.py`, `test_meme_proprietaire.py`, `test_plafonds.py`, `taches-a11y.spec.js`, `taches-journee.spec.js`, `taches-projets.spec.js`, `taches-saisie.spec.js` |
| pur-classement (F1) | `test_classement.py`, `test_flux_pur.py` |
| socle-services (F1) | `test_creation.py`, `test_gestes.py`, `test_nocturne.py`, `test_planification.py`, `test_rappels.py` |
| pur-projets (F1) | `test_decalage.py`, `test_sante.py` |
| erp (F2) | `test_donnees.py`, `test_erp.py`, `test_suggestions.py` |
| pur-sollicitations (F1) | `test_gabarits.py`, `test_sollicitations_pures.py` |
| pur-saisie (F1) | `test_recurrence.py`, `test_saisie_pure.py` |
| routes (F1) | `test_routes.py` |
| pur-rythme (F1) | `test_rythme_pur.py` |
| socle-front (F1) | `tachesApi.test.js`, `gestes.test.js`, `textes.test.js`, `routes.test.jsx`, `LigneTache.test.jsx`, `composants.test.jsx` |
| ecran-agenda (F3) | `PlanifierSemaine.test.jsx`, `ColonneBureau.test.jsx`, `VoletAPlacer.test.jsx`, `Agenda.test.jsx` |
| ecran-aujourdhui (F2) | `FeuilleAlleger.test.jsx`, `FeuilleBilan.test.jsx`, `LignesErp.test.jsx`, `Propose.test.jsx`, `CarteDuMoment.test.jsx`, `Aujourdhui.test.jsx` |
| cartes (F3) | `CartesTaches.test.jsx` |
| ecran-saisie (F2) | `Fiche.test.jsx`, `FichePlus.test.jsx`, `FeuilleSaisie.test.jsx`, `ApercuListe.test.jsx`, `ATrier.test.jsx`, `Recherche.test.jsx` |
| presence-front (F3) | `captureQueue.test.js`, `CarteMesTaches.test.jsx`, `TachesPresence.test.jsx`, `useBadgeTaches.test.js` |
| ecran-reglages (F3) | `MonIphone.test.jsx`, `scriptTuile.test.js`, `Reglages.test.jsx`, `Rythme.test.jsx` |
| ecran-projets (F2) | `Dialogues.test.jsx`, `PlanifierProjet.test.jsx`, `VueChronologie.test.jsx`, `Projet.test.jsx`, `Projets.test.jsx`, `Revue.test.jsx` |

Tests ajoutés à un module EXISTANT d'un autre propriétaire : `DJ/apps/records/tests.py`, `DJ/authentication/tests_recovery.py`,
`DJ/authentication/tests_ntmob6_mobile_home_route.py`, `DJ/core/tests/test_registre_traitements.py`,
`DJ/apps/notifications/tests.py`, `DJ/apps/roles/tests.py`, `DJ/apps/agent/tests/test_registry.py`,
`scripts/tests/test_check_services_appeles_constantes.py`, `backend/fastapi_ia/tests/{test_prompt_copilote,test_action_tools,
test_sql_agent_endpoint,test_eval_harness}.py`, `frontend/src/features/ia/{cartes/cartes.test.jsx,copilotMessages.test.mjs}`,
`frontend/src/components/layout/{Header,BottomTabBar}.test.jsx`, `frontend/src/lib/apps/useAppBadges.test.jsx`,
`frontend/src/providers/{commandActions.test.mjs,focusedRecordShortcuts.test.jsx}`, `frontend/src/lib/search/entityRoutes.test.jsx`,
`frontend/src/features/pwa/shortcuts.test.mjs`, `frontend/src/pages/Dashboard.cockpit.test.jsx`,
`frontend/src/features/offlinesync/mobile/CockpitHome.test.jsx`, `frontend/src/features/uxviews/quickcreate/quickCreateEvents.test.mjs`.

### 1.4 Ce qui part sur `main` dans `docs/taches/` (TCH150)

`docs/taches/reference/` · `docs/taches/maquettes/*.html`, `*.css`, `SCENARIO.md`, `outils/capturer.cjs` ·
`docs/taches/README.md`. Jamais : `docs/taches/travail/` (ce fichier compris : `PLAN_TACHES.md` en est la mise au propre),
`docs/taches/maquettes/captures/`.

## 2. Lanes, vagues, fusions

### 2.1 Atterrissage puis trois fusions

| Étape | Contenu | Tâches | Effet en production |
|---|---|---|---|
| **Atterrissage** (PR docs, ~2 min de CI) | `PLAN_TACHES.md`, bloc `ownership.yml` (TCH1), mémoire D-TCH (TCH148), README (TCH149), nettoyage (TCH150) | 4, cochées à la fusion | aucun |
| **F1 — socle** | contrats, échafaudage (`installable: False`), 19 modèles + 0001, sélecteurs, confidentialité, services centraux, routes 501 + schémas, coquille et composants montés, 9 modules purs, `records`, traces, garde des services | 47 | **invisible** : tables vides, aucun beat, aucun type de notification, rien au catalogue des Applications, 403 pour tout compte (rôle fin ou non) sauf superutilisateur (`authentication/models.py:519`) ; seule trace : la case `taches_voir` dans l'éditeur de rôles (§7, non résolu) |
| **F2 — vague A** | 5 domaines serveur + 3 groupes d'écrans, 8 lanes | 47 + 3 acceptations | invisible (receivers muets : `taches_voir` + `ReglagesRythme` requis) |
| **F3 — vagues B puis C** | présence, types de notification, registre, hors ligne, pastille, agenda, rythme/réglages/iPhone, assistant, cartes, agenda externe ; puis coquille ERP, canari, balayage, plafonds, octroi + nav, e2e | 45 + 6 acceptations | **visible** à TCH130-TCH132 |

Pourquoi trois : PACT10 (le contrat seul sur `main` avant les moitiés) ; WOW23 (une fusion ≈ 80 tâches, jamais plus de
~100 non fusionnées) ; une CI rouge ne bloque qu'une fusion ; A17 (l'activation et ses e2e isolées en F3). Les
dépendances entre lanes d'une même fusion passent par la branche d'intégration (règle 5), pas par `main`.

Commandes : `python scripts/plan_lanes.py docs/plans/PLAN_TACHES.md --workers 8 --wave-size 80 --group "Fusion F<k>"`
(le `[GATED]` rend `--group` redondant, il reste conseillé). Une fusion = une PR, une CI, `gh pr merge --auto --merge`.
`docs/BUILD_ORDER.yml` ne connaît pas TCH.

### 2.2 Les lanes

Modèle : `sonnet` par défaut ; `opus` = jeton, vie privée, sélecteurs de visibilité, droits, assistant, unité `securite`,
URL externe, créateur unique ; `haiku` = régénérations et docs. Modèle d'une lane = sa tâche la plus risquée.

| Lane (`@lane:`) | Fusion · sous-vague | Tâches | Modèle |
|---|---|---|---|
| `taches/orchestrateur` | F0·—, F1·fin, F2·fin, F3·fin | TCH1, TCH148, TCH149, TCH150, TCH47, TCH94, TCH135 (7) | haiku |
| `taches/contrats` | F1·0a | TCH2, TCH3 (2) | sonnet |
| `taches/socle` | F1·0a | TCH4, TCH5, TCH6, TCH7, TCH8, TCH9, TCH11, TCH12, TCH13, TCH14 (10) | opus |
| `taches/routes` | F1·0b | TCH15, TCH145, TCH146, TCH147 (4) | opus |
| `taches/etranger-securite` | F1·0a | TCH16, TCH17, TCH18 (3) | opus |
| `taches/etranger-gardes` | F1·0a | TCH151 (1) | sonnet |
| `taches/pur-classement` | F1·0a | TCH22, TCH23, TCH24 (3) | sonnet |
| `taches/pur-rythme` | F1·0a | TCH25, TCH26, TCH27, TCH28 (4) | sonnet |
| `taches/pur-sollicitations` | F1·0a | TCH29, TCH30 (2) | sonnet |
| `taches/pur-projets` | F1·0a | TCH31, TCH32 (2) | sonnet |
| `taches/pur-saisie` | F1·0b | TCH10, TCH38, TCH39, TCH40 (4) | sonnet |
| `taches/socle-services` | F1·0b | TCH33, TCH34, TCH35, TCH36, TCH37 (5) | opus |
| `taches/socle-front` | F1·0c | TCH41, TCH42, TCH43, TCH44, TCH45, TCH46 (6) | sonnet |
| `taches/saisie` | F2·A | TCH48, TCH49, TCH50, TCH51, TCH52, TCH53 (6) | sonnet |
| `taches/journee` | F2·A | TCH54, TCH55, TCH56, TCH57, TCH58, TCH59 (6) | opus |
| `taches/projets` | F2·A | TCH60, TCH61, TCH62, TCH63, TCH64, TCH65 (6) | sonnet |
| `taches/rythme` | F2·A | TCH66, TCH67, TCH68, TCH69, TCH70 (5) | opus |
| `taches/erp` | F2·A | TCH71, TCH72, TCH73, TCH74, TCH75 (5) | opus |
| `taches/ecran-aujourdhui` | F2·A | TCH76, TCH77, TCH78, TCH79, TCH80, TCH81 (6) | sonnet |
| `taches/ecran-saisie` | F2·A | TCH82, TCH83, TCH84, TCH85, TCH86, TCH87 (6) | sonnet |
| `taches/ecran-projets` | F2·A | TCH88, TCH89, TCH90, TCH91, TCH92, TCH93 (6) | sonnet |
| `taches/acceptation` | F2·acc, F3·acc | TCH136, TCH137, TCH138, TCH139, TCH140, TCH141, TCH142, TCH143, TCH144 (9) | opus |
| `taches/presence` | F3·B | TCH95, TCH96, TCH97, TCH20, TCH21, TCH98, TCH99 (7) | opus |
| `taches/presence-front` | F3·B | TCH100, TCH101, TCH102, TCH103 (4) | sonnet |
| `taches/ecran-agenda` | F3·B | TCH104, TCH105, TCH106, TCH152 (4) | sonnet |
| `taches/ecran-reglages` | F3·B | TCH107, TCH108, TCH109, TCH110 (4) | sonnet |
| `taches/assistant` | F3·B | TCH111, TCH112, TCH113, TCH114, TCH115, TCH116 (6) | opus |
| `taches/cartes` | F3·B | TCH117, TCH118 (2) | sonnet |
| `taches/etranger-deploy` | F3·B | TCH119, TCH120, TCH19 (3) | opus |
| `taches/agenda-externe` | F3·B | TCH121, TCH122 (2) | opus |
| `taches/etranger-coquille` | F3·C | TCH123, TCH124, TCH125, TCH126 (4) | sonnet |
| `taches/final` | F3·C | TCH127, TCH128, TCH129, TCH130, TCH131, TCH132, TCH133, TCH134 (8) | opus |

Dépendances entre lanes : F1 0b (`routes`, `pur-saisie`, `socle-services`) attend `socle` ; 0c (`socle-front`) attend
`contrats` et `routes` ; F2 n'attend que F1 ; F3 B attend F1-F2 ; `etranger-coquille` attend `presence-front` ; `final`
attend toutes les lanes de B. Équilibre mesuré (LPT) : makespan F1 ~25, F2 ~20, F3 ~20.

## 3. Les tâches, dans l'ordre de construction

Colonnes = le format demandé ; dans le plan, `Files:` passe en dernière clause et les tâches F2/F3 commencent par leur
`[GATED]`. Chaque preuve est un test COMPORTEMENTAL rouge d'abord, jamais une regex sur le source ; aucune preuve ne
mesure une mise en page dans jsdom (44 px, 130 %, colonne de bureau : TCH134, Playwright).

| ID | Ce que ça livre (· maquettes qui font foi) | Fusion | Lane | Files | @after | Modèle | Preuve | Source |
|---|---|---|---|---|---|---|---|---|
| TCH1 | Déclarer le propriétaire `taches` et lier PLAN_TACHES à ses 5 propriétaires (bloc owners + ligne plans:) | F0·— | `taches/orchestrateur` | `docs/ownership.yml` | — | haiku | `python scripts/check_ownership.py` vert avec PLAN_TACHES.md ; `--owner-of backend/django_core/apps/taches/models/taches.py` → taches | brief-r1 §2 governance ; A8 ; socle §1 |
| TCH148 | Mémoire partagée : un fichier des décisions fondateur D-TCH-1 à D-TCH-5 (+ où vivent la référence et le plan) et sa ligne d'index | F0·— | `taches/orchestrateur` | `docs/claude-memory/taches-decisions-fondateur.md`, `docs/claude-memory/MEMORY.md` | — | haiku | le fichier cite socle §0 mot pour mot ; une ligne ajoutée à MEMORY.md, aucune autre touchée ; aucun secret | socle §0 ; CLAUDE.md « Shared Claude memory » |
| TCH149 | Dossier de la fonctionnalité `docs/taches/README.md` : ce que c'est, où sont la référence, les maquettes et le scénario, comment l'essayer (pile locale, superutilisateur avant l'activation), gestes du fondateur | F0·— | `taches/orchestrateur` | `docs/taches/README.md` | — | haiku | chaque chemin cité existe sur la branche d'atterrissage ; gestes du fondateur = liste de §7 du squelette (raccourci Siri, `.env` prod, VAPID) | socle §0 ; spec-7 §12 ; A14-M5 ; api.md §9 |
| TCH150 | Nettoyage avant `main` : `docs/taches/travail/` et `docs/taches/maquettes/captures/` retirés de la branche d'atterrissage ; restent `docs/taches/reference/`, les maquettes `*.html`, `*.css`, `SCENARIO.md`, `outils/capturer.cjs` et le README | F0·— | `taches/orchestrateur` | — | — | haiku | `git diff --name-only origin/main...HEAD -- docs/taches` ne liste que reference/, maquettes/*.html\|css\|SCENARIO.md, maquettes/outils/, README.md | consigne de l'orchestrateur (révision 2) ; consignes.md |
| TCH2 | Contrat d'abord (1/2) : 21 échantillons (journée, saisie, gestes, agenda, recherche, formes) enveloppés `{endpoint, exemple, pourquoi}` ; chaque forme reçoit la route qui la renvoie (item → GET taches/, tache → GET taches/{id}/, tache_ecrite → POST taches/{id}/terminer/, carte_du_moment → POST vu/) + index README | F1·0a | `taches/contrats` | `T/contract_samples/aujourdhui.json`, `T/contract_samples/carte_du_moment.json`, `T/contract_samples/ailleurs.json`, `T/contract_samples/badge.json`, `T/contract_samples/vu.json`, `T/contract_samples/item.json`, `T/contract_samples/tache.json`, `T/contract_samples/tache_ecrite.json`, `T/contract_samples/tache_changement.json`, `T/contract_samples/saisie_apercu.json`, `T/contract_samples/saisie_rapide.json`, `T/contract_samples/capture.json`, `T/contract_samples/lot.json`, `T/contract_samples/lier_activite.json`, `T/contract_samples/geste_annuler.json`, `T/contract_samples/gestes.json`, `T/contract_samples/supprimees.json`, `T/contract_samples/journee_proposition.json`, `T/contract_samples/journee_cloture.json`, `T/contract_samples/agenda.json`, `T/contract_samples/recherche.json`, `T/contract_samples/README.md` | — | sonnet | `python scripts/check_api_shapes.py` vert ; chaque fichier = `{endpoint, exemple, pourquoi}` (modèle `apps/adsengine/contract_samples/engine_action_erreur.json`), `exemple` = l'exemple d'api.md mot pour mot | api.md §1-§4, §6 (rév. 2.1) ; PACT10 |
| TCH3 | Contrat d'abord (2/2) : 26 échantillons (projets, rythme, réglages, présence, ERP, listes simples de la rév. 2.1) enveloppés ; proposition → POST rythme/propositions/{id}/repondre/, erreurs → PATCH taches/{id}/ (409), liens_cibles → GET taches/{id}/ ; déclaration « posés avant leur vue » si la garde l'exige | F1·0a | `taches/contrats` | `T/contract_samples/projets_liste.json`, `T/contract_samples/projet_vue.json`, `T/contract_samples/planification_apercu.json`, `T/contract_samples/decalage.json`, `T/contract_samples/modele_instancier.json`, `T/contract_samples/revue_projets.json`, `T/contract_samples/rythme.json`, `T/contract_samples/proposition.json`, `T/contract_samples/reglages.json`, `T/contract_samples/jeton.json`, `T/contract_samples/tuile.json`, `T/contract_samples/suggestions.json`, `T/contract_samples/convertir_activite.json`, `T/contract_samples/coach_entete.json`, `T/contract_samples/liens_cibles.json`, `T/contract_samples/erreurs.json`, `T/contract_samples/agenda_externe.json`, `T/contract_samples/etiquettes.json`, `T/contract_samples/vues.json`, `T/contract_samples/modeles_liste.json`, `T/contract_samples/jetons_liste.json`, `T/contract_samples/rappel_repeter.json`, `T/contract_samples/revue_decision.json`, `T/contract_samples/projet_ecrit.json`, `T/contract_samples/mes_donnees.json`, `T/contract_samples/tout_effacer.json`, `T/contract_samples/README.md`, `scripts/check_api_shapes.py` | TCH2 | sonnet | `python scripts/check_api_shapes.py` vert ; chaque fichier = `{endpoint, exemple, pourquoi}` (modèle `apps/adsengine/contract_samples/engine_action_erreur.json`), `exemple` = l'exemple d'api.md mot pour mot ; 47 fichiers au total | api.md §3.3-§3.4, §4, §6 ; A3 |
| TCH4 | Échafauder l'app : `startapp_erp taches`, manifeste (clé taches, `installable: False` jusqu'à TCH131), INSTALLED_APPS, platform.py honnête (aucune surface), pas d'admin.py, `tests/__init__.py` | F1·0a | `taches/socle` | `T/__init__.py`, `T/apps.py`, `T/platform.py`, `DJ/erp_agentique/settings/base.py`, `T/tests/__init__.py`, `T/tests/test_socle.py` | — | sonnet | `test_socle.py` : manifeste collecté non installable (absent du catalogue des Applications) ; `check_modules.py`, `check_platform.py` verts ; aucun admin enregistré | module-playbook §8 points ; donnees.md §6 L0 ; socle §2.2-§2.4 ; verif-squelette M2 |
| TCH5 | Déclarer le droit `taches_voir` EN FIN de liste (+ PERMISSION_MODULE) sans l'accorder à aucun rôle | F1·0a | `taches/socle` | `DJ/apps/roles/permissions_registre.py`, `T/tests/test_socle.py` | TCH4 | opus | `test_socle.py` : aucun rôle système ne le porte (invariant 28) ; golden `registre_permissions.json` (sous-suite ordonnée, `apps/roles/tests_spl300_registre_golden.py`) inchangé et vert | socle §8 Droits ; A17 ; donnees.md inv. 28 |
| TCH6 | Énumérations fermées (`choix.py`, dont CarteDuMoment avec `pause`), mixin `__str__` neutre, paquets `saisie/` et `moteur/` (leurs `__init__.py`), normalisation et dates pures | F1·0a | `taches/socle` | `T/choix.py`, `T/models/base.py`, `T/saisie/__init__.py`, `T/saisie/normalisation.py`, `T/saisie/dates_pures.py`, `T/moteur/__init__.py`, `T/tests/test_normalisation.py` | TCH4 | sonnet | `test_normalisation.py` : table regles.md §1.1 (longueur égale, İ/ẞ), cle_nom ; `check_choices_declares.py` | donnees.md §1 (rév. 2.1), règles transverses ; regles.md §1.1, §1.12 |
| TCH7 | Modèles Projet, Section, Tache, ElementChecklist, Etiquette, EtiquetteTache, RegleRecurrence (contraintes, index, nom_cle dans save, CheckConstraint condition=) | F1·0a | `taches/socle` | `T/models/__init__.py`, `T/models/projets.py`, `T/models/taches.py`, `T/tests/test_modeles.py` | TCH6 | sonnet | `test_modeles.py` : unicités company-first + is_deleted, deux CheckConstraint, bulk_create refusé sur nom_cle | donnees.md §2.1-§2.7, inv. 15-16 |
| TCH8 | Modèles PlanJour, LignePlanJour, ReglagesRythme, Preference, IncitationCoach, Rappel, JetonAcces, GesteAnnulable, VueEnregistree, ModeleProjet, RevueProjet, SuggestionTache | F1·0a | `taches/socle` | `T/models/__init__.py`, `T/models/journee.py`, `T/models/rythme.py`, `T/models/presence.py`, `T/models/erp.py`, `T/models/gestes.py`, `T/tests/test_modeles.py` | TCH7 | sonnet | `test_modeles.py` : contraintes §2.8-§2.19, défauts appelables, 11 clés Preference | donnees.md §2.8-§2.19 |
| TCH9 | Migration `0001_initial` (19 modèles, AgendaExterne exclu) + fabriques de test partagées (lecture seule ensuite) | F1·0a | `taches/socle` | `T/migrations/__init__.py`, `T/migrations/0001_initial.py`, `T/tests/fabriques.py`, `T/tests/test_modeles.py` | TCH8 | sonnet | `makemigrations --check` vide ; `check_on_delete.py`, `check_unique_scoping.py`, `check_company_fk.py`, `check_safe_migrations.py` verts ; noms d'index ≤ 30 | donnees.md §6.1 |
| TCH11 | Confidentialité unique : est_confidentielle (héritage 4 voies) et nom_pour(obj, usage) pour écran, assistant, flux, tuile, notification | F1·0a | `taches/socle` | `T/confidentialite.py`, `T/tests/test_confidentialite.py` | TCH8 | opus | `test_confidentialite.py` : table regles.md §8 (5 usages × 4 colonnes) | regles.md §8 ; donnees.md inv. 8 ; A6 ; socle §2.6-§2.8 |
| TCH12 | Sélecteur unique : taches_de & co (société ET propriétaire), jours_travailles_de, prochain_jour_travaille, filtrer_q (assistant=True sans notes ni confidentielles) | F1·0a | `taches/socle` | `T/selectors/__init__.py`, `T/selectors/base.py`, `T/tests/test_selecteurs.py` | TCH11 | opus | `test_selecteurs.py` : deux sociétés, deux comptes ; jours travaillés − congés ; IR17 | donnees.md §5 ; socle §2.1 ; regles.md §0 |
| TCH13 | Liens ERP vérifiés dans `selectors/erp.py` (nom de donnees.md §5) : url_de_cible, libelle_de_cible, cible_visible pour lead, client, devis par les sélecteurs de visibilité des apps cibles | F1·0a | `taches/socle` | `T/selectors/erp.py`, `T/tests/test_selecteurs.py` | TCH12 | opus | `test_selecteurs.py` : commercial hors portée → invisible ; cible hors CibleLiable → refus ; `lint-imports` vert | donnees.md §5, inv. 23 ; A3 ; spec-6a crit. 1-2 |
| TCH14 | Formes partagées sérialisées une seule fois : ITEM (tâche ET activité ERP), TACHE, TACHE_ECRITE, PROJET, PROPOSITION, LIEN | F1·0a | `taches/socle` | `T/serializers/__init__.py`, `T/serializers/formes.py`, `T/tests/test_formes.py` | TCH13 | sonnet | `test_formes.py` : chaque forme rend exactement les clés de l'`exemple` de `item.json`, `tache.json`, `tache_ecrite.json`, `projets_liste.json`, `proposition.json` (contrat partagé) | api.md §1 ; donnees.md inv. 8 |
| TCH15 | Toutes les routes déclarées d'un coup : include `taches/`, urls.py complet (100 couples, convertisseurs `<int:id>`, `<str:cle>`), `views/base.py` (exception PasEncore à 501 levée, jamais un `return` ; permission STRICTE `has_erp_permission('taches_voir')`), 11 modules de vues en `APIView` nues | F1·0b | `taches/routes` | `T/urls.py`, `DJ/erp_agentique/urls.py`, `T/views/__init__.py`, `T/views/base.py`, `T/views/saisie.py`, `T/views/taches.py`, `T/views/journee.py`, `T/views/agenda.py`, `T/views/projets.py`, `T/views/rythme.py`, `T/views/reglages.py`, `T/views/presence.py`, `T/views/erp.py`, `T/views/donnees.py`, `T/views/agenda_externe.py`, `T/tests/test_routes.py` | TCH5 | opus | `test_routes.py` : les 100 routes résolvent ; 403 sans `taches_voir`, y compris pour un compte SANS rôle fin et responsable (repli `_user_has_or_legacy` refusé) ; 501 avec ; routes J:x → 401 ; `check_tenant_isolation.py`, `check_viewset_model_scope.py`, `check_api_shapes.py` verts | api.md §0, §3 ; MAJ-10 ; verif-squelette B3, M1, M9 |
| TCH145 | Schémas OpenAPI des routes journée, agenda, recherche, saisie et tâches (§3.1-§3.2) : `@extend_schema(request=, responses=, parameters=)` sur chaque opération | F1·0b | `taches/routes` | `T/views/journee.py`, `T/views/agenda.py`, `T/views/saisie.py`, `T/views/taches.py`, `T/views/erp.py`, `T/tests/test_routes.py` | TCH15 | sonnet | `test_routes.py` : chaque opération de ces modules porte un schéma ; `check_openapi_schema.py --strict` sans avertissement (artefact CI si Django absent de l'hôte) | api.md §0 OpenAPI, §3.1-§3.2 ; verif-squelette B3 |
| TCH146 | Schémas OpenAPI des routes projets, étapes, modèles et revue (§3.3) | F1·0b | `taches/routes` | `T/views/projets.py`, `T/tests/test_routes.py` | TCH145 | sonnet | `check_openapi_schema.py --strict` sans avertissement sur views/projets.py | api.md §3.3 ; verif-squelette B3 |
| TCH147 | Schémas OpenAPI des routes rythme, réglages, iPhone, données, agenda externe (§3.4) ; types `text/calendar` et `text/plain` déclarés | F1·0b | `taches/routes` | `T/views/rythme.py`, `T/views/reglages.py`, `T/views/presence.py`, `T/views/donnees.py`, `T/views/agenda_externe.py`, `T/tests/test_routes.py` | TCH146 | sonnet | `check_openapi_schema.py --strict` sans avertissement sur les 100 opérations | api.md §0, §3.4 ; verif-squelette B3 |
| TCH16 | Lecture des activités ERP pour Tâches : nouveau `records/selectors.py` (activites_ouvertes_pour, nb_a_faire_personnels, peut_cloturer_activites) | F1·0a | `taches/etranger-securite` | `DJ/apps/records/selectors.py`, `DJ/apps/records/tests.py` | — | opus | `apps/records/tests.py` : à-faire créé par A assigné à B absent chez B ; peut_cloturer == (POST done ≠ 403) par rôle système | donnees.md §5 (étrangers) ; spec-6a §9, crit. 6-7 |
| TCH17 | Clôture d'un à-faire personnel converti : `records/services.py` cloturer_a_faire_personnel, rouvrir_a_faire_personnel | F1·0a | `taches/etranger-securite` | `DJ/apps/records/services.py`, `DJ/apps/records/tests.py` | TCH16 | opus | `apps/records/tests.py` : clôture idempotente, réouverture, refus hors créateur | spec-6a §5, §9 ; donnees.md inv. 30 |
| TCH18 | Exclure `taches` du décompte des traces d'un compte (`_traces_du_compte`), sans effet visible tant qu'aucune tâche n'existe | F1·0a | `taches/etranger-securite` | `DJ/authentication/views.py`, `DJ/authentication/tests_recovery.py` | — | opus | `authentication/tests_recovery.py` (test ASUP5) étendu : 40 tâches seules → '' | socle §8 cycle de vie ; spec-6a crit. 13 ; donnees.md inv. 26 |
| TCH151 | Surveiller `taches` dans la garde « service sans appelant » : `"taches"` ajouté à APPS_SURVEILLEES et à son test de constantes | F1·0a | `taches/etranger-gardes` | `scripts/check_services_appeles.py`, `scripts/tests/test_check_services_appeles_constantes.py` | — | sonnet | `python scripts/check_services_appeles.py` vert ; `scripts/tests/test_check_services_appeles_constantes.py` vert | verif-squelette M8a ; CALX57 |
| TCH22 | Classement pur : cle_tri (ordre total strict, projet de la semaine, activité priorité 0) et placer (premier cas vrai) | F1·0a | `taches/pur-classement` | `T/moteur/classement.py`, `T/tests/test_classement.py` | — | sonnet | `test_classement.py` (unittest pur, sans base) : jeu de test regles.md §3.3 (300/300) et §4.2 | regles.md §3.1-§3.3, §4.2 |
| TCH23 | Proposé pur : proposer_plan (N = objectif − faites − gardées ouvertes), explication (3 faits), capacite (temps disponible) | F1·0a | `taches/pur-classement` | `T/moteur/classement.py`, `T/tests/test_classement.py` | TCH22 | sonnet | `test_classement.py` : cas §3.4-§3.6, journée allégée IR10 | regles.md §3.4-§3.6, §4.4 |
| TCH24 | Flux et tuile purs : evenements_flux (8 journées entières puis « + N autres », 200 au plus, UID) et tuile_pure (top 6, reste, prochaine échéance) | F1·0a | `taches/pur-classement` | `T/moteur/flux.py`, `T/tests/test_flux_pur.py` | TCH23 | sonnet | `test_flux_pur.py` : règles regles.md §10 (exclusions, plafonds, IR15) | regles.md §10 ; donnees.md inv. 12 |
| TCH25 | Rythme pur (1/4) : compte_du_jour, statut_jour, journee_reussie, arrondir (demie vers le bas), plafonner_jours | F1·0a | `taches/pur-rythme` | `T/moteur/rythme.py`, `T/tests/test_rythme_pur.py` | — | sonnet | `test_rythme_pur.py` : tables spec-5a §6 (compte, statut, journée réussie) ; arrondir | regles.md §0, §6.1-§6.4 |
| TCH26 | Rythme pur (2/4) : En faire plus — palier_initial, evaluer_bloc, clore_bloc, objectif_dit, objectif_affiche (+ zone en tenir) | F1·0a | `taches/pur-rythme` | `T/moteur/rythme.py`, `T/tests/test_rythme_pur.py` | TCH25 | sonnet | `test_rythme_pur.py` : 5/10 monter, ≤ 3/10 baisser, plancher 1, un cran (inv. 24) | regles.md §6.5 ; A2 |
| TCH27 | Rythme pur (3/4) : Garder ce rythme et bascules — reference_tenir, bande_tenir, derive_tenir, basculer | F1·0a | `taches/pur-rythme` | `T/moteur/rythme.py`, `T/tests/test_rythme_pur.py` | TCH26 | sonnet | `test_rythme_pur.py` : 14 / 13 jours, bandes 5/8/2, plafond 2 × médiane + 1 | regles.md §6.6-§6.7 |
| TCH28 | Rythme pur (4/4) : constats C1-C8, retour_absence, semaine_courte + les 65 exemples chiffrés recalculés (49 + 12 + 4 de la rév. 2) | F1·0a | `taches/pur-rythme` | `T/moteur/rythme.py`, `T/tests/test_rythme_pur.py` | TCH27 | sonnet | `test_rythme_pur.py` : les 65 exemples de regles.md §6.10, un par test (65/65) | regles.md §4.8, §6.9-§6.10 |
| TCH29 | Sollicitations pures : due, choisir_relance, etat_decroissance, variante, plafond_atteint | F1·0a | `taches/pur-sollicitations` | `T/moteur/sollicitations.py`, `T/tests/test_sollicitations_pures.py` | — | sonnet | `test_sollicitations_pures.py` : tables choisir_relance / etat_decroissance / variante ; sautée jamais différée | regles.md §7 ; donnees.md inv. 22 |
| TCH30 | Gabarits de phrases purs : texte(type, cle, donnees, variante, nom_pour) — notifications, cartes (dont `pause`), bilan, constats, retour, revue ; accords, formats jour/heure | F1·0a | `taches/pur-sollicitations` | `T/moteur/gabarits.py`, `T/tests/test_gabarits.py` | TCH29 | sonnet | `test_gabarits.py` : chaque gabarit de textes.md §3-§4 rendu mot pour mot, singulier et pluriel ; aucun nombre en dur | textes.md §0, §1, §3, §4 ; donnees.md §2.12 (I9) |
| TCH31 | Santé de projet pure : avancement, burnup, sans_prochaine_action, a_l_arret, echeance_menacee, neglige, tout_fait, constat_projets | F1·0a | `taches/pur-projets` | `T/moteur/sante.py`, `T/tests/test_sante.py` | — | sonnet | `test_sante.py` : table « Cas » de regles.md §5, IR16, IR18 | regles.md §5 ; donnees.md §5 |
| TCH32 | Décalage et modèles purs : decaler (refus avant aujourd'hui), instancier, figer_modele (contenu v1) | F1·0a | `taches/pur-projets` | `T/moteur/decalage.py`, `T/tests/test_decalage.py` | TCH31 | sonnet | `test_decalage.py` : delta 7, « 2 tâches passeraient avant aujourd'hui », aller-retour figer → instancier | donnees.md §2.17, §7 ; api.md §4 decaler/instancier |
| TCH10 | Moteur de récurrence pur : premiere_occurrence, prochaine_occurrence, libelle_regle, routine | F1·0b | `taches/pur-saisie` | `T/moteur/recurrence.py`, `T/tests/test_recurrence.py` | TCH6 | sonnet | `test_recurrence.py` : les 25 cas B1-B25 (fériés 18/11/2026, 01/01/2027), 25/25 | regles.md §2 ; textes.md §2.10 |
| TCH38 | Analyseur (1/2) : table des motifs, candidats, contexte (moments nus, IR2), choix sans chevauchement, convertisseurs jour, heure, moment, échéance, durée | F1·0b | `taches/pur-saisie` | `T/saisie/grammaire.py`, `T/saisie/analyseur.py`, `T/tests/test_saisie_pure.py` | TCH10 | sonnet | `test_saisie_pure.py` : lignes jour/heure/moment/échéance/durée de la table regles.md §1.11 | regles.md §1.2-§1.5, §1.7, IR1-IR5 |
| TCH39 | Analyseur (2/2) : projet, étape, étiquette, priorité, récurrence, rappel, assembler, portes (capture : projet EXISTANT, « projet <nom> » en tête, pas « en réserve »), alertes | F1·0b | `taches/pur-saisie` | `T/saisie/analyseur.py`, `T/tests/test_saisie_pure.py` | TCH38 | sonnet | `test_saisie_pure.py` : les 86 phrases de la table §1.11 (39 + 16 + 25 pièges + 6 captures) ; porte capture A1 | regles.md §1.6, §1.8-§1.11 ; A1 ; A14-M6 |
| TCH40 | Collage et plan collé : decouper_collage (projet par collage, Moyenne par défaut, doublons, projets_communs[]) et decouper_plan (étapes, sous-tâches, ◆ jalon) | F1·0b | `taches/pur-saisie` | `T/saisie/collage.py`, `T/saisie/plan.py`, `T/tests/test_saisie_pure.py` | TCH39 | sonnet | `test_saisie_pure.py` : 4 notes Apple, 10 collages, 200 lignes, M9, A17-M3 | regles.md §1.10 ; api.md §4 planification/apercu ; A14-M9 |
| TCH33 | Annuler côté serveur : enregistrer_geste / annuler_geste (opérations par champ, liste blanche §4, conflits, FK revérifiées) | F1·0b | `taches/socle-services` | `T/services/__init__.py`, `T/services/gestes.py`, `T/tests/test_gestes.py` | TCH9, TCH12 | sonnet | `test_gestes.py` : restauration, conflit modifiee_depuis, champ hors liste ignoré (inv. 21) | donnees.md §4 ; A7 |
| TCH34 | Seul chemin d'un jour : planifier() (select_for_update, version → ConflitVersion, reports par F(), moment dérivé) | F1·0b | `taches/socle-services` | `T/services/planification.py`, `T/tests/test_planification.py` | TCH33 | sonnet | `test_planification.py` : invariants 4, 14, 15 ; 409 conflit_version ; `check_read_modify_write.py` | donnees.md §5, inv. 4/14/15 ; regles.md §4.3 |
| TCH35 | Rappels : poser (jour/heure ou ancre), retirer, répéter, recalcul d'ancre, annulés à la clôture, ≤ 5 par tâche, ≤ 100 par compte, drapeau hors_fenetre | F1·0b | `taches/socle-services` | `T/services/rappels.py`, `T/tests/test_rappels.py` | TCH33 | sonnet | `test_rappels.py` : invariant 19, ancre effacée → annule | regles.md §7 rappels ; donnees.md §2.13 |
| TCH36 | Seul créateur : creer_taches (idempotence client_id par all_objects puis IntegrityError relue, ReglagesRythme née ici, triee_le, lien vérifié, récurrence, check-list, étiquettes, rappel, geste) + crochet révélations | F1·0b | `taches/socle-services` | `T/services/creation.py`, `T/services/revelations.py`, `T/tests/test_creation.py` | TCH34, TCH35, TCH10, TCH13 | opus | `test_creation.py` : invariants 1, 5, 9, 29 ; deux créations concurrentes au même client_id = une tâche ; `check_get_or_create.py` | donnees.md §5, inv. 1/5/29 ; A1 ; I8 ; verif-squelette M12 |
| TCH37 | Nocturne orchestrée dès le socle : nocturne.executer() appelle dans l'ordre les étapes des domaines (fonctions vides livrées ici, remplies par leurs lanes en F2) | F1·0b | `taches/socle-services` | `T/nocturne.py`, `T/services/journee.py`, `T/services/rythme.py`, `T/services/erp.py`, `T/services/purge.py`, `T/tests/test_nocturne.py` | TCH36, TCH151 | sonnet | `test_nocturne.py` : ordre des étapes, rejeu idempotent ; `check_services_appeles.py` (qui surveille `taches` depuis TCH151) vert | api.md §9 taches.nocturne ; donnees.md §8 |
| TCH41 | Jetons visuels `--tch-*` versés dans tokens.css (clair et sombre), feuilles sous garde hex, fichiers de style par zone créés et importés · maquettes : `taches.css`, `ecrans-coeur.css`, `ecrans-agenda.css`, `ecrans-projets.css`, `ecrans-secondaires.css`, `composants.html` | F1·0c | `taches/socle-front` | `frontend/src/design/tokens.css`, `frontend/scripts/check_hex.mjs`, `frontend/src/index.css`, `ST/base.css`, `ST/coeur.css`, `ST/saisie.css`, `ST/projets.css`, `ST/agenda.css`, `ST/reglages.css`, `ST/presence.css` | TCH3, TCH15 | sonnet | `node frontend/scripts/check_hex.mjs` vert ; `css_golden.mjs` ; contrastes de spec-8 §3-§4 rejoués sur `composants.html` | spec-8 §1-§8 |
| TCH42 | Client d'API complet : une fonction par route (100), fetchAllPages sur les 4 listes paginées, Idempotency-Key, proprietaire_attendu, codes 409 distingués | F1·0c | `taches/socle-front` | `FA/tachesApi.js`, `FA/tachesApi.test.js` | TCH41, TCH15 | sonnet | `tachesApi.test.js` : chaque fonction appelle le chemin d'api.md §3 ; réponses lues par `exempleContrat('taches', …)` (contrat partagé, le test frontend importe les échantillons) ; `check_api_contract.py` | api.md §0, §3, §5 ; MAJ-8 ; `check_liste_page1.py` |
| TCH43 | Routes du module sans navigation (13, `// contextuelle:` A17), 12 pages vides, coquille commune (fiche ?tache=, saisie, `useEnLigne()` pour griser hors ligne) et ses deux points de montage vides | F1·0c | `taches/socle-front` | `FT/module.config.jsx`, `PT/Aujourdhui.jsx`, `PT/ATrier.jsx`, `PT/Projets.jsx`, `PT/Projet.jsx`, `PT/ProjetsArchive.jsx`, `PT/ProjetsModeles.jsx`, `PT/Agenda.jsx`, `PT/Revue.jsx`, `PT/Rythme.jsx`, `PT/Recherche.jsx`, `PT/Supprimees.jsx`, `PT/Reglages.jsx`, `FT/coquille/CoquilleTaches.jsx`, `FT/lib/enLigne.js`, `FT/fiche/Fiche.jsx`, `FT/saisie/FeuilleSaisie.jsx`, `FT/routes.test.jsx` | TCH42, TCH15 | sonnet | `routes.test.jsx` : les 13 routes d'api.md §7 rendent leur page dans la coquille ; `/taches` → `/taches/aujourdhui` ; aucune nav ; `useEnLigne()` passe à faux sur `offline` ; `check_ecrans_atteignables.py` vert | api.md §7 ; spec-7 §2, §4 hors ligne ; regles.md §4.11 ; A17 ; verif-squelette M7 |
| TCH44 | Composants de ligne, montés dès F1 dans la page Aujourd'hui (liste vide) : LigneTache (bouton Actions, menu de l'appui long, balayages, ligne gardée barrée), CaseRonde (< 0,1 s, retour arrière si échec), Etoile (4e refusée) · maquettes : `composants-1.html`, `composants-2.html`, `composants-4.html` | F1·0c | `taches/socle-front` | `FT/ui/LigneTache.jsx`, `FT/ui/CaseRonde.jsx`, `FT/ui/Etoile.jsx`, `PT/Aujourdhui.jsx`, `FT/ui/LigneTache.test.jsx`, `FT/module.config.jsx` | TCH43, TCH15 | sonnet | `LigneTache.test.jsx` : rendu de l'`exemple` d'`item.json` ; Tab → Actions → item ; échec réseau → case revenue ; `check_ecrans_atteignables.py` (classe 1) vert | spec-7 §5, §6, §10 ; spec-8 §2, §5 ; verif-squelette B1 |
| TCH45 | Composants partagés montés dès F1 dans la coquille : FeuilleACrans, SelecteurProjet (« + Nouveau projet » fixe), BarreSelection (lot), BoutonCopilote (taqinor:assistant:ouvrir, sans clé : une phrase) · maquettes : `composants-5.html`, `composants-7.html` | F1·0c | `taches/socle-front` | `FT/ui/FeuilleACrans.jsx`, `FT/ui/SelecteurProjet.jsx`, `FT/ui/BarreSelection.jsx`, `FT/ui/BoutonCopilote.jsx`, `FT/coquille/CoquilleTaches.jsx`, `FT/ui/composants.test.jsx`, `FT/module.config.jsx` | TCH44, TCH15 | sonnet | `composants.test.jsx` : crans 50/85 %, clavier ouvert, sans clé → la phrase de textes.md §5.2 ; `check_ecrans_atteignables.py` vert | spec-7 §10 ; textes.md §5.3 ; A12 ; verif-squelette B1 |
| TCH46 | Gestes, annonces et clavier montés dans la coquille : useGeste (toast « Annuler » 8 s, pause au survol/focus, messages sans délai), role=status, BandeauConflit, formats jour/heure/durée, clavier de liste · maquettes : `etat-toast.html`, `etat-conflit.html` | F1·0c | `taches/socle-front` | `FT/lib/gestes.js`, `FT/lib/textes.js`, `FT/lib/clavierListe.js`, `FT/ui/BandeauConflit.jsx`, `FT/coquille/CoquilleTaches.jsx`, `FT/lib/gestes.test.js`, `FT/lib/textes.test.js`, `FT/module.config.jsx` | TCH45, TCH15 | sonnet | `gestes.test.js` : critères (1)-(4) de spec-7 §6 (annonce lue, toast focalisé qui reste, réglage, Tab → Actions) ; `textes.test.js` : formats textes.md §0, même sortie que `moteur/gabarits.py` sur 10 dates (jumeau) ; aucune touche seule ne fait disparaître une ligne | spec-7 §5-§6 ; A7 ; A16-N8, N10 ; textes.md §0, §1, §2.15, §2.16, §2.19 ; verif-squelette B1 |
| TCH47 | Régénérer les dérivés de F1 : openapi-schema.yml, api-contracts.md, rbac-endpoint-inventory.md, CODEMAP + empreinte ; retirer les `[GATED]` de F2 dans le commit de la fusion suivante | F1·fin | `taches/orchestrateur` | `docs/openapi-schema.yml`, `docs/api-contracts.md`, `docs/rbac-endpoint-inventory.md`, `docs/CODEMAP.md` | TCH3, TCH14, TCH147, TCH18, TCH151, TCH24, TCH28, TCH30, TCH32, TCH40, TCH37, TCH46 | haiku | `check_openapi_schema.py --check`, `check_api_shapes.py` (api-contracts.md sans dérive), `codemap_fingerprint.py --check` verts ; `--write` via l'artefact CI si Django absent | donnees.md §6 dernière vague ; CLAUDE.md CODEMAP upkeep ; verif-squelette M3, M4 |
| TCH48 | Saisie rapide : aperçu (jetons, projets_communs, doublons, alertes, ids → projet proposé) et création tout ou rien (201 deja_creees, 409 autre_compte) | F2·A | `taches/saisie` | `T/views/saisie.py`, `T/serializers/saisie.py`, `T/tests/test_api_saisie.py` | TCH40, TCH36, TCH15 | sonnet | `test_api_saisie.py` : réponses = `exemple` de `saisie_apercu.json`, `saisie_rapide.json` ; plafonds 200 lignes / 20 000 car. ; Idempotency-Key suffixée | api.md §3.2, §4 saisie-rapide ; donnees.md inv. 1, 31 |
| TCH49 | Tâches : liste paginée (vue=boite, quelque_jour, filtres, cible/cible_id/ouvertes pour ✓+), création, fiche (revérifie le lien), PATCH à verrou, suppression avec sous-tâches | F2·A | `taches/saisie` | `T/views/taches.py`, `T/services/taches.py`, `T/serializers/saisie.py`, `T/tests/test_api_taches.py` | TCH48 | sonnet | `test_api_taches.py` : 409 conflit_version, jour_prevu refusé au PATCH, boucle bloquee_par ≤ 50, `tache.json` | api.md §3.2, §4 taches/ ; donnees.md inv. 6, 7, 15, 27 |
| TCH50 | Actions d'état : planifier, terminer (sous-tâches, récurrence suivante, progression, rappels annulés), rouvrir, sauter, trancher, attendre, reçu, restaurer | F2·A | `taches/saisie` | `T/views/taches.py`, `T/services/taches.py`, `T/tests/test_api_taches.py` | TCH49 | sonnet | `test_api_taches.py` : invariants 4, 5, 16, 27 ; « Fait · prochaine jeu. 19 » | api.md §4 ; regles.md §2, §4.3 ; MAJ-5 |
| TCH51 | Réordonner, écho de changement, rappels (poser, retirer, répéter), règle de récurrence (PATCH, appliquer à l'ouverte, arrêter) | F2·A | `taches/saisie` | `T/views/taches.py`, `T/services/taches.py`, `T/tests/test_api_taches.py` | TCH50 | sonnet | `test_api_taches.py` : invariant 32 ; `tache_changement.json`, `rappel_repeter.json` ; question_titres au 1er rappel | api.md §3.2, §4 ; M13 ; A17-T4 |
| TCH52 | Lot (7 actions, ≤ 200), check-list, étiquettes (paginées), vues enregistrées (filtres fermés, ≤ 30) | F2·A | `taches/saisie` | `T/views/saisie.py`, `T/services/taches.py`, `T/serializers/saisie.py`, `T/tests/test_api_saisie.py` | TCH51 | sonnet | `test_api_saisie.py` : `lot.json`, `etiquettes.json`, `vues.json` ; clé de filtre inconnue → 400 nommé ; ids étrangers → refusées | api.md §3.2, §4 lot ; donnees.md §2.4-§2.6, §2.16 |
| TCH53 | Recherche (projets + tâches), Supprimées récemment (un projet = une ligne), Derniers gestes, Annuler un geste | F2·A | `taches/saisie` | `T/views/saisie.py`, `T/serializers/saisie.py`, `T/tests/test_api_saisie.py` | TCH52 | sonnet | `test_api_saisie.py` : `recherche.json`, `supprimees.json`, `gestes.json`, `geste_annuler.json` ; 200 partiel | api.md §3.2, §4 ; A7 ; A16-N7 |
| TCH54 | Journée côté serveur : préfiltre unique, placement par section et motif À revoir, ordre d'affichage, compter_journee (pastille), progression | F2·A | `taches/journee` | `T/selectors/journee.py`, `T/tests/test_api_journee.py` | TCH23, TCH25, TCH37 | sonnet | `test_api_journee.py` : invariants 2, 3, 10, 11, 13, 32 | regles.md §4.1-§4.2, §4.9 ; donnees.md inv. 10-13 |
| TCH55 | ERP dans la journée (`selectors/obligations.py`) : activités ouvertes, bande « Toute la journée », Suivi des relances, compteurs « Ailleurs dans l'ERP » par les sélecteurs des apps cibles | F2·A | `taches/journee` | `T/selectors/obligations.py`, `T/tests/test_api_journee.py` | TCH54, TCH16 | opus | `test_api_journee.py` : admin à 4 touches dont 1 à lui → nb 1 ; famille en échec absente ; `lint-imports` | spec-6a §4, crit. 8 ; A16-N4 ; donnees.md §1 FamilleObligation |
| TCH56 | GET aujourdhui/ (carte du moment choisie par le serveur, `pause` comprise, Proposé replié après Alléger, 200 lignes), badge/, aujourdhui/ailleurs/, vu/ (carte retour, rien sans tâche) | F2·A | `taches/journee` | `T/views/journee.py`, `T/serializers/journee.py`, `T/services/journee.py`, `T/tests/test_api_journee.py` | TCH55, TCH30 | sonnet | `test_api_journee.py` : réponses = `exemple` de `aujourdhui.json`, `badge.json`, `vu.json`, `ailleurs.json`, `carte_du_moment.json` ; invariant 29 | api.md §2, §3.1, §4 vu ; regles.md §4.10 ; R16 ; A14-B1 |
| TCH57 | Proposition et « Garder ces N » : journee/proposition/ (ids étrangers ignorés, Voir tout), journee/planifier/ express (triage facultatif), journee/essentiel/ (≤ 3) | F2·A | `taches/journee` | `T/views/journee.py`, `T/services/journee.py`, `T/tests/test_api_journee.py` | TCH56 | sonnet | `test_api_journee.py` : `journee_proposition.json` ; invariant 18 ; A17-T2 | api.md §4 journee/* ; regles.md §3.4, §4.4 ; A11 |
| TCH58 | Alléger (allege_le, sans report) et Bilan du soir (cloture/ d'hier jusqu'à 12 h, cloturer/ Tout reporter, un constat) + étape nocturne « clore la veille » | F2·A | `taches/journee` | `T/views/journee.py`, `T/services/journee.py`, `T/tests/test_api_journee.py` | TCH57, TCH28 | sonnet | `test_api_journee.py` : `journee_cloture.json` ; A14-M4, M7 ; A16-N6 ; reportées 3 fois marquées, jamais refusées | regles.md §4.5-§4.7 ; api.md §4 alleger/cloture |
| TCH59 | Agenda : jours (≤ 42), Toute la journée, sans heure, blocs, échéances, À placer, Mes projets en vue semaine, férié, externes vide, ?projet= même propriétaire | F2·A | `taches/journee` | `T/views/agenda.py`, `T/serializers/journee.py`, `T/tests/test_api_agenda.py` | TCH56 | sonnet | `test_api_agenda.py` : `agenda.json` ; 400 « 42 jours au plus. » | api.md §3.1, §4 agenda ; A16-N3, N4 ; R18 |
| TCH60 | Projets : liste (constat, compteurs, santé, À planifier), création (couleur d'office, nom pris), fiche, PATCH (statut terminé refusé), suppression avec ses tâches en un geste | F2·A | `taches/projets` | `T/views/projets.py`, `T/services/projets.py`, `T/selectors/projets.py`, `T/serializers/projets.py`, `T/tests/test_api_projets.py` | TCH31, TCH36, TCH15 | sonnet | `test_api_projets.py` : `projets_liste.json`, `projet_ecrit.json` ; invariant 27 ; IR6 | api.md §3.3, §4 projets ; donnees.md §2.1 |
| TCH61 | Ordre et cycle de vie : réordonner, Mettre en haut, trier par priorité, terminer (issue, boite/annuler/deplacer), rouvrir, restaurer (409 nom_pris) | F2·A | `taches/projets` | `T/views/projets.py`, `T/services/projets.py`, `T/tests/test_api_projets.py` | TCH60 | sonnet | `test_api_projets.py` : invariant 17, T14, N7 ; `projet_ecrit.json` | api.md §4 terminer/restaurer ; R15 |
| TCH62 | Vue d'un projet (liste, tableau, chronologie : étapes, sans étape, avancement, prochain jalon, burn-up) + étapes (CRUD, réordonner) | F2·A | `taches/projets` | `T/views/projets.py`, `T/selectors/projets.py`, `T/serializers/projets.py`, `T/tests/test_api_projets.py` | TCH61 | sonnet | `test_api_projets.py` : `projet_vue.json` | api.md §4 vue ; regles.md §5 |
| TCH63 | Planifier le projet : aperçu d'une liste collée (403 confidentiel sous l'en-tête assistant), création en un tout, Décaler les dates (aperçu, refus) | F2·A | `taches/projets` | `T/views/projets.py`, `T/services/projets.py`, `T/tests/test_api_projets.py` | TCH62, TCH32, TCH40 | sonnet | `test_api_projets.py` : `planification_apercu.json`, `decalage.json` ; A14-M3 | api.md §4 planification/decaler |
| TCH64 | Dupliquer, Enregistrer comme modèle, modèles (liste, fiche, renommer, supprimer, instancier avec aperçu) | F2·A | `taches/projets` | `T/views/projets.py`, `T/services/projets.py`, `T/tests/test_api_projets.py` | TCH63 | sonnet | `test_api_projets.py` : `modele_instancier.json`, `modeles_liste.json` | api.md §3.3, §4 modeles ; s4 §G |
| TCH65 | Revue de la semaine : bilan ou Semaine courte, cartes par projet, décision (Garder, Pause, Terminer par le même service), projet de la semaine unique | F2·A | `taches/projets` | `T/views/projets.py`, `T/services/projets.py`, `T/tests/test_api_revue.py` | TCH64 | sonnet | `test_api_revue.py` : `revue_projets.json`, `revue_decision.json` ; invariant 25 | api.md §4 revue ; A16-N9 |
| TCH66 | Mon rythme côté serveur : GET rythme/ (RYTHME complet) et POST rythme/ (le nombre dit s'applique aussitôt, 400 hors 1-12) | F2·A | `taches/rythme` | `T/views/rythme.py`, `T/services/rythme.py`, `T/selectors/rythme.py`, `T/serializers/rythme.py`, `T/tests/test_api_rythme.py` | TCH28, TCH30, TCH37 | sonnet | `test_api_rythme.py` : `rythme.json` ; A2.1 ; MAJ-6 | api.md §3.4, §4 rythme ; regles.md §6 |
| TCH67 | Répondre à une carte : propositions/{id}/repondre/ (réponses permises par clé, 409 expirée, refus comptés sous verrou, baisse jamais imposée) | F2·A | `taches/rythme` | `T/views/rythme.py`, `T/services/rythme.py`, `T/tests/test_api_rythme.py` | TCH66 | sonnet | `test_api_rythme.py` : `proposition.json` ; invariant 24 ; `check_read_modify_write.py` | donnees.md §1 réponses permises ; R9 |
| TCH68 | Préférences dites (11 clés, validation, anciens noms refusés, retirer) et en-tête du Copilote (2 lignes ≤ 300 caractères) | F2·A | `taches/rythme` | `T/views/rythme.py`, `T/services/rythme.py`, `T/tests/test_api_rythme.py` | TCH67 | sonnet | `test_api_rythme.py` : `coach_entete.json` ; « Heure attendue (HH:MM). » | donnees.md §2.11 ; api.md §4 preferences, coach/entete |
| TCH69 | Réglages : GET et PATCH en liste blanche, question du titre au 1er rappel, couper « Comprendre mon rythme » efface le profil, réactiver un type en pause | F2·A | `taches/rythme` | `T/views/reglages.py`, `T/services/rythme.py`, `T/tests/test_api_reglages.py` | TCH68 | opus | `test_api_reglages.py` : `reglages.json` ; champ hors liste → « Non modifiable ici. » ; effacements donnees.md §8 | api.md §4 reglages ; MAJ-6 ; socle §8 registre |
| TCH70 | Révélations à leur événement et étapes nocturnes du rythme (jour clos, blocs, propositions, dérive, constats, révélation revue, expirations, ignorées, pauses à 14) | F2·A | `taches/rythme` | `T/services/revelations.py`, `T/services/rythme.py`, `T/tests/test_nocturne_rythme.py` | TCH69, TCH29 | sonnet | `test_nocturne_rythme.py` : I13, I14 ; rejeu déterministe ; cartes J+7, mon_iphone J+3 | api.md §9 ; regles.md §6, §7 ; textes.md §2.18 ; A17-T3 |
| TCH71 | Suggestions venues de l'ERP : abonnés aux 5 signaux existants (destinataire strict, conditions, anti-doublon, retrait à l'annulation) connectés dans apps.py | F2·A | `taches/erp` | `T/receivers.py`, `T/services/erp.py`, `T/apps.py`, `T/tests/test_suggestions.py` | TCH36, TCH13 | opus | `test_suggestions.py` : spec-6a crit. 9-12 ; `orphan_signals()` vide ; aucun signal neuf (`core/event_coverage.py`) | regles.md §9 ; A4 ; IR14 |
| TCH72 | Routes des suggestions : liste (≤ 20, < 7 jours), Ajouter (titre éditable), Pas utile | F2·A | `taches/erp` | `T/views/erp.py`, `T/serializers/erp.py`, `T/services/erp.py`, `T/tests/test_suggestions.py` | TCH71 | opus | `test_suggestions.py` : `suggestions.json` ; id d'un autre → 404 | api.md §3.2, §4 suggestions |
| TCH73 | Convertir les à-faire personnels (200 partiel, raisons) et Lier une tâche à une activité ERP (409 deja_lie, l'activité reste ouverte) | F2·A | `taches/erp` | `T/views/erp.py`, `T/services/erp.py`, `T/tests/test_erp.py` | TCH72, TCH17 | opus | `test_erp.py` : `convertir_activite.json`, `lier_activite.json` ; invariant 30 | api.md §4 convertir/lier ; A17 ; R19 |
| TCH74 | Données personnelles : fournisseur d'effacement 09-08 (lead effacé), export « Mes données » des 20 modèles, « Tout effacer » (EFFACER, suppression dure) | F2·A | `taches/erp` | `T/dsr.py`, `T/apps.py`, `T/services/donnees.py`, `T/views/donnees.py`, `T/tests/test_donnees.py` | TCH73 | opus | `test_donnees.py` : spec-6a crit. 3, 14 ; `mes_donnees.json`, `tout_effacer.json` ; jetons sans empreinte ; `check_exports_bornes.py` | donnees.md §5 fournisseur, §8 ; MAJ-7 ; socle §8 |
| TCH75 | Purge et revérification nocturnes : rétentions (PlanJour 400 j, lignes 90 j, journal 90 j, rappels 30 j, gestes 7 j, suggestions 30 j, supprimées 30 j) et liens des tâches ouvertes | F2·A | `taches/erp` | `T/services/purge.py`, `T/services/erp.py`, `T/tests/test_donnees.py` | TCH74 | opus | `test_donnees.py` : purge par dates, lien introuvable/inaccessible ; `trash` ne voit rien (inv. 26) | donnees.md §8 ; A15 ; socle §8 purge |
| TCH76 | Écran Aujourd'hui : ordre vertical, sections, repliés, squelette après 1 s, « Pas à jour · Réessayer » sans vider la liste, vide « Colle ou dicte tes listes » + Coller mes listes, grisé par `useEnLigne()`, relecture au focus · maquettes : `ecran-aujourdhui-matin.html`, `ecran-aujourdhui-matin-bas.html`, `ecran-aujourdhui-vide.html`, `premier-usage-2-aujourdhui.html`, `etat-chargement.html`, `etat-pas-a-jour.html`, `composants-3.html`, `composants-9.html`, `composants-10.html` | F2·A | `taches/ecran-aujourdhui` | `PT/Aujourdhui.jsx`, `FT/aujourdhui/Sections.jsx`, `ST/coeur.css`, `PT/Aujourdhui.test.jsx`, `FT/module.config.jsx` | TCH46, TCH15 | sonnet | `Aujourdhui.test.jsx` sur l'`exemple` d'`aujourdhui.json` : 7 sections dans l'ordre de regles.md §4.1, liste gardée sur un rafraîchissement en échec, actions désactivées quand `useEnLigne()` est faux (le 130 % se prouve en TCH134) | spec-7 §4 ; textes.md §2.2 ; A14-M1 ; A11 |
| TCH77 | Progression « 1 sur 5 · essentiel 0/2 » (Reprise, toucher → Mon rythme), AnneauProgression et carte du moment (ordre serveur dont `pause`, brouillon devant, astuce derrière, Mon iPhone 3 jours, réponses) · maquettes : `ecran-aujourdhui-retour.html`, `ecran-aujourdhui-retour-bas.html`, `ecran-aujourdhui-15h.html`, `etat-astuce.html` | F2·A | `taches/ecran-aujourdhui` | `FT/aujourdhui/Progression.jsx`, `FT/ui/AnneauProgression.jsx`, `FT/ui/CarteDuMoment.jsx`, `FT/ui/CarteDuMoment.test.jsx`, `PT/Aujourdhui.jsx`, `FT/module.config.jsx` | TCH76, TCH15 | sonnet | `CarteDuMoment.test.jsx` sur `carte_du_moment.json`, `proposition.json` : chaque type de CarteDuMoment rendu, réponse envoyée à repondre/ | spec-7 §4 ; textes.md §2.17, §2.18 ; regles.md §4.10 ; A14-B1, A16-N9, A17-T3 |
| TCH78 | Proposé pour aujourd'hui : « Garder ces N » (contour), surcharge, Voir tout groupé par projet, ★ (≤ 3) puis focus sur Prévu, « Planifier avec le Copilote » · maquettes : `ecran-aujourdhui-matin.html` | F2·A | `taches/ecran-aujourdhui` | `FT/aujourdhui/Propose.jsx`, `FT/aujourdhui/Propose.test.jsx`, `PT/Aujourdhui.jsx`, `FT/module.config.jsx` | TCH77, TCH15 | sonnet | `Propose.test.jsx` sur `journee_proposition.json` ; critère (8) : focus sur Prévu après Garder | spec-7 §4 ; textes.md §2.2 ; A11 ; A17-M1 |
| TCH79 | Menu ⋯ d'Aujourd'hui (Alléger, Réorganiser, Sélectionner ; « En faire mon accueil » MASQUÉE jusqu'à TCH132) et feuille « Alléger ma journée » · maquettes : `ecran-aujourdhui-15h-menu.html`, `ecran-aujourdhui-15h-bas.html` | F2·A | `taches/ecran-aujourdhui` | `FT/aujourdhui/MenuJournee.jsx`, `FT/aujourdhui/FeuilleAlleger.jsx`, `FT/aujourdhui/FeuilleAlleger.test.jsx`, `PT/Aujourdhui.jsx`, `FT/module.config.jsx` | TCH78, TCH15 | sonnet | `FeuilleAlleger.test.jsx` : rien coché, « 3 retournées aux projets » annoncé ; l'entrée d'accueil absente du menu | spec-7 §2, §4 ; textes.md §2.10 ; A14-M7 ; A16-N6 ; verif-squelette min. 8 |
| TCH80 | Feuille « Bilan du soir » (ouverte aussi par `?ouvrir=bilan`) : 4 sur 5 et gardées faites, par reste Reporter à lun. 23 · Choisir un jour · En réserve · Abandonner, Tout reporter, un constat, un mot, d'hier jusqu'à 12 h · maquettes : `ecran-bilan.html`, `ecran-bilan-bas.html`, `ecran-bilan-rythme.html` | F2·A | `taches/ecran-aujourdhui` | `FT/aujourdhui/FeuilleBilan.jsx`, `FT/aujourdhui/FeuilleBilan.test.jsx`, `PT/Aujourdhui.jsx`, `FT/module.config.jsx` | TCH79, TCH15 | sonnet | `FeuilleBilan.test.jsx` sur `journee_cloture.json` ; `?ouvrir=bilan` ouvre la feuille | spec-7 §2, §4 ; textes.md §2.9, §4.3 ; api.md §7 (rév. 2.1) ; A14-M4 |
| TCH81 | Lignes de l'ERP sur Aujourd'hui : activités (badge ERP, case si peut_cloturer, sans Annuler), Toute la journée, Suivi des relances, Ailleurs dans l'ERP, appui long « Lier une tâche », À revoir (Tout en réserve), En attente, Faites · maquettes : `composants-4.html`, `ecran-aujourdhui-matin-bas.html` | F2·A | `taches/ecran-aujourdhui` | `FT/aujourdhui/LignesErp.jsx`, `FT/aujourdhui/Replies.jsx`, `FT/aujourdhui/LignesErp.test.jsx`, `PT/Aujourdhui.jsx`, `FT/module.config.jsx` | TCH80, TCH15 | sonnet | `LignesErp.test.jsx` sur `aujourdhui.json`, `ailleurs.json`, `lier_activite.json` : activité cochée appelle `records/activities/{id}/done/` et n'offre pas Annuler | spec-7 §4-§5 ; textes.md §2.2 ; spec-6a §6 ; A17 lier |
| TCH82 | Saisie : ChampSaisie (puces reconnues, ×, ignorer, `#projet` → Nouveau projet), SelecteurQuand (tuiles, date, « 10 h »), feuille au bouton flottant avec brouillon, erreur sous le champ · maquettes : `ecran-saisie.html`, `ecran-saisie-nouveau.html`, `etat-erreur-champ.html`, `composants-5.html`, `composants-6.html` | F2·A | `taches/ecran-saisie` | `FT/ui/ChampSaisie.jsx`, `FT/ui/SelecteurQuand.jsx`, `FT/saisie/FeuilleSaisie.jsx`, `FT/saisie/FeuilleSaisie.test.jsx`, `ST/saisie.css`, `FT/module.config.jsx` | TCH46, TCH15 | sonnet | `FeuilleSaisie.test.jsx` sur `saisie_apercu.json` et `erreurs.json` : brouillon rouvert identique après fermeture (état persisté) ; annexe A spec 2 | spec-7 §4, §7 parcours 1-2 ; textes.md §2.3, §2.16 ; A16-N1 |
| TCH83 | Coller mes listes : ApercuListe (un projet par collage, puce de priorité Moyenne, doublons, Coller encore, Créer N tâches), carte Mon iPhone après le 1er collage · maquettes : `ecran-saisie-liste.html`, `premier-usage-1-apercu.html`, `premier-usage-3-mon-iphone.html` | F2·A | `taches/ecran-saisie` | `FT/ui/ApercuListe.jsx`, `FT/saisie/ColleListes.jsx`, `FT/ui/ApercuListe.test.jsx`, `FT/module.config.jsx` | TCH82, TCH15 | sonnet | `ApercuListe.test.jsx` sur `saisie_apercu.json`, `saisie_rapide.json` | spec-7 §8 ; textes.md §2.3 ; A14-M5, M9 ; A17-M3 |
| TCH84 | Fiche (?tache=) : Quand, Échéance, Projet, Priorité, ★, notes, check-list, Reporter, Fait, conflit sans perte, « Encore 10 min · 1 h · Demain 9 h » quand ouverte par un rappel · maquettes : `ecran-fiche.html`, `rappel-ouvert.html`, `etat-conflit.html` | F2·A | `taches/ecran-saisie` | `FT/fiche/Fiche.jsx`, `FT/fiche/Fiche.test.jsx`, `FT/module.config.jsx` | TCH83, TCH15 | sonnet | `Fiche.test.jsx` sur `tache.json`, `tache_ecrite.json`, `rappel_repeter.json`, `erreurs.json` (409) : saisie en cours conservée après « Prendre l'autre » | spec-7 §4 ; textes.md §2.4, §2.16 ; A16-N8 ; A17 rappel |
| TCH85 | Fiche → Plus : Répéter, étiquettes, durée, en attente de (personne ou tâche), jalon, lié à, confidentielle, sous-tâches, rappel avec question du titre, Abandonner, Supprimer (dialogue nommant) · maquettes : `ecran-fiche-plus.html`, `etat-question-rappel.html` | F2·A | `taches/ecran-saisie` | `FT/fiche/FichePlus.jsx`, `FT/fiche/FichePlus.test.jsx`, `FT/fiche/Fiche.jsx`, `FT/module.config.jsx` | TCH84, TCH15 | sonnet | `FichePlus.test.jsx` sur `etiquettes.json` : la question du 1er rappel écrit `PATCH reglages/` | spec-7 §2 ; textes.md §2.4 ; A17-T4 |
| TCH86 | Écran À trier : Suggéré par l'ERP (Ajouter, Pas utile), bandeau à convertir, Aujourd'hui · Demain · Projet… · ⋯, Trier une par une, En réserve, Tout ranger, « Ranger avec le Copilote » · maquettes : `ecran-a-trier.html` | F2·A | `taches/ecran-saisie` | `PT/ATrier.jsx`, `FT/atrier/TrierUneParUne.jsx`, `PT/ATrier.test.jsx`, `FT/module.config.jsx` | TCH85, TCH15 | sonnet | `ATrier.test.jsx` sur `suggestions.json`, `lot.json`, `convertir_activite.json` | spec-7 §4 ; textes.md §2.5 ; spec-6a §6 |
| TCH87 | Écrans Recherche (Faites aussi, Projet ▾, Priorité haute, 7 filtres repliés, tri, Enregistrer une vue, vide) et Supprimées récemment (Restaurer, un projet = une ligne, Derniers gestes) · maquettes : `recherche.html`, `recherche-filtres.html`, `recherche-vide.html`, `supprimees.html`, `supprimees-gestes.html` | F2·A | `taches/ecran-saisie` | `PT/Recherche.jsx`, `PT/Supprimees.jsx`, `PT/Recherche.test.jsx`, `FT/module.config.jsx` | TCH86, TCH15 | sonnet | `Recherche.test.jsx` sur `recherche.json`, `vues.json`, `supprimees.json`, `gestes.json` | spec-7 §4 ; textes.md §2.12-§2.13 ; A16-N7 |
| TCH88 | Écran Projets : puce de priorité touchable, « 12 sur 20 », à surveiller, À planifier, Nouveau projet, En pause replié, Mettre en haut, Trier par priorité, Archive et Modèles par ⋯ · maquettes : `projets-liste.html` | F2·A | `taches/ecran-projets` | `PT/Projets.jsx`, `FT/projets/LigneProjet.jsx`, `ST/projets.css`, `PT/Projets.test.jsx`, `FT/module.config.jsx` | TCH46, TCH15 | sonnet | `Projets.test.jsx` sur `projets_liste.json` | spec-7 §4 ; textes.md §2.6 ; A14-M3 ; A16-M3 |
| TCH89 | Écran Un projet, vue Liste : étapes, ajouter, santé si signal, Détails, Faites, ⋯ (Voir dans l'agenda, Décaler, Modèle, Dupliquer, Pause, Terminer, Supprimer) · maquettes : `projet-liste.html` | F2·A | `taches/ecran-projets` | `PT/Projet.jsx`, `FT/projets/VueListe.jsx`, `PT/Projet.test.jsx`, `FT/module.config.jsx` | TCH88, TCH15 | sonnet | `Projet.test.jsx` sur `projet_vue.json` : `affichage.vue` relu identique après réouverture | spec-7 §4 ; textes.md §2.6 |
| TCH90 | Vues Tableau et Chronologie d'un projet (mémorisées), burn-up reconstruit · maquettes : `projet-tableau.html`, `projet-chronologie.html` | F2·A | `taches/ecran-projets` | `FT/ui/Tableau.jsx`, `FT/projets/VueChronologie.jsx`, `FT/projets/VueChronologie.test.jsx`, `PT/Projet.jsx`, `FT/module.config.jsx` | TCH89, TCH15 | sonnet | `VueChronologie.test.jsx` ; déplacement au clavier (`kanbanA11y.js`) | spec-7 §9-§10 ; spec-4 |
| TCH91 | Planifier le projet : priorité + « fini quand… », échéance (1 sem → 3 mois), actions, étapes, jalons, risque, brouillon gardé, « Planifier avec le Copilote » · maquettes : `projet-planifier.html`, `projet-planifier-2.html` | F2·A | `taches/ecran-projets` | `FT/projets/PlanifierProjet.jsx`, `FT/projets/PlanifierProjet.test.jsx`, `PT/Projet.jsx`, `FT/module.config.jsx` | TCH90, TCH15 | sonnet | `PlanifierProjet.test.jsx` sur `planification_apercu.json` : brouillon rouvert identique ; parcours 10 = 7 gestes | spec-7 §4, §7 ; textes.md §2.6 ; A14-M3 |
| TCH92 | Écrans Archive et Modèles (utiliser avec aperçu) + dialogues Supprimer le projet (« … et ses 25 tâches ? »), Décaler les dates (dont tâches avant aujourd'hui), Terminer (issue), Dupliquer, Enregistrer comme modèle · maquettes : `projets-archive.html`, `projets-modeles.html`, `projets-modeles-utiliser.html`, `projets-modeles-enregistrer.html`, `projet-supprimer.html`, `projet-decaler.html`, `projet-decaler-avant.html`, `projet-terminer.html` | F2·A | `taches/ecran-projets` | `PT/ProjetsArchive.jsx`, `PT/ProjetsModeles.jsx`, `FT/projets/Dialogues.jsx`, `FT/projets/Dialogues.test.jsx`, `FT/module.config.jsx` | TCH91, TCH15 | sonnet | `Dialogues.test.jsx` sur `decalage.json`, `modele_instancier.json`, `modeles_liste.json`, `projet_ecrit.json` | spec-7 §4 ; textes.md §2.6 ; A16-N7 |
| TCH93 | Écran Revue de la semaine : 4 faits ou Semaine courte, cartes Garder · Pause · Terminer · Suivant, intention, projet de la semaine, fin → Planifier ma semaine · maquettes : `revue-semaine.html` | F2·A | `taches/ecran-projets` | `PT/Revue.jsx`, `PT/Revue.test.jsx`, `FT/module.config.jsx` | TCH92, TCH15 | sonnet | `Revue.test.jsx` sur `revue_projets.json`, `revue_decision.json` | spec-7 §4 ; textes.md §2.7, §4.6 ; A16-N3, N9 |
| TCH94 | Régénérer les dérivés de F2 (openapi, api-contracts, inventaire RBAC, CODEMAP + empreinte) ; retirer les `[GATED]` de F3 dans le commit de la fusion suivante | F2·fin | `taches/orchestrateur` | `docs/openapi-schema.yml`, `docs/api-contracts.md`, `docs/rbac-endpoint-inventory.md`, `docs/CODEMAP.md` | TCH53, TCH59, TCH65, TCH70, TCH75, TCH81, TCH87, TCH93 | haiku | `check_openapi_schema.py --check`, `check_api_shapes.py`, `codemap_fingerprint.py --check` verts | CLAUDE.md CODEMAP upkeep ; verif-squelette M3, M4 |
| TCH136 | Parcours « je note tout » : 4 listes collées → projets proposés (Moyenne) → Créer → À trier vidé en 9 gestes ; brouillon repris | F2·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés) ; ne rejoue que ce qui est construit à ce moment | spec-7 §7 parcours 2, 9, 14 ; A11 |
| TCH137 | Parcours « ma journée » : Garder ces 5 + ★★, cocher, reporter, choisir un jour, Alléger, bilan Tout reporter, bilan d'hier ; ouverture directe par URL (sans nav, sans notification ni pastille) | F2·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés) ; ne rejoue que ce qui est construit à ce moment | spec-7 §7 parcours 3-8, 15 |
| TCH138 | Parcours « projets » : créer et planifier en 7 gestes, Tableau mémorisé, Terminer (boite), Revue, Supprimer puis restaurer en une ligne | F2·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés) ; ne rejoue que ce qui est construit à ce moment | spec-7 §7 parcours 10, 19, 20 |
| TCH95 | Jetons d'accès : authentification par jeton par usage (compte actif interne, user_can_operate, `has_erp_permission('taches_voir')` strict, société du jeton en mémoire), débits, routes jetons/ (clair une fois, l'ancien révoqué) | F3·B | `taches/presence` | `T/auth_jeton.py`, `T/throttles.py`, `T/views/presence.py`, `T/serializers/presence.py`, `T/tests/test_jetons.py` | TCH15, TCH12 | opus | `test_jetons.py` : jeton flux sur capture → 401 identique à un inconnu ; compte sans rôle fin → 401 ; multi-sociétés MAJ-4 ; aucun jeton journalisé ; `jeton.json`, `jetons_liste.json` | api.md §0 J:x ; donnees.md §2.14, §5 ; socle §2.5 ; verif-squelette M1 |
| TCH96 | Capture Siri : capture/ analysée comme la saisie (porte capture), `dans`, réponse lue `?reponse=texte` (textes §7), rejeu deja | F3·B | `taches/presence` | `T/views/presence.py`, `T/tests/test_capture.py` | TCH95, TCH39 | opus | `test_capture.py` : `capture.json` ; « Ajouté pour demain 10 h : appeler le fournisseur » ; 401 et 429 lisibles ; invariant 20 | api.md §4 capture ; A1 ; textes.md §7 |
| TCH97 | Flux de calendrier abonné (.ics, no-store, 404 neutre) et tuile Scriptable (JSON) ; test de notification hors plafond | F3·B | `taches/presence` | `T/views/presence.py`, `T/tests/test_flux_tuile.py` | TCH96, TCH24, TCH56 | opus | `test_flux_tuile.py` : `tuile.json` ; ni notes, ni tâche d'un collègue, ni faite ; confidentielle masquée | regles.md §10 ; api.md §3.4 |
| TCH20 | Quatre types de notification en fin d'énum (TACHES_PLAN_DU_JOUR, TACHES_BILAN_SOIR, TACHES_RELANCE, TACHES_RAPPEL) + module_map + module_gating + migration 0079 dans le même commit (déplacée en F3 : visible dans les préférences de chaque utilisateur) | F3·B | `taches/presence` | `DJ/apps/notifications/types_evenements.py`, `DJ/apps/notifications/module_map.py`, `DJ/apps/notifications/module_gating.py`, `DJ/apps/notifications/migrations/0079_eventtype_taches.py`, `DJ/apps/notifications/tests.py` | TCH97 | sonnet | `apps/notifications/tests.py` : 4 types push + in-app seuls, gatés par le module ; migration 3 AlterField max_length=40 (renuméroter si 0079 pris) | donnees.md §1 EventType, §6.4 ; api.md §9 ; verif-squelette M2a |
| TCH21 | Paramètre `badge` de `notify()` porté dans la charge push | F3·B | `taches/presence` | `DJ/apps/notifications/services.py`, `DJ/apps/notifications/tests.py` | TCH20 | sonnet | `apps/notifications/tests.py` : notify(badge=3) ⇒ `badge: 3` ; sans paramètre, aucun champ | spec-6b §10 ; api.md §9 |
| TCH98 | Balayage de chaque minute : rappels dus groupés (manqué > 2 h), sollicitations dues (plafond 3, sautée jamais différée), marqueur + notify dans la même transaction, pastille dans la charge | F3·B | `taches/presence` | `T/balayage.py`, `T/tests/test_balayage.py` | TCH21, TCH70 | sonnet | `test_balayage.py` : invariant 22 ; rejouer n'envoie rien de plus ; corps sans titre par défaut ; `check_notify_point_unique.py` | api.md §9 ; regles.md §7 |
| TCH99 | Tâches planifiées et réglages : sweeps.py (taches.balayer, taches.nocturne, sociétés actives), beats dans celery.py, TACHES_RACCOURCI_SIRI_URL et taches_rappel immédiat dans settings, .env.example | F3·B | `taches/presence` | `T/sweeps.py`, `DJ/erp_agentique/celery.py`, `DJ/erp_agentique/settings/base.py`, `.env.example`, `T/tests/test_balayage.py` | TCH98 | sonnet | `check_celery_tasks.py`, `check_beat_active_companies.py`, `check_settings_declares.py`, `check_commandes_planifiees.py` verts | api.md §9 ; min-22 |
| TCH100 | Hors ligne : file d'envoi du module (ajouter, cocher, reporter) branchée sur `useEnLigne()`, proprietaire_attendu, 409 autre_compte jeté, conflit vers le bandeau, cache par compte et par jour vidé à la déconnexion · maquettes : `etat-hors-ligne.html` | F3·B | `taches/presence-front` | `FT/horsligne/captureQueue.js`, `FT/horsligne/cacheJournee.js`, `FA/tachesApi.js`, `FT/coquille/CoquilleTaches.jsx`, `FT/horsligne/captureQueue.test.js`, `FT/module.config.jsx` | TCH46, TCH15 | sonnet | `captureQueue.test.js` : 3 ops rejouées après `online`, op d'un autre compte jetée (inv. 31), cache vidé sur `taqinor:auth-logout` | api.md §5 ; regles.md §4.11 ; A16-N11 ; MAJ-9 |
| TCH101 | Pastille : useBadgeTaches (badge/, setAppBadge), compte À trier pour l'onglet | F3·B | `taches/presence-front` | `FT/useBadgeTaches.js`, `FT/useBadgeTaches.test.js`, `FT/module.config.jsx` | TCH100, TCH15 | sonnet | `useBadgeTaches.test.js` sur `badge.json` ; gardées seules (A16-N5) | donnees.md inv. 11 ; spec-6b |
| TCH102 | Créer une tâche depuis ici : hôte TachesPresence (c t, palette quick-create), cibleEcran (pré-lien aligné sur liens_cibles.json et entityRoutes), BoutonTachesIci ✓+ (compte, liste, cocher, Nouvelle tâche liée) | F3·B | `taches/presence-front` | `FT/presence/TachesPresence.jsx`, `FT/presence/cibleEcran.js`, `FT/presence/BoutonTachesIci.jsx`, `FT/presence/TachesPresence.test.jsx`, `ST/presence.css`, `FT/module.config.jsx` | TCH101, TCH15 | sonnet | `TachesPresence.test.jsx` : gabarits `liens_cibles.json` = cibleDepuisEcran = entityRoutes.ROUTE (spec-6a crit. 5) ; masqué sans `taches_voir` | spec-6a §6 ; A10 ; spec-7 §5 N1 |
| TCH103 | Carte du cockpit « 1 sur 5 », 3 lignes (essentiel d'abord), Ouvrir, « Rien de gardé » · maquettes : `cockpit-carte.html` | F3·B | `taches/presence-front` | `FT/presence/CarteMesTaches.jsx`, `FT/presence/CarteMesTaches.test.jsx`, `FT/module.config.jsx` | TCH102, TCH15 | sonnet | `CarteMesTaches.test.jsx` sur `aujourdhui.json` | spec-7 §4 ; spec-6a §6 |
| TCH104 | Écran Agenda : vues Jour, Semaine, Mois, À venir, ← Aujourd'hui →, Toute la journée, Férié, GrilleAgenda (créneau vide = Ajouter à son heure) · maquettes : `agenda-jour.html`, `agenda-semaine.html`, `agenda-mois.html`, `agenda-a-venir.html`, `composants-8.html` | F3·B | `taches/ecran-agenda` | `PT/Agenda.jsx`, `FT/ui/GrilleAgenda.jsx`, `FT/agenda/VueMois.jsx`, `PT/Agenda.test.jsx`, `ST/agenda.css`, `FT/module.config.jsx` | TCH46, TCH15 | sonnet | `Agenda.test.jsx` sur `agenda.json` | spec-7 §4 ; textes.md §2.8 ; A16-N4 |
| TCH105 | VoletAPlacer et « Placer à une heure » (toucher la tâche puis le créneau, durée par pas de 15, Maj+↓) · maquettes : `agenda-placer-heure.html`, `agenda-placer-heure-duree.html` | F3·B | `taches/ecran-agenda` | `FT/ui/VoletAPlacer.jsx`, `FT/ui/VoletAPlacer.test.jsx`, `PT/Agenda.jsx`, `FT/module.config.jsx` | TCH104, TCH15 | sonnet | `VoletAPlacer.test.jsx` : la pose appelle `taches/{id}/planifier/` ; parcours 17 = 9 gestes | spec-7 §2, §7 ; `dndA11y.js` |
| TCH106 | Planifier ma semaine : Semaine + À placer + Mes projets, toucher une tâche puis un jour, glisser au bureau, 7 lignes sur iPhone, ouvert par ?placer=1 · maquettes : `agenda-semaine-planifier.html`, `agenda-semaine-planifier-pose.html` | F3·B | `taches/ecran-agenda` | `FT/agenda/PlanifierSemaine.jsx`, `FT/agenda/PlanifierSemaine.test.jsx`, `PT/Agenda.jsx`, `FT/module.config.jsx` | TCH105, TCH15 | sonnet | `PlanifierSemaine.test.jsx` ; parcours 16 = 31 gestes | A16-N3 ; R18 ; textes.md §2.8 |
| TCH152 | Mise en page de bureau d'Aujourd'hui : agenda du jour à droite (GrilleAgenda), colonne des projets, glisser vers une heure · maquettes : `ecran-aujourdhui-matin.html` | F3·B | `taches/ecran-agenda` | `FT/aujourdhui/ColonneBureau.jsx`, `FT/aujourdhui/ColonneBureau.test.jsx`, `PT/Aujourdhui.jsx`, `ST/coeur.css`, `FT/module.config.jsx` | TCH106, TCH15 | sonnet | `ColonneBureau.test.jsx` : la colonne n'apparaît qu'au-dessus de 1024 px ; glisser appelle `planifier/` (mesure de mise en page en TCH134) | spec-7 §4 (bureau) ; verif-squelette min. 5 |
| TCH107 | Écran Mon rythme : aujourd'hui, 3 modes, 14 jours, proposition, constats, Mes jours (congés, jours courts, temps disponible), Comprendre mon rythme, « Parler de mon rythme » · maquettes : `rythme.html`, `premier-usage-4-rythme.html` | F3·B | `taches/ecran-reglages` | `PT/Rythme.jsx`, `FT/rythme/MesJours.jsx`, `PT/Rythme.test.jsx`, `ST/reglages.css`, `FT/module.config.jsx` | TCH46, TCH15 | sonnet | `Rythme.test.jsx` sur `rythme.json`, `proposition.json` ; vide « 3 jours sur 10 » | spec-7 §4 ; textes.md §2.11, §4 ; A2 |
| TCH108 | Écran Réglages : Notifications (heures, Message de 15 h, revue, réactiver), Vie privée (texte exact), L'ERP me suggère, Mes données (Exporter, Tout effacer EFFACER), Avancé (messages sans délai, agenda ICS) · maquettes : `reglages.html`, `reglages-notifications.html`, `reglages-vie-privee.html`, `reglages-vie-privee-bas.html`, `reglages-donnees.html`, `reglages-donnees-effacer.html` | F3·B | `taches/ecran-reglages` | `PT/Reglages.jsx`, `FT/reglages/ViePrivee.jsx`, `FT/reglages/Rubriques.jsx`, `PT/Reglages.test.jsx`, `FT/module.config.jsx` | TCH107, TCH15 | sonnet | `Reglages.test.jsx` sur `reglages.json`, `agenda_externe.json`, `mes_donnees.json`, `tout_effacer.json` ; Vie privée = textes.md §6 mot pour mot | spec-7 §4 ; textes.md §2.14, §6 ; A9 |
| TCH109 | Mon iPhone : 5 étapes repliables, jetons (Créer, Copier, Régénérer, Révoquer, dernier usage), Envoyer un test, S'abonner, Installer le raccourci si l'URL est posée, En faire mon accueil, Ce qui est visible · maquettes : `mon-iphone.html` | F3·B | `taches/ecran-reglages` | `FT/iphone/MonIphone.jsx`, `FT/iphone/MonIphone.test.jsx`, `PT/Reglages.jsx`, `FT/module.config.jsx` | TCH108, TCH15 | sonnet | `MonIphone.test.jsx` sur `jeton.json`, `jetons_liste.json`, `reglages.json` ; textes.md §7 mot pour mot | spec-6b §9 ; textes.md §7 ; A14-M5 ; A16-N12 |
| TCH110 | Script de la grande tuile Scriptable (≤ 90 lignes, textes §8) + « Copier le script » · maquettes : `tuile.html` | F3·B | `taches/ecran-reglages` | `FT/iphone/scriptTuile.js`, `FT/iphone/scriptTuile.test.js`, `FT/iphone/MonIphone.jsx`, `FT/module.config.jsx` | TCH109, TCH15 | sonnet | `scriptTuile.test.js` : lit `faites`, `prevues`, `objectif`, `essentiel.prevues` de `tuile.json` ; ≤ 90 lignes | spec-6b annexe A ; textes.md §8 ; C35 |
| TCH111 | Actions de l'assistant : agent_actions.py (16 clés, taches_voir, RISK_INTERNAL, lot copilote, ≤ 3 écritures, échos) + platform.py déclare agent_actions_module | F3·B | `taches/assistant` | `T/agent_actions.py`, `T/platform.py`, `T/tests/test_agent_actions.py` | TCH15 | opus | `test_agent_actions.py` : méthode et droit = route (api.md §8) ; échos sans écriture ; `check_action_permission_override.py`, `check_platform.py` | api.md §8 ; A5 ; spec-5b §1 |
| TCH112 | Registre de l'agent : clés `taches.*` et cartes au registre + échantillon assistant_reponse.json | F3·B | `taches/assistant` | `DJ/apps/agent/registry.py`, `DJ/apps/agent/contract_samples/assistant_reponse.json`, `DJ/apps/agent/tests/test_registry.py` | TCH111 | opus | `apps/agent/tests/test_registry.py` : carte ∈ CARTES ; `check_api_shapes.py` | spec-5b §10.4 ; api.md §8 |
| TCH113 | Consignes du Copilote : bloc « TÂCHES — CONSIGNES DU COPILOTE » (texte exact, 278 mots, 0 chiffre) + constantes de test recalculées | F3·B | `taches/assistant` | `backend/fastapi_ia/app/services/prompt_copilote.py`, `backend/fastapi_ia/tests/test_prompt_copilote.py` | TCH112 | opus | `backend/fastapi_ia/tests/test_prompt_copilote.py` : texte = textes.md §5.1 ; ≤ 280 mots ; 10 clés | textes.md §5.1 ; IT10 |
| TCH114 | Contexte d'écran et jeu d'outils : catalogue_pour_tour (Groq + écran /taches → 5 actions), lien pris du contexte, sortie bornée, en-tête X-Taqinor-Assistant | F3·B | `taches/assistant` | `backend/fastapi_ia/app/services/relais_copilote.py`, `backend/fastapi_ia/app/services/action_tools.py`, `backend/fastapi_ia/tests/test_action_tools.py` | TCH113 | opus | `test_action_tools.py` : 16 actions sous claude, 5 sous Groq sur /taches, 0 hors /taches | spec-5b §7 ; api.md §0, §8 |
| TCH115 | Masquage du journal de l'assistant : tour à outil `taches.*` OU écran /taches → question « [tâches — privé] », réponse et erreur vidées | F3·B | `taches/assistant` | `backend/fastapi_ia/app/services/sql_agent_service.py`, `backend/fastapi_ia/tests/test_sql_agent_endpoint.py` | TCH114 | opus | `test_sql_agent_endpoint.py` : avec outil ; sans outil sur /taches/aujourdhui ; tour CRM intact | socle §2.6, §8 Coach ; spec-5b §8 |
| TCH116 | Douze conversations d'évaluation du Copilote (CASES_COACH, cartes attendues, injections) | F3·B | `taches/assistant` | `backend/fastapi_ia/tests/eval/cases_commerciaux.py`, `backend/fastapi_ia/tests/eval/runner.py`, `backend/fastapi_ia/tests/test_eval_harness.py` | TCH115 | opus | `test_eval_harness.py` : 12 cas, ids uniques, clés ⊆ CLES_COACH ; `CASES_COPILOTE` reste à 19 | spec-5b annexe |
| TCH117 | Cartes Tâches du Copilote : ma_journee, plan_propose (adopter = « Garder ces N » express), liste_taches, tache (écho ou écriture), capture_apercu, rythme, plan_projet, projet, revue_semaine · maquettes : `copilote.html` | F3·B | `taches/cartes` | `FT/cartes/CartesTaches.jsx`, `FT/cartes/CartesTaches.test.jsx`, `FT/module.config.jsx` | TCH83, TCH15 | sonnet | `CartesTaches.test.jsx` rend chaque échantillon via CarteResultat (contrat partagé, `exempleContrat`) | api.md §8 ; textes.md §5.4 ; A17-T2 |
| TCH118 | Branchement des cartes et des 4 demandes prêtes : cartes.js, CartesDuMessage.jsx, copilotMessages.js (ouvert depuis /taches, sans clé : une phrase) | F3·B | `taches/cartes` | `frontend/src/features/ia/cartes/cartes.js`, `frontend/src/features/ia/cartes/CartesDuMessage.jsx`, `frontend/src/features/ia/copilotMessages.js`, `frontend/src/features/ia/cartes/cartes.test.jsx`, `frontend/src/features/ia/copilotMessages.test.mjs` | TCH117, TCH15 | sonnet | `cartes.test.jsx`, `copilotMessages.test.mjs` : 4 demandes de textes.md §5.2 ; cartes CRM intactes | A12 ; textes.md §5.2 ; spec-5b §10.7 |
| TCH119 | Raccourcis clavier et palette : c t / g j, entrées de palette (Créer une tâche, Chercher dans mes tâches, Nouveau projet, Faire le bilan, 4 onglets), filtre des entrées à événement, aide du module, entité « tache » · maquettes : `recherche-palette.html` | F3·B | `taches/etranger-deploy` | `frontend/src/providers/shortcuts.js`, `frontend/src/providers/commandActions.js`, `frontend/src/providers/focusedRecordShortcuts.jsx`, `frontend/src/lib/search/entityRoutes.js`, `frontend/src/providers/commandActions.test.mjs`, `frontend/src/providers/focusedRecordShortcuts.test.jsx`, `frontend/src/lib/search/entityRoutes.test.jsx` | TCH15 | sonnet | `commandActions.test.mjs`, `focusedRecordShortcuts.test.jsx`, `entityRoutes.test.jsx` : `g t` reste au SAV ; clavier muet sous dialogue (N1) | spec-7 §5 N1, N2 ; A10 ; A14-M11 ; spec-6a §9 |
| TCH120 | Service worker et manifeste : badge de l'app à la réception, clic de notification vers les liens d'api.md §7 (`?ouvrir=bilan` compris), raccourci de manifeste « Tâches » | F3·B | `taches/etranger-deploy` | `frontend/src/sw.js`, `frontend/vite.config.js`, `frontend/src/features/pwa/shortcuts.test.mjs` | TCH15 | sonnet | `shortcuts.test.mjs` ; lien rappel → /taches/aujourdhui?tache=<id>, bilan → ?ouvrir=bilan | api.md §7 (rév. 2.1) ; spec-6b §2-§3 |
| TCH19 | Ligne du registre des traitements 09-08 « taches_rythme » (déplacée en F3 : visible à l'administrateur dans le registre) | F3·B | `taches/etranger-deploy` | `DJ/core/management/commands/seed_registre_traitements.py`, `DJ/core/tests/test_registre_traitements.py` | TCH120 | opus | `core/tests/test_registre_traitements.py` : entrée présente, idempotente | socle §8 registre ; textes.md §6 ; verif-squelette M2 |
| TCH121 | Agenda externe (AVANCÉ) : modèle AgendaExterne + migration 0002, lecture d'une adresse ICS bornée (https, hôte public, taille, délai, cache, états), routes agenda-externe/ | F3·B | `taches/agenda-externe` | `T/models/agenda.py`, `T/models/__init__.py`, `T/migrations/0002_agendaexterne.py`, `T/services/agenda_externe.py`, `T/views/agenda_externe.py`, `T/tests/test_agenda_externe.py` | TCH9 | opus | `test_agenda_externe.py` : adresse privée ou http refusée, trop grande, délai ; `agenda_externe.json` ; jamais au flux, à la tuile, à l'assistant | donnees.md §2.20 ; A14-M8 ; api.md §3.4 |
| TCH122 | Événements externes dans agenda/ (clé `externes`, cache borné) | F3·B | `taches/agenda-externe` | `T/views/agenda.py`, `T/tests/test_agenda_externe.py` | TCH121 | opus | `test_agenda_externe.py` : `agenda.json` avec externes ; cible agenda/ ≤ 16 requêtes posée | api.md §4 agenda ; A14-M8 |
| TCH123 | Monter l'hôte et le bouton ✓+ dans la coquille de l'ERP : Layout.jsx (TachesPresence) et Header.jsx (BoutonTachesIci) | F3·C | `taches/etranger-coquille` | `frontend/src/components/layout/Layout.jsx`, `frontend/src/components/layout/Header.jsx`, `frontend/src/components/layout/Header.test.jsx` | TCH102, TCH15 | sonnet | `Header.test.jsx` : ✓+ masqué sans `taches_voir` | spec-6a §6, §9 |
| TCH124 | Pastille d'onglet et badges personnels : BottomTabBar.jsx (À trier, masquée à 0) et useAppBadges.js (badgePersonnel) | F3·C | `taches/etranger-coquille` | `frontend/src/components/layout/BottomTabBar.jsx`, `frontend/src/lib/apps/useAppBadges.js`, `frontend/src/components/layout/BottomTabBar.test.jsx`, `frontend/src/lib/apps/useAppBadges.test.jsx` | TCH101, TCH15 | sonnet | `BottomTabBar.test.jsx`, `useAppBadges.test.jsx` | spec-7 §2 ; spec-6a §9 |
| TCH125 | Carte du cockpit montée : Dashboard.jsx (bureau) · maquettes : `cockpit-carte.html` | F3·C | `taches/etranger-coquille` | `frontend/src/pages/Dashboard.jsx`, `frontend/src/pages/Dashboard.cockpit.test.jsx` | TCH103, TCH15 | sonnet | `Dashboard.cockpit.test.jsx` : carte présente avec `taches_voir`, absente sinon | spec-6a §9 |
| TCH126 | Carte du cockpit mobile et création rapide : CockpitHome.jsx (carte lazy) et quickCreateEvents.js (entrée « tache ») | F3·C | `taches/etranger-coquille` | `frontend/src/features/offlinesync/mobile/CockpitHome.jsx`, `frontend/src/features/uxviews/quickcreate/quickCreateEvents.js`, `frontend/src/features/offlinesync/mobile/CockpitHome.test.jsx`, `frontend/src/features/uxviews/quickcreate/quickCreateEvents.test.mjs` | TCH103, TCH15 | sonnet | `CockpitHome.test.jsx`, `quickCreateEvents.test.mjs` étendus | spec-6a §9 |
| TCH127 | Test canari de confidentialité : « Canari-7Q9 » / « Canari-X3K » absent de toute chaîne servie à l'assistant, au flux, à la tuile, aux notifications, aux suggestions et dans IncitationCoach.donnees ; visible à l'écran | F3·C | `taches/final` | `T/tests/test_canari.py` | TCH97, TCH98, TCH111, TCH75, TCH70 | opus | `test_canari.py` : routes de regles.md §8 ; casse et accents ignorés, JSON décodé ; témoin sans en-tête qui voit le titre | regles.md §8 ; A6 ; donnees.md inv. 8 |
| TCH128 | Test de balayage « même propriétaire » : pour chaque route et chaque id reçu (inv. 9), un id d'un autre compte répond comme un id inconnu et rien n'est écrit | F3·C | `taches/final` | `T/tests/test_meme_proprietaire.py` | TCH127, TCH122 | opus | `test_meme_proprietaire.py` : les 100 routes, ids de lot/plan/triage/réordonnancement compris ; exception lecture de journee/proposition | donnees.md inv. 9 ; socle §2.1 |
| TCH129 | Plafonds de requêtes : cibles d'api.md §10 posées dans docs/query-budgets.yml et tests `assertNumQueries` par route ; la CI mesure, la cible est remplacée par la mesure au premier vert | F3·C | `taches/final` | `T/tests/test_plafonds.py`, `docs/query-budgets.yml` | TCH128 | sonnet | `test_plafonds.py` exécuté par la CI (backend-tests) ; `check_query_budgets.py` vert | api.md §10 ; A15 ; socle §8 performance ; verif-squelette M12 |
| TCH130 | Activation (1/3) : accorder `taches_voir` aux rôles système INTERNES seulement (jamais portail, ni rôles à liste blanche) | F3·C | `taches/final` | `DJ/apps/roles/permissions_registre.py`, `DJ/apps/roles/tests.py` | TCH129 | opus | `init_roles` puis `apps/roles/tests.py` : rôles internes l'ont, portail et Commercial terrain non ; sociétés existantes atteintes au déploiement (`init_roles`) | socle §8 Droits ; A17 ; donnees.md inv. 28 ; verif-squelette M8b |
| TCH131 | Activation (2/3) : manifeste `installable: True`, navigation (4 onglets, labelKey, glyphe unique, pastille À trier), marqueurs contextuels retirés, ligne appSkus, 5 clés de traduction, échantillons retirés de « posés avant leur vue », README mis à jour | F3·C | `taches/final` | `T/apps.py`, `FT/module.config.jsx`, `frontend/src/lib/apps/appSkus.js`, `frontend/src/i18n/catalogs/fr.json`, `frontend/src/i18n/catalogs/en.json`, `frontend/src/i18n/catalogs/ar.json`, `scripts/check_api_shapes.py`, `docs/taches/README.md`, `FT/routes.test.jsx` | TCH130, TCH124, TCH15 | sonnet | `routes.test.jsx` : 4 onglets dans l'ordre ; `i18n-coverage.test.mjs`, `nav-keys-no-raw-key.test.mjs`, `appSkus.test.jsx`, `check_ecrans_atteignables.py`, `check_modules.py` verts | spec-7 §2 ; textes.md §9 ; A17 ; MAJ-10 ; verif-squelette M2b |
| TCH132 | Activation (3/3) : Aujourd'hui admise comme écran d'accueil mobile et entrée « En faire mon accueil » démasquée | F3·C | `taches/final` | `DJ/authentication/selectors.py`, `DJ/authentication/tests_ntmob6_mobile_home_route.py`, `FT/aujourdhui/MenuJournee.jsx`, `FT/module.config.jsx` | TCH131, TCH15 | opus | `tests_ntmob6_mobile_home_route.py` : '/taches/aujourdhui' accepté ; l'entrée du menu ⋯ réapparaît | spec-6b §10 ; api.md §7 ; verif-squelette min. 8 |
| TCH133 | Tests de bout en bout (1/2) : journée (Garder ces 5, ★★, cocher, reporter, Alléger, bilan Tout reporter), saisie et À trier (collage 4 listes), fiche, rappel (parcours 11), conflit | F3·C | `taches/final` | `E2E/taches-journee.spec.js`, `E2E/taches-saisie.spec.js` | TCH132 | sonnet | Playwright vert en CI ; hooks DOM = contrat ; parcours 1-9, 11, 13, 15, 20-22 de spec-7 §7 | spec-7 §7 |
| TCH134 | Tests de bout en bout (2/2) : projets, revue → Planifier ma semaine, agenda, Mon iPhone, clavier (parcours 18) ; axe-core 0 violation, cibles ≥ 44 px et texte à 130 % mesurés dans le navigateur | F3·C | `taches/final` | `E2E/taches-projets.spec.js`, `E2E/taches-a11y.spec.js` | TCH133 | sonnet | Playwright : critères (5)-(7) de spec-7 §6 sur chaque écran, à 390 × 844 et 1440 ; parcours 16-19 | spec-7 §6-§7 ; verif-squelette M8c |
| TCH135 | Régénérer les dérivés de F3 (openapi, api-contracts, inventaire RBAC, CODEMAP + empreinte) ; manuel de l'assistant régénéré après la fusion par le skill assistant-manuel | F3·fin | `taches/orchestrateur` | `docs/openapi-schema.yml`, `docs/api-contracts.md`, `docs/rbac-endpoint-inventory.md`, `docs/CODEMAP.md` | TCH99, TCH103, TCH152, TCH110, TCH116, TCH118, TCH19, TCH122, TCH126, TCH134 | haiku | `check_openapi_schema.py --check`, `check_api_shapes.py`, `codemap_fingerprint.py --check` verts | CLAUDE.md CODEMAP upkeep ; spec-5b §9 ; verif-squelette M3, M4 |
| TCH139 | Parcours « agenda » : 4 tâches placées à une heure, Planifier ma semaine (15 tâches, fin de Revue), visites et poses en Toute la journée, agenda ICS externe | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés) ; ne rejoue que ce qui est construit à ce moment | spec-7 §7 parcours 16-17 ; A14-M8 |
| TCH140 | Parcours « rythme, notifications, rappel » : objectif dit (7), carte monter, Garder ce rythme, réglages des heures, push de test, plan du matin par le balayage, pastille juste, rappel reçu → fiche → « Encore 1 h » (parcours 11), rien pour un compte sans tâche | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés) ; ne rejoue que ce qui est construit à ce moment | A2 ; A15 ; regles.md §7 ; spec-7 §7 parcours 11 |
| TCH141 | Parcours « iPhone et hors ligne » : jetons, capture `?reponse=texte`, flux .ics sans notes, tuile JSON, Aujourd'hui en accueil ; hors ligne : ajouter, cocher, reporter puis rejeu | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés) ; ne rejoue que ce qui est construit à ce moment | spec-6b ; textes.md §7-§8 ; A16-N11 |
| TCH142 | Parcours « ERP » : lier une tâche à une activité, convertir un à-faire, suggestion après devis accepté, lead effacé → « Lead effacé », ✓+ sur une fiche lead | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés) ; ne rejoue que ce qui est construit à ce moment | spec-6a crit. 1-15 |
| TCH143 | Parcours « Copilote » : 4 demandes, carte plan en express, liste collée → carte à valider, confidentielle jamais citée, tour masqué au journal | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés) ; ne rejoue que ce qui est construit à ce moment | A5 ; A6 ; A12 ; socle §2.6 |
| TCH144 | Parcours « vie privée, clavier et activation » : deux appareils (conflit sans perte), export, Tout effacer, 27 touches au clavier (parcours 18), onglets visibles pour un rôle interne, absents pour portail et Commercial terrain | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés) ; ne rejoue que ce qui est construit à ce moment | A16-N8 ; A17 ; socle §2, §8 ; spec-7 §7 parcours 18 |

Critères communs à écrire dans CHAQUE corps (`lecons-construction-qjr5.md`) : (1) vert CI ≠ déployable ; (2) état
persisté prouvé (« enregistrer → rouvrir → enregistrer sans toucher » = même objet serveur) ; (3) jamais mocker la source
sous test (les tests front lisent `exempleContrat('taches', …)`) ; (4) TOUS les appelants listés par grep ; (5) rouge
d'abord ; (6) jumeau corrigé dans le même commit (`lib/textes.js` ↔ `moteur/gabarits.py`) ; (7) preuve en direct = les
acceptations ; (8) aller ET retour (rouvrir, annuler, relire au focus).

## 4. Fichiers d'un autre propriétaire

Propriétaires vérifiés par `check_ownership.py --owner-of` (AO = append-only). Une tâche par fichier et par fusion ;
réservation `file:<chemin>` juste avant (règle 6). `plan_claims.py list` (17/11) : `acc8` tient 14 plans
`PLAN_AUDIT_*` (fichiers de plan seulement) ; aucune réservation `file:` sur les chemins ci-dessous.

| Fichier | Propriétaire | Édition exacte | Tâche |
|---|---|---|---|
| `docs/ownership.yml` | hors racines (AO) | bloc `taches` + ligne `plans:` ci-dessous | TCH1 (atterrissage) |
| `docs/claude-memory/{taches-decisions-fondateur.md (neuf), MEMORY.md}` | hors racines | fichier D-TCH-1 à 5 + une ligne d'index | TCH148 (atterrissage) |
| `scripts/check_api_shapes.py` | deploy (AO) | `ECHANTILLONS_POSES_AVANT_LEUR_VUE` seulement si la garde l'exige (F1), retrait en F3 | TCH3 ; TCH131 |
| `scripts/check_services_appeles.py` + `scripts/tests/test_check_services_appeles_constantes.py` | deploy | `"taches"` dans `APPS_SURVEILLEES` (`:74`) | TCH151 |
| `DJ/erp_agentique/settings/base.py` | deploy (AO, 2 139 l.) | F1 : `'apps.taches'` en fin d'`INSTALLED_APPS` (≤ 3 lignes) ; F3 : `TACHES_RACCOURCI_SIRI_URL`, `taches_rappel` au défaut de `NOTIFICATIONS_TOUJOURS_IMMEDIATES` (≤ 5) | TCH4 ; TCH99 |
| `DJ/erp_agentique/urls.py` | deploy (AO) | `path('taches/', include('apps.taches.urls'))` | TCH15 |
| `DJ/erp_agentique/celery.py`, `.env.example` | deploy (AO) | 2 beats en fin ; variable commentée | TCH99 |
| `frontend/src/design/tokens.css` (AO), `frontend/scripts/check_hex.mjs`, `frontend/src/index.css` (AO) | deploy | bloc `--tch-*` clair ET sombre ; `ST/` dans `GUARDED_SELECTORS` ; 7 `@import` en fin | TCH41 |
| `DJ/apps/roles/permissions_registre.py` (AO), `DJ/apps/roles/tests.py` | securite | F1 : `taches_voir` EN FIN + `PERMISSION_MODULE`, aucun rôle (golden `tests_spl300_registre_golden.py` inchangé) ; F3 : rôles système internes | TCH5 ; TCH130 |
| `DJ/apps/records/{selectors.py (neuf), services.py, tests.py}` | securite | 3 sélecteurs ; 2 services | TCH16, TCH17 |
| `DJ/authentication/views.py` + `tests_recovery.py` | securite | exclure `taches` de `_traces_du_compte` (`views.py:1404`) | TCH18 |
| `DJ/authentication/selectors.py` + `tests_ntmob6_mobile_home_route.py` | securite | `'/taches/aujourdhui'` dans `MOBILE_HOME_ALLOWED_ROUTES` (`:184`) | TCH132 |
| `DJ/core/management/commands/seed_registre_traitements.py` + `core/tests/test_registre_traitements.py` | securite | entrée `taches_rythme` | TCH19 (F3) |
| `DJ/apps/notifications/{types_evenements.py (AO), module_map.py (AO), module_gating.py, migrations/0079_eventtype_taches.py (AO), tests.py}` | parametres | 4 `EventType` en fin + carte des modules + migration, un commit | TCH20 (F3) |
| `DJ/apps/notifications/services.py` | parametres | paramètre `badge` de `notify()` (`:624`) | TCH21 (F3) |
| `DJ/apps/agent/{registry.py, contract_samples/assistant_reponse.json, tests/test_registry.py}` | analyse | 16 clés et 9 cartes ; échantillon | TCH112 |
| `backend/fastapi_ia/app/services/{prompt_copilote,relais_copilote,action_tools,sql_agent_service}.py` + tests, `tests/eval/{cases_commerciaux,runner}.py` | analyse | consignes (textes §5.1) ; `catalogue_pour_tour` ; masquage `_journaliser` (≤ 40) ; 12 cas | TCH113-TCH116 |
| `frontend/src/features/ia/{cartes/cartes.js, cartes/CartesDuMessage.jsx, copilotMessages.js}` + tests | analyse | dispatch des cartes ; 4 demandes | TCH118 |
| `frontend/src/features/offlinesync/mobile/CockpitHome.jsx`, `frontend/src/features/uxviews/quickcreate/quickCreateEvents.js` + tests | analyse | carte lazy ; entrée `tache` | TCH126 |
| `frontend/src/providers/{shortcuts.js (AO), commandActions.js, focusedRecordShortcuts.jsx}`, `frontend/src/lib/search/entityRoutes.js` (AO) + 3 tests | deploy | `c t`, `g j` ; filtre `!!s.to` (spec-6a §9) + palette ; aide ; entité | TCH119 |
| `frontend/src/sw.js`, `frontend/vite.config.js`, `frontend/src/features/pwa/shortcuts.test.mjs` | deploy | badge, liens de clic (dont `?ouvrir=bilan`), raccourci de manifeste | TCH120 |
| `frontend/src/components/layout/{Layout,Header}.jsx` + `Header.test.jsx` | deploy | hôte + ✓+ | TCH123 |
| `frontend/src/components/layout/BottomTabBar.jsx`, `frontend/src/lib/apps/useAppBadges.js` + tests | deploy | pastille d'onglet ; badges personnels | TCH124 |
| `frontend/src/pages/Dashboard.jsx` + `Dashboard.cockpit.test.jsx` | deploy | carte lazy | TCH125 |
| `docs/query-budgets.yml` | deploy (`--owner-of`) | cibles d'api.md §10, remplacées par la mesure CI | TCH129 |
| `frontend/src/lib/apps/appSkus.js`, `frontend/src/i18n/catalogs/{fr,en,ar}.json` | deploy (AO) | ligne `taches` ; 5 clés `nav.*` | TCH131 |
| `docs/openapi-schema.yml` (AO), `docs/api-contracts.md`, `docs/rbac-endpoint-inventory.md`, `docs/CODEMAP.md` (AO) | hors racines (régénérés) | `--write` des gardes | TCH47, TCH94, TCH135 |

Non touchés : `apps/reporting/calendar.py`, `apps/trash/*`, `records.Tag`, `record_targets`, recherche globale,
`core/events.py`, `contractSamples.js`.

**À ajouter à `docs/ownership.yml`** (dans `owners:`, avant `parked:`) :

```yaml
  taches:
    plan: docs/plans/PLAN_TACHES.md
    titre: "Tâches et agenda personnels + Copilote (apps/taches) : sa session PLAN_TACHES"
    paths:
      - backend/django_core/apps/taches/**
      - frontend/src/api/tachesApi*
      - frontend/src/features/taches/**
      - frontend/src/pages/taches/**
      - frontend/src/styles/taches/**
      - frontend/e2e/taches-*
      - frontend/e2e/acceptation/tch.spec.js
```
et dans `plans:` : `  docs/plans/PLAN_TACHES.md: [taches, deploy, securite, parametres, analyse]`. Les tâches
étrangères restent dans `PLAN_TACHES.md` (aucun `@after` vers un autre plan, que `plan_lanes.py` refuserait) ; la
coexistence avec les autres sessions passe par les réservations `file:` (règle 6), pas par une exclusion de plans.
L'en-tête de `PLAN_TACHES.md` copie le contrat de `PLAN_YANBOW_WEB.md:3-33` (liste ci-dessus ; INTERDIT : tout autre
fichier de `records`, `notifications`, `agent`, `fastapi_ia`, `crm`, `ventes`, `visites`, `installations`, lus par leurs
`selectors.py`).

## 5. Table de couverture

### 5.1 Modèles (20)
Projet, Section, Tache, ElementChecklist, Etiquette, EtiquetteTache, RegleRecurrence → TCH7 · PlanJour, LignePlanJour,
ReglagesRythme, Preference, IncitationCoach, Rappel, JetonAcces, GesteAnnulable, VueEnregistree, ModeleProjet,
RevueProjet, SuggestionTache → TCH8 · 0001 → TCH9 · AgendaExterne + 0002 → TCH121 · énums (CarteDuMoment avec `pause`)
→ TCH6 · EventType → TCH20.

### 5.2 Routes (100, api.md §3)
| Groupe | Déclaration · schémas | Comportement |
|---|---|---|
| 3.1 journée, agenda, recherche | TCH15 · TCH145 | aujourdhui/ailleurs/badge/vu TCH56 · proposition/planifier/essentiel TCH57 · alleger/cloture/cloturer TCH58 · agenda TCH59 (externes TCH122) · recherche TCH53 |
| 3.2 saisie, tâches | TCH15 · TCH145 | saisie-rapide TCH48 · capture TCH96 · taches CRUD TCH49 · actions d'état TCH50 · reordonner, rappels, repeter, changement, recurrences TCH51 · lot, checklist, etiquettes, vues TCH52 · supprimees, gestes, annuler TCH53 · lier/convertir TCH73 · suggestions TCH72 |
| 3.3 projets | TCH15 · TCH146 | TCH60-TCH65 |
| 3.4 rythme, réglages, iPhone, données | TCH15 · TCH147 | rythme TCH66 · repondre TCH67 · preferences, coach/entete TCH68 · reglages TCH69 · jetons TCH95 · test-notification, tuile, flux TCH97 · mes-donnees, tout-effacer TCH74 · agenda-externe TCH121 |
| étrangères consommées | — | `records/activities/{id}/done/` TCH81 · `auth/mobile-home-route/` TCH109, TCH132 |

### 5.3 Modules purs et leurs tables
`saisie/normalisation` §1.1 → TCH6 · analyseur, 86 phrases §1.11 → TCH38-TCH39 · collage, plan → TCH40 · récurrence
B1-B25 → TCH10 · classement §3.3 (300/300), §3.4-§3.6, §4.2 → TCH22-TCH23 · flux, tuile §10 → TCH24 · rythme §6.1-§6.10,
65 exemples → TCH25-TCH28 · sollicitations §7 → TCH29 · gabarits textes §3-§4 → TCH30 · santé §5 → TCH31 · décalage →
TCH32 · confidentialité §8 → TCH11.

### 5.4 Écrans, maquettes qui font foi
Chaque écran de spec-7 §4 et chaque maquette du dossier sont rattachés dans la colonne « Ce que ça livre » du §3 :
Aujourd'hui TCH76-TCH81 (+ bureau TCH152) · saisie TCH82-TCH83 · fiche TCH84-TCH85 · À trier TCH86 · Recherche,
Supprimées TCH87 · palette TCH119 · Projets TCH88 · Un projet TCH89-TCH91 · Archive, Modèles, dialogues TCH92 · Revue
TCH93 · Agenda TCH104-TCH106 · Mon rythme TCH107 · Réglages TCH108 · Mon iPhone TCH109 · tuile TCH110 · Copilote
TCH117 · cockpit TCH103, TCH125 · états (`etat-*.html`) TCH46, TCH76, TCH77, TCH82, TCH84, TCH85, TCH100 · première
utilisation (`premier-usage-*.html`) TCH76, TCH83, TCH107 · langage visuel (`taches.css`, `ecrans-*.css`) TCH41.

### 5.5 Composants (spec-7 §10)
LigneTache, CaseRonde, Etoile TCH44 · FeuilleACrans, SelecteurProjet, BarreSelection, BoutonCopilote TCH45 ·
BandeauConflit TCH46 · SelecteurQuand, ChampSaisie TCH82 · ApercuListe TCH83 · CarteDuMoment, AnneauProgression TCH77 ·
Tableau TCH90 · GrilleAgenda TCH104 · VoletAPlacer TCH105 · CoquilleTaches, `useEnLigne` TCH43.

### 5.6 Invariants (donnees.md §3)
| Inv. | Tâches | Inv. | Tâches | Inv. | Tâches | Inv. | Tâches |
|---|---|---|---|---|---|---|---|
| 1 | TCH36, TCH49, TCH61, TCH96 | 9 | TCH12, TCH128 | 17 | TCH61, TCH65 | 25 | TCH65 |
| 2 | TCH54 | 10 | TCH54 | 18 | TCH57, TCH58 | 26 | TCH4, TCH18, TCH53, TCH75 |
| 3 | TCH54 | 11 | TCH54, TCH56, TCH101 | 19 | TCH35 | 27 | TCH50, TCH60, TCH61 |
| 4 | TCH34, TCH50, TCH58 | 12 | TCH24, TCH97 | 20 | TCH95, TCH96 | 28 | TCH4, TCH5, TCH15, TCH43, TCH130, TCH131 |
| 5 | TCH10, TCH36, TCH50 | 13 | TCH54 | 21 | TCH33 | 29 | TCH36, TCH56, TCH98 |
| 6 | TCH49 | 14 | TCH34, TCH35, TCH98 | 22 | TCH29, TCH98 | 30 | TCH17, TCH73 |
| 7 | TCH49, TCH50 | 15 | TCH34, TCH49 | 23 | TCH13, TCH49, TCH75 | 31 | TCH48, TCH100 |
| 8 | TCH11, TCH127 | 16 | TCH50 | 24 | TCH26, TCH67 | 32 | TCH51, TCH54 |

Fonctions uniques (§5) : `taches_de` & co, `jours_travailles_de`, `filtrer_q` TCH12 · liens TCH13 · `taches_de_la_journee`,
`compter_journee` TCH54 · `est_confidentielle`, `nom_pour` TCH11 · `creer_taches` TCH36 · `planifier` TCH34 · gestes
TCH33 · jeton, débits TCH95 · DSR TCH74 · `neglige`, `tout_fait` TCH31 · abonnés TCH71 · records TCH16-TCH17. Rétention
§8 TCH75 ; profil coupé TCH69 ; plafonds §10 TCH129.

### 5.7 Vie privée (socle §2) et cycle de vie (§8)
1 sélecteur + balayage TCH12, TCH128 · 2 corbeille propre, `__str__` neutre TCH4, TCH6, TCH33, TCH53, TCH87 · 3 étiquettes
propres TCH7, TCH4 · 4 recherche propre TCH53, TCH119 · 5 jetons TCH95-TCH97 · 6 donnée ≠ consigne, journal masqué
TCH111, TCH113, TCH115, TCH117 · 7 Vie privée TCH108 · 8 notifications sans titre TCH98, TCH51, TCH85 · droit unique et
strict TCH5, TCH15, TCH95, TCH130 · traces, export, effacer, purge TCH18, TCH74, TCH75, TCH108 · registre 09-08 TCH19,
TCH69 · fuseau, multi-sociétés TCH12, TCH95.

### 5.8 Arbitrages
A1 TCH39, TCH96 · A2 TCH26, TCH66, TCH107 · A3 TCH13, TCH3 · A4 TCH71-TCH72 · A5 TCH111, TCH117 · A6 TCH11, TCH127 · A7
TCH33, TCH46, TCH53 · A8 §4 · A9 TCH108 · A10 TCH119, TCH102 · A11 TCH57, TCH78 · A12 TCH45, TCH118 · A13 TCH43, TCH131 ·
A14 B1 TCH56/77, M1 TCH76/78, M2 TCH77/80, M3 TCH63/83/88, M4 TCH58/80, M5 TCH83/109, M6 TCH39, M7 TCH58/79, M8
TCH121-122, M9 TCH40, M10 TCH30/46, M11 TCH119 · A15 palette TCH6/41, rétentions TCH75, rien sans tâche TCH36/98, liens
TCH120 · A16 N1 TCH119, N3 TCH106, N4 TCH55, N5 TCH54/101, N6 TCH58/79, N7 TCH61/87/92, N8 TCH46/84, N9 TCH65/77/93,
N10 TCH46/134, N11 TCH43/100, N12 TCH109 · A17 T2 TCH57/117, T3 TCH70/77, T4 TCH51/85, lier TCH73/81, invisibilité
TCH4/5/15/43/130-132, tutoiement TCH30/46.

### 5.9 Demandes explicites
Contrat d'abord TCH2-TCH3 · échafaudage TCH4, TCH15 · droit TCH5 · modèles TCH7-TCH9 · sélecteur + balayage TCH12,
TCH128 · canari TCH127 · hors ligne TCH43, TCH100 · pastille TCH101, TCH124 · notifications TCH20-TCH21, TCH98 · tâches
planifiées TCH37, TCH99 · jetons TCH95 · Siri TCH96, TCH109 · flux TCH97 · tuile, Scriptable TCH97, TCH110 · Mon iPhone
TCH109 · assistant TCH111-TCH118 · suggestions TCH71-TCH72, TCH86 · « créer depuis ici » TCH102, TCH123 · cockpit
TCH103, TCH125-TCH126 · export, effacer TCH74, TCH108 · purge TCH75 · DSR TCH74 · registre TCH19 · traces TCH18 · agenda
externe TCH121-TCH122 · traductions TCH131 · régénérations TCH47, TCH94, TCH135 · ownership TCH1 · mémoire TCH148 · README
TCH149 · nettoyage TCH150 · plafonds TCH129 · e2e TCH133-TCH134 · activation TCH130-TCH132 · acceptations TCH136-TCH144 ·
accessibilité (1)-(4) TCH46, (5)-(7) TCH134, (8) TCH78 · parcours 11 TCH133, TCH140 ; parcours 18 TCH134, TCH144.

## 6. Risques et parades

| Risque | Parade |
|---|---|
| Chaîne de migrations | `taches` : 0001 (TCH9), 0002 (TCH121) ; aucun modèle ailleurs (règle 2) ; `notifications` 0079 par TCH20 seule, renumérotée si prise |
| Construction de F2/F3 par une autre boucle (B4) | `[GATED]` + réservation `file:docs/plans/PLAN_TACHES.md` ; mesuré : sans `--group`, F2/F3 restent hors lanes |
| Union de lanes | aucun fichier non append-only dans deux lanes d'une fusion (contrôlé) ; 0 union mesurée |
| Garde des formes et OpenAPI strict (B2, B3) | échantillons enveloppés ; vues qui lèvent ; `@extend_schema` sur les 100 opérations dès F1 |
| Composants inatteignables (B1) | montés dans la coquille ou la page dès leur tâche |
| Invisibilité (M1, M2) | permission stricte ; `installable: False` ; types de notification et registre en F3 |
| Deux moitiés sans contrat | 47 échantillons en F1 ; `@after: TCH15` sur toute tâche front |
| `settings/base.py` fichier-mur | deux tâches, « Code net ≤ N » |
| Fonctions > 60 lignes | `check_forme_code.py` ; découpage regles §1.12 |
| Listes fermées de l'assistant | une lane `assistant` + `cartes` en F3 |
| Golden à étendre | `tests_spl300_registre_golden.py` (droit en fin), `css_golden.mjs`, i18n, `appSkus.test.jsx`, `test_prompt_copilote.py`, `test_eval_harness.py`, OpenAPI, `api-contracts.md` |
| Service sans appelant | TCH151 avant TCH37 |
| Agents sans `node_modules` | jonction (mémoire `worktree_windows_tooling`) ; sinon eslint + `vite build` au fold par l'orchestrateur |
| Sous-vagues sur un `main` nu (M5) | règle 5 |
| Acceptations prématurées (M6) | chacune ne rejoue que ce qui est construit ; `check_acceptation.py` ne lit que les `PLAN_AUDIT_*` : la couverture TCH est appliquée à la main par l'orchestrateur et dite au rapport |
| Plafonds inventés | cibles posées, mesure par la CI (TCH129) |

Gardes à lancer SUR L'HÔTE avant de rendre la main (jamais de docker) :

| Lanes | Gardes |
|---|---|
| toute lane Python | `flake8`, `py_compile`, `check_forme_code.py`, `check_naive_datetime.py`, `check_except_larges.py` |
| `contrats` | `check_api_shapes.py` |
| `socle`, `routes` | + `check_modules.py`, `check_platform.py`, `check_on_delete.py`, `check_unique_scoping.py`, `check_company_fk.py`, `check_fk_scoping.py`, `check_safe_migrations.py`, `check_migration_safety.py`, `check_choices_declares.py`, `check_tenant_isolation.py`, `check_viewset_model_scope.py`, `check_api_shapes.py`, `check_ownership.py`, `check_test_placement.py`, `lint-imports` |
| `socle-services`, lanes serveur F2 | + `check_read_modify_write.py`, `check_get_or_create.py`, `check_services_appeles.py`, `check_tenant_isolation.py`, `check_api_shapes.py`, `check_exports_bornes.py` (erp), `check_beat_active_companies.py` (journee, erp), `lint-imports` (journee, erp) |
| `etranger-gardes` | `python -m pytest scripts/tests/test_check_services_appeles*.py` |
| `presence` | + `check_celery_tasks.py`, `check_commandes_planifiees.py`, `check_beat_active_companies.py`, `check_settings_declares.py`, `check_notify_point_unique.py` |
| `etranger-*`, `assistant` | + tests du module étranger ; `check_action_permission_override.py`, `check_platform.py` ; `pytest backend/fastapi_ia/tests/<fichier>` |
| toute lane front | `eslint` ; `check_ecrans_atteignables.py` ; `check_taches_cablage.py` ; `check_api_contract.py` ; `check_liste_page1.py`, `check_page_size_front.py`, `check_fetchallpages_taille_page.py`, `check_frontend_query_params.py`, `check_date_jour_utc.py` ; `check_hex.mjs` (styles) |
| `final` | + `check_query_budgets.py`, `check_modules.py`, `check_openapi_schema.py --check` |
| `orchestrateur` | `check_openapi_schema.py --write/--check`, `check_api_shapes.py --write`, `codemap_fingerprint.py --write/--check`, `check_stages.py`, `check_ownership.py` |

## 7. Choix par défaut et trous de la référence

Choix par défaut : (1) atterrissage + 3 fusions ; (2) tâches étrangères dans `PLAN_TACHES.md`, coexistence par
réservations `file:` ; (3) `saisie` et `selectors` en paquets sans ré-export, aucune `admin.py`, `sweeps.py` en F3 ;
(4) `?ouvrir=bilan` (rév. 2.1) ; (5) glyphe et `sku` choisis à TCH131.

Trous restants (à remonter) :
1. **Case `taches_voir` visible dans l'éditeur de rôles dès F1** (verif M2c) : aucune correction proposée par la
   vérification ; un administrateur pourrait l'accorder avant F3. Mesure possible : déclarer le droit en F3 seulement, si
   aucune garde n'exige qu'un code de `read_permission` soit au registre — non vérifié ici.
2. **`check_api_shapes.py` face à une vue qui lève** : la vérification déduit qu'une vue sans `return` n'a pas de forme
   lisible ; la nécessité de `ECHANTILLONS_POSES_AVANT_LEUR_VUE` reste à constater au build (TCH3 dit « si la garde
   l'exige »).
3. **Les enregistrements d'acceptation `TCH/`** ne sont gardés par aucun script (`check_acceptation.py` : `PLAN_AUDIT_*`).
4. **Maquettes** : le lot « écrans secondaires » était encore en cours ; état pris au 17/11 (86 fichiers `.html|.css`,
   tous rattachés). `ecran-a-trier-bas.html` n'existe plus ; `premier-usage-*` renumérotées (3 = Mon iPhone, 4 = rythme).
5. Les 10 échantillons et `?ouvrir=bilan` signalés en révision 1 sont réglés par la référence 2.1.

## Révision 2 : ce qui a changé

| Changement | Tâches |
|---|---|
| Ajoutées | TCH145-TCH147 (schémas OpenAPI par domaine, scission de TCH15) · TCH148 mémoire D-TCH · TCH149 README · TCH150 nettoyage de `docs/taches/` · TCH151 `taches` sous la garde « service sans appelant » · TCH152 mise en page de bureau d'Aujourd'hui |
| Scindée | TCH15 → TCH15 (urls + vues `APIView` qui lèvent, permission stricte) + TCH145, TCH146, TCH147 |
| Déplacées | TCH1 → atterrissage · TCH2-TCH3 → lane `contrats` · TCH10 → `pur-saisie` · TCH15 → lane `routes` · TCH19 → F3 (`etranger-deploy`) · TCH20-TCH21 → F3 (`presence`, avant TCH98) |
| Modèle | TCH15, TCH36 → opus |
| Preuves refaites | TCH2-TCH3 (enveloppe), TCH37 (après TCH151), TCH44 et TCH76 (sans mesure jsdom), TCH129 (mesure CI), TCH130 (`init_roles`), TCH28 (65 exemples), TCH39 (86 phrases) |
| Fichiers | TCH13 → `selectors/erp.py`, TCH55 → `selectors/obligations.py` ; TCH43 + `lib/enLigne.js` ; TCH44-TCH46 montent dans la coquille ou la page ; TCH131 + `apps.py` (`installable: True`), README ; TCH132 + `MenuJournee.jsx` ; TCH119 + 2 tests ; régénérations + `api-contracts.md` et `@after` sur chaque lane |
| Acceptations | TCH136-TCH138 sans hors ligne, pastille, notification ni Planifier ma semaine ; ces étapes → TCH139-TCH141 ; parcours 11 → TCH140, parcours 18 → TCH144 |
| En-tête | `[GATED]` F2/F3 et réservation du plan (B4) ; APIView nues (M9) ; pas de modèle en F2 ; sous-vagues (M5) ; réservations `file:` (M10) |
| Maquettes | chaque écran rattaché à ses maquettes, écrans secondaires et états compris |
