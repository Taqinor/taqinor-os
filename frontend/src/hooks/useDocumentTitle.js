// VX82 — Chrome navigateur vivant : titre d'onglet PAR PAGE. Un seul
// `<title>` statique pour toute la vie du SPA (`frontend/index.html`) rendait
// 6 onglets ERP ouverts indiscernables — deviner lequel est lequel. Zéro
// dépendance : `document.title` directement, restauré au démontage pour ne
// pas laisser le titre d'une page fermée collé sur la suivante (ex. retour à
// un composant hôte qui gère lui-même son titre).
import { useEffect } from 'react'

const SUFFIX = ' · TAQINOR'

/**
 * @param {string} title - Titre de PAGE (sans suffixe), ex. « Devis ».
 *   `null`/`undefined`/chaîne vide → no-op (le titre courant n'est pas touché).
 */
export default function useDocumentTitle(title) {
  useEffect(() => {
    if (!title) return undefined
    const previous = document.title
    document.title = `${title}${SUFFIX}`
    return () => { document.title = previous }
  }, [title])
}
