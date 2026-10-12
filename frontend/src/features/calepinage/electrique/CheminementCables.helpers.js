// ENF22 — helpers extraits de CheminementCables.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.
import { formatNumber } from '../../../lib/format'

const LIBELLES_COTE = { dc: 'DC', ac: 'AC', terre: 'Terre' }

/** Le libellé du côté d'un tronçon — un code inconnu est NOMMÉ, jamais tu. */
export function libelleCote(cote) {
  return LIBELLES_COTE[cote] ?? `côté « ${cote} »`
}

const LIBELLES_ORIGINE = {
  plan: 'tracé sur le plan',
  saisie: 'saisie au clavier',
  mixte: 'tracé + saisie (mixte)',
}

/** Le libellé français de l'origine d'une longueur — jamais un nombre nu. */
export function libelleOrigine(origine) {
  if (!origine) return null
  return LIBELLES_ORIGINE[origine] ?? `origine « ${origine} »`
}

/** Le contenu de la cellule « longueur » : le nombre ET sa provenance ensemble. */
export function celluleLongueur(troncon) {
  if (troncon?.longueur_m === null || troncon?.longueur_m === undefined) return '—'
  const origine = libelleOrigine(troncon.longueur_origine)
  const nombre = formatNumber(troncon.longueur_m, { decimals: 1 })
  return origine ? `${nombre} m (${origine})` : `${nombre} m`
}
