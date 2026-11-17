# Plan de construction — SQUELETTE (`apps/taches`, `features/taches`, plan `docs/plans/PLAN_TACHES.md`, tâches `TCH<n>`)

Statut : squelette ARCHITECTE, prêt à rédiger. 144 tâches (135 de construction + 9 d'acceptation en direct), 30 lanes,
3 fusions vers `main`. Lu en entier : `reference/{donnees,api}.md`, `spec-7-ecrans.md` r3.1, `spec-8`, `arbitrages.md`,
`socle.md` ; lus par section : `reference/{regles,textes}.md` (plans, tables de test, §5-§9), `verif-reference.md` §6,
`brief-r1.md` §2, gardes du dépôt. Les rédacteurs de corps de tâche lisent CE fichier + la section de référence citée
dans la colonne « source » de leur tâche.

**Vérifié dans cette session (preuves).** Le plan d'essai généré depuis la table du §3 (`docs/taches/travail/essai-plan/
essai-F{1,2,3}.md`, une copie par fusion où les fusions précédentes sont cochées) a été passé à :
- `python scripts/plan_lanes.py <essai-Fk> --workers 8 --wave-size 80 --group "Fusion Fk"` : F1 = 47 tâches, 11 lanes,
  0 refus, « 0 lane-pair(s) merged on a shared declared file » ; F2 = 47 tâches, 9 lanes (8 en parallèle + orchestrateur),
  0 refus, 0 fusion de lanes ; F3 = 41 tâches, 11 lanes, 0 refus, 0 fusion de lanes ; les `(@acceptation)`, rangées dans
  une sous-section `### Fk — acceptation en direct` de LEUR fusion (sinon `--group` les met hors portée), sont listées
  « Acceptation (orchestrateur) — jamais en lane » (3 en F2, 6 en F3) ; `--check --group "Fusion F1"` sort 0.
- **Sans `--group`**, le même fichier F1 (toutes fusions ouvertes) donne « 8 lane-pair(s) merged » et UNE lane
  `taches/saisie` de 55 tâches : un fichier rempli en F2 par une lane et créé en F1 par une autre (vues 501, pages vides)
  unit les deux lanes. **Règle d'exécution : toujours planifier une fusion à la fois avec `--group "Fusion Fk"`.**
- `check_taches_cablage.analyse()` sur les trois essais : FORME 1 24/24, 24/24, 9/9 créations d'écran conformes, FORME 3
  0 tâche mixte backend↔frontend, 0 constat (un avertissement FORME 2 sur TCH15 corrigé par la clause « Consommateur »).
- `check_plan_taches_mixtes.taches_mixtes()` : seules TCH2, TCH3 sont mixtes (JSON backend + `contractSamples.js`) et
  touchent bien leurs deux moitiés.
- Propriété : les 540 déclarations `Files:` (364 chemins distincts) résolues avec le bloc `taches` proposé (§4) sur une
  COPIE du registre (scratchpad) : taches 453, deploy 34, analyse 22, securite 13, parametres 7, hors racines 11 (docs) ;
  0 chemin hors des 5 propriétaires liés, aucun conflit de `paths` stricts. Non vérifié : `check_ownership.py` sur le vrai
  registre (le bloc n'est pas encore commité — c'est TCH1).
- `python scripts/plan_claims.py list` (17/11) : la session `Reda_Laptop/acc8` tient `file:` sur 14 plans
  `docs/plans/PLAN_AUDIT_*.md`, dont DEPLOY, SECURITE, PARAMETRES, ANALYSE et TRANSVERSE (0,2 h) ; `app:publicapi` périmé
  (44,7 h). Aucune claim `app:taches`, `app:records`, `app:notifications`, `app:agent`.

**Format d'une ligne de plan (lu par `plan_lanes.py`, `check_taches_cablage.py`, `check_plan_taches_mixtes.py`).**
`- [ ] TCH<n> — <titre>. Preuve : … Source : … [Nouveau fichier car : … (`chemin`).] [Et l'écran est ATTEIGNABLE : route
déclarée dans `frontend/src/features/taches/module.config.jsx` (TCH43), entrée de nav à l'activation (TCH131).] [Contrat
partagé : `contract_samples/*.json`, le test frontend importe `contractSamples.js`.] [Code net : …] (ROUTINE|SCHEMA|AUTH —
S|M|L) (@after: TCHx, TCHy) (@lane: taches/<lane>) (@model: haiku|sonnet|opus) Files: \`chemin complet\`, …`
- `Files:` est TOUJOURS la dernière clause (les trois gardes lisent tout ce qui suit le dernier `Files:`) ; chemins
  complets depuis la racine, jamais d'accolades (`check_taches_cablage` ne les développe pas).
- `@lane: taches/<x>` : `taches` n'est pas dans `KNOWN_APPS` (`plan_lanes.py:305`), la clé reste distincte ; ne jamais
  écrire `apps/` dans un nom de lane (sinon `_APP_PATH_RE` replie tout sur `apps/taches`).
- `@model:` explicite partout (sinon « permission », « sécurité », « secret » montent seuls en opus).
- `(@acceptation)` nu, SANS `@after` (`plan_lanes.py` : « jouée à la couverture, pas à l'ordre »), dans la sous-section
  `### Fk — acceptation en direct` de sa fusion.
- Sections du plan : `## Fusion F1 — …`, `## Fusion F2 — …`, `## Fusion F3 — …` (clé de `--group`) ; jamais un titre qui
  commence par GATED, MANUEL, DONE LOG, ALREADY LIVE (`plan_lanes.py:200`).
- Tout test neuf porte « Nouveau fichier car : » ET son chemin entre backticks sur la même ligne (`check_test_placement`),
  sans id de tâche dans le nom.
- Une tâche d'écran ou de composant `.jsx` sous `features/`/`pages/` nomme `module.config.jsx` dans `Files:` + la clause
  « ATTEIGNABLE » (FORME 1 ; `est_ecran` compte aussi `features/taches/ui/*.jsx`).

## 1. Découpage en fichiers

Abréviations : `T/` = `backend/django_core/apps/taches/`, `FT/` = `frontend/src/features/taches/`, `PT/` =
`frontend/src/pages/taches/`, `ST/` = `frontend/src/styles/taches/`, `FA/` = `frontend/src/api/`, `DJ/` =
`backend/django_core/`. « créé par » = lane · fusion · tâche ; « rempli ensuite par » = lanes d'une fusion POSTÉRIEURE
(jamais deux lanes de la même fusion sur un même fichier non append-only — contrôlé par script).

### 1.1 Fichiers-goulots : le choix tranché

| Goulot | Choix | Raison |
|---|---|---|
| `T/urls.py` | **Complet dans le socle** (TCH15) : 100 couples méthode × chemin vers des vues qui existent et répondent 501 ; aucune autre tâche ne le rouvre | `plan_lanes.py:1374-1378` : `urls.py` est le seul « producteur » PACT11 d'un paquet `selectors/` ; s'il n'est touché qu'une fois et coché en F1, aucune moitié front de F2/F3 n'est plus refusée. Un `urls_<domaine>.py` par lane rouvrirait `urls.py` (include) dans chaque lane = N producteurs |
| `T/views/*.py` | Un fichier par domaine (11), **créés vides (501) par TCH15**, remplis chacun par UNE lane en F2/F3 | le socle les crée pour que `urls.py` soit complet ; aucun partage dans une même fusion |
| `__init__.py` de paquet (`models/`, `selectors/`, `services/`, `serializers/`, `views/`, `saisie/`, `moteur/`) | **Écrits une fois par le socle, SANS ré-export** ; on importe le sous-module (`from apps.taches.selectors.journee import …`) | un ré-export forcerait chaque lane à rouvrir le même `__init__.py` ; `check_services_appeles.py` ignore de toute façon la façade comme appelant. Exception : `models/__init__.py` (import des modèles pour Django), rouvert UNE fois par TCH121 en F3, seule lane `models` de cette fusion |
| `FA/tachesApi.js` | **Complet dans le socle-front** (TCH42) : une fonction par route ; rouvert une seule fois, en F3, par la seule lane hors ligne (TCH100) | 100 routes connues d'avance (api.md §3) ; un client par lane créerait des doublons de fonctions (FORME 4) |
| `FT/module.config.jsx` | **Routes complètes dans le socle-front** (TCH43), SANS nav, chaque route marquée `// contextuelle: module invisible jusqu'à TCH131 (A17)` ; surface append-only (registre) : les tâches d'écran la NOMMENT (FORME 1) sans l'éditer ; nav ajoutée par TCH131 seulement | `check_ecrans_atteignables.py` classe 3 « route sans nav » rougirait sinon pendant l'invisibilité ; append-only = jamais de fusion de lanes (`plan_lanes.py:953-960`) |
| Pages `PT/*.jsx` | 12 pages **vides créées par TCH43**, chacune remplie par UNE lane | les routes du socle pointent vers des fichiers qui existent |
| Fiche et saisie (montées partout) | `FT/coquille/CoquilleTaches.jsx` + `FT/fiche/Fiche.jsx` + `FT/saisie/FeuilleSaisie.jsx` **créés vides par TCH43**, remplis par `ecran-saisie` (F2) ; l'hôte global hors `/taches` (`TachesPresence`) arrive en F3 | Aujourd'hui, À trier, Projets importent la coquille dès F2 sans attendre une autre lane de la même fusion |
| Styles | `ST/base.css` + un fichier par zone (`coeur`, `saisie`, `projets`, `agenda`, `reglages`, `presence`) **créés et importés une fois** dans `index.css` par TCH41 ; chaque lane ne remplit que le sien | règle de `index.css` (registre) : un `@import` par fichier neuf, le CSS d'une tâche en fin de SON fichier |
| Contrats `T/contract_samples/*.json` | **Tous (47) dans le socle** (TCH2-TCH3), exportés dans `contractSamples.js` | PACT10 « contrat d'abord, SEUL, sur `main` » : F1 fusionne les contrats avant toute moitié |
| Formes partagées (ITEM, TACHE…) | `T/serializers/formes.py` dans le socle (TCH14) ; chaque domaine a son `serializers/<domaine>.py` | une seule forme ITEM pour 15 listes |
| Étapes de la nocturne | `T/nocturne.py` orchestre dès F1 (TCH37) des fonctions VIDES livrées dans `services/{journee,rythme,erp,purge}.py`, remplies par leurs lanes en F2 | `check_services_appeles.py` : chaque étape a un appelant non-test dès sa création ; aucune lane de F2 n'a à éditer `nocturne.py` |
| Normalisation et dates | `T/saisie/` devient un PAQUET : `normalisation.py`, `dates_pures.py` (socle, utilisés par les modèles et la récurrence) ; `grammaire.py`, `analyseur.py`, `collage.py`, `plan.py` (lane `pur-saisie`) | `nom_cle` est calculé dans `save()` (donnees.md §0) : le socle ne peut pas attendre l'analyseur |
| Fabriques de test | `T/tests/fabriques.py` créé par TCH9, lecture seule ensuite | une lane qui a besoin d'une fabrique neuve l'écrit dans SON module de test |
| Fichiers régénérés (`openapi-schema.yml`, `rbac-endpoint-inventory.md`, `CODEMAP.md`) | Lane `taches/orchestrateur`, une tâche par fusion (TCH47, TCH94, TCH135) | la dérive OpenAPI est bloquante à CHAQUE fusion ; jamais une lane |

### 1.2 Arbre complet (hors échantillons JSON et tests, listés après)

| Fichier | Créé par | Rempli ensuite par |
|---|---|---|
| `T/__init__.py` | socle · F1 · TCH4 | — |
| `T/agent_actions.py` | assistant · F3 · TCH111 | — |
| `T/apps.py` | socle · F1 · TCH4 | erp (F2) |
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
| `T/moteur/__init__.py` | socle · F1 · TCH10 | — |
| `T/moteur/classement.py` | pur-classement · F1 · TCH22 | — |
| `T/moteur/decalage.py` | pur-projets · F1 · TCH32 | — |
| `T/moteur/flux.py` | pur-classement · F1 · TCH24 | — |
| `T/moteur/gabarits.py` | pur-sollicitations · F1 · TCH30 | — |
| `T/moteur/recurrence.py` | socle · F1 · TCH10 | — |
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
| `T/selectors/erp.py` | journee · F2 · TCH55 | — |
| `T/selectors/journee.py` | journee · F2 · TCH54 | — |
| `T/selectors/liens.py` | socle · F1 · TCH13 | — |
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
| `T/urls.py` | socle · F1 · TCH15 | — |
| `T/views/__init__.py` | socle · F1 · TCH15 | — |
| `T/views/agenda.py` | socle · F1 · TCH15 | journee (F2), agenda-externe (F3) |
| `T/views/agenda_externe.py` | socle · F1 · TCH15 | agenda-externe (F3) |
| `T/views/donnees.py` | socle · F1 · TCH15 | erp (F2) |
| `T/views/erp.py` | socle · F1 · TCH15 | erp (F2) |
| `T/views/journee.py` | socle · F1 · TCH15 | journee (F2) |
| `T/views/presence.py` | socle · F1 · TCH15 | presence (F3) |
| `T/views/projets.py` | socle · F1 · TCH15 | projets (F2) |
| `T/views/reglages.py` | socle · F1 · TCH15 | rythme (F2) |
| `T/views/rythme.py` | socle · F1 · TCH15 | rythme (F2) |
| `T/views/saisie.py` | socle · F1 · TCH15 | saisie (F2) |
| `T/views/taches.py` | socle · F1 · TCH15 | saisie (F2) |
| `FA/tachesApi.js` | socle-front · F1 · TCH42 | presence-front (F3) |
| `FT/agenda/PlanifierSemaine.jsx` | ecran-agenda · F3 · TCH106 | — |
| `FT/agenda/VueMois.jsx` | ecran-agenda · F3 · TCH104 | — |
| `FT/atrier/TrierUneParUne.jsx` | ecran-saisie · F2 · TCH86 | — |
| `FT/aujourdhui/FeuilleAlleger.jsx` | ecran-aujourdhui · F2 · TCH79 | — |
| `FT/aujourdhui/FeuilleBilan.jsx` | ecran-aujourdhui · F2 · TCH80 | — |
| `FT/aujourdhui/LignesErp.jsx` | ecran-aujourdhui · F2 · TCH81 | — |
| `FT/aujourdhui/MenuJournee.jsx` | ecran-aujourdhui · F2 · TCH79 | — |
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
| `PT/Aujourdhui.jsx` | socle-front · F1 · TCH43 | ecran-aujourdhui (F2) |
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
| `ST/coeur.css` | socle-front · F1 · TCH41 | ecran-aujourdhui (F2) |
| `ST/presence.css` | socle-front · F1 · TCH41 | presence-front (F3) |
| `ST/projets.css` | socle-front · F1 · TCH41 | ecran-projets (F2) |
| `ST/reglages.css` | socle-front · F1 · TCH41 | ecran-reglages (F3) |
| `ST/saisie.css` | socle-front · F1 · TCH41 | ecran-saisie (F2) |

`T/contract_samples/` : 47 JSON + `README.md`, tous créés par `socle` (F1, TCH2-TCH3). Pas d'`admin.py` (choix §7).

### 1.3 Modules de test (un par domaine ; tous neufs ⇒ « Nouveau fichier car : » sur la tâche créatrice)

| Lane (fusion) | Modules |
|---|---|
| socle (F1) | `__init__.py`, `fabriques.py`, `test_confidentialite.py`, `test_formes.py`, `test_modeles.py`, `test_normalisation.py`, `test_recurrence.py`, `test_routes.py`, `test_selecteurs.py`, `test_socle.py` |
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
| pur-rythme (F1) | `test_rythme_pur.py` |
| pur-saisie (F1) | `test_saisie_pure.py` |
| socle-front (F1) | `tachesApi.test.js`, `gestes.test.js`, `textes.test.js`, `routes.test.jsx`, `LigneTache.test.jsx`, `composants.test.jsx` |
| ecran-agenda (F3) | `PlanifierSemaine.test.jsx`, `VoletAPlacer.test.jsx`, `Agenda.test.jsx` |
| ecran-aujourdhui (F2) | `FeuilleAlleger.test.jsx`, `FeuilleBilan.test.jsx`, `LignesErp.test.jsx`, `Propose.test.jsx`, `CarteDuMoment.test.jsx`, `Aujourdhui.test.jsx` |
| cartes (F3) | `CartesTaches.test.jsx` |
| ecran-saisie (F2) | `Fiche.test.jsx`, `FichePlus.test.jsx`, `FeuilleSaisie.test.jsx`, `ApercuListe.test.jsx`, `ATrier.test.jsx`, `Recherche.test.jsx` |
| presence-front (F3) | `captureQueue.test.js`, `CarteMesTaches.test.jsx`, `TachesPresence.test.jsx`, `useBadgeTaches.test.js` |
| ecran-reglages (F3) | `MonIphone.test.jsx`, `scriptTuile.test.js`, `Reglages.test.jsx`, `Rythme.test.jsx` |
| ecran-projets (F2) | `Dialogues.test.jsx`, `PlanifierProjet.test.jsx`, `VueChronologie.test.jsx`, `Projet.test.jsx`, `Projets.test.jsx`, `Revue.test.jsx` |

Tests ajoutés à un module EXISTANT d'un autre propriétaire (jamais un fichier neuf) : `DJ/apps/records/tests.py`,
`DJ/authentication/tests_recovery.py`, `DJ/authentication/tests_ntmob6_mobile_home_route.py`,
`DJ/core/tests/test_registre_traitements.py`, `DJ/apps/notifications/tests.py`, `DJ/apps/roles/tests.py`,
`DJ/apps/agent/tests/test_registry.py`, `backend/fastapi_ia/tests/{test_prompt_copilote,test_action_tools,
test_sql_agent_endpoint,test_eval_harness}.py`, `frontend/src/features/ia/{cartes/cartes.test.jsx,copilotMessages.test.mjs}`,
`frontend/src/components/layout/{Header,BottomTabBar}.test.jsx`, `frontend/src/lib/apps/useAppBadges.test.jsx`,
`frontend/src/providers/commandActions.test.mjs`, `frontend/src/features/pwa/shortcuts.test.mjs`,
`frontend/src/pages/Dashboard.cockpit.test.jsx`, `frontend/src/features/offlinesync/mobile/CockpitHome.test.jsx`,
`frontend/src/features/uxviews/quickcreate/quickCreateEvents.test.mjs`.

## 2. Lanes, vagues, fusions

### 2.1 Trois fusions vers `main` (et pourquoi pas une, ni deux)

| Fusion | Contenu | Tâches | Module |
|---|---|---|---|
| **F1 — socle** | contrats, échafaudage, 19 modèles + 0001, sélecteur unique, confidentialité, services centraux, `urls.py` complet + vues 501, coquille front, les 9 modules purs, étrangers sans dépendance (records, traces, registre, types de notification) | TCH1-TCH47 (47) | invisible : `taches_voir` déclaré, accordé à aucun rôle, aucune nav, aucun `appSku` |
| **F2 — vague A** | les 5 domaines serveur (saisie, journée, projets, rythme, ERP) + 3 écrans (Aujourd'hui, saisie/fiche/À trier, projets/revue) en 8 lanes parallèles | TCH48-TCH94 (47) + 3 acceptations | invisible |
| **F3 — vagues B puis C** | présence (jetons, Siri, flux, tuile, balayage, beats), hors ligne, pastille, agenda, rythme/réglages/Mon iPhone, assistant (taches + analyse), cartes, agenda externe ; puis câblage de la coquille ERP, canari, balayage « même propriétaire », plafonds, octroi + nav, e2e | TCH95-TCH135 (41) + 6 acceptations | **visible** à TCH130-TCH132 |

Raisons : (1) PACT10 exige le contrat SEUL sur `main` avant les deux moitiés — c'est F1 ; (2) les agents de worktree
partent de `origin/main` (CLAUDE.md « How a plan run works » 2) : F2 a besoin du socle SUR `main`, pas sur une branche
d'intégration ; (3) WOW23 : une fusion ≈ une vague de ~80 tâches et jamais plus de ~100 non fusionnées — 144 en une seule
fusion dépasserait ; (4) A17 : F1 et F2 arrivent en prod module invisible (403 pour tout rôle ; seul un superutilisateur,
`authentication/models.py:519`, atteint l'API, sans nav), l'octroi n'est que dans F3. Deux fusions (« invisible » puis
« reste + activation ») laisseraient ~95 tâches dans la seconde et casseraient (1)-(2).

Commandes : `python scripts/plan_lanes.py docs/plans/PLAN_TACHES.md --workers 8 --wave-size 80 --group "Fusion F1"`
(puis F2, F3). Dans F1 et F3, `plan_lanes.py` émet des sous-vagues (`@after` inter-lanes, AMET97) : 0a → 0b → orchestrateur
pour F1 ; B → C (coquille) → C (final) → orchestrateur pour F3. Une fusion = une PR, une CI, une mise en file
(`gh pr merge --auto --merge`). `docs/BUILD_ORDER.yml` ne connaît pas le préfixe TCH : porte SCA3 sans effet.

### 2.2 Les 30 lanes

Modèle : `sonnet` par défaut ; `opus` = jeton, vie privée/confidentialité, sélecteurs de visibilité, droits, assistant,
fichiers de l'unité `securite`, lecture d'URL externe ; `haiku` = régénérations et registre. Le modèle d'une lane = sa
tâche la plus risquée (`plan_lanes.py` « model = lane's max tier »).

| Lane (`@lane:`) | Fusion · sous-vague (plan_lanes) | Tâches | Dépend de (autres lanes) | Modèle |
|---|---|---|---|---|
| `taches/socle` | F1 · 0a | TCH1-TCH15 (15) | — | opus (TCH5, TCH11-TCH13) |
| `taches/etranger-securite` | F1 · 0a | TCH16-TCH19 (4) | — | opus (unité securite) |
| `taches/etranger-parametres` | F1 · 0a | TCH20-TCH21 (2) | — | sonnet |
| `taches/pur-classement` | F1 · 0a | TCH22-TCH24 (3) | — (stdlib seule) | sonnet |
| `taches/pur-rythme` | F1 · 0a | TCH25-TCH28 (4) | — | sonnet |
| `taches/pur-sollicitations` | F1 · 0a | TCH29-TCH30 (2) | — | sonnet |
| `taches/pur-projets` | F1 · 0a | TCH31-TCH32 (2) | — | sonnet |
| `taches/socle-services` | F1 · 0b | TCH33-TCH37 (5) | socle (TCH9-TCH13) | sonnet |
| `taches/pur-saisie` | F1 · 0b | TCH38-TCH40 (3) | socle (TCH6) | sonnet |
| `taches/socle-front` | F1 · 0b | TCH41-TCH46 (6) | socle (TCH2, TCH3, TCH15) | sonnet |
| `taches/saisie` | F2 · A | TCH48-TCH53 (6) | F1 | sonnet |
| `taches/journee` | F2 · A | TCH54-TCH59 (6) | F1 | opus (TCH55 lit 4 apps étrangères) |
| `taches/projets` | F2 · A | TCH60-TCH65 (6) | F1 | sonnet |
| `taches/rythme` | F2 · A | TCH66-TCH70 (5) | F1 | opus (TCH69 effacement du profil) |
| `taches/erp` | F2 · A | TCH71-TCH75 (5) | F1 (dont TCH16-TCH17) | opus (DSR, effacement, suggestions) |
| `taches/ecran-aujourdhui` | F2 · A | TCH76-TCH81 (6) | F1 (contrats) | sonnet |
| `taches/ecran-saisie` | F2 · A | TCH82-TCH87 (6) | F1 | sonnet |
| `taches/ecran-projets` | F2 · A | TCH88-TCH93 (6) | F1 | sonnet |
| `taches/presence` | F3 · B | TCH95-TCH99 (5) | F1, F2 | opus (jeton) |
| `taches/presence-front` | F3 · B | TCH100-TCH103 (4) | F1, F2 | sonnet |
| `taches/ecran-agenda` | F3 · B | TCH104-TCH106 (3) | F1 | sonnet |
| `taches/ecran-reglages` | F3 · B | TCH107-TCH110 (4) | F1 | sonnet |
| `taches/assistant` | F3 · B | TCH111-TCH116 (6) | F1, F2 | opus |
| `taches/cartes` | F3 · B | TCH117-TCH118 (2) | F2 (ApercuListe) | sonnet |
| `taches/etranger-deploy` | F3 · B | TCH119-TCH120 (2) | — | sonnet |
| `taches/agenda-externe` | F3 · B | TCH121-TCH122 (2) | F1 | opus (lecture d'URL : SSRF) |
| `taches/etranger-coquille` | F3 · C | TCH123-TCH126 (4) | presence-front | sonnet |
| `taches/final` | F3 · C | TCH127-TCH134 (8) | toutes | opus (canari, balayage, droits) |
| `taches/orchestrateur` | fin de chaque fusion | TCH47, TCH94, TCH135 | la fusion | haiku |
| `taches/acceptation` | avant le push de F2 et F3 | TCH136-TCH144 (9) | jouée par l'orchestrateur | opus |

Équilibre mesuré (`plan_lanes`, LPT) : F1 makespan ~40 (lane socle, chemin critique) ; F2 makespan ~20, 8 agents de 5-6
tâches ; F3 vague B ~14, puis C.

## 3. Les tâches, dans l'ordre de construction

Colonnes = le format demandé ; dans le plan, `Files:` passe en DERNIÈRE clause (§0). « F1·0a » = fusion · sous-vague.
Chaque « preuve » est un test COMPORTEMENTAL rouge d'abord, jamais une regex sur le source (leçon 5 de
`lecons-construction-qjr5.md`).

| ID | Ce que ça livre | Fusion | Lane | Files | @after | Modèle | Preuve | Source |
|---|---|---|---|---|---|---|---|---|
| TCH1 | Déclarer le propriétaire `taches` et lier PLAN_TACHES à ses propriétaires (bloc owners + ligne plans:), commité AVEC le plan | F1·0a | `taches/socle` | `docs/ownership.yml` | — | haiku | `python scripts/check_ownership.py` vert ; `--owner-of backend/django_core/apps/taches/models/taches.py` → taches | brief-r1 §2 governance ; A8 ; socle §1 |
| TCH2 | Contrat d'abord (1/2) : 21 échantillons journée, saisie, gestes, agenda, recherche, formes + index README + export contractSamples.js + déclaration « posés avant leur vue » | F1·0a | `taches/socle` | `T/contract_samples/aujourdhui.json`, `T/contract_samples/carte_du_moment.json`, `T/contract_samples/ailleurs.json`, `T/contract_samples/badge.json`, `T/contract_samples/vu.json`, `T/contract_samples/item.json`, `T/contract_samples/tache.json`, `T/contract_samples/tache_ecrite.json`, `T/contract_samples/tache_changement.json`, `T/contract_samples/saisie_apercu.json`, `T/contract_samples/saisie_rapide.json`, `T/contract_samples/capture.json`, `T/contract_samples/lot.json`, `T/contract_samples/lier_activite.json`, `T/contract_samples/geste_annuler.json`, `T/contract_samples/gestes.json`, `T/contract_samples/supprimees.json`, `T/contract_samples/journee_proposition.json`, `T/contract_samples/journee_cloture.json`, `T/contract_samples/agenda.json`, `T/contract_samples/recherche.json`, `T/contract_samples/README.md`, `frontend/src/test/fixtures/contractSamples.js`, `scripts/check_api_shapes.py` | TCH1 | sonnet | `python scripts/check_api_shapes.py` vert ; chaque JSON = l'exemple d'api.md §1-§4 octet pour octet (enveloppe de pagination comprise) | api.md §1-§4, §6 ; PACT10 |
| TCH3 | Contrat d'abord (2/2) : 16 échantillons projets, rythme, réglages, présence, ERP, erreurs, liens_cibles + 10 manquants d'api.md §6 (agenda_externe, etiquettes, vues, modeles_liste, jetons_liste, rappel_repeter, revue_decision, projet_ecrit, mes_donnees, tout_effacer) | F1·0a | `taches/socle` | `T/contract_samples/projets_liste.json`, `T/contract_samples/projet_vue.json`, `T/contract_samples/planification_apercu.json`, `T/contract_samples/decalage.json`, `T/contract_samples/modele_instancier.json`, `T/contract_samples/revue_projets.json`, `T/contract_samples/rythme.json`, `T/contract_samples/proposition.json`, `T/contract_samples/reglages.json`, `T/contract_samples/jeton.json`, `T/contract_samples/tuile.json`, `T/contract_samples/suggestions.json`, `T/contract_samples/convertir_activite.json`, `T/contract_samples/coach_entete.json`, `T/contract_samples/liens_cibles.json`, `T/contract_samples/erreurs.json`, `T/contract_samples/agenda_externe.json`, `T/contract_samples/etiquettes.json`, `T/contract_samples/vues.json`, `T/contract_samples/modeles_liste.json`, `T/contract_samples/jetons_liste.json`, `T/contract_samples/rappel_repeter.json`, `T/contract_samples/revue_decision.json`, `T/contract_samples/projet_ecrit.json`, `T/contract_samples/mes_donnees.json`, `T/contract_samples/tout_effacer.json`, `T/contract_samples/README.md`, `frontend/src/test/fixtures/contractSamples.js`, `scripts/check_api_shapes.py` | TCH2 | sonnet | `python scripts/check_api_shapes.py` vert ; `liens_cibles.json` = 3 cibles A3 | api.md §3.3-§3.4, §4, §6 ; A3 |
| TCH4 | Échafauder l'app : `startapp_erp taches`, manifeste (clé taches, installable), INSTALLED_APPS, platform.py honnête (record_targets [], aucune surface déclarée), pas d'admin.py | F1·0a | `taches/socle` | `T/__init__.py`, `T/apps.py`, `T/platform.py`, `DJ/erp_agentique/settings/base.py`, `T/tests/__init__.py`, `T/tests/test_socle.py` | TCH1 | sonnet | `test_socle.py` : manifeste lu par collect_manifests, `check_modules.py`, `check_platform.py` verts ; aucun admin enregistré | module-playbook §8 points ; donnees.md §6 L0 ; socle §2.2-§2.4 |
| TCH5 | Déclarer le droit `taches_voir` (fin du groupe, PERMISSION_MODULE) SANS l'accorder à aucun rôle ; module invisible | F1·0a | `taches/socle` | `DJ/apps/roles/permissions_registre.py`, `T/tests/test_socle.py` | TCH4 | opus | `test_socle.py` : aucun rôle système ne porte `taches_voir` (invariant 28) ; init_roles inchangé | socle §8 Droits ; A17 ; donnees.md inv. 28 |
| TCH6 | Énumérations fermées (`choix.py`), mixin `__str__` neutre, normalisation et dates pures partagées (normaliser, cle_nom, dates_pures) | F1·0a | `taches/socle` | `T/choix.py`, `T/models/base.py`, `T/saisie/__init__.py`, `T/saisie/normalisation.py`, `T/saisie/dates_pures.py`, `T/tests/test_normalisation.py` | TCH4 | sonnet | `test_normalisation.py` : table regles.md §1.1 (longueur égale, İ/ẞ), cle_nom ; `check_choices_declares.py` | donnees.md §1, règles transverses ; regles.md §1.1, §1.12 |
| TCH7 | Modèles Projet, Section, Tache, ElementChecklist, Etiquette, EtiquetteTache, RegleRecurrence (contraintes, index, nom_cle dans save, CheckConstraint condition=) | F1·0a | `taches/socle` | `T/models/__init__.py`, `T/models/projets.py`, `T/models/taches.py`, `T/tests/test_modeles.py` | TCH6 | sonnet | `test_modeles.py` : unicités company-first + is_deleted, deux CheckConstraint, bulk_create interdit sur nom_cle | donnees.md §2.1-§2.7, inv. 15-16 |
| TCH8 | Modèles PlanJour, LignePlanJour, ReglagesRythme, Preference, IncitationCoach, Rappel, JetonAcces, GesteAnnulable, VueEnregistree, ModeleProjet, RevueProjet, SuggestionTache | F1·0a | `taches/socle` | `T/models/__init__.py`, `T/models/journee.py`, `T/models/rythme.py`, `T/models/presence.py`, `T/models/erp.py`, `T/models/gestes.py`, `T/tests/test_modeles.py` | TCH7 | sonnet | `test_modeles.py` : contraintes §2.8-§2.19, défauts appelables (`default=list`), 11 clés Preference | donnees.md §2.8-§2.19 |
| TCH9 | Migration `0001_initial` (19 modèles, AgendaExterne exclu) + gardes de schéma + fabriques de test partagées (lecture seule ensuite) | F1·0a | `taches/socle` | `T/migrations/__init__.py`, `T/migrations/0001_initial.py`, `T/tests/fabriques.py`, `T/tests/test_modeles.py` | TCH8 | sonnet | `makemigrations --check` vide ; `check_on_delete.py`, `check_unique_scoping.py`, `check_company_fk.py`, `check_safe_migrations.py` verts ; noms d'index ≤ 30 | donnees.md §6.1 |
| TCH10 | Moteur de récurrence pur : premiere_occurrence, prochaine_occurrence, libelle_regle, routine | F1·0a | `taches/socle` | `T/moteur/__init__.py`, `T/moteur/recurrence.py`, `T/tests/test_recurrence.py` | TCH6 | sonnet | `test_recurrence.py` : les 25 cas B1-B25 (fériés 18/11/2026, 01/01/2027) | regles.md §2 ; textes.md §2.10 |
| TCH11 | Confidentialité unique : est_confidentielle (héritage 4 voies) et nom_pour(obj, usage) pour écran, assistant, flux, tuile, notification | F1·0a | `taches/socle` | `T/confidentialite.py`, `T/tests/test_confidentialite.py` | TCH8 | opus | `test_confidentialite.py` : table regles.md §8 (5 usages × 4 colonnes) | regles.md §8 ; donnees.md inv. 8 ; A6 ; socle §2.6-§2.8 |
| TCH12 | Sélecteur unique : taches_de, projets_de, sections_de, etiquettes_de, rappels_de, gestes_de… ; jours_travailles_de, prochain_jour_travaille ; filtrer_q (assistant=True sans notes ni confidentielles) | F1·0a | `taches/socle` | `T/selectors/__init__.py`, `T/selectors/base.py`, `T/tests/test_selecteurs.py` | TCH11 | opus | `test_selecteurs.py` : société ET propriétaire ; deux sociétés, deux comptes ; jours travaillés − congés ; IR17 | donnees.md §5 ; socle §2.1 ; regles.md §0 |
| TCH13 | Liens ERP vérifiés : url_de_cible, libelle_de_cible, cible_visible pour lead, client, devis (sélecteurs de visibilité des apps cibles, jamais leurs modèles) | F1·0a | `taches/socle` | `T/selectors/liens.py`, `T/tests/test_selecteurs.py` | TCH12, TCH3 | opus | `test_selecteurs.py` : commercial hors portée → invisible ; cible hors CibleLiable → refus ; `lint-imports` vert | donnees.md §5, inv. 23 ; A3 ; spec-6a crit. 1-2 |
| TCH14 | Formes partagées sérialisées une seule fois : ITEM (tâche ET activité ERP), TACHE, TACHE_ECRITE, PROJET, PROPOSITION, LIEN | F1·0a | `taches/socle` | `T/serializers/__init__.py`, `T/serializers/formes.py`, `T/tests/test_formes.py` | TCH13, TCH2 | sonnet | `test_formes.py` : chaque forme rend exactement les clés de `item.json`, `tache.json`, `tache_ecrite.json`, `projets_liste.json`, `proposition.json` (contrat partagé) | api.md §1 ; donnees.md inv. 8 |
| TCH15 | Toutes les routes déclarées d'un coup : include `taches/` dans erp_agentique/urls.py, urls.py complet (100 couples méthode × chemin) vers des vues existantes qui répondent 501, schémas OpenAPI déclarés | F1·0a | `taches/socle` | `T/urls.py`, `DJ/erp_agentique/urls.py`, `T/views/__init__.py`, `T/views/saisie.py`, `T/views/taches.py`, `T/views/journee.py`, `T/views/agenda.py`, `T/views/projets.py`, `T/views/rythme.py`, `T/views/reglages.py`, `T/views/presence.py`, `T/views/erp.py`, `T/views/donnees.py`, `T/views/agenda_externe.py`, `T/tests/test_routes.py` | TCH14, TCH5 | sonnet | `test_routes.py` : les 100 routes d'api.md §3 résolvent ; 403 sans `taches_voir` ; 501 avec ; routes J:x → 401 neutre ; `check_viewset_model_scope.py`, `check_tenant_isolation.py` | api.md §0, §3 ; MAJ-10 |
| TCH16 | Lecture des activités ERP pour Tâches : nouveau `records/selectors.py` (activites_ouvertes_pour, nb_a_faire_personnels, peut_cloturer_activites) | F1·0a | `taches/etranger-securite` | `DJ/apps/records/selectors.py`, `DJ/apps/records/tests.py` | — | opus | `apps/records/tests.py` : à-faire créé par A assigné à B absent chez B ; peut_cloturer == (POST done ≠ 403) par rôle système | donnees.md §5 (étrangers) ; spec-6a §9, crit. 6-7 |
| TCH17 | Clôture d'un à-faire personnel converti : `records/services.py` cloturer_a_faire_personnel, rouvrir_a_faire_personnel | F1·0a | `taches/etranger-securite` | `DJ/apps/records/services.py`, `DJ/apps/records/tests.py` | TCH16 | opus | `apps/records/tests.py` : clôture idempotente, réouverture, refus hors créateur | spec-6a §5, §9 ; donnees.md inv. 30 |
| TCH18 | Exclure `taches` du décompte des traces d'un compte (`_traces_du_compte`) | F1·0a | `taches/etranger-securite` | `DJ/authentication/views.py`, `DJ/authentication/tests_recovery.py` | — | opus | `authentication/tests_recovery.py` (test ASUP5 existant) étendu : 40 tâches seules → '' | socle §8 cycle de vie ; spec-6a crit. 13 ; donnees.md inv. 26 |
| TCH19 | Ligne du registre des traitements 09-08 « taches_rythme » (profil de rythme, interrupteur comprendre_mon_rythme) | F1·0a | `taches/etranger-securite` | `DJ/core/management/commands/seed_registre_traitements.py`, `DJ/core/tests/test_registre_traitements.py` | — | opus | `core/tests/test_registre_traitements.py` : entrée présente, idempotente | socle §8 registre ; textes.md §6 |
| TCH20 | Quatre types de notification en fin d'énum (TACHES_PLAN_DU_JOUR, TACHES_BILAN_SOIR, TACHES_RELANCE, TACHES_RAPPEL) + module_map + module_gating + migration 0079 (même commit) | F1·0a | `taches/etranger-parametres` | `DJ/apps/notifications/types_evenements.py`, `DJ/apps/notifications/module_map.py`, `DJ/apps/notifications/module_gating.py`, `DJ/apps/notifications/migrations/0079_eventtype_taches.py`, `DJ/apps/notifications/tests.py` | — | sonnet | `apps/notifications/tests.py` : 4 types push + in-app seuls, gatés par le module `taches` ; migration 3 AlterField max_length=40 | donnees.md §1 EventType, §6.4 ; api.md §9 |
| TCH21 | Paramètre `badge` de `notify()` porté dans la charge push | F1·0a | `taches/etranger-parametres` | `DJ/apps/notifications/services.py`, `DJ/apps/notifications/tests.py` | TCH20 | sonnet | `apps/notifications/tests.py` : notify(badge=3) ⇒ `badge: 3` ; sans paramètre, aucun champ (spec-6b crit.) | spec-6b §10 ; api.md §9 |
| TCH22 | Classement pur : cle_tri (ordre total strict, projet de la semaine, activité priorité 0) et placer (premier cas vrai) | F1·0a | `taches/pur-classement` | `T/moteur/classement.py`, `T/tests/test_classement.py` | — | sonnet | `test_classement.py` (unittest pur) : jeu de test regles.md §3.3 et §4.2 | regles.md §3.1-§3.3, §4.2 |
| TCH23 | Proposé pur : proposer_plan (places = cible − faites − ouverts, IR9), explication (3 faits), capacite (temps disponible) | F1·0a | `taches/pur-classement` | `T/moteur/classement.py`, `T/tests/test_classement.py` | TCH22 | sonnet | `test_classement.py` : cas §3.4-§3.6, journée allégée IR10 | regles.md §3.4-§3.6, §4.4 |
| TCH24 | Flux et tuile purs : evenements_flux (8 journées entières puis « + N autres », 200 au plus, UID) et tuile_pure (top 6, reste, prochaine échéance) | F1·0a | `taches/pur-classement` | `T/moteur/flux.py`, `T/tests/test_flux_pur.py` | TCH23 | sonnet | `test_flux_pur.py` : règles regles.md §10 (exclusions, plafonds, IR15) | regles.md §10 ; donnees.md inv. 12 |
| TCH25 | Rythme pur (1/4) : compte_du_jour, statut_jour, journee_reussie, arrondir (demie vers le bas), plafonner_jours | F1·0a | `taches/pur-rythme` | `T/moteur/rythme.py`, `T/tests/test_rythme_pur.py` | — | sonnet | `test_rythme_pur.py` : tables spec-5a §6 lignes compte/statut/journée réussie ; arrondir | regles.md §0, §6.1-§6.4 |
| TCH26 | Rythme pur (2/4) : mode En faire plus — palier_initial, evaluer_bloc, clore_bloc, objectif_dit, objectif_affiche (+ zone en tenir) | F1·0a | `taches/pur-rythme` | `T/moteur/rythme.py`, `T/tests/test_rythme_pur.py` | TCH25 | sonnet | `test_rythme_pur.py` : 5/10 monter, ≤ 3/10 baisser, plancher 1, un cran (inv. 24) | regles.md §6.5 ; A2 |
| TCH27 | Rythme pur (3/4) : Garder ce rythme et bascules — reference_tenir, bande_tenir, derive_tenir, basculer | F1·0a | `taches/pur-rythme` | `T/moteur/rythme.py`, `T/tests/test_rythme_pur.py` | TCH26 | sonnet | `test_rythme_pur.py` : 14 jours / 13 jours, bandes 5/8/2, plafond 2 × médiane + 1 | regles.md §6.6-§6.7 |
| TCH28 | Rythme pur (4/4) : constats C1-C8, retour_absence, semaine_courte + les 61 exemples chiffrés recalculés | F1·0a | `taches/pur-rythme` | `T/moteur/rythme.py`, `T/tests/test_rythme_pur.py` | TCH27 | sonnet | `test_rythme_pur.py` : 49 exemples spec-5a §7 + 12 de A2 (regles.md §6.10), un par test | regles.md §4.8, §6.9-§6.10 |
| TCH29 | Sollicitations pures : due, choisir_relance, etat_decroissance, variante, plafond_atteint | F1·0a | `taches/pur-sollicitations` | `T/moteur/sollicitations.py`, `T/tests/test_sollicitations_pures.py` | — | sonnet | `test_sollicitations_pures.py` : table spec-5a lignes choisir_relance/etat_decroissance/variante ; sautée jamais différée | regles.md §7 ; donnees.md inv. 22 |
| TCH30 | Gabarits de phrases purs : texte(type, cle, donnees, variante, nom_pour) — notifications, cartes, bilan, constats, retour, revue ; accords et formats jour/heure | F1·0a | `taches/pur-sollicitations` | `T/moteur/gabarits.py`, `T/tests/test_gabarits.py` | TCH29 | sonnet | `test_gabarits.py` : chaque gabarit de textes.md §3-§4 rendu mot pour mot, singulier et pluriel ; aucun nombre en dur | textes.md §0, §3, §4 ; donnees.md §2.12 (I9) |
| TCH31 | Santé de projet pure : avancement, burnup, sans_prochaine_action, a_l_arret, echeance_menacee, neglige, tout_fait, constat_projets | F1·0a | `taches/pur-projets` | `T/moteur/sante.py`, `T/tests/test_sante.py` | — | sonnet | `test_sante.py` : table « Cas » de regles.md §5, IR16, IR18 | regles.md §5 ; donnees.md §5 |
| TCH32 | Décalage et modèles purs : decaler (refus avant aujourd'hui), instancier, figer_modele (contenu v1) | F1·0a | `taches/pur-projets` | `T/moteur/decalage.py`, `T/tests/test_decalage.py` | TCH31 | sonnet | `test_decalage.py` : delta 7, « 2 tâches passeraient avant aujourd'hui », aller-retour figer → instancier | donnees.md §2.17, §7 ; api.md §4 decaler/instancier |
| TCH33 | Annuler côté serveur : enregistrer_geste / annuler_geste (opérations par champ, liste blanche §4, conflits, FK revérifiées) | F1·0b | `taches/socle-services` | `T/services/__init__.py`, `T/services/gestes.py`, `T/tests/test_gestes.py` | TCH9, TCH12 | sonnet | `test_gestes.py` : restauration, conflit modifiee_depuis, champ hors liste ignoré (inv. 21) | donnees.md §4 ; A7 |
| TCH34 | Seul chemin d'un jour : planifier() (select_for_update, version → ConflitVersion, reports par F(), moment dérivé) | F1·0b | `taches/socle-services` | `T/services/planification.py`, `T/tests/test_planification.py` | TCH33 | sonnet | `test_planification.py` : invariants 4, 14, 15 ; 409 conflit_version ; `check_read_modify_write.py` | donnees.md §5, inv. 4/14/15 ; regles.md §4.3 |
| TCH35 | Rappels : poser (jour/heure ou ancre), retirer, répéter, recalcul d'ancre, annulés à la clôture, ≤ 5 par tâche, ≤ 100 par compte, drapeau hors_fenetre | F1·0b | `taches/socle-services` | `T/services/rappels.py`, `T/tests/test_rappels.py` | TCH33 | sonnet | `test_rappels.py` : invariant 19, ancre effacée → annule | regles.md §7 rappels ; donnees.md §2.13 |
| TCH36 | Seul créateur : creer_taches (idempotence client_id par all_objects puis IntegrityError, ReglagesRythme née ici, triee_le, lien vérifié, récurrence, check-list, étiquettes, rappel, geste) + crochet révélations | F1·0b | `taches/socle-services` | `T/services/creation.py`, `T/services/revelations.py`, `T/tests/test_creation.py` | TCH34, TCH35, TCH10, TCH13 | sonnet | `test_creation.py` : invariants 1, 5, 9, 29 ; rejeu même client_id = même tâche ; `check_get_or_create.py` | donnees.md §5, inv. 1/5/29 ; A1 ; I8 |
| TCH37 | Nocturne orchestrée dès le socle : nocturne.executer() appelle dans l'ordre les étapes des domaines (fonctions vides livrées ici, remplies par leurs lanes) | F1·0b | `taches/socle-services` | `T/nocturne.py`, `T/services/journee.py`, `T/services/rythme.py`, `T/services/erp.py`, `T/services/purge.py`, `T/tests/test_nocturne.py` | TCH36 | sonnet | `test_nocturne.py` : ordre des étapes, rejeu idempotent ; `check_services_appeles.py` (chaque étape a un appelant non-test) | api.md §9 taches.nocturne ; donnees.md §8 |
| TCH38 | Analyseur (1/2) : table des motifs, candidats, contexte (moments nus, IR2), choix sans chevauchement, convertisseurs jour, heure, moment, échéance, durée | F1·0b | `taches/pur-saisie` | `T/saisie/grammaire.py`, `T/saisie/analyseur.py`, `T/tests/test_saisie_pure.py` | TCH6 | sonnet | `test_saisie_pure.py` : lignes jour/heure/moment/échéance/durée de la table regles.md §1.11 | regles.md §1.2-§1.5, §1.7, IR1-IR5 |
| TCH39 | Analyseur (2/2) : projet, étape, étiquette, priorité, récurrence, rappel, assembler, portes (capture : projet EXISTANT seul, pas « en réserve »), alertes | F1·0b | `taches/pur-saisie` | `T/saisie/analyseur.py`, `T/tests/test_saisie_pure.py` | TCH38 | sonnet | `test_saisie_pure.py` : reste de la table §1.11 ; porte capture A1 ; IR6, IR7 | regles.md §1.6, §1.8-§1.9 ; A1 ; A14-M6 |
| TCH40 | Collage et plan collé : decouper_collage (une première ligne + ≥ 2 lignes = projet, Moyenne par défaut, doublons, projets_communs[]) et decouper_plan (étapes, sous-tâches, ◆ jalon) | F1·0b | `taches/pur-saisie` | `T/saisie/collage.py`, `T/saisie/plan.py`, `T/tests/test_saisie_pure.py` | TCH39 | sonnet | `test_saisie_pure.py` : 4 notes Apple, 10 collages, 200 lignes, M9, A17-M3 | regles.md §1.10 ; api.md §4 planification/apercu ; A14-M9 |
| TCH41 | Jetons visuels `--tch-*` versés dans tokens.css (clair et sombre), feuille de l'app sous garde hex, fichiers de style par zone créés et importés | F1·0b | `taches/socle-front` | `frontend/src/design/tokens.css`, `frontend/scripts/check_hex.mjs`, `frontend/src/index.css`, `ST/base.css`, `ST/coeur.css`, `ST/saisie.css`, `ST/projets.css`, `ST/agenda.css`, `ST/reglages.css`, `ST/presence.css` | TCH15 | sonnet | `node frontend/scripts/check_hex.mjs` vert ; `css_golden.mjs` ; contrastes de spec-8 §3-§4 rejoués sur la planche `composants.html` | spec-8 §1-§8 ; maquette `docs/taches/maquettes/taches.css` |
| TCH42 | Client d'API complet : une fonction par route (100), fetchAllPages sur les 4 listes paginées, Idempotency-Key, proprietaire_attendu, codes 409 distingués | F1·0b | `taches/socle-front` | `frontend/src/api/tachesApi.js`, `frontend/src/api/tachesApi.test.js` | TCH15, TCH3 | sonnet | `tachesApi.test.js` : chaque fonction appelle le chemin d'api.md §3 ; réponses = `contractSamples.js` (contrat partagé, le test frontend importe les échantillons) ; `check_api_contract.py` | api.md §0, §3, §5 ; MAJ-8 ; `check_liste_page1.py` |
| TCH43 | Routes du module sans navigation : module.config.jsx (13 routes lazy, `// contextuelle:` A17), 12 pages vides, coquille commune (fiche ?tache=, saisie) et ses deux points de montage vides | F1·0b | `taches/socle-front` | `FT/module.config.jsx`, `PT/Aujourdhui.jsx`, `PT/ATrier.jsx`, `PT/Projets.jsx`, `PT/Projet.jsx`, `PT/ProjetsArchive.jsx`, `PT/ProjetsModeles.jsx`, `PT/Agenda.jsx`, `PT/Revue.jsx`, `PT/Rythme.jsx`, `PT/Recherche.jsx`, `PT/Supprimees.jsx`, `PT/Reglages.jsx`, `FT/coquille/CoquilleTaches.jsx`, `FT/fiche/Fiche.jsx`, `FT/saisie/FeuilleSaisie.jsx`, `FT/routes.test.jsx` | TCH42, TCH15 | sonnet | `routes.test.jsx` : les 13 routes d'api.md §7 rendent leur page ; `/taches` → `/taches/aujourdhui` ; aucune entrée de nav ; `check_ecrans_atteignables.py` muet (marqueurs contextuels) | api.md §7 ; spec-7 §2 ; A17 ; donnees.md inv. 28 |
| TCH44 | Composants de ligne : LigneTache (bouton Actions, menu de l'appui long, balayages, ligne gardée barrée), CaseRonde (< 0,1 s, retour arrière si échec), Etoile (4e refusée) | F1·0b | `taches/socle-front` | `FT/ui/LigneTache.jsx`, `FT/ui/CaseRonde.jsx`, `FT/ui/Etoile.jsx`, `FT/ui/LigneTache.test.jsx`, `FT/module.config.jsx` | TCH43, TCH15 | sonnet | `LigneTache.test.jsx` : rendu d'`item.json` ; Tab → Actions → item ; cibles ≥ 44 px ; maquettes `composants-1.html`, `composants-2.html`, `composants-4.html` | spec-7 §5, §6, §10 ; spec-8 §2, §5 |
| TCH45 | Composants partagés : FeuilleACrans, SelecteurProjet (« + Nouveau projet » fixe), BarreSelection (lot), BoutonCopilote (taqinor:assistant:ouvrir, sans clé : une phrase) | F1·0b | `taches/socle-front` | `FT/ui/FeuilleACrans.jsx`, `FT/ui/SelecteurProjet.jsx`, `FT/ui/BarreSelection.jsx`, `FT/ui/BoutonCopilote.jsx`, `FT/ui/composants.test.jsx`, `FT/module.config.jsx` | TCH44, TCH15 | sonnet | `composants.test.jsx` : crans 50/85 %, clavier ouvert ; maquettes `composants-5.html`, `composants-7.html` | spec-7 §10 ; textes.md §5.3 ; A12 |
| TCH46 | Gestes, annonces et clavier : useGeste (toast « Annuler » 8 s, pause au survol/focus, messages sans délai), role=status, BandeauConflit (Garder la mienne / Prendre l'autre), formats jour/heure/durée, clavier de liste | F1·0b | `taches/socle-front` | `FT/lib/gestes.js`, `FT/lib/textes.js`, `FT/lib/clavierListe.js`, `FT/ui/BandeauConflit.jsx`, `FT/lib/gestes.test.js`, `FT/lib/textes.test.js`, `FT/module.config.jsx` | TCH44, TCH15 | sonnet | `gestes.test.js` : critères a11y (1)-(4) spec-7 §6 ; `textes.test.js` : formats textes.md §0 ; aucune touche seule ne fait disparaître une ligne | spec-7 §5-§6 ; A7 ; A16-N8, N10 ; textes.md §0, §2.15 |
| TCH47 | Régénérer les fichiers dérivés de la fusion F1 : openapi-schema.yml, rbac-endpoint-inventory.md, CODEMAP + empreinte (orchestrateur) | F1·fin | `taches/orchestrateur` | `docs/openapi-schema.yml`, `docs/rbac-endpoint-inventory.md`, `docs/CODEMAP.md` | TCH15, TCH43 | haiku | `python scripts/check_openapi_schema.py --write` puis `--check` ; `codemap_fingerprint.py --check` vert | donnees.md §6 dernière vague ; CLAUDE.md CODEMAP upkeep |
| TCH48 | Saisie rapide : aperçu (jetons, projets_communs, doublons, alertes, ids → projet proposé) et création tout ou rien (201 deja_creees, 409 autre_compte) | F2·A | `taches/saisie` | `T/views/saisie.py`, `T/serializers/saisie.py`, `T/tests/test_api_saisie.py` | TCH40, TCH36, TCH15 | sonnet | `test_api_saisie.py` : réponses = `saisie_apercu.json`, `saisie_rapide.json` ; plafonds 200 lignes / 20 000 car. ; Idempotency-Key suffixée | api.md §3.2, §4 saisie-rapide ; donnees.md inv. 1, 31 |
| TCH49 | Tâches : liste paginée (vue=boite, quelque_jour, filtres, cible/cible_id/ouvertes pour ✓+), création d'une ligne, fiche (revérifie le lien), PATCH à verrou, suppression avec sous-tâches | F2·A | `taches/saisie` | `T/views/taches.py`, `T/services/taches.py`, `T/serializers/saisie.py`, `T/tests/test_api_taches.py` | TCH48 | sonnet | `test_api_taches.py` : 409 conflit_version, jour_prevu refusé au PATCH, boucle bloquee_par ≤ 50, `tache.json` | api.md §3.2, §4 taches/ ; donnees.md inv. 6, 7, 15, 27 |
| TCH50 | Actions d'état d'une tâche : planifier, terminer (sous-tâches, récurrence suivante, progression, rappels annulés), rouvrir, sauter, trancher, attendre, reçu, restaurer | F2·A | `taches/saisie` | `T/views/taches.py`, `T/services/taches.py`, `T/tests/test_api_taches.py` | TCH49 | sonnet | `test_api_taches.py` : invariants 4, 5, 16, 27 ; « Fait · prochaine jeu. 19 » (suivante) | api.md §4 ; regles.md §2, §4.3 ; MAJ-5 |
| TCH51 | Réordonner (section du jour ou projet), écho de changement, rappels (poser, retirer, répéter), règle de récurrence (PATCH, appliquer à l'ouverte, arrêter) | F2·A | `taches/saisie` | `T/views/taches.py`, `T/services/taches.py`, `T/tests/test_api_taches.py` | TCH50 | sonnet | `test_api_taches.py` : invariant 32, pas 1 024 ; `tache_changement.json` ; question_titres au 1er rappel (A17-T4) | api.md §3.2, §4 rappels/changement ; M13 |
| TCH52 | Lot (7 actions, ≤ 200, appliquées/refusées), check-list, étiquettes (paginées), vues enregistrées (filtres fermés, ≤ 30) | F2·A | `taches/saisie` | `T/views/saisie.py`, `T/services/taches.py`, `T/serializers/saisie.py`, `T/tests/test_api_saisie.py` | TCH51 | sonnet | `test_api_saisie.py` : `lot.json` ; clé de filtre inconnue → 400 nommé ; ids étrangers → refusées | api.md §3.2, §4 lot ; donnees.md §2.4-§2.6, §2.16 |
| TCH53 | Recherche (projets + tâches par mots), Supprimées récemment (un projet = une ligne), Derniers gestes, Annuler un geste | F2·A | `taches/saisie` | `T/views/saisie.py`, `T/serializers/saisie.py`, `T/tests/test_api_saisie.py` | TCH52 | sonnet | `test_api_saisie.py` : `recherche.json`, `supprimees.json`, `gestes.json`, `geste_annuler.json` ; 200 partiel | api.md §3.2, §4 ; A7 ; A16-N7 |
| TCH54 | Journée côté serveur : préfiltre unique, placement par section et motif À revoir, ordre d'affichage, compter_journee (pastille), progression | F2·A | `taches/journee` | `T/selectors/journee.py`, `T/tests/test_api_journee.py` | TCH23, TCH25, TCH37 | sonnet | `test_api_journee.py` : invariants 2, 3, 10, 11, 13, 32 | regles.md §4.1-§4.2, §4.9 ; donnees.md inv. 10-13 |
| TCH55 | ERP dans la journée : activités ouvertes, bande « Toute la journée » (visites, poses, interventions), Suivi des relances, compteurs « Ailleurs dans l'ERP » (sélecteurs des apps cibles) | F2·A | `taches/journee` | `T/selectors/erp.py`, `T/tests/test_api_journee.py` | TCH54, TCH16 | opus | `test_api_journee.py` : admin à 4 touches dont 1 à lui → nb 1 ; famille en échec absente ; `lint-imports` | spec-6a §4, crit. 8 ; A16-N4 ; donnees.md §1 FamilleObligation |
| TCH56 | GET aujourdhui/ (contrat complet, carte du moment choisie par le serveur, Proposé replié après Alléger, 200 lignes), badge/, aujourdhui/ailleurs/, vu/ (carte retour, rien sans tâche) | F2·A | `taches/journee` | `T/views/journee.py`, `T/serializers/journee.py`, `T/services/journee.py`, `T/tests/test_api_journee.py` | TCH55, TCH30 | sonnet | `test_api_journee.py` : réponse = `aujourdhui.json`, `badge.json`, `vu.json`, `ailleurs.json`, `carte_du_moment.json` ; invariant 29 | api.md §2, §3.1, §4 vu ; R16 ; A14-B1 |
| TCH57 | Proposition et « Garder ces N » : journee/proposition/ (ids étrangers ignorés, Voir tout), journee/planifier/ express (triage facultatif), journee/essentiel/ (≤ 3) | F2·A | `taches/journee` | `T/views/journee.py`, `T/services/journee.py`, `T/tests/test_api_journee.py` | TCH56 | sonnet | `test_api_journee.py` : `journee_proposition.json` ; invariant 18 ; A17-T2 | api.md §4 journee/* ; regles.md §3.4, §4.4 ; A11 |
| TCH58 | Alléger ma journée (allege_le, sans report) et Bilan du soir (cloture/ d'hier jusqu'à 12 h, cloturer/ Tout reporter, un constat) + étape nocturne « clore la veille » | F2·A | `taches/journee` | `T/views/journee.py`, `T/services/journee.py`, `T/tests/test_api_journee.py` | TCH57, TCH28 | sonnet | `test_api_journee.py` : `journee_cloture.json` ; A14-M4, A14-M7, A16-N6 ; reportées 3 fois marquées, jamais refusées | regles.md §4.5-§4.7 ; api.md §4 alleger/cloture |
| TCH59 | Agenda : jours (≤ 42), Toute la journée, sans heure, blocs, échéances, À placer, Mes projets en vue semaine, férié, externes vide, ?projet= même propriétaire | F2·A | `taches/journee` | `T/views/agenda.py`, `T/serializers/journee.py`, `T/tests/test_api_agenda.py` | TCH56 | sonnet | `test_api_agenda.py` : `agenda.json` ; 400 « 42 jours au plus. » | api.md §3.1, §4 agenda ; A16-N3, N4 ; R18 |
| TCH60 | Projets : liste (constat, compteurs, santé, À planifier), création (couleur d'office, nom pris), fiche, PATCH (statut terminé refusé), suppression avec ses tâches en un geste | F2·A | `taches/projets` | `T/views/projets.py`, `T/services/projets.py`, `T/selectors/projets.py`, `T/serializers/projets.py`, `T/tests/test_api_projets.py` | TCH31, TCH36, TCH15 | sonnet | `test_api_projets.py` : `projets_liste.json` ; invariant 27 ; IR6 | api.md §3.3, §4 projets ; donnees.md §2.1 |
| TCH61 | Ordre et cycle de vie : réordonner, Mettre en haut, trier par priorité, terminer (issue, tâches ouvertes boite/annuler/deplacer), rouvrir, restaurer (409 nom_pris) | F2·A | `taches/projets` | `T/views/projets.py`, `T/services/projets.py`, `T/tests/test_api_projets.py` | TCH60 | sonnet | `test_api_projets.py` : invariant 17, T14, N7 | api.md §4 terminer/restaurer ; R15 |
| TCH62 | Vue d'un projet (liste, tableau, chronologie : étapes, sans étape, avancement, prochain jalon, burn-up) + étapes (CRUD, réordonner) | F2·A | `taches/projets` | `T/views/projets.py`, `T/selectors/projets.py`, `T/serializers/projets.py`, `T/tests/test_api_projets.py` | TCH61 | sonnet | `test_api_projets.py` : `projet_vue.json` | api.md §4 vue ; regles.md §5 |
| TCH63 | Planifier le projet : aperçu d'une liste collée (403 confidentiel sous l'en-tête assistant), création en un tout (priorité, actions aujourd'hui/demain), Décaler les dates (aperçu, refus) | F2·A | `taches/projets` | `T/views/projets.py`, `T/services/projets.py`, `T/tests/test_api_projets.py` | TCH62, TCH32, TCH40 | sonnet | `test_api_projets.py` : `planification_apercu.json`, `decalage.json` ; A14-M3 | api.md §4 planification/decaler |
| TCH64 | Dupliquer, Enregistrer comme modèle (notes facultatives), modèles (liste, fiche, renommer, supprimer, instancier avec aperçu) | F2·A | `taches/projets` | `T/views/projets.py`, `T/services/projets.py`, `T/tests/test_api_projets.py` | TCH63 | sonnet | `test_api_projets.py` : `modele_instancier.json` | api.md §3.3, §4 modeles ; s4 §G |
| TCH65 | Revue de la semaine : bilan de semaine ou Semaine courte, cartes par projet, décision (Garder, Pause, Terminer par le même service), projet de la semaine unique | F2·A | `taches/projets` | `T/views/projets.py`, `T/services/projets.py`, `T/tests/test_api_revue.py` | TCH64 | sonnet | `test_api_revue.py` : `revue_projets.json` ; invariant 25 | api.md §4 revue ; A16-N9 |
| TCH66 | Mon rythme côté serveur : GET rythme/ (objectif, trace, bloc, tenir, 14 jours, constats, repère, préférences) et POST rythme/ (le nombre dit s'applique aussitôt, 400 hors 1-12) | F2·A | `taches/rythme` | `T/views/rythme.py`, `T/services/rythme.py`, `T/selectors/rythme.py`, `T/serializers/rythme.py`, `T/tests/test_api_rythme.py` | TCH28, TCH30, TCH37 | sonnet | `test_api_rythme.py` : `rythme.json` ; A2.1 ; MAJ-6 (mode par cette route seule) | api.md §3.4, §4 rythme ; regles.md §6 |
| TCH67 | Répondre à une carte : propositions/{id}/repondre/ (réponses permises par clé, 409 expirée, refus comptés sous verrou, baisse jamais imposée) | F2·A | `taches/rythme` | `T/views/rythme.py`, `T/services/rythme.py`, `T/tests/test_api_rythme.py` | TCH66 | sonnet | `test_api_rythme.py` : `proposition.json` ; invariant 24 ; `check_read_modify_write.py` | donnees.md §1 réponses permises ; R9 |
| TCH68 | Préférences dites (11 clés, validation, anciens noms refusés, retirer) et en-tête du Copilote (2 lignes ≤ 300 caractères) | F2·A | `taches/rythme` | `T/views/rythme.py`, `T/services/rythme.py`, `T/tests/test_api_rythme.py` | TCH67 | sonnet | `test_api_rythme.py` : `coach_entete.json` ; « Heure attendue (HH:MM). » | donnees.md §2.11 ; api.md §4 preferences, coach/entete |
| TCH69 | Réglages : GET et PATCH en liste blanche, question du titre au 1er rappel, couper « Comprendre mon rythme » efface le profil, réactiver un type en pause | F2·A | `taches/rythme` | `T/views/reglages.py`, `T/services/rythme.py`, `T/tests/test_api_reglages.py` | TCH68 | opus | `test_api_reglages.py` : `reglages.json` ; champ hors liste → « Non modifiable ici. » ; effacements donnees.md §8 | api.md §4 reglages ; MAJ-6 ; socle §8 registre |
| TCH70 | Révélations à leur événement et étapes nocturnes du rythme (jour clos, blocs et propositions, dérive, constats, révélation revue, expirations, ignorées, pauses à 14) | F2·A | `taches/rythme` | `T/services/revelations.py`, `T/services/rythme.py`, `T/tests/test_nocturne_rythme.py` | TCH69, TCH29 | sonnet | `test_nocturne_rythme.py` : I13, I14 ; rejeu déterministe ; cartes J+7, mon_iphone J+3 | api.md §9 ; regles.md §6, §7 ; A17-T3 |
| TCH71 | Suggestions venues de l'ERP : abonnés aux 5 signaux existants (destinataire strict, conditions, anti-doublon, retrait à l'annulation) connectés dans apps.py | F2·A | `taches/erp` | `T/receivers.py`, `T/services/erp.py`, `T/apps.py`, `T/tests/test_suggestions.py` | TCH36, TCH13 | opus | `test_suggestions.py` : spec-6a crit. 9-12 ; `orphan_signals()` vide ; aucun signal nouveau (`core/event_coverage.py`) | regles.md §9 ; A4 ; IR14 |
| TCH72 | Routes des suggestions : liste (≤ 20, < 7 jours), Ajouter (titre éditable), Pas utile | F2·A | `taches/erp` | `T/views/erp.py`, `T/serializers/erp.py`, `T/services/erp.py`, `T/tests/test_suggestions.py` | TCH71 | opus | `test_suggestions.py` : `suggestions.json` ; id d'un autre → 404 | api.md §3.2, §4 suggestions |
| TCH73 | Convertir les à-faire personnels (200 partiel, raisons) et Lier une tâche à une activité ERP (409 deja_lie, l'activité reste ouverte) | F2·A | `taches/erp` | `T/views/erp.py`, `T/services/erp.py`, `T/tests/test_erp.py` | TCH72, TCH17 | opus | `test_erp.py` : `convertir_activite.json`, `lier_activite.json` ; invariant 30 | api.md §4 convertir/lier ; A17 ; R19 |
| TCH74 | Données personnelles : fournisseur d'effacement 09-08 (lead effacé), export « Mes données » des 20 modèles, « Tout effacer » (EFFACER, suppression dure) | F2·A | `taches/erp` | `T/dsr.py`, `T/apps.py`, `T/services/donnees.py`, `T/views/donnees.py`, `T/tests/test_donnees.py` | TCH73 | opus | `test_donnees.py` : spec-6a crit. 3, 14 ; jetons sans empreinte ; `check_exports_bornes.py` | donnees.md §5 fournisseur, §8 ; MAJ-7 ; socle §8 |
| TCH75 | Purge et revérification nocturnes : rétentions (PlanJour 400 j, lignes 90 j, journal 90 j, rappels 30 j, gestes 7 j, suggestions 30 j, supprimées 30 j) et liens des tâches ouvertes | F2·A | `taches/erp` | `T/services/purge.py`, `T/services/erp.py`, `T/tests/test_donnees.py` | TCH74 | opus | `test_donnees.py` : purge par dates, lien introuvable/inaccessible ; `trash` ne voit rien (invariant 26) | donnees.md §8 ; A15 ; socle §8 purge |
| TCH76 | Écran Aujourd'hui : ordre vertical, sections, repliés, squelette après 1 s, erreur « Pas à jour · Réessayer » sans vider la liste, vide « Colle ou dicte tes listes », relecture au focus | F2·A | `taches/ecran-aujourdhui` | `PT/Aujourdhui.jsx`, `FT/aujourdhui/Sections.jsx`, `ST/coeur.css`, `PT/Aujourdhui.test.jsx`, `FT/module.config.jsx` | TCH46, TCH15 | sonnet | `Aujourdhui.test.jsx` sur `aujourdhui.json` ; maquettes `ecran-aujourdhui-matin.html`, `-matin-bas`, `-vide`, `composants-3.html`, `composants-9.html`, `composants-10.html` ; critère (5) 130 % | spec-7 §4 ; A14-M1 ; A11 |
| TCH77 | Progression « 1 sur 5 · essentiel 0/2 » (Reprise, toucher → Mon rythme), AnneauProgression et carte du moment (ordre serveur, brouillon devant, astuce derrière, Mon iPhone 3 jours, réponses) | F2·A | `taches/ecran-aujourdhui` | `FT/aujourdhui/Progression.jsx`, `FT/ui/AnneauProgression.jsx`, `FT/ui/CarteDuMoment.jsx`, `FT/ui/CarteDuMoment.test.jsx`, `PT/Aujourdhui.jsx`, `FT/module.config.jsx` | TCH76 | sonnet | `CarteDuMoment.test.jsx` sur `carte_du_moment.json`, `proposition.json` ; maquettes `ecran-aujourdhui-retour.html`, `ecran-aujourdhui-15h.html` | spec-7 §4 carte du moment ; A14-B1, A16-N9, A17-T3 |
| TCH78 | Proposé pour aujourd'hui : « Garder ces N » (contour), surcharge, Voir tout groupé par projet, ★ (≤ 3) puis focus sur Prévu, « Planifier avec le Copilote » | F2·A | `taches/ecran-aujourdhui` | `FT/aujourdhui/Propose.jsx`, `FT/aujourdhui/Propose.test.jsx`, `PT/Aujourdhui.jsx`, `FT/module.config.jsx` | TCH77 | sonnet | `Propose.test.jsx` sur `journee_proposition.json` ; critère (8) focus ; maquette `ecran-aujourdhui-matin.html` | spec-7 §4 ; A11 ; A17-M1 |
| TCH79 | Menu ⋯ d'Aujourd'hui (Alléger, Réorganiser, Sélectionner, En faire mon accueil) et feuille « Alléger ma journée » | F2·A | `taches/ecran-aujourdhui` | `FT/aujourdhui/MenuJournee.jsx`, `FT/aujourdhui/FeuilleAlleger.jsx`, `FT/aujourdhui/FeuilleAlleger.test.jsx`, `PT/Aujourdhui.jsx`, `FT/module.config.jsx` | TCH78 | sonnet | `FeuilleAlleger.test.jsx` : rien coché, « 3 retournées aux projets » annoncé ; maquettes `ecran-aujourdhui-15h-menu.html`, `-15h-bas` | spec-7 §2, §4 ; A14-M7 ; A16-N6 |
| TCH80 | Feuille « Bilan du soir » : 4 sur 5 et gardées faites, par reste Reporter à lun. 23 · Choisir un jour · En réserve · Abandonner, Tout reporter, un constat, un mot, d'hier jusqu'à 12 h | F2·A | `taches/ecran-aujourdhui` | `FT/aujourdhui/FeuilleBilan.jsx`, `FT/aujourdhui/FeuilleBilan.test.jsx`, `PT/Aujourdhui.jsx`, `FT/module.config.jsx` | TCH79 | sonnet | `FeuilleBilan.test.jsx` sur `journee_cloture.json` ; maquettes `ecran-bilan.html`, `ecran-bilan-bas.html`, `ecran-bilan-rythme.html` | spec-7 §4 ; A14-M4 ; A16-M2 |
| TCH81 | Lignes de l'ERP sur Aujourd'hui : activités (badge ERP, case si peut_cloturer, sans Annuler), Toute la journée, Suivi des relances, Ailleurs dans l'ERP, appui long « Lier une tâche », À revoir (Tout en réserve), En attente, Faites | F2·A | `taches/ecran-aujourdhui` | `FT/aujourdhui/LignesErp.jsx`, `FT/aujourdhui/Replies.jsx`, `FT/aujourdhui/LignesErp.test.jsx`, `PT/Aujourdhui.jsx`, `FT/module.config.jsx` | TCH80 | sonnet | `LignesErp.test.jsx` sur `aujourdhui.json`, `ailleurs.json`, `lier_activite.json` ; maquette `composants-4.html` | spec-7 §4-§5 ; spec-6a §6 ; A17 lier |
| TCH82 | Saisie : ChampSaisie (puces reconnues, ×, ignorer, `#projet`), SelecteurQuand (tuiles, date, « 10 h »), feuille de saisie au bouton flottant avec brouillon | F2·A | `taches/ecran-saisie` | `FT/ui/ChampSaisie.jsx`, `FT/ui/SelecteurQuand.jsx`, `FT/saisie/FeuilleSaisie.jsx`, `FT/saisie/FeuilleSaisie.test.jsx`, `ST/saisie.css`, `FT/module.config.jsx` | TCH46, TCH15 | sonnet | `FeuilleSaisie.test.jsx` sur `saisie_apercu.json` ; annexe A spec 2 ; maquettes `ecran-saisie.html`, `composants-5.html`, `composants-6.html` | spec-7 §4, §7 parcours 1-2 ; A16-N1 |
| TCH83 | Coller mes listes : ApercuListe (un projet par collage, puce de priorité Moyenne, doublons, Coller encore, Créer N tâches), carte Mon iPhone après le 1er collage | F2·A | `taches/ecran-saisie` | `FT/ui/ApercuListe.jsx`, `FT/saisie/ColleListes.jsx`, `FT/ui/ApercuListe.test.jsx`, `FT/module.config.jsx` | TCH82 | sonnet | `ApercuListe.test.jsx` sur `saisie_apercu.json`, `saisie_rapide.json` ; maquette `ecran-saisie-liste.html` | spec-7 §8 ; A14-M5, M9 ; A17-M3 |
| TCH84 | Fiche d'une tâche (?tache=) : Quand, Échéance, Projet, Priorité, ★, notes, check-list, Reporter, Fait, conflit sans perte, « Encore 10 min · 1 h · Demain 9 h » ouverte par un rappel | F2·A | `taches/ecran-saisie` | `FT/fiche/Fiche.jsx`, `FT/fiche/Fiche.test.jsx`, `FT/module.config.jsx` | TCH83 | sonnet | `Fiche.test.jsx` sur `tache.json`, `tache_ecrite.json`, `erreurs.json` (409) ; maquette `ecran-fiche.html` | spec-7 §4 ; A16-N8 ; A17 rappel |
| TCH85 | Fiche → Plus : Répéter, étiquettes, durée, en attente de (personne ou tâche), jalon, lié à, confidentielle, sous-tâches, rappel avec question du titre, Abandonner, Supprimer (dialogue nommant) | F2·A | `taches/ecran-saisie` | `FT/fiche/FichePlus.jsx`, `FT/fiche/FichePlus.test.jsx`, `FT/fiche/Fiche.jsx`, `FT/module.config.jsx` | TCH84 | sonnet | `FichePlus.test.jsx` ; maquette `ecran-fiche-plus.html` | spec-7 §2 lignes Plus ; A17-T4 ; textes.md §2.4 |
| TCH86 | Écran À trier : Suggéré par l'ERP (Ajouter, Pas utile), bandeau à convertir, Aujourd'hui · Demain · Projet… · ⋯, Trier une par une, En réserve, Tout ranger, « Ranger avec le Copilote » | F2·A | `taches/ecran-saisie` | `PT/ATrier.jsx`, `FT/atrier/TrierUneParUne.jsx`, `PT/ATrier.test.jsx`, `FT/module.config.jsx` | TCH85 | sonnet | `ATrier.test.jsx` sur `suggestions.json`, `lot.json`, `convertir_activite.json` ; maquettes `ecran-a-trier.html`, `ecran-a-trier-bas.html` | spec-7 §4 ; spec-6a §6 ; textes.md §2.5 |
| TCH87 | Écrans Recherche (Faites aussi, Projet ▾, Priorité haute, 7 filtres repliés, tri, Enregistrer une vue) et Supprimées récemment (Restaurer, un projet = une ligne, Derniers gestes) | F2·A | `taches/ecran-saisie` | `PT/Recherche.jsx`, `PT/Supprimees.jsx`, `PT/Recherche.test.jsx`, `FT/module.config.jsx` | TCH86 | sonnet | `Recherche.test.jsx` sur `recherche.json`, `supprimees.json`, `gestes.json` ; aucune maquette d'écran (états vides `composants-9.html`) | spec-7 §4 ; textes.md §2.12-§2.13 ; A16-N7 |
| TCH88 | Écran Projets : puce de priorité touchable, « 12 sur 20 », à surveiller, À planifier, Nouveau projet, En pause replié, Mettre en haut, Trier par priorité, Archive et Modèles par ⋯ | F2·A | `taches/ecran-projets` | `PT/Projets.jsx`, `FT/projets/LigneProjet.jsx`, `ST/projets.css`, `PT/Projets.test.jsx`, `FT/module.config.jsx` | TCH46, TCH15 | sonnet | `Projets.test.jsx` sur `projets_liste.json` ; maquette `projets-liste.html` | spec-7 §4 ; A14-M3 ; A16-M3 |
| TCH89 | Écran Un projet, vue Liste : étapes, ajouter, santé si signal, Détails, Faites, ⋯ (Voir dans l'agenda, Décaler, Modèle, Dupliquer, Pause, Terminer, Supprimer « … et ses 25 tâches ? ») | F2·A | `taches/ecran-projets` | `PT/Projet.jsx`, `FT/projets/VueListe.jsx`, `PT/Projet.test.jsx`, `FT/module.config.jsx` | TCH88 | sonnet | `Projet.test.jsx` sur `projet_vue.json` ; maquette `projet-liste.html` | spec-7 §4 ; A16-N7 |
| TCH90 | Vues Tableau et Chronologie d'un projet (mémorisées), burn-up reconstruit | F2·A | `taches/ecran-projets` | `FT/ui/Tableau.jsx`, `FT/projets/VueChronologie.jsx`, `FT/projets/VueChronologie.test.jsx`, `PT/Projet.jsx`, `FT/module.config.jsx` | TCH89 | sonnet | `VueChronologie.test.jsx` ; dnd au clavier (`kanbanA11y.js`) ; maquettes `projet-tableau.html`, `projet-chronologie.html` | spec-7 §9-§10 ; spec-4 |
| TCH91 | Planifier le projet : priorité + « fini quand… », échéance (1 sem → 3 mois), actions, étapes, jalons, risque, brouillon gardé, « Planifier avec le Copilote » | F2·A | `taches/ecran-projets` | `FT/projets/PlanifierProjet.jsx`, `FT/projets/PlanifierProjet.test.jsx`, `PT/Projet.jsx`, `FT/module.config.jsx` | TCH90 | sonnet | `PlanifierProjet.test.jsx` sur `planification_apercu.json` ; parcours 10 = 7 gestes ; maquettes `projet-planifier.html`, `projet-planifier-2.html` | spec-7 §4, §7 ; A14-M3 |
| TCH92 | Écrans Archive et Modèles (instancier avec aperçu) + dialogues Décaler les dates, Terminer (issue), Dupliquer, Enregistrer comme modèle | F2·A | `taches/ecran-projets` | `PT/ProjetsArchive.jsx`, `PT/ProjetsModeles.jsx`, `FT/projets/Dialogues.jsx`, `FT/projets/Dialogues.test.jsx`, `FT/module.config.jsx` | TCH91 | sonnet | `Dialogues.test.jsx` sur `decalage.json`, `modele_instancier.json` ; vides « Aucun projet archivé » / « Aucun modèle » | spec-7 §4 ; textes.md §2.6 |
| TCH93 | Écran Revue de la semaine : 4 faits ou Semaine courte, cartes Garder · Pause · Terminer · Suivant, intention, projet de la semaine, fin → Planifier ma semaine | F2·A | `taches/ecran-projets` | `PT/Revue.jsx`, `PT/Revue.test.jsx`, `FT/module.config.jsx` | TCH92 | sonnet | `Revue.test.jsx` sur `revue_projets.json` ; maquette `revue-semaine.html` | spec-7 §4 ; A16-N3, N9 ; textes.md §2.7, §4.6 |
| TCH94 | Régénérer les fichiers dérivés de la fusion F2 (openapi, inventaire RBAC, CODEMAP + empreinte) | F2·fin | `taches/orchestrateur` | `docs/openapi-schema.yml`, `docs/rbac-endpoint-inventory.md`, `docs/CODEMAP.md` | TCH53, TCH59, TCH65, TCH70, TCH75 | haiku | `check_openapi_schema.py --check`, `codemap_fingerprint.py --check` verts | CLAUDE.md CODEMAP upkeep |
| TCH95 | Jetons d'accès : authentification par jeton par usage (compte actif interne, user_can_operate, société du jeton en mémoire), débits, routes jetons/ (clair rendu une fois, l'ancien révoqué) | F3·B | `taches/presence` | `T/auth_jeton.py`, `T/throttles.py`, `T/views/presence.py`, `T/serializers/presence.py`, `T/tests/test_jetons.py` | TCH15, TCH12 | opus | `test_jetons.py` : jeton flux sur capture → 401 identique à un inconnu ; multi-sociétés MAJ-4 ; aucun jeton dans un journal ; `jeton.json` | api.md §0 J:x ; donnees.md §2.14, §5 ; socle §2.5 |
| TCH96 | Capture Siri : capture/ analysée comme la saisie (porte capture), `dans`, réponse lue `?reponse=texte` (textes §7, 401 et 429 lisibles), rejeu deja | F3·B | `taches/presence` | `T/views/presence.py`, `T/tests/test_capture.py` | TCH95, TCH39 | opus | `test_capture.py` : `capture.json` ; « Ajouté pour demain 10 h : appeler le fournisseur » ; invariant 20 | api.md §4 capture ; A1 ; textes.md §7 |
| TCH97 | Flux de calendrier abonné (.ics, no-store, 404 neutre) et tuile Scriptable (JSON) ; test de notification hors plafond | F3·B | `taches/presence` | `T/views/presence.py`, `T/tests/test_flux_tuile.py` | TCH96, TCH24, TCH56 | opus | `test_flux_tuile.py` : `tuile.json` ; ni notes, ni tâche d'un collègue, ni faite ; confidentielle masquée | regles.md §10 ; api.md §3.4 ; spec-6b crit. |
| TCH98 | Balayage de chaque minute : rappels dus groupés (manqué > 2 h), sollicitations dues (plafond 3, sautée jamais différée), marqueur + notify dans la même transaction, pastille dans la charge | F3·B | `taches/presence` | `T/balayage.py`, `T/tests/test_balayage.py` | TCH97, TCH70, TCH21 | sonnet | `test_balayage.py` : invariant 22 ; rejouer n'envoie rien de plus ; corps sans titre par défaut ; `check_notify_point_unique.py` | api.md §9 ; regles.md §7 |
| TCH99 | Tâches planifiées et réglages : sweeps.py (taches.balayer, taches.nocturne, sociétés actives), beats dans celery.py, TACHES_RACCOURCI_SIRI_URL et taches_rappel immédiat dans settings, .env.example | F3·B | `taches/presence` | `T/sweeps.py`, `DJ/erp_agentique/celery.py`, `DJ/erp_agentique/settings/base.py`, `.env.example`, `T/tests/test_balayage.py` | TCH98 | sonnet | `check_celery_tasks.py`, `check_beat_active_companies.py`, `check_settings_declares.py`, `check_commandes_planifiees.py` verts | api.md §9 ; min-22 |
| TCH100 | Hors ligne : file d'envoi du module (ajouter, cocher, reporter), proprietaire_attendu, 409 autre_compte jeté, conflit vers le bandeau, cache par compte et par jour vidé à la déconnexion, le reste grisé | F3·B | `taches/presence-front` | `FT/horsligne/captureQueue.js`, `FT/horsligne/cacheJournee.js`, `frontend/src/api/tachesApi.js`, `FT/coquille/CoquilleTaches.jsx`, `FT/horsligne/captureQueue.test.js`, `FT/module.config.jsx` | TCH46 | sonnet | `captureQueue.test.js` : 3 ops rejouées, autre compte jeté (invariant 31) ; contrat partagé `saisie_rapide.json`, `tache_ecrite.json` | api.md §5 ; A16-N11 ; MAJ-9 |
| TCH101 | Pastille : useBadgeTaches (badge/, setAppBadge), compte À trier pour l'onglet | F3·B | `taches/presence-front` | `FT/useBadgeTaches.js`, `FT/useBadgeTaches.test.js`, `FT/module.config.jsx` | TCH100 | sonnet | `useBadgeTaches.test.js` sur `badge.json` ; gardées seules (A16-N5) | donnees.md inv. 11 ; spec-6b |
| TCH102 | Créer une tâche depuis ici : hôte TachesPresence (c t, palette quick-create), cibleEcran (pré-lien aligné sur liens_cibles.json et entityRoutes), BoutonTachesIci ✓+ (compte, liste, cocher, Nouvelle tâche liée) | F3·B | `taches/presence-front` | `FT/presence/TachesPresence.jsx`, `FT/presence/cibleEcran.js`, `FT/presence/BoutonTachesIci.jsx`, `FT/presence/TachesPresence.test.jsx`, `ST/presence.css`, `FT/module.config.jsx` | TCH101 | sonnet | `TachesPresence.test.jsx` : spec-6a crit. 5 (gabarits `liens_cibles.json` = cibleDepuisEcran = entityRoutes.ROUTE) ; masqué sans `taches_voir` | spec-6a §6 ; A10 ; spec-7 §5 N1 |
| TCH103 | Carte du cockpit « 1 sur 5 », 3 lignes (essentiel d'abord), Ouvrir, « Rien de gardé » | F3·B | `taches/presence-front` | `FT/presence/CarteMesTaches.jsx`, `FT/presence/CarteMesTaches.test.jsx`, `FT/module.config.jsx` | TCH102 | sonnet | `CarteMesTaches.test.jsx` sur `aujourdhui.json` ; maquette `cockpit-carte.html` | spec-7 §4 carte cockpit ; spec-6a §6 |
| TCH104 | Écran Agenda : vues Jour, Semaine, Mois, À venir, ← Aujourd'hui →, Toute la journée, Férié, GrilleAgenda (créneau vide = Ajouter à son heure) | F3·B | `taches/ecran-agenda` | `PT/Agenda.jsx`, `FT/ui/GrilleAgenda.jsx`, `FT/agenda/VueMois.jsx`, `PT/Agenda.test.jsx`, `ST/agenda.css`, `FT/module.config.jsx` | TCH46, TCH15 | sonnet | `Agenda.test.jsx` sur `agenda.json` ; maquettes `agenda-jour.html`, `agenda-semaine.html`, `agenda-mois.html`, `agenda-a-venir.html`, `composants-8.html` | spec-7 §4 ; A16-N4 ; textes.md §2.8 |
| TCH105 | VoletAPlacer et « Placer à une heure » (toucher la tâche puis le créneau, durée par pas de 15, Maj+↓) | F3·B | `taches/ecran-agenda` | `FT/ui/VoletAPlacer.jsx`, `FT/ui/VoletAPlacer.test.jsx`, `PT/Agenda.jsx`, `FT/module.config.jsx` | TCH104 | sonnet | `VoletAPlacer.test.jsx` ; parcours 17 = 9 gestes ; maquettes `agenda-placer-heure.html`, `agenda-placer-heure-duree.html` | spec-7 §2, §7 ; `dndA11y.js` |
| TCH106 | Planifier ma semaine : Semaine + À placer + Mes projets, toucher une tâche puis un jour, glisser au bureau, 7 lignes sur iPhone, ouvert par ?placer=1 depuis la Revue | F3·B | `taches/ecran-agenda` | `FT/agenda/PlanifierSemaine.jsx`, `FT/agenda/PlanifierSemaine.test.jsx`, `PT/Agenda.jsx`, `FT/module.config.jsx` | TCH105 | sonnet | `PlanifierSemaine.test.jsx` ; parcours 16 = 31 gestes ; maquettes `agenda-semaine-planifier.html`, `agenda-semaine-planifier-pose.html` | A16-N3 ; R18 |
| TCH107 | Écran Mon rythme : aujourd'hui, 3 modes, 14 jours, proposition, constats, Mes jours (congés, jours courts, temps disponible), Comprendre mon rythme, « Parler de mon rythme » | F3·B | `taches/ecran-reglages` | `PT/Rythme.jsx`, `FT/rythme/MesJours.jsx`, `PT/Rythme.test.jsx`, `ST/reglages.css`, `FT/module.config.jsx` | TCH46, TCH15 | sonnet | `Rythme.test.jsx` sur `rythme.json`, `proposition.json` ; maquette `rythme.html` ; vide « 3 jours sur 10 » | spec-7 §4 ; textes.md §2.11, §4 ; A2 |
| TCH108 | Écran Réglages : Notifications (heures, Message de 15 h, revue, réactiver), Vie privée (texte exact), L'ERP me suggère, Mes données (Exporter, Tout effacer), Avancé (messages sans délai, agenda ICS) | F3·B | `taches/ecran-reglages` | `PT/Reglages.jsx`, `FT/reglages/ViePrivee.jsx`, `FT/reglages/Rubriques.jsx`, `PT/Reglages.test.jsx`, `FT/module.config.jsx` | TCH107 | sonnet | `Reglages.test.jsx` sur `reglages.json`, `agenda_externe.json` ; texte Vie privée = textes.md §6 mot pour mot ; aucune maquette (hors Mon iPhone) | spec-7 §4 ; textes.md §2.14, §6 ; A9 |
| TCH109 | Mon iPhone : 5 étapes repliables, jetons (Créer, Copier, Régénérer, Révoquer, dernier usage), Envoyer un test, S'abonner, Installer le raccourci si l'URL est posée, En faire mon accueil, Ce qui est visible | F3·B | `taches/ecran-reglages` | `FT/iphone/MonIphone.jsx`, `FT/iphone/MonIphone.test.jsx`, `PT/Reglages.jsx`, `FT/module.config.jsx` | TCH108 | sonnet | `MonIphone.test.jsx` sur `jeton.json`, `reglages.json` ; maquette `mon-iphone.html` ; textes.md §7 mot pour mot | spec-6b §9 ; textes.md §7 ; A14-M5 ; A16-N12 |
| TCH110 | Script de la grande tuile Scriptable (≤ 90 lignes, textes §8) + « Copier le script » | F3·B | `taches/ecran-reglages` | `FT/iphone/scriptTuile.js`, `FT/iphone/scriptTuile.test.js`, `FT/iphone/MonIphone.jsx`, `FT/module.config.jsx` | TCH109 | sonnet | `scriptTuile.test.js` : lit `faites`, `prevues`, `objectif`, `essentiel.prevues` de `tuile.json` ; ≤ 90 lignes ; maquette `tuile.html` | spec-6b annexe A ; textes.md §8 ; C35 |
| TCH111 | Actions de l'assistant : agent_actions.py (16 clés, taches_voir, RISK_INTERNAL, lot copilote, ≤ 3 écritures, échos) + platform.py déclare agent_actions_module | F3·B | `taches/assistant` | `T/agent_actions.py`, `T/platform.py`, `T/tests/test_agent_actions.py` | TCH15 | opus | `test_agent_actions.py` : méthode et droit = route (api.md §8) ; échos sans écriture ; `check_action_permission_override.py`, `check_platform.py` | api.md §8 ; A5 ; spec-5b §1 |
| TCH112 | Registre de l'agent : clés `taches.*` et cartes au registre + échantillon assistant_reponse.json | F3·B | `taches/assistant` | `DJ/apps/agent/registry.py`, `DJ/apps/agent/contract_samples/assistant_reponse.json`, `DJ/apps/agent/tests/test_registry.py` | TCH111 | opus | `apps/agent/tests/test_registry.py` : carte ∈ CARTES ; `check_api_shapes.py` | spec-5b §10.4 ; api.md §8 |
| TCH113 | Consignes du Copilote : bloc « TÂCHES — CONSIGNES DU COPILOTE » (texte exact, 278 mots, 0 chiffre) + constantes de test recalculées | F3·B | `taches/assistant` | `backend/fastapi_ia/app/services/prompt_copilote.py`, `backend/fastapi_ia/tests/test_prompt_copilote.py` | TCH112 | opus | `backend/fastapi_ia/tests/test_prompt_copilote.py` : texte = textes.md §5.1 ; ≤ 280 mots ; 10 clés | textes.md §5.1 ; IT10 |
| TCH114 | Contexte d'écran et jeu d'outils : catalogue_pour_tour (Groq + écran /taches → 5 actions), lien pris du contexte, sortie bornée, en-tête X-Taqinor-Assistant | F3·B | `taches/assistant` | `backend/fastapi_ia/app/services/relais_copilote.py`, `backend/fastapi_ia/app/services/action_tools.py`, `backend/fastapi_ia/tests/test_action_tools.py` | TCH113 | opus | `test_action_tools.py` : 16 actions sous claude, 5 sous Groq sur /taches, 0 hors /taches | spec-5b §7 ; api.md §0, §8 |
| TCH115 | Masquage du journal de l'assistant : tour à outil `taches.*` OU écran /taches → question « [tâches — privé] », réponse et erreur vidées | F3·B | `taches/assistant` | `backend/fastapi_ia/app/services/sql_agent_service.py`, `backend/fastapi_ia/tests/test_sql_agent_endpoint.py` | TCH114 | opus | `test_sql_agent_endpoint.py` : avec outil ; sans outil sur /taches/aujourdhui ; tour CRM intact | socle §2.6, §8 Coach ; spec-5b §8 |
| TCH116 | Douze conversations d'évaluation du Copilote (CASES_COACH, cartes attendues, injections) | F3·B | `taches/assistant` | `backend/fastapi_ia/tests/eval/cases_commerciaux.py`, `backend/fastapi_ia/tests/eval/runner.py`, `backend/fastapi_ia/tests/test_eval_harness.py` | TCH115 | opus | `test_eval_harness.py` : 12 cas, ids uniques, clés ⊆ CLES_COACH, réponse idéale à 100 % | spec-5b annexe |
| TCH117 | Cartes Tâches du Copilote : ma_journee, plan_propose (adopter = « Garder ces N » express), liste_taches, tache (écho ou écriture), capture_apercu, rythme, plan_projet, projet, revue_semaine | F3·B | `taches/cartes` | `FT/cartes/CartesTaches.jsx`, `FT/cartes/CartesTaches.test.jsx`, `FT/module.config.jsx` | TCH83 | sonnet | `CartesTaches.test.jsx` rend chaque échantillon (contrat partagé `contractSamples.js`) via CarteResultat ; maquette `copilote.html` | api.md §8 ; textes.md §5.4 ; A17-T2 |
| TCH118 | Branchement des cartes et des 4 demandes prêtes : cartes.js, CartesDuMessage.jsx, copilotMessages.js (ouvert depuis /taches, sans clé : une phrase) | F3·B | `taches/cartes` | `frontend/src/features/ia/cartes/cartes.js`, `frontend/src/features/ia/cartes/CartesDuMessage.jsx`, `frontend/src/features/ia/copilotMessages.js`, `frontend/src/features/ia/cartes/cartes.test.jsx`, `frontend/src/features/ia/copilotMessages.test.mjs` | TCH117 | sonnet | `cartes.test.jsx`, `copilotMessages.test.mjs` : 4 demandes de textes.md §5.2 ; aucune régression des cartes CRM | A12 ; textes.md §5.2 ; spec-5b §10.7 |
| TCH119 | Raccourcis clavier et palette : c t / g j, entrées de palette (Créer une tâche, Chercher dans mes tâches, Nouveau projet, Faire le bilan, 4 onglets), filtre des entrées à événement, aide du module, entité « tache » | F3·B | `taches/etranger-deploy` | `frontend/src/providers/shortcuts.js`, `frontend/src/providers/commandActions.js`, `frontend/src/providers/focusedRecordShortcuts.jsx`, `frontend/src/lib/search/entityRoutes.js`, `frontend/src/providers/commandActions.test.mjs` | — | sonnet | `commandActions.test.mjs`, `focusedRecordShortcuts.test.jsx`, `entityRoutes.test.jsx` : `g t` reste au SAV ; clavier muet sous dialogue (N1) | spec-7 §5 N1, N2 ; A10 ; A14-M11 ; spec-6a §9 |
| TCH120 | Service worker et manifeste : badge de l'app sur réception, clic de notification vers les liens d'api.md §7, raccourci de manifeste « Tâches » | F3·B | `taches/etranger-deploy` | `frontend/src/sw.js`, `frontend/vite.config.js`, `frontend/src/features/pwa/shortcuts.test.mjs` | — | sonnet | `shortcuts.test.mjs` ; lien rappel → /taches/aujourdhui?tache=<id> | api.md §7 ; spec-6b §2-§3 |
| TCH121 | Agenda externe (AVANCÉ) : modèle AgendaExterne + migration 0002, lecture d'une adresse ICS bornée (https, hôte public, taille, délai, cache, états), routes agenda-externe/ | F3·B | `taches/agenda-externe` | `T/models/agenda.py`, `T/models/__init__.py`, `T/migrations/0002_agendaexterne.py`, `T/services/agenda_externe.py`, `T/views/agenda_externe.py`, `T/tests/test_agenda_externe.py` | TCH9 | opus | `test_agenda_externe.py` : adresse privée/http refusée « Adresse https publique attendue. », trop grande, délai ; `agenda_externe.json` ; jamais au flux, à la tuile, à l'assistant | donnees.md §2.20 ; A14-M8 ; api.md §3.4 |
| TCH122 | Événements externes dans agenda/ (clé `externes`, cache borné) sous plafond de requêtes | F3·B | `taches/agenda-externe` | `T/views/agenda.py`, `T/tests/test_agenda_externe.py` | TCH121 | opus | `test_agenda_externe.py` : `agenda.json` avec externes ; agenda/ ≤ 16 requêtes | api.md §4 agenda ; A14-M8 |
| TCH123 | Monter l'hôte et le bouton ✓+ dans la coquille de l'ERP : Layout.jsx (TachesPresence) et Header.jsx (BoutonTachesIci) | F3·C | `taches/etranger-coquille` | `frontend/src/components/layout/Layout.jsx`, `frontend/src/components/layout/Header.jsx`, `frontend/src/components/layout/Header.test.jsx` | TCH102 | sonnet | `Header.test.jsx` : ✓+ masqué sans `taches_voir` ; en-tête mobile serré → menu utilisateur | spec-6a §6, §9 |
| TCH124 | Pastille d'onglet et badges personnels : BottomTabBar.jsx (À trier, masquée à 0) et useAppBadges.js (badgePersonnel des module.config) | F3·C | `taches/etranger-coquille` | `frontend/src/components/layout/BottomTabBar.jsx`, `frontend/src/lib/apps/useAppBadges.js`, `frontend/src/components/layout/BottomTabBar.test.jsx`, `frontend/src/lib/apps/useAppBadges.test.jsx` | TCH101 | sonnet | `BottomTabBar.test.jsx`, `useAppBadges.test.jsx` | spec-7 §2 ; spec-6a §9 |
| TCH125 | Carte du cockpit montée : Dashboard.jsx (bureau) | F3·C | `taches/etranger-coquille` | `frontend/src/pages/Dashboard.jsx`, `frontend/src/pages/Dashboard.cockpit.test.jsx` | TCH103 | sonnet | `Dashboard.cockpit.test.jsx` étendu : carte lazy présente avec `taches_voir`, absente sinon | spec-6a §9 |
| TCH126 | Carte du cockpit mobile et création rapide : CockpitHome.jsx (carte lazy) et quickCreateEvents.js (entrée « tache ») | F3·C | `taches/etranger-coquille` | `frontend/src/features/offlinesync/mobile/CockpitHome.jsx`, `frontend/src/features/uxviews/quickcreate/quickCreateEvents.js`, `frontend/src/features/offlinesync/mobile/CockpitHome.test.jsx`, `frontend/src/features/uxviews/quickcreate/quickCreateEvents.test.mjs` | TCH103 | sonnet | `CockpitHome.test.jsx`, `quickCreateEvents.test.mjs` étendus | spec-6a §9 |
| TCH127 | Test canari de confidentialité : « Canari-7Q9 » / « Canari-X3K » absent de toute chaîne servie à l'assistant, au flux, à la tuile, aux notifications, aux suggestions et dans IncitationCoach.donnees ; visible à l'écran | F3·C | `taches/final` | `T/tests/test_canari.py` | TCH97, TCH98, TCH111, TCH75, TCH70 | opus | `test_canari.py` : liste exacte des routes de regles.md §8 ; casse et accents ignorés, JSON décodé | regles.md §8 test canari ; A6 ; donnees.md inv. 8 |
| TCH128 | Test de balayage « même propriétaire » : pour chaque route et chaque id reçu (inv. 9), un id d'un autre compte répond comme un id inconnu et rien n'est écrit | F3·C | `taches/final` | `T/tests/test_meme_proprietaire.py` | TCH127, TCH122 | opus | `test_meme_proprietaire.py` : les 100 routes d'api.md §3, ids de lot/plan/triage/réordonnancement compris ; exception lecture de journee/proposition | donnees.md inv. 9 ; socle §2.1 |
| TCH129 | Plafonds de requêtes : tests par route (api.md §10) et entrées dans docs/query-budgets.yml | F3·C | `taches/final` | `T/tests/test_plafonds.py`, `docs/query-budgets.yml` | TCH128 | sonnet | `test_plafonds.py` mesuré ; `check_query_budgets.py` vert ; cibles A15 remplacées par la mesure | api.md §10 ; socle §8 performance ; spec-6a crit. 15 |
| TCH130 | Activation (1/3) : accorder `taches_voir` aux rôles système INTERNES seulement (jamais portail, ni rôles à liste blanche) | F3·C | `taches/final` | `DJ/apps/roles/permissions_registre.py`, `DJ/apps/roles/tests.py` | TCH129 | opus | `apps/roles/tests.py` : rôles internes l'ont, portail et Commercial terrain non ; `check_roles_mirror.py` | socle §8 Droits ; A17 ; donnees.md inv. 28 |
| TCH131 | Activation (2/3) : navigation du module (4 onglets, labelKey, glyphe unique, pastille À trier), marqueurs contextuels retirés, ligne appSkus, 5 clés de traduction fr/en/ar, échantillons retirés de la liste « posés avant leur vue » | F3·C | `taches/final` | `FT/module.config.jsx`, `frontend/src/lib/apps/appSkus.js`, `frontend/src/i18n/catalogs/fr.json`, `frontend/src/i18n/catalogs/en.json`, `frontend/src/i18n/catalogs/ar.json`, `scripts/check_api_shapes.py`, `FT/routes.test.jsx` | TCH130, TCH124 | sonnet | `routes.test.jsx` : 4 onglets dans l'ordre ; `i18n-coverage.test.mjs`, `nav-keys-no-raw-key.test.mjs`, `appSkus.test.jsx`, `check_ecrans_atteignables.py`, `check_api_shapes.py` verts | spec-7 §2 ; textes.md §9 ; A17 ; MAJ-10 |
| TCH132 | Activation (3/3) : Aujourd'hui admise comme écran d'accueil mobile (MOBILE_HOME_ALLOWED_ROUTES) | F3·C | `taches/final` | `DJ/authentication/selectors.py`, `DJ/authentication/tests_ntmob6_mobile_home_route.py` | TCH131 | opus | `tests_ntmob6_mobile_home_route.py` étendu : '/taches/aujourdhui' accepté ; OpenAPI enum régénéré | spec-6b §10 ; api.md §7 |
| TCH133 | Tests de bout en bout (1/2) : journée (Garder ces 5, ★★, cocher, reporter, Alléger, bilan Tout reporter), saisie et À trier (collage 4 listes), fiche et conflit | F3·C | `taches/final` | `frontend/e2e/taches-journee.spec.js`, `frontend/e2e/taches-saisie.spec.js` | TCH132 | sonnet | Playwright vert sur la pile CI ; hooks DOM = contrat ; parcours 1-9, 13, 15, 20-22 de spec-7 §7 | spec-7 §7 ; e2e_suite |
| TCH134 | Tests de bout en bout (2/2) : projets (créer, planifier, tableau, terminer), revue → Planifier ma semaine, agenda (placer à une heure), Mon iPhone, axe-core 0 violation et cibles ≥ 44 px | F3·C | `taches/final` | `frontend/e2e/taches-projets.spec.js`, `frontend/e2e/taches-a11y.spec.js` | TCH133 | sonnet | Playwright vert ; critères (5)-(7) de spec-7 §6 sur chaque écran | spec-7 §6-§7 |
| TCH135 | Régénérer les fichiers dérivés de la fusion F3 (openapi, inventaire RBAC, CODEMAP + empreinte) ; manuel de l'assistant régénéré après la fusion par le skill assistant-manuel | F3·fin | `taches/orchestrateur` | `docs/openapi-schema.yml`, `docs/rbac-endpoint-inventory.md`, `docs/CODEMAP.md` | TCH134, TCH118, TCH126 | haiku | `check_openapi_schema.py --check`, `codemap_fingerprint.py --check` verts | CLAUDE.md CODEMAP upkeep ; spec-5b §9 |
| TCH136 | Parcours « je note tout » : 4 listes collées → projets proposés (priorité Moyenne) → Créer → À trier vidé en 9 gestes ; brouillon repris ; rejeu hors ligne | F2·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés, results.json) ; spec `frontend/e2e/acceptation/tch.spec.js` si elle existe | spec-7 §7 parcours 2, 9, 14 ; A11 |
| TCH137 | Parcours « ma journée » : matin Garder ces 5 + ★★ → cocher, reporter (balayage), choisir un jour → 15 h Alléger → bilan Tout reporter → lendemain bilan d'hier ; pastille juste | F2·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés, results.json) ; spec `frontend/e2e/acceptation/tch.spec.js` si elle existe | spec-7 §7 parcours 3-8, 15 ; A16-N5 |
| TCH138 | Parcours « projets » : créer et planifier un projet en 7 gestes → Tableau mémorisé → Terminer (boite) → Revue → Planifier ma semaine ; Supprimer puis restaurer en une ligne | F2·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés, results.json) ; spec `frontend/e2e/acceptation/tch.spec.js` si elle existe | spec-7 §7 parcours 10, 16, 19, 20 |
| TCH139 | Parcours « agenda » : 4 tâches placées à une heure, semaine de 15 tâches planifiée, visites et poses en Toute la journée, agenda ICS externe | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés, results.json) ; spec `frontend/e2e/acceptation/tch.spec.js` si elle existe | spec-7 §7 parcours 16-17 ; A14-M8 |
| TCH140 | Parcours « rythme et notifications » : objectif dit (7) appliqué aussitôt, carte monter, Garder ce rythme, réglages des heures, push de test, plan du matin réel par le balayage, rien pour un compte sans tâche | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés, results.json) ; spec `frontend/e2e/acceptation/tch.spec.js` si elle existe | A2 ; A15 ; regles.md §7 |
| TCH141 | Parcours « iPhone » : jetons créés/révoqués, capture `?reponse=texte` lue, flux .ics abonné sans notes, tuile JSON, Aujourd'hui en accueil | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés, results.json) ; spec `frontend/e2e/acceptation/tch.spec.js` si elle existe | spec-6b ; textes.md §7-§8 |
| TCH142 | Parcours « ERP » : lier une tâche à une activité, convertir un à-faire, suggestion après devis accepté, lead effacé → « Lead effacé », ✓+ sur une fiche lead | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés, results.json) ; spec `frontend/e2e/acceptation/tch.spec.js` si elle existe | spec-6a crit. 1-15 |
| TCH143 | Parcours « Copilote » : 4 demandes prêtes, carte plan en express, liste collée → carte à valider, tâche confidentielle jamais citée, tour masqué au journal | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés, results.json) ; spec `frontend/e2e/acceptation/tch.spec.js` si elle existe | A5 ; A6 ; A12 ; socle §2.6 |
| TCH144 | Parcours « vie privée et activation » : deux appareils (conflit sans perte), export Mes données, Tout effacer, onglets visibles pour un rôle interne et absents pour portail et Commercial terrain | F3·acc | `taches/acceptation` | — | — | opus | enregistrement `docs/audits/acceptation/TCH/<date>-<sha9>.md` (couvre: ids cochés, results.json) ; spec `frontend/e2e/acceptation/tch.spec.js` si elle existe | A16-N8 ; A17 ; socle §2, §8 |

Critères d'acceptation communs à rédiger dans CHAQUE corps (`lecons-construction-qjr5.md`) : (1) vert CI ≠ déployable —
aucun import hors de `frontend/` dans le front, `check_dockerfile_context.mjs` ; (2) état persisté prouvé : « enregistrer →
rouvrir → enregistrer sans toucher » = objet serveur identique (brouillons, `affichage.vue`, réglages) ; (3) jamais mocker
la source sous test (les tests front lisent `contractSamples.js`, les tests de sélecteurs lisent de vraies lignes
`records`/`crm`) ; (4) TOUS les appelants listés par grep et chacun transmet le paramètre (ex. `proprietaire_attendu` sur
les 3 ops hors ligne, `compter_report=False` sur Alléger et Retour) ; (5) test comportemental rouge d'abord ; (6) jumeau
cherché et corrigé dans le même commit (ex. format de jour : `lib/textes.js` et `moteur/gabarits.py` disent la même chose
— un test croisé) ; (7) preuve en direct en fin de fusion = les tâches `(@acceptation)` ; (8) le parcours est rejoué de bout
en bout, aller ET retour (rouvrir, annuler, relire au focus).

## 4. Fichiers d'un autre propriétaire

Propriétaires vérifiés par `python scripts/check_ownership.py --owner-of <chemin>` dans cette session (AO = surface
append-only du registre). Un fichier étranger = une tâche par fusion au plus ; édition minimale, en fin de liste.
Réservations : `plan_claims.py list` montre `acc8` sur les plans `PLAN_AUDIT_{DEPLOY,SECURITE,PARAMETRES,ANALYSE}.md` ;
aucune claim `app:` sur ces fichiers. Avant chaque lane étrangère : `plan_claims.py claim file:docs/plans/PLAN_TACHES.md
app:<app du fichier>` ; refus → lane suivante (règle « shared by claims »).

| Fichier | Propriétaire | Édition exacte | Tâche(s) |
|---|---|---|---|
| `docs/ownership.yml` | aucun (hors racines, AO) | bloc `taches` + ligne `plans:` ci-dessous | TCH1 (commité AVEC le plan, sinon règle c rouge) |
| `frontend/src/test/fixtures/contractSamples.js` | deploy (AO) | un export par échantillon, en fin | TCH2, TCH3 |
| `scripts/check_api_shapes.py` | deploy (AO) | entrées `taches/<x>.json` dans `ECHANTILLONS_POSES_AVANT_LEUR_VUE` (F1), retirées en F3 | TCH2, TCH3 ; TCH131 |
| `DJ/erp_agentique/settings/base.py` | deploy (AO, fichier-mur 2 139 l.) | F1 : `'apps.taches'` en fin d'`INSTALLED_APPS` (« Code net ≤ 3 ») ; F3 : `TACHES_RACCOURCI_SIRI_URL`, `taches_rappel` au défaut de `NOTIFICATIONS_TOUJOURS_IMMEDIATES` (« ≤ 5 ») | TCH4 ; TCH99 |
| `DJ/erp_agentique/urls.py` | deploy (AO) | `path('taches/', include('apps.taches.urls'))` dans `_APP_URLS` | TCH15 |
| `DJ/erp_agentique/celery.py` | deploy (AO) | 2 entrées `beat_schedule` en fin (`taches-balayer`, `taches-nocturne`) | TCH99 |
| `.env.example` | deploy (AO) | `TACHES_RACCOURCI_SIRI_URL=` commenté sous un bloc `taches` | TCH99 |
| `frontend/src/design/tokens.css` · `frontend/scripts/check_hex.mjs` · `frontend/src/index.css` | deploy (AO · — · AO) | bloc `--tch-*` clair ET sombre (spec-8 §8) · `ST/` dans `GUARDED_SELECTORS` · 7 `@import` en fin | TCH41 |
| `DJ/apps/roles/permissions_registre.py` · `DJ/apps/roles/tests.py` | securite (AO · —) | F1 : `taches_voir` en fin + `PERMISSION_MODULE`, aucune liste de rôle ; F3 : listes des rôles système internes | TCH5 ; TCH130 |
| `DJ/apps/records/selectors.py` (neuf) · `DJ/apps/records/services.py` · `DJ/apps/records/tests.py` | securite | `activites_ouvertes_pour`, `nb_a_faire_personnels`, `peut_cloturer_activites` · `cloturer_a_faire_personnel`, `rouvrir_a_faire_personnel` | TCH16, TCH17 |
| `DJ/authentication/views.py` · `DJ/authentication/tests_recovery.py` | securite | exclure `app_label == 'taches'` de `_traces_du_compte` (`views.py:1404`) | TCH18 |
| `DJ/core/management/commands/seed_registre_traitements.py` · `DJ/core/tests/test_registre_traitements.py` | securite | entrée `taches_rythme` | TCH19 |
| `DJ/authentication/selectors.py` · `DJ/authentication/tests_ntmob6_mobile_home_route.py` | securite | `'/taches/aujourdhui'` dans `MOBILE_HOME_ALLOWED_ROUTES` (`selectors.py:184`) | TCH132 |
| `DJ/apps/notifications/{types_evenements,module_map}.py` (AO), `module_gating.py`, `migrations/0079_eventtype_taches.py` (AO), `tests.py` | parametres | 4 `EventType` en fin + entrées `module_map`/`module_gating` + migration (3 `AlterField`, `max_length=40`) DANS LE MÊME COMMIT (règle du registre) | TCH20 |
| `DJ/apps/notifications/services.py` | parametres | paramètre `badge` de `notify()` (`services.py:624`) dans la charge push | TCH21 |
| `DJ/apps/agent/{registry.py,contract_samples/assistant_reponse.json,tests/test_registry.py}` | analyse | 16 clés `taches.*` et 9 cartes ; échantillon | TCH112 |
| `backend/fastapi_ia/app/services/prompt_copilote.py` + test | analyse | bloc `CONSIGNES_COACH` (textes.md §5.1) | TCH113 |
| `backend/fastapi_ia/app/services/{relais_copilote,action_tools}.py` + test | analyse | `catalogue_pour_tour` (Groq + `/taches` → 5 actions) ; contexte d'écran | TCH114 |
| `backend/fastapi_ia/app/services/sql_agent_service.py` + `test_sql_agent_endpoint.py` | analyse | masquage dans `_journaliser` (« Code net ≤ 40 », spec-5b §10.5) | TCH115 |
| `backend/fastapi_ia/tests/eval/{cases_commerciaux,runner}.py`, `tests/test_eval_harness.py` | analyse | `CASES_COACH` (12) + `_bonnes_cartes` ; `CASES_COPILOTE` reste à 19 | TCH116 |
| `frontend/src/features/ia/{cartes/cartes.js,cartes/CartesDuMessage.jsx,copilotMessages.js}` + tests | analyse | dispatch des cartes `taches` ; 4 demandes prêtes depuis `/taches` | TCH118 |
| `frontend/src/features/{offlinesync/mobile/CockpitHome.jsx,uxviews/quickcreate/quickCreateEvents.js}` + tests | analyse | carte lazy ; `{ id:'tache', label:'Créer une tâche' }` | TCH126 |
| `frontend/src/providers/{shortcuts.js (AO),commandActions.js,focusedRecordShortcuts.jsx}`, `frontend/src/lib/search/entityRoutes.js` (AO) | deploy | `c t`, `g j` en fin ; `.filter((s) => !!s.to)` (spec-6a §9 risque c) + entrées palette ; registre d'aide `taches` ; ligne `tache` dans ROUTE/LIST_ROUTE/TYPE_LABEL | TCH119 |
| `frontend/src/sw.js`, `frontend/vite.config.js`, `frontend/src/features/pwa/shortcuts.test.mjs` | deploy | `setAppBadge` à la réception, liens de clic (api.md §7) ; raccourci de manifeste « Tâches » | TCH120 |
| `frontend/src/components/layout/{Layout,Header}.jsx` + `Header.test.jsx` | deploy | 1 import + `<TachesPresence />` ; 1 import + `<BoutonTachesIci />` | TCH123 |
| `frontend/src/components/layout/BottomTabBar.jsx`, `frontend/src/lib/apps/useAppBadges.js` + tests | deploy | pastille d'onglet À trier (masquée à 0) ; fusion des `badgePersonnel` | TCH124 |
| `frontend/src/pages/Dashboard.jsx` + `Dashboard.cockpit.test.jsx` | deploy | carte lazy `CarteMesTaches` | TCH125 |
| `docs/query-budgets.yml` | deploy (selon `--owner-of`) | une entrée par route d'api.md §10, valeurs MESURÉES | TCH129 |
| `frontend/src/lib/apps/appSkus.js`, `frontend/src/i18n/catalogs/{fr,en,ar}.json` | deploy (AO) | ligne `taches` à sa place alphabétique ; 5 clés `nav.*` (textes.md §9) même position dans les 3 | TCH131 |
| `docs/openapi-schema.yml` (AO), `docs/rbac-endpoint-inventory.md`, `docs/CODEMAP.md` (AO) | aucun (régénérés) | `check_openapi_schema.py --write`, inventaire, CODEMAP §4/§5 + `codemap_fingerprint.py --write` | TCH47, TCH94, TCH135 |

Non touchés, volontairement : `apps/reporting/calendar.py` (patron recopié dans `throttles.py`, objection de spec-6b),
`apps/trash/*`, `records.Tag`, `record_targets`, recherche globale, `core/events.py` (aucun signal neuf).

**Lignes exactes à ajouter à `docs/ownership.yml`** (bloc dans `owners:`, avant `parked:` ; simulées sur une copie,
0 conflit avec un `paths` strict existant) :

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
et dans `plans:` : `  docs/plans/PLAN_TACHES.md: [taches, deploy, securite, parametres, analyse]`.

Conséquence (comme `PLAN_YANBOW_WEB`, `ownership.yml:1057`) : les tâches étrangères vivent dans `PLAN_TACHES.md` (pas de
`@after` vers un autre plan, que `plan_lanes.py` refuserait tant qu'il est ouvert) ; `PLAN_TACHES` ne tourne JAMAIS en
même temps qu'une session `PLAN_AUDIT_{DEPLOY,SECURITE,PARAMETRES,ANALYSE}` ni `PLAN_AUDIT_TRANSVERSE` (aujourd'hui tenus
par `acc8`) : c'est la lecture de A8 retenue ici. L'en-tête de `PLAN_TACHES.md` copie celui de `PLAN_YANBOW_WEB.md:1-33`
(contrat de propriété : la liste ci-dessus ; INTERDIT : tout autre fichier de `records`, `notifications`, `agent`,
`fastapi_ia`, `crm`, `ventes`, `visites`, `installations` ; ces apps sont LUES par leurs `selectors.py`).

## 5. Table de couverture

### 5.1 Modèles (20)
Projet, Section, Tache, ElementChecklist, Etiquette, EtiquetteTache, RegleRecurrence → TCH7 · PlanJour, LignePlanJour,
ReglagesRythme, Preference, IncitationCoach, Rappel, JetonAcces, GesteAnnulable, VueEnregistree, ModeleProjet,
RevueProjet, SuggestionTache → TCH8 · migration 0001 → TCH9 · AgendaExterne + 0002 → TCH121 · énums §1 → TCH6 ;
EventType → TCH20.

### 5.2 Routes (100 couples, api.md §3)
| Groupe | Routes | Tâches |
|---|---|---|
| 3.1 journée | aujourdhui, ailleurs, badge, vu | TCH56 |
| | journee/proposition, journee/planifier, journee/essentiel | TCH57 |
| | journee/alleger, journee/cloture, journee/cloturer | TCH58 |
| | agenda (externes : TCH122) · recherche | TCH59 · TCH53 |
| 3.2 saisie | saisie-rapide · capture | TCH48 · TCH96 |
| | taches/ GET, POST ; taches/{id}/ GET, PATCH, DELETE | TCH49 |
| | planifier, terminer, rouvrir, trancher, sauter, attendre, recu, restaurer | TCH50 |
| | reordonner, rappels/ POST, rappels/{id} DELETE, repeter, changement/apercu, recurrences/{id} PATCH | TCH51 |
| | lot, checklist ×4, etiquettes ×4, vues ×4 | TCH52 |
| | supprimees, gestes, gestes/{id}/annuler | TCH53 |
| | lier-activite, convertir-activite · suggestions ×3 | TCH73 · TCH72 |
| 3.3 projets | projets/ GET, POST ; {id} GET, PATCH, DELETE | TCH60 |
| | reordonner, trier-par-priorite, terminer, rouvrir, restaurer | TCH61 |
| | vue, sections ×4 | TCH62 |
| | planification/apercu, planification, decaler | TCH63 |
| | dupliquer, enregistrer-modele, modeles ×5 | TCH64 |
| | revue/projets GET, PUT | TCH65 |
| 3.4 rythme et réglages | rythme GET, POST · propositions/repondre · preferences POST, DELETE + coach/entete · reglages GET, PATCH | TCH66 · TCH67 · TCH68 · TCH69 |
| | jetons ×3 · test-notification, tuile, flux | TCH95 · TCH97 |
| | mes-donnees, tout-effacer · agenda-externe ×3 | TCH74 · TCH121 |
| déclaration de toutes | urls.py + vues 501 + OpenAPI | TCH15, TCH47, TCH94, TCH135 |
| étrangères consommées | `records/activities/{id}/done/` · `auth/mobile-home-route/` | TCH81 · TCH109, TCH132 |

### 5.3 Modules purs (regles.md) et leurs tables
`saisie/normalisation` §1.1 → TCH6 · `saisie/analyseur`+`grammaire` table §1.11 → TCH38-TCH39 · `collage`, `plan` §1.10 →
TCH40 · `moteur/recurrence` B1-B25 → TCH10 · `classement` §3.3 jeu de test, §3.4-§3.6, §4.2 → TCH22-TCH23 · `flux`
(`evenements_flux`, `tuile_pure`) §10 → TCH24 · `rythme` §6.1-§6.10 (61 exemples) → TCH25-TCH28 · `sollicitations` §7 →
TCH29 · `gabarits` (textes §3-§4) → TCH30 · `sante` table « Cas » §5 → TCH31 · `decalage` → TCH32 · `confidentialite` table
§8 → TCH11.

### 5.4 Écrans (spec-7 §4) et maquettes qui font foi
| Écran | Tâches | Maquettes |
|---|---|---|
| Aujourd'hui (+ progression, carte du moment, Proposé, ⋯, ERP, repliés) | TCH76-TCH79, TCH81 | `ecran-aujourdhui-{matin,matin-bas,15h,15h-bas,15h-menu,retour,vide}.html`, `composants-3,-4,-9,-10.html` |
| Saisie, aperçu (Coller mes listes) | TCH82-TCH83 | `ecran-saisie.html`, `ecran-saisie-liste.html`, `composants-5,-6.html` |
| Fiche (+ Plus, Quand, Rappel) | TCH84-TCH85 | `ecran-fiche.html`, `ecran-fiche-plus.html` |
| À trier | TCH86 | `ecran-a-trier.html`, `ecran-a-trier-bas.html` |
| Bilan du soir · Alléger | TCH80 · TCH79 | `ecran-bilan{,-bas,-rythme}.html` · `ecran-aujourdhui-15h-menu.html` |
| Agenda (4 vues, À placer, Planifier ma semaine) | TCH104-TCH106 | `agenda-{jour,semaine,mois,a-venir,placer-heure,placer-heure-duree,semaine-planifier,semaine-planifier-pose}.html`, `composants-8.html` |
| Projets · Un projet · Tableau/Chronologie · Planifier le projet | TCH88 · TCH89 · TCH90 · TCH91 | `projets-liste.html` · `projet-liste.html` · `projet-tableau.html`, `projet-chronologie.html` · `projet-planifier{,-2}.html` |
| Archive, Modèles, dialogues | TCH92 | aucune (états vides `composants-9.html`) |
| Revue | TCH93 | `revue-semaine.html` |
| Mon rythme | TCH107 | `rythme.html` |
| Recherche · Supprimées récemment | TCH87 | aucune |
| Réglages · Mon iPhone · tuile | TCH108 · TCH109 · TCH110 | aucune · `mon-iphone.html` · `tuile.html` |
| Copilote | TCH113-TCH118 | `copilote.html` |
| Carte cockpit | TCH103, TCH125, TCH126 | `cockpit-carte.html` |
| Langage visuel (jetons, typo, palette) | TCH41 | `taches.css`, `composants.html`, `composants-7.html`, `ecrans-{coeur,agenda,projets}.css` |

### 5.5 Composants (spec-7 §10)
LigneTache, CaseRonde, Etoile → TCH44 · SelecteurQuand, ChampSaisie → TCH82 · FeuilleACrans → TCH45 · CarteDuMoment,
AnneauProgression → TCH77 · BandeauConflit → TCH46 · GrilleAgenda → TCH104 · VoletAPlacer → TCH105 · Tableau → TCH90 ·
SelecteurProjet → TCH45 · ApercuListe → TCH83 · (ajoutés par ce plan) BarreSelection, BoutonCopilote → TCH45 ;
CoquilleTaches → TCH43, TCH100.

### 5.6 Invariants (donnees.md §3)
| Inv. | Tâches | Inv. | Tâches | Inv. | Tâches | Inv. | Tâches |
|---|---|---|---|---|---|---|---|
| 1 | TCH36, TCH49, TCH61, TCH96 | 9 | TCH12, TCH128 | 17 | TCH61, TCH65 | 25 | TCH65 |
| 2 | TCH54 | 10 | TCH54 | 18 | TCH57, TCH58 | 26 | TCH4, TCH18, TCH53, TCH75 |
| 3 | TCH54 | 11 | TCH54, TCH56, TCH101 | 19 | TCH35 | 27 | TCH50, TCH60, TCH61 |
| 4 | TCH34, TCH50, TCH58 | 12 | TCH24, TCH97 | 20 | TCH95, TCH96 | 28 | TCH5, TCH43, TCH130, TCH131 |
| 5 | TCH10, TCH36, TCH50 | 13 | TCH54 | 21 | TCH33 | 29 | TCH36, TCH56, TCH98 |
| 6 | TCH49 | 14 | TCH34, TCH35, TCH98 | 22 | TCH29, TCH98 | 30 | TCH17, TCH73 |
| 7 | TCH49, TCH50 | 15 | TCH34, TCH49 | 23 | TCH13, TCH49, TCH75 | 31 | TCH48, TCH100 |
| 8 | TCH11, TCH127 | 16 | TCH50 | 24 | TCH26, TCH67 | 32 | TCH51, TCH54 |

Fonctions uniques (§5) : `taches_de` & co → TCH12 · `taches_de_la_journee`, `compter_journee` → TCH54 · `est_confidentielle`,
`nom_pour` → TCH11 · `creer_taches` → TCH36 · `planifier` → TCH34 · gestes → TCH33 · `JetonAccesAuthentication`,
throttles → TCH95 · `jours_travailles_de`, `filtrer_q` → TCH12 · liens → TCH13 · fournisseur DSR → TCH74 · `neglige`,
`tout_fait` → TCH31 · abonnés aux signaux → TCH71 · étrangers records → TCH16-TCH17. Rétention §8 → TCH75 ; « Comprendre
mon rythme » coupé → TCH69. Opérations annulables §4 → TCH33 (+ chaque service qui rend `geste_id`). Plafonds §10 → TCH129.

### 5.7 Vie privée (socle §2) et cycle de vie (socle §8)
| Règle | Tâches |
|---|---|
| 1 sélecteur unique + balayage même propriétaire | TCH12, TCH128 |
| 2 pas de corbeille commune, `record=False`, Supprimées propres, `__str__` neutre | TCH4, TCH6, TCH33, TCH53, TCH87 |
| 3 étiquettes propres, pas de `record_targets` | TCH7, TCH4 |
| 4 pas de recherche globale ; recherche propre ; « Chercher dans mes tâches » | TCH4, TCH53, TCH119 |
| 5 jetons hachés par usage | TCH95-TCH97 |
| 6 donnée ≠ consigne ; cartes à valider ; journal masqué | TCH111, TCH113, TCH115, TCH117 |
| 7 dire la vérité (Vie privée) | TCH108 |
| 8 notifications sans titre par défaut ; question au 1er rappel | TCH98, TCH51, TCH85 |
| droit unique `taches_voir`, jamais `taches_gerer` | TCH5, TCH130 |
| traces du compte, export, tout effacer, purge 30 j | TCH18, TCH74, TCH75, TCH108 |
| registre 09-08 + interrupteur | TCH19, TCH69 |
| fuseau Casablanca, multi-sociétés (société du jeton) | TCH12, TCH95 |

### 5.8 Arbitrages
A1 TCH39, TCH96 · A2 TCH26, TCH66, TCH107 · A3 TCH13, TCH3 (`liens_cibles.json`) · A4 TCH71-TCH72 · A5 TCH111, TCH117 ·
A6 TCH11, TCH127 · A7 TCH33, TCH46, TCH53 · A8 §4 · A9 TCH108 · A10 TCH119, TCH102 · A11 TCH57, TCH78 · A12 TCH45, TCH118 ·
A13 TCH43, TCH131 · A14 B1 TCH56/TCH77, M1 TCH76/TCH78, M2 TCH77/TCH80, M3 TCH63/TCH83/TCH88, M4 TCH58/TCH80, M5 TCH83/TCH109,
M6 TCH39, M7 TCH58/TCH79, M8 TCH121-TCH122, M9 TCH40, M10 TCH30/TCH46, M11 TCH119 · A15 palette TCH6/TCH41, rétentions
TCH75, aucune sollicitation sans tâche TCH36/TCH98, liens de notification TCH120 · A16 N1 TCH119, N3 TCH106, N4 TCH55,
N5 TCH54/TCH101, N6 TCH58/TCH79, N7 TCH61/TCH87/TCH89, N8 TCH46/TCH84, N9 TCH65/TCH77/TCH93, N10 TCH46/TCH134, N11 TCH100,
N12 TCH109 · A17 T2 TCH57/TCH117, T3 TCH70/TCH77, T4 TCH51/TCH85, lier une tâche TCH73/TCH81, invisibilité TCH5/TCH43/
TCH130-TCH131, tutoiement TCH30/TCH46.

### 5.9 Demandes explicites de la mission
Contrat d'abord TCH2-TCH3 · échafaudage TCH4, TCH15 · droit déclaré non accordé TCH5 · modèles et migration TCH7-TCH9 ·
sélecteur + balayage TCH12, TCH128 · canari TCH127 · hors ligne TCH100 · pastille TCH101, TCH124 · notifications TCH20-TCH21,
TCH98 · deux tâches planifiées TCH37, TCH99 · jetons TCH95 · Siri TCH96, TCH109 · flux TCH97 · tuile TCH97, TCH110 ·
Scriptable TCH110 · Mon iPhone TCH109 · actions et cartes TCH111-TCH112, TCH117-TCH118 · consignes TCH113 · contexte d'écran
TCH114 · masquage TCH115 · suggestions ERP TCH71-TCH72, TCH86 · « créer une tâche depuis ici » TCH102, TCH123 · cockpit
TCH103, TCH125-TCH126 · export / tout effacer TCH74, TCH108 · purge TCH75 · fournisseur d'effacement TCH74 · registre TCH19 ·
traces TCH18 · agenda externe TCH121-TCH122 · traductions TCH131 · régénérations TCH47, TCH94, TCH135 · ownership TCH1 ·
plafonds TCH129 · e2e TCH133-TCH134 · octroi + nav TCH130-TCH132 · acceptations TCH136-TCH144 · accessibilité spec-7 §6
(1)-(4) TCH46, (5) TCH76, (6)-(7) TCH134, (8) TCH78.

## 6. Risques de construction et parades

| Risque | Parade dans ce plan |
|---|---|
| Chaîne de migrations à deux écrivains | `taches` : 0001 par TCH9 (F1), 0002 par TCH121 (F3), une lane `models` par fusion ; `notifications` : 0079 par TCH20 seul (renuméroter si une autre session pose 0079 avant : « régénère SA migration au-dessus », registre) |
| Union de lanes par un fichier rempli plus tard | `--group "Fusion Fk"` obligatoire (mesuré : sans lui, 55 tâches dans une lane) ; un fichier non append-only n'est jamais dans deux lanes d'une même fusion (contrôlé par script sur les 144) |
| Deux moitiés sans contrat (incident AO du 03/08) | F1 pose les 47 échantillons ; tout test front les importe ; `urls.py` seul producteur PACT11, coché en F1 |
| Écran livré mais mort | pages et routes du socle ; chaque écran nomme `module.config.jsx` + clause ATTEIGNABLE ; marqueurs `// contextuelle:` jusqu'à TCH131 ; `check_ecrans_atteignables.py` sur chaque lane front |
| Module visible à demi (MAJ-10) | `taches_voir` accordé à aucun rôle en F1/F2 ; nav, `appSku`, accueil mobile seulement en F3 (TCH130-TCH132) |
| `settings/base.py` fichier-mur (2 139 l.) | deux tâches, une par fusion, avec « Code net ≤ N » ; jamais réordonner `INSTALLED_APPS` |
| Fonctions > 60 lignes logiques | `check_forme_code.py` sur chaque lane Python ; découpage de regles.md §1.12 pour l'analyseur ; orchestration `analyser` ≤ 25 lignes |
| Listes fermées de l'assistant (`CARTES`, `CLES_COACH`, lot `copilote`, `ALLOWED_TARGETS`) | une seule lane `assistant` (+ `cartes`) en F3 ; `test_registry.py`, `check_action_permission_override.py` |
| Énumération fermée des notifications | 4 membres EN FIN + module_map + migration dans UN commit (TCH20) ; jamais renommer |
| Tests « golden » à étendre, jamais à affaiblir | `contractSamples.js`, `css_golden.mjs`, `i18n-coverage.test.mjs` (mêmes clés dans fr/en/ar), `nav-keys-no-raw-key.test.mjs`, `appSkus.test.jsx`, `test_prompt_copilote.py` (constantes recalculées), `test_eval_harness.py` (`CASES_COPILOTE` = 19), OpenAPI |
| Service sans appelant | stubs des étapes nocturnes appelés par `nocturne.py` dès F1 ; `check_services_appeles.py` |
| Agents sans `node_modules` dans leur worktree | jonction `node_modules` (mémoire `worktree_windows_tooling`) ; à défaut la lane livre et l'orchestrateur lance eslint + `vite build` au fold ; aucune lane front ne se déclare verte sans eslint |
| Tests purs lancés sans Django en F1 | les lanes `pur-*` écrivent des `unittest.TestCase` sans base, lançables par `python -m unittest` depuis `backend/django_core` avant que le socle soit foldé |
| Session parallèle sur les plans d'audit (`acc8`) | claims `file:docs/plans/PLAN_TACHES.md` + `app:<x>` par lane étrangère ; refus → autre lane ; claims rendues après la fusion seulement (D-CLAIMS-MERGE) |
| Prod : `taches_rappel` remplaçable par l'env | geste de Reda noté sur TCH99 (vérifier `.env` prod) |
| Plafonds de requêtes inventés | cibles d'api.md §10 remplacées par la mesure (A15) dans TCH129 ; chaque route de F2 compte déjà ses requêtes dans son test |

Gardes à lancer SUR L'HÔTE par lane avant de rendre la main (WOW23 « test economics » ; jamais de docker) :

| Lanes | Gardes |
|---|---|
| toute lane Python | `flake8` + `py_compile` sur les fichiers changés ; `check_forme_code.py` ; `check_naive_datetime.py` ; `check_except_larges.py` |
| `socle` | + `check_modules.py`, `check_platform.py`, `check_on_delete.py`, `check_unique_scoping.py`, `check_company_fk.py`, `check_fk_scoping.py`, `check_safe_migrations.py`, `check_migration_safety.py`, `check_choices_declares.py`, `check_tenant_isolation.py`, `check_viewset_model_scope.py`, `check_api_shapes.py`, `check_ownership.py`, `check_test_placement.py`, `lint-imports` |
| `socle-services`, `saisie`, `journee`, `projets`, `rythme`, `erp` | + `check_read_modify_write.py`, `check_get_or_create.py`, `check_services_appeles.py`, `check_tenant_isolation.py`, `check_api_shapes.py`, `check_exports_bornes.py` (erp), `check_beat_active_companies.py` (journee, erp : boucles par société), `lint-imports` (journee, erp) |
| `presence` | + `check_celery_tasks.py`, `check_commandes_planifiees.py`, `check_beat_active_companies.py`, `check_settings_declares.py`, `check_notify_point_unique.py` |
| `etranger-*`, `assistant` | + les tests du module étranger touché ; `check_action_permission_override.py`, `check_platform.py` (assistant) ; `pytest backend/fastapi_ia/tests/<fichier>` (analyse) |
| toute lane front | `eslint` sur les fichiers changés ; `check_ecrans_atteignables.py` ; `check_taches_cablage.py` ; `check_api_contract.py` ; `check_liste_page1.py`, `check_page_size_front.py`, `check_fetchallpages_taille_page.py`, `check_frontend_query_params.py` ; `check_date_jour_utc.py` ; `node frontend/scripts/check_hex.mjs` (styles) |
| `final` | + `check_query_budgets.py`, `check_roles_mirror.py`, `check_openapi_schema.py --check` (après TCH135) |
| `orchestrateur` | `check_openapi_schema.py --write/--check`, `codemap_fingerprint.py --write/--check`, `check_stages.py`, `check_ownership.py` |

## 7. Choix par défaut et trous trouvés dans la référence (à remonter à l'orchestrateur)

Choix par défaut (sans question au fondateur) :
1. Trois fusions (§2.1), pas une ni deux.
2. Tâches étrangères DANS `PLAN_TACHES.md`, plan lié à 5 propriétaires (modèle `PLAN_YANBOW_WEB`) — lecture de A8 qui
   garde les `@after` dans un seul plan ; contrepartie : jamais en parallèle des plans d'audit de ces 4 unités.
3. `saisie` en paquet ; `__init__.py` sans ré-export ; aucune `admin.py` (un admin lirait les titres : socle §2) ;
   `sweeps.py` et les beats en F3 seulement (une tâche planifiée sans travail réel tournerait en prod dès F1).
4. Liens de notification : `?ouvrir=bilan` gardé pour le bilan (spec-7 r3 §2 prime sur api.md R20 pour les routes du
   front) ; tous les autres vers `/taches/aujourdhui` sauf revue et rappel.
5. Glyphe et `sku` de `appSkus.js` : à choisir à TCH131 (unique, `check_modules`), aucun n'est fixé par la référence.

Trous et contradictions relevés par la table de couverture :
1. **10 échantillons de contrat manquent à api.md §6** pour des routes qu'un écran consomme : `agenda-externe/`,
   `etiquettes/`, `vues/`, `modeles/` (liste), `jetons/` (liste), `rappels/{id}/repeter/`, `PUT revue/projets/{id}/`,
   réponses d'écriture de projet (terminer, restaurer, supprimer), `mes-donnees/`, `tout-effacer/` ; ajoutés à TCH3
   (47 au lieu de 37). `supprimees.json` figure deux fois dans api.md §6.
2. **Liens de notification contradictoires** : regles.md §7 et spec-7 r3 §2 envoient le bilan vers
   `/taches/aujourdhui?ouvrir=bilan` ; api.md §7 et R20 disent « paramètre `ouvrir` retiré ». Tranché au choix 4.
3. **`cle_nom` dans `saisie.py`** (donnees.md §0) rend les modèles dépendants de l'analyseur : le socle ne peut pas
   construire. Plan : `saisie/normalisation.py` ; donnees.md à aligner.
4. **Maquettes absentes** pour Recherche, Supprimées récemment, Réglages (5 rubriques hors Mon iPhone), Archive, Modèles,
   dialogues (Supprimer le projet N7, Décaler, Terminer), bandeau de conflit, fiche ouverte par un rappel : construits sur
   les planches `composants-*.html` + spec-8 ; pas de contrat visuel à comparer.
5. **Invisibilité vs `check_ecrans_atteignables.py` classe 3** (« route sans nav ») : la référence ne prévoit pas les
   marqueurs `// contextuelle:` nécessaires de F1 à F3.
6. **`check_api_shapes.py`** exige la déclaration des échantillons posés avant leur vue (`ECHANTILLONS_POSES_AVANT_LEUR_VUE`,
   deploy) : absent de la référence ; TCH2-TCH3 puis retrait à TCH131.
7. **Montage de la fiche et de la saisie** non dit par la référence (écran de qui ?) : coquille commune TCH43 + hôte global
   TCH102.
8. **Aucun test désigné** pour `_traces_du_compte` et la route d'accueil mobile : `tests_recovery.py` (ASUP5) et
   `tests_ntmob6_mobile_home_route.py` retenus.
9. **e2e et styles** : `frontend/e2e/taches-*` et `frontend/src/styles/taches/**` résolvent aujourd'hui vers `deploy`
   (`--owner-of`) ; le bloc `taches` les revendique.
10. **Groupe d'acceptation** : TCH n'est pas une unité de `docs/audits/unites.yml` ; enregistrements prévus sous
    `docs/audits/acceptation/TCH/` (à confirmer avec `check_acceptation.py` quand il existera).
11. **Non vérifiés ici** : comportement exact de `check_api_shapes.py` face à une vue 501 (déclaration supposée suffire) ;
    `check_ownership.py` sur le vrai registre ; que `check_ecrans_atteignables` accepte un marqueur par route du même
    fichier.
