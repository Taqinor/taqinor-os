/* ============================================================================
   R4-41 — le préchargement des écrans de Tâches. Chaque fichier de `ecrans/` enregistre ici le chargeur de SON morceau
   (`CHARGEURS[clé] = () => import(…)`) ; dès l'entrée dans le module, les écrans des onglets se chargent à l'inactivité,
   un à un : le premier toucher d'un onglet n'attend plus le réseau. Aucune dépendance : ce petit fichier vit dans le
   morceau commun du module.
   ========================================================================== */

export const CHARGEURS = {}

/** Les écrans préchargés à l'entrée dans le module, dans l'ordre où l'on y va : les onglets, puis la page d'un projet. */
const A_PRECHARGER = ['atrier', 'projets', 'agenda', 'aujourdhui', 'projet']

let prechargement = null
/** Pour les tests : remet le préchargement à zéro (une session ne le fait qu'une fois). */
export function reinitialiserPrechargement() { prechargement = null }

/** Charge les écrans des onglets, UN par UN, chaque fois à l'inactivité du navigateur : ni le premier rendu ni le réseau
 *  du premier écran n'attendent après eux. Une seule fois par session ; hors économie de données ; un échec (réseau) se
 *  retente au prochain écran monté. */
export function prechargerEcrans() {
  if (prechargement) return prechargement
  if (globalThis.navigator?.connection?.saveData) return Promise.resolve()
  const auRepos = () => new Promise((fait) => {
    if (typeof window.requestIdleCallback === 'function') window.requestIdleCallback(() => fait(), { timeout: 3000 })
    else setTimeout(fait, 250)
  })
  prechargement = (async () => {
    for (const cle of A_PRECHARGER) {
      await auRepos()
      try {
        await CHARGEURS[cle]()
      } catch {
        prechargement = null // réseau coupé : on réessaiera à l'écran suivant ; ce n'était qu'une avance
        return
      }
    }
  })()
  return prechargement
}
