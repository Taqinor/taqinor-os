// ENF22 — helpers extraits de SunDiagram.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.
import { WINTER_SOLSTICE_DAY as JOUR_SOLSTICE_HIVER } from '@rooflib/roofPro2'

/** Jours de repère de l'année (équinoxe, solstice d'été) — l'hiver vient du moteur. */
const JOUR_EQUINOXE = 80

const JOUR_SOLSTICE_ETE = 172

export const COURBES_REPERE = [
  { jour: JOUR_SOLSTICE_ETE, label: 'Solstice d’été', couleur: '#e0b25c' },
  { jour: JOUR_EQUINOXE, label: 'Équinoxe', couleur: '#8f9bb8' },
  { jour: JOUR_SOLSTICE_HIVER, label: 'Solstice d’hiver', couleur: '#5c7ce0' },
]
