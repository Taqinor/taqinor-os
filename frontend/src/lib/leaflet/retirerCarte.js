// Retrait SÛR d'une carte Leaflet (même garde que MapView, CAD177) : `remove()`
// n'annule ni le panoramique/l'inertie en cours ni le `setTimeout` de 250 ms du
// zoom animé (Leaflet 1.9 `_animateZoom`) ; s'ils tombent après, `_move` lit
// `_mapPane` détruit → « Cannot read properties of undefined (reading
// '_leaflet_pos') » (marcheur aléatoire, nocturne 40000624035). On arrête le
// mouvement et on CLÔT le zoom tant que les panneaux existent, puis on retire.
export function retirerCarte(map) {
  if (!map) return
  try {
    map.stop?.()
    if (map._animatingZoom) map._onZoomTransitionEnd?.()
    // Nocturne 40000624035 (marcheur aléatoire, espèce « scroller ») : le
    // gestionnaire molette (Leaflet 1.9 `ScrollWheelZoom`) arme son propre
    // `setTimeout(_performZoom, 40 ms)` que ni `stop()` ni `remove()`
    // n'annulent ; tombé après le retrait, `setZoomAround` lit `_mapPane`
    // détruit → « reading '_leaflet_pos' ». On désarme le timer.
    const molette = map.scrollWheelZoom
    if (molette && molette._timer) {
      clearTimeout(molette._timer)
      molette._timer = null
    }
  } catch { /* carte déjà démontée : rien à arrêter */ }
  // Une carte retirée n'a plus rien à déplacer : un panBy tardif (inertie du
  // glisser) devient inerte.
  const panBy = map.panBy
  if (typeof panBy === 'function') {
    map.panBy = function panByTantQueMontee(...args) {
      return this._mapPane ? panBy.apply(this, args) : this
    }
  }
  map.remove()
}
