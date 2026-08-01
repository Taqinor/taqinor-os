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
