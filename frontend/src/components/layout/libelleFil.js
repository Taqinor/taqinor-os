// T4-X1-016 — LE LIBELLÉ DU FIL D'ARIANE POSÉ PAR L'ÉCRAN. Le fil d'Ariane dérive de
// l'URL (`routes.meta.js`) : une même route peut éditer un objet précis (le
// générateur de devis sur `?edit=<id>`, ouvert par « Réviser »), que seul l'écran
// connaît. L'écran pose le nom de cet objet le temps qu'il est monté ; l'en-tête le
// lit pour le dernier segment du fil. Sans écran qui en pose, rien ne change.
import { useEffect, useSyncExternalStore } from 'react'

let libelle = null
const abonnes = new Set()

const poser = (valeur) => {
  if (libelle === valeur) return
  libelle = valeur
  abonnes.forEach((f) => f())
}
const s_abonner = (f) => {
  abonnes.add(f)
  return () => abonnes.delete(f)
}

/** Côté écran : nomme l'objet édité (ou `null`/vide : titre générique de la route). */
export function useLibelleFil(valeur) {
  useEffect(() => {
    poser(valeur || null)
    return () => poser(null)
  }, [valeur])
}

/** Lecture directe (hors rendu) : le libellé posé en ce moment, ou `null`. */
export const libelleFilPose = () => libelle

/** Côté en-tête : le libellé posé par l'écran courant, ou `null`. */
export function useLibelleFilCourant() {
  return useSyncExternalStore(s_abonner, () => libelle, () => null)
}
