/* AOF80 — Calibration deux points : le facteur px→m de l'atelier.
   ----------------------------------------------------------------------------
   Un fond de plan sans échelle connue est un piège : tout ce qu'on y trace a
   l'air juste et ne vaut RIEN. La calibration est donc BLOQUANTE — tant qu'elle
   n'est pas faite, les outils de tracé et de cotation sont désactivés et la
   barre d'état affiche « échelle inconnue ». Aucune cote ne peut naître sur un
   underlay non calibré : `peutCoter()` est la garde unique, consommée par
   l'écran ET par les tests.

   Le recalibrage ne perd jamais le tracé : `reechelonner()` propose
   EXPLICITEMENT de ré-échelonner les sommets déjà saisis (l'appelant décide ;
   rien n'est appliqué en douce). */

/* Bornes de vraisemblance d'un plan de toiture. En dessous de 0,0005 m/px un
   plan de 25 m ferait 50 000 px ; au-dessus de 0,5 m/px un pixel vaudrait un
   demi-mètre — dans les deux cas la saisie d'une distance s'est trompée d'unité
   (cm au lieu de m, mm au lieu de cm…). On ALERTE, on ne refuse pas : un cas
   exotique reste possible, mais jamais silencieux. */
export const MPP_MIN_VRAISEMBLABLE = 0.0005
export const MPP_MAX_VRAISEMBLABLE = 0.5

/* En deçà, les deux points cliqués sont trop proches : l'erreur de clic (±2 px)
   se propage en pourcentage énorme sur toutes les cotes du plan. */
export const ECART_PX_MINIMAL = 24

export function distancePx(p1, p2) {
  if (!p1 || !p2) return 0
  const dx = Number(p2.x) - Number(p1.x)
  const dy = Number(p2.y) - Number(p1.y)
  if (!Number.isFinite(dx) || !Number.isFinite(dy)) return 0
  return Math.hypot(dx, dy)
}

/**
 * Construit la calibration. Renvoie toujours un objet :
 *   { valide, metresParPixel, distancePx, distanceReelleM, motif }
 * `motif` est un message FR quand la calibration est refusée.
 */
export function calibrer({ p1, p2, distanceReelleM }) {
  const dpx = distancePx(p1, p2)
  const d = Number(distanceReelleM)
  if (!Number.isFinite(d) || d <= 0) {
    return { valide: false, motif: 'Saisissez la distance réelle en mètres (un nombre positif).' }
  }
  if (dpx <= 0) {
    return { valide: false, motif: 'Cliquez DEUX points distincts sur le plan.' }
  }
  if (dpx < ECART_PX_MINIMAL) {
    return {
      valide: false,
      motif:
        `Les deux points sont trop proches (${Math.round(dpx)} px). Prenez une distance longue ` +
        'et bien connue : l’imprécision du clic se reporterait sur toutes les cotes.',
    }
  }
  return {
    valide: true,
    metresParPixel: d / dpx,
    distancePx: dpx,
    distanceReelleM: d,
    p1: { x: Number(p1.x), y: Number(p1.y) },
    p2: { x: Number(p2.x), y: Number(p2.y) },
    motif: null,
  }
}

/** Une calibration est acquise, ou elle ne l'est pas. Aucun état intermédiaire. */
export function estCalibree(cal) {
  return Boolean(
    cal && cal.valide && Number.isFinite(cal.metresParPixel) && cal.metresParPixel > 0,
  )
}

/* ── Les gardes BLOQUANTES ──────────────────────────────────────────────────── */

/** Les outils de tracé sont-ils utilisables ? */
export function peutTracer(cal) {
  return estCalibree(cal)
}

/** Une cote peut-elle être créée ? C'est la garde citée par le « Done = ». */
export function peutCoter(cal) {
  return estCalibree(cal)
}

/** Libellé de la barre d'état — jamais vide, jamais technique. */
export function libelleEchelle(cal) {
  if (!estCalibree(cal)) return 'échelle inconnue'
  const pxParMetre = 1 / cal.metresParPixel
  return `échelle : 1 m = ${pxParMetre.toFixed(1)} px`
}

/**
 * Contrôle de vraisemblance à la validation.
 * → { niveau: 'ok' | 'alerte', message }
 */
export function verifierVraisemblance(cal) {
  if (!estCalibree(cal)) {
    return { niveau: 'alerte', message: 'Échelle inconnue : le plan n’est pas calibré.' }
  }
  const mpp = cal.metresParPixel
  if (mpp < MPP_MIN_VRAISEMBLABLE) {
    return {
      niveau: 'alerte',
      message:
        `Échelle suspecte : 1 pixel vaudrait ${mpp.toFixed(6)} m. La distance saisie est ` +
        'probablement en centimètres ou en millimètres — vérifiez avant de continuer.',
    }
  }
  if (mpp > MPP_MAX_VRAISEMBLABLE) {
    return {
      niveau: 'alerte',
      message:
        `Échelle suspecte : 1 pixel vaudrait ${mpp.toFixed(3)} m. Les deux points sont sans doute ` +
        'trop rapprochés pour la distance annoncée — vérifiez avant de continuer.',
    }
  }
  return { niveau: 'ok', message: 'Échelle plausible pour un plan de toiture.' }
}

/* ── Conversions ────────────────────────────────────────────────────────────── */

export function pxVersM(cal, px) {
  if (!estCalibree(cal)) return null
  const v = Number(px)
  return Number.isFinite(v) ? v * cal.metresParPixel : null
}

export function mVersPx(cal, m) {
  if (!estCalibree(cal)) return null
  const v = Number(m)
  return Number.isFinite(v) ? v / cal.metresParPixel : null
}

/**
 * Recalibrage sans perte : renvoie les sommets ré-échelonnés d'un ancien
 * facteur vers un nouveau. L'appelant PROPOSE ce ré-échelonnage à l'écran — il
 * n'est jamais appliqué implicitement (un utilisateur qui recalibre parce que
 * le premier essai était faux ne veut pas forcément déplacer son tracé).
 */
export function reechelonner(sommetsM, ancienne, nouvelle) {
  if (!Array.isArray(sommetsM) || sommetsM.length === 0) return []
  if (!estCalibree(ancienne) || !estCalibree(nouvelle)) return sommetsM.map((s) => ({ ...s }))
  const k = nouvelle.metresParPixel / ancienne.metresParPixel
  return sommetsM.map((s) => ({ ...s, x: Number(s.x) * k, y: Number(s.y) * k }))
}
