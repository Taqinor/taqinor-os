import { useCallback, useState } from 'react'

/* T4-U4-020 / T4-U4-022 — ce qui est TAPÉ au relevé n'est jamais perdu.
   * Le BROUILLON : chaque mesure tapée (Longueur, Largeur, pente, orientation tapée ou boussole + précision) est gardée
     sur le téléphone dès la frappe ; elle est relue à la réouverture et retirée seulement quand le serveur l'a prise.
   * Le PAN EN ATTENTE : la pente et l'orientation à écrire sur le pan quand « Terminer le relevé » se fait sans réseau ;
     elles repartent par la MÊME écriture que l'envoi en ligne (`layout/section/`), au retour du réseau.
   Stockage du navigateur : il peut manquer (navigation privée) — chaque accès est protégé et l'écran marche sans. */

const cle = (id, quoi) => `taqinor.releve.${quoi}.${id}`

function lire(k) {
  try {
    const brut = window.localStorage.getItem(k)
    return brut ? JSON.parse(brut) : null
  } catch {
    return null
  }
}

function ecrire(k, valeur) {
  try {
    if (valeur === null) window.localStorage.removeItem(k)
    else window.localStorage.setItem(k, JSON.stringify(valeur))
  } catch {
    /* stockage indisponible : l'écran garde la valeur en mémoire */
  }
}

const videOuNul = (v) => v === undefined || v === null || v === ''

/** Le brouillon gardé sur ce téléphone pour ce calepinage (`{}` sans brouillon). */
export const lireBrouillon = (id) => lire(cle(id, 'brouillon')) ?? {}
/** Le pan en attente (`{ zoneId, champs }`) ou `null`. */
export const lirePanEnAttente = (id) => lire(cle(id, 'pan'))

/** Le nombre de MESURES gardées (Longueur, Largeur, pente, orientation) — ce que la note compte. */
export function compterMesures(brouillon) {
  const b = brouillon ?? {}
  return ['Longueur', 'Largeur', 'pente'].filter((k) => !videOuNul(b[k])).length
    + (!videOuNul(b.azimutMain) || !videOuNul(b.boussole?.azimutDeg) ? 1 : 0)
}

export default function useBrouillonReleve(calepinageId) {
  const [brouillon, setBrouillon] = useState(() => (calepinageId ? lireBrouillon(calepinageId) : {}))
  const [pan, setPan] = useState(() => (calepinageId ? lirePanEnAttente(calepinageId) : null))

  /** Pose (ou retire, valeur vide) des champs du brouillon. */
  const garder = useCallback((champs) => {
    if (!calepinageId) return
    setBrouillon((courant) => {
      const suivant = { ...courant }
      Object.entries(champs).forEach(([k, v]) => { if (videOuNul(v)) delete suivant[k]; else suivant[k] = v })
      ecrire(cle(calepinageId, 'brouillon'), Object.keys(suivant).length ? suivant : null)
      return suivant
    })
  }, [calepinageId])

  /** Retire les champs nommés (tous si `noms` est absent) : le serveur les a pris. */
  const oublier = useCallback((noms = null) => {
    if (!calepinageId) return
    setBrouillon((courant) => {
      const suivant = noms ? Object.fromEntries(Object.entries(courant).filter(([k]) => !noms.includes(k))) : {}
      ecrire(cle(calepinageId, 'brouillon'), Object.keys(suivant).length ? suivant : null)
      return suivant
    })
  }, [calepinageId])

  const garderPan = useCallback((attente) => {
    if (!calepinageId) return
    ecrire(cle(calepinageId, 'pan'), attente)
    setPan(attente)
  }, [calepinageId])

  const oublierPan = useCallback(() => {
    if (!calepinageId) return
    ecrire(cle(calepinageId, 'pan'), null)
    setPan(null)
  }, [calepinageId])

  return { brouillon, garder, oublier, pan, garderPan, oublierPan }
}
