import { annulerGeste, lireTache } from '../../../api/tachesApi'

/* ============================================================================
   F4 revue #6/#7 — « Annuler » change la VERSION de chaque tâche qu'il remet (`lock_version`, verrou optimiste) ;
   `gestes/{id}/annuler/` ne la rend pas (`geste_annuler.json` : `restaurees: [{objet, id}]`). Un écran qui remet
   alors l'objet d'AVANT garde un `lock_version` périmé : le geste suivant sur la même tâche est refusé (« Modifiée
   ailleurs. ») jusqu'au rechargement. Règle unique : après un « Annuler » réussi, on relit CHAQUE tâche remise —
   cette tâche seule, jamais la vue — et l'écran garde la version RENDUE par le serveur.
   ========================================================================== */

/** La TACHE lue (version à jour), ou `null` si la lecture échoue : la version gardée reste alors celle d'avant, et un
 *  éventuel refus du serveur sort par le bandeau de conflit habituel — jamais un blocage de l'annulation. */
async function lireVersion(id) {
  try {
    const reponse = await lireTache(id)
    return reponse?.data?.id === id ? reponse.data : null
  } catch {
    return null // lecture en échec : l'annulation a réussi ; on garde la version d'avant (voir ci-dessus)
  }
}

/**
 * « Annuler » le geste `gesteId`, puis relit chaque tâche remise (`restaurees` du serveur + `ids` que l'appelant
 * sait concernées). Rend la réponse du serveur avec `taches` : `{ [id]: TACHE à jour }`. `annulerGeste` qui échoue
 * remonte à l'appelant, comme avant.
 */
export async function annulerEtRecaler(gesteId, ids = []) {
  const reponse = await annulerGeste(gesteId)
  const rendues = (reponse?.data?.restaurees ?? []).filter((r) => r.objet === 'tache').map((r) => r.id)
  const aLire = [...new Set([...ids, ...rendues])].filter((id) => Number.isInteger(id))
  const lues = await Promise.all(aLire.map(lireVersion))
  const taches = Object.fromEntries(lues.filter(Boolean).map((t) => [t.id, t]))
  return { ...reponse, taches }
}

/** Le `lock_version` à jour de `id` dans le résultat de `annulerEtRecaler`, sinon `repli` (la version d'avant). */
export const versionDe = (resultat, id, repli) => resultat?.taches?.[id]?.lock_version ?? repli
