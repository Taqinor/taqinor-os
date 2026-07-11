// VX82 — Chrome navigateur vivant : titre d'onglet PAR PAGE. Un seul
// `<title>` statique pour toute la vie du SPA (`frontend/index.html`) rendait
// 6 onglets ERP ouverts indiscernables — deviner lequel est lequel. Zéro
// dépendance : `document.title` directement, restauré au démontage pour ne
// pas laisser le titre d'une page fermée collé sur la suivante (ex. retour à
// un composant hôte qui gère lui-même son titre).
// SCA29 — AUCUN suffixe de marque en dur (white-label) : le titre d'onglet est
// le nom de PAGE seul ; l'identité société (si un jour affichée) viendrait de
// TenantTheme/CompanyProfile, jamais d'une chaîne codée en dur ici.
import { useEffect } from 'react'

/**
 * @param {string} title - Titre de PAGE, ex. « Devis ».
 *   `null`/`undefined`/chaîne vide → no-op (le titre courant n'est pas touché).
 */
export default function useDocumentTitle(title) {
  useEffect(() => {
    if (!title) return undefined
    const previous = document.title
    document.title = title
    return () => { document.title = previous }
  }, [title])
}
