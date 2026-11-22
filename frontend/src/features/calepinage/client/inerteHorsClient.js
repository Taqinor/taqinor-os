import { useEffect } from 'react'

/* ============================================================================
   « MONTRER AU CLIENT » — J1 (tour 4) : L'ATELIER SOUS LA VUE CLIENT EST INERTE.
   L'atelier reste MONTÉ sous la vue client (le constructeur se lie au DOM par id : rien n'est démonté) ;
   tout ce qui n'est pas la vue client devient `inert` + `aria-hidden` — ni Tab, ni lecteur d'écran, ni clic.
   Restent vivants : la scène client (puce, pastilles), le corps et le pied de la vue client
   (`[data-vue-client]`) et la toile de la carte (`.maplibregl-canvas-container` : un doigt fait tourner la
   maison). Les gestes de la vue client sur les VRAIS contrôles du constructeur (soleil) passent par le
   script (`click()`, `input`), pas par l'utilisateur : `inert` ne les arrête pas.
   Suit le DOM (le constructeur ajoute des nœuds tard) ; tout est rendu à la sortie.
   ========================================================================== */

const GARDES = '.cal-coque-sur-carte-client, [data-vue-client], .maplibregl-canvas-container'

/** Pose `inert` + `aria-hidden` sur chaque branche de `racine` qui ne mène à aucune garde ; rend la liste posée. */
export function rendreInerteHorsClient(racine, poses = new Map()) {
  const gardes = [...racine.querySelectorAll(GARDES)]
  const chemin = new Set()
  for (const g of gardes) {
    for (let n = g; n && n !== racine; n = n.parentElement) chemin.add(n)
  }
  const gardeesOuSous = (n) => gardes.some((g) => g === n || g.contains(n))
  const visiter = (parent) => {
    for (const enfant of parent.children) {
      if (gardeesOuSous(enfant)) continue
      if (chemin.has(enfant)) { visiter(enfant); continue }
      if (!poses.has(enfant)) poses.set(enfant, { inert: enfant.hasAttribute('inert'), cache: enfant.getAttribute('aria-hidden') })
      if (!enfant.hasAttribute('inert')) enfant.setAttribute('inert', '')
      if (enfant.getAttribute('aria-hidden') !== 'true') enfant.setAttribute('aria-hidden', 'true')
    }
  }
  if (gardes.length) visiter(racine)
  return poses
}

/** Rend chaque nœud posé tel qu'il était. */
export function rendreVivant(poses) {
  for (const [n, avant] of poses) {
    if (!avant.inert) n.removeAttribute('inert')
    if (avant.cache === null) n.removeAttribute('aria-hidden')
    else n.setAttribute('aria-hidden', avant.cache)
  }
  poses.clear()
}

/** La coque (`.cal-coque`, ancêtre du nœud de la scène client) inerte hors de la vue client, tant qu'elle est montée. */
export function useHorsVueClientInerte(noeudScene) {
  useEffect(() => {
    const racine = noeudScene?.closest?.('.cal-coque')
    if (!racine) return undefined
    const poses = new Map()
    let image = null
    const poser = () => { image = null; rendreInerteHorsClient(racine, poses) }
    poser()
    const suivre = typeof MutationObserver === 'function'
      ? new MutationObserver(() => { if (image === null) image = window.requestAnimationFrame(poser) }) : null
    suivre?.observe(racine, { childList: true, subtree: true })
    return () => {
      suivre?.disconnect()
      if (image !== null) window.cancelAnimationFrame(image)
      rendreVivant(poses)
    }
  }, [noeudScene])
}
