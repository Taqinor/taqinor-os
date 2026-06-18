// L55 — Aide réutilisable pour les mises à jour optimistes avec rollback en cas
// d'erreur. Aucune dépendance React : utilisable dans des thunks, des handlers,
// ou un hook (voir `useOptimistic` plus bas qui s'appuie dessus).
//
// Principe : on applique tout de suite le changement dans l'UI (optimiste), on
// lance l'appel réseau, et si celui-ci échoue on restaure l'état précédent
// (rollback). Le motif est volontairement « sans framework » pour s'adapter à
// du state local React comme à du state Redux.

/**
 * runOptimistic — exécute une mise à jour optimiste.
 *
 * @param {object}   opts
 * @param {*}        opts.current   État actuel (sera renvoyé tel quel au rollback).
 * @param {*|Function} opts.optimistic  Prochain état optimiste, ou (current)=>next.
 * @param {Function} opts.apply     (state) => void : pousse l'état dans l'UI.
 * @param {Function} opts.commit    () => Promise : l'appel réseau réel.
 * @param {Function} [opts.onError] (error, previous) => void : effet en cas d'échec
 *                                   (ex. toast), appelé APRÈS le rollback.
 * @param {Function} [opts.rollback] (previous) => void : restauration custom ;
 *                                   par défaut `apply(previous)`.
 * @returns {Promise<{ok:boolean, data?, error?}>} ne rejette jamais.
 */
export async function runOptimistic({
  current,
  optimistic,
  apply,
  commit,
  onError,
  rollback,
}) {
  if (typeof apply !== 'function') throw new Error('runOptimistic: `apply` requis')
  if (typeof commit !== 'function') throw new Error('runOptimistic: `commit` requis')

  const previous = current
  const next = typeof optimistic === 'function' ? optimistic(current) : optimistic

  // 1) Applique l'état optimiste immédiatement.
  apply(next)

  try {
    // 2) Confirme côté serveur.
    const data = await commit()
    return { ok: true, data }
  } catch (error) {
    // 3) Échec : on restaure l'état précédent puis on signale.
    if (typeof rollback === 'function') rollback(previous)
    else apply(previous)
    if (typeof onError === 'function') {
      try { onError(error, previous) } catch { /* l'effet d'erreur ne doit pas masquer l'erreur */ }
    }
    return { ok: false, error }
  }
}

/**
 * optimisticListUpdate — fabrique le prochain état d'une liste en remplaçant
 * l'élément dont la clé correspond (par défaut `id`). Pratique pour un edit
 * inline optimiste : `optimistic: (rows) => optimisticListUpdate(rows, edited)`.
 */
export function optimisticListUpdate(list, item, key = 'id') {
  if (!Array.isArray(list)) return list
  return list.map((row) => (row?.[key] === item?.[key] ? { ...row, ...item } : row))
}

/** optimisticListRemove — retire un élément d'une liste par clé. */
export function optimisticListRemove(list, id, key = 'id') {
  if (!Array.isArray(list)) return list
  return list.filter((row) => row?.[key] !== id)
}

export default runOptimistic
