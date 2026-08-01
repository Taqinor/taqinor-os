# NOTES_LANE — lane `frontend/ao-qualite` (AOF187-192)

- **Base réelle vs base attendue.** Le brief de run annonce un worktree basé sur
  `dev-aof` avec `apps/ao` complet et « tout le frontend AO » déjà livré. En
  réalité ce worktree est basé sur `main` post-insertion du plan (commit
  `2793ee05`) : `backend/django_core/apps/ao` ne contient que ses squelettes
  (models/migrations/tests vides) et `frontend/src/features/ao/` ne contient
  QUE `module.config.jsx` dans son état WIR166 (« reste BACKEND-ONLY »,
  `nav`/`routes` absents). Aucun des prérequis nommés par mes tâches (AOF8
  hooks `data-ao-*`, AOF90/92 studio, AOF102 canvas, AOF176 dossier, AOF186 seed
  de démo) n'est présent dans CE worktree. Les tâches ci-dessous sont donc
  livrées CONTRE LE CONTRAT documenté dans l'en-tête du Groupe AOF et le texte
  intégral d'AOF8/AOF186 (lu dans `docs/PLAN.md`), pas contre du code
  vérifiable localement — aucun `npm`/DB disponible ici de toute façon pour
  exécuter les specs Playwright. À reconcilier par l'orchestrateur au moment du
  fold avec les lanes soeurs (`frontend/ao-socle`, `frontend/ao-studio`,
  `frontend/ao-dossier`, `backend/ao`).

- **Bilan AOF187-192 (aucune tâche marquée BLOQUÉE — 6/6 livrées) — hypothèses
  À VÉRIFIER par l'orchestrateur au fold :**
  - AOF187/188/190 (`ao-parcours.spec.js`, `ao-dossier.spec.js`, `ao-a11y.spec.js`,
    `ao-mobile.spec.js`) supposent des routes `/ao`, `/ao/affaires`, des liens
    accessibles « Toiture »/« Calepinage »/« Dossier »/« Variantes »/« Bordereau »,
    et un marqueur `FRDISI` dans le nom de l'affaire plantée par `seed_ao_demo`
    (AOF186) — à ajuster si `frontend/ao-socle` (AOF7)/`frontend/ao-dossier`/
    `backend/ao` (AOF186) nomment différemment. Les hooks `data-ao-*` utilisés
    reprennent MOT POUR MOT la liste normative d'AOF8 lue dans `docs/PLAN.md`
    (canvas, outil, verdict, compte, tiroir, variante, piece, controle, repere,
    provenance, etat) mais le fichier `E2E_HOOKS.md` lui-même n'existe pas
    encore dans ce worktree pour être diffé.
  - AOF189/190 (`ModeChantier.jsx`/`ModeMobile.jsx`) sont des WRAPPERS qui
    reçoivent l'éditeur réel en `children`/props — ils ne recréent aucun canvas
    ni logique de calepinage (qui n'existent pas encore ici). À brancher par la
    lane qui livre l'atelier réel (`frontend/ao-studio`).
  - AOF192 : le chunk `ao-studio` cible `features/ao/studio/**` (mes deux
    fichiers AOF189/190 seulement, pour l'instant) — AUCUNE mesure
    avant/après réelle prise (pas de `node_modules`/build ici) ; la logique de
    `check_bundle_budget.mjs` a été validée par exécution `node` directe contre
    un `dist/` synthétique (chunk `ao-studio` correctement détecté et flaggé
    au `modulepreload` de boot), mais jamais contre un VRAI build.
  - AOF191 (`fileReleve.js`) est autonome (zéro import cross-feature) et ses
    10 tests sont RÉELLEMENT exécutés en vert via `node --test` (pas seulement
    grep-vérifiés) — le seul livrable de cette lane avec une preuve d'exécution
    complète.
