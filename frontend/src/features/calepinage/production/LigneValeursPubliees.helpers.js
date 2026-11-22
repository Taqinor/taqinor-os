import { estProfilDepart } from '../reglages/profilDepart'

/** Les clés des réglages FIGÉS au calcul dont la référence est une valeur publiée (profil de départ). */
export function reglagesPublies(simulation) {
  const reglages = simulation?.reglages_utilises
  return reglages && typeof reglages === 'object'
    ? Object.keys(reglages).filter((cle) => estProfilDepart(reglages[cle]?.reference))
    : []
}
