import fs from 'node:fs'
import path from 'node:path'

/* Racine du dépôt pour les tests qui lisent des fichiers hors `frontend/` (ENF19).
   `import.meta.url` est virtuel sous vitest : on part du dossier de travail
   (fixé à `frontend/` par la configuration vitest) et on remonte jusqu'à la
   racine du dépôt — même repli que `src/api/calepinageApi.test.mjs`.
   `globalThis.process` plutôt que `process` nu : le lint de ce dossier ne
   déclare pas les globales Node. */
export const RACINE_FRONTEND = globalThis.process.cwd()

export function racineDepot() {
  let dossier = RACINE_FRONTEND
  for (let i = 0; i < 8; i += 1) {
    if (fs.existsSync(path.join(dossier, 'backend', 'django_core'))) return dossier
    dossier = path.dirname(dossier)
  }
  throw new Error(`Racine du depot introuvable depuis ${RACINE_FRONTEND}`)
}
