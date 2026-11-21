// ACAL516 — boussole et inclinaison du téléphone, en une petite couche partagée (aucun écran ici :
// ACAL518 et ACAL519 la consomment). Aucune précision n'est supposée ni rendue : c'est
// l'utilisateur qui la déclare. Repères W3C DeviceOrientation : x = Est, y = Nord, z = haut ;
// R = Rz(alpha)·Rx(beta)·Ry(gamma) ; l'ARRIÈRE du téléphone pointe selon -z de l'appareil.

const MOTIF_REFUSE = 'Capteurs refusés : saisissez l’azimut et la hauteur à la main.'
const MOTIF_ABSENT = 'Capteurs absents : saisissez l’azimut et la hauteur à la main.'
const RAD = Math.PI / 180

let fenetreActive = null
let derniere = null // { alpha, beta, gamma } — dernier événement exploitable
let ecouteurs = []

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const norme360 = (d) => ((d % 360) + 360) % 360

function surEvenement(e) {
  if (!e || num(e.beta) === null || num(e.gamma) === null) return
  const cap = num(e.webkitCompassHeading)
  // iOS donne le cap (sens horaire) ; sinon alpha (sens antihoraire) de l'événement.
  const alpha = cap !== null ? norme360(360 - cap) : num(e.alpha)
  derniere = { alpha, beta: e.beta, gamma: e.gamma }
}

/** À appeler depuis un GESTE de l'utilisateur. Rend `{ok: true}` ou `{indisponible: true, motif}`. */
export async function demarrerCapteurs(fenetre = typeof window !== 'undefined' ? window : null) {
  arreter()
  const Evt = fenetre && fenetre.DeviceOrientationEvent
  if (!Evt) return { indisponible: true, motif: MOTIF_ABSENT }
  if (typeof Evt.requestPermission === 'function') {
    let reponse = null
    try { reponse = await Evt.requestPermission() } catch { reponse = null }
    if (reponse !== 'granted') return { indisponible: true, motif: MOTIF_REFUSE }
  }
  fenetreActive = fenetre
  for (const nom of ['deviceorientationabsolute', 'deviceorientation']) {
    fenetre.addEventListener(nom, surEvenement)
    ecouteurs.push(nom)
  }
  return { ok: true }
}

/** Inclinaison brute du dernier événement (degrés), ou indisponible. */
export function lireInclinaison() {
  if (!derniere) return { indisponible: true, motif: MOTIF_REFUSE }
  return { betaDeg: derniere.beta, gammaDeg: derniere.gamma }
}

/** Visée de l'arrière du téléphone : `{azimutDeg, hauteurDeg}` (hauteur > 0 au-dessus de l'horizon). */
export function lireVisee() {
  if (!derniere || derniere.alpha === null) return { indisponible: true, motif: MOTIF_REFUSE }
  const a = derniere.alpha * RAD
  const b = derniere.beta * RAD
  const g = derniere.gamma * RAD
  const est = -(Math.cos(a) * Math.sin(g) + Math.sin(a) * Math.sin(b) * Math.cos(g))
  const nord = -(Math.sin(a) * Math.sin(g) - Math.cos(a) * Math.sin(b) * Math.cos(g))
  const haut = -(Math.cos(b) * Math.cos(g))
  return {
    azimutDeg: norme360(Math.atan2(est, nord) / RAD),
    hauteurDeg: Math.asin(Math.max(-1, Math.min(1, haut))) / RAD,
  }
}

export function arreter() {
  if (fenetreActive) for (const nom of ecouteurs) fenetreActive.removeEventListener(nom, surEvenement)
  fenetreActive = null
  ecouteurs = []
  derniere = null
}
