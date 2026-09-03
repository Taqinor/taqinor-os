/* SOL6 — Registre STATIQUE des éditions produit, côté frontend.
   ----------------------------------------------------------------------------
   Miroir de `backend/django_core/erp_agentique/settings/editions.py` : les mêmes
   six verticaux sortent du BUILD de l'édition solaire (le backend en parque un
   septième, `ecommerce_connect`, qui n'a aucune surface frontend dédiée).

   Ce fichier est du JAVASCRIPT PUR (aucun import React, aucun import Vite) : il
   est lu par `vite.config.js`, `vitest.config.js`, `eslint.config.js`, le script
   de vérification du dist ET par le code applicatif. Une seule liste, donc
   aucune dérive possible entre le tree-shake, la règle de lint et la garde CI.

   IMPORTANT — comment l'exclusion se fait réellement : `VITE_EDITION` est lue
   ICI, au moment de la CONFIG, puis figée en CONSTANTES LITTÉRALES par le bloc
   `define` de Vite (`__EDITION_SOLAIRE__`, `__EDITION_A_MRP__`). Les conditions
   écrites dans le code applicatif sont donc résolues À LA COMPILATION et Rollup
   élimine la branche morte AVEC ses imports. Un filtre à l'exécution ne
   tree-shakerait rien : les écrans parqués seraient déjà dans le bundle. */

export const EDITION_FULL = 'full'
export const EDITION_SOLAR = 'solar'
export const DEFAULT_EDITION = EDITION_FULL
export const EDITIONS = [EDITION_FULL, EDITION_SOLAR]

/** Répertoires de premier niveau, sous `src/`, d'un vertical parqué. */
export const ARBRES = ['features', 'pages', 'components']

/* Verticaux PARQUÉS par édition (clé de module = nom de répertoire).
   Les trois arbres `features/<x>`, `pages/<x>` et `components/<x>` d'un même
   vertical sortent ENSEMBLE — c'est le point qui manquait aux gardes : exclure
   `features/mrp` sans `pages/mrp` laisse les écrans dans le bundle. */
export const VERTICAUX_PARQUES = {
  [EDITION_FULL]: [],
  [EDITION_SOLAR]: [
    'agriculture',
    'education',
    'hospitality',
    'immobilier',
    'mrp',
    'sante',
  ],
}

export function normaliserEdition(valeur) {
  const v = String(valeur ?? '').trim().toLowerCase()
  if (!v) return DEFAULT_EDITION
  if (!EDITIONS.includes(v)) {
    throw new Error(
      `VITE_EDITION : édition « ${v} » inconnue (attendu : ${EDITIONS.join(', ')}).`,
    )
  }
  return v
}

/** Verticaux parqués par cette édition (liste vide en édition complète). */
export function verticauxParques(edition) {
  return VERTICAUX_PARQUES[normaliserEdition(edition)] ?? []
}

/** Chemins `src/<arbre>/<vertical>` exclus du build de cette édition. */
export function arbresParques(edition) {
  const out = []
  for (const vertical of verticauxParques(edition)) {
    for (const arbre of ARBRES) out.push(`src/${arbre}/${vertical}`)
  }
  return out
}

/** Vrai si le module `cle` fait partie du build de cette édition. */
export function moduleDansEdition(cle, edition) {
  return !verticauxParques(edition).includes(cle)
}
