// ENF22 — helpers extraits de CalepinageList.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

import { formatNumber } from '../../lib/format'

/* ACAL197 — LES STATUTS SERVIS (contrat `calepinage_liste.json`,
   `statuts_publies`) : le filtre les propose TOUJOURS, pas seulement ceux de la
   page courante. Gardée par un vitest contre l'échantillon de contrat. */
export const STATUTS_CALEPINAGE = [
  ['brouillon', 'Brouillon'],
  ['valide', 'Validé'],
  ['perime', 'Périmé'],
  ['refuse', 'Refusé'], // ACON28 — dernière décision d'approbation : un refus
]

/* Maquette « Liste » — la pastille d'état de chaque carte : classes sur les
   JETONS du thème (jamais une couleur littérale), pictogramme par état. */
export const STYLE_STATUT = {
  brouillon: 'bg-muted text-muted-foreground',
  valide: 'bg-success/10 text-success-text',
  perime: 'bg-warning/15 text-warning-text',
  refuse: 'bg-destructive/10 text-destructive',
}

const FR = (valeur, decimales) => formatNumber(Number(valeur), { decimals: decimales })

/** « 6,96 kWc · 12 panneaux · 11 480 kWh/an » — CHAQUE morceau seulement quand
    le serveur le sert (`kwc`, `layout_nb_panneaux`, `production_kwh_an`), jamais
    un chiffre fabriqué. Rend `[{ texte, fort }]` (le kWc est en gras). */
export function morceauxMesures(ligne) {
  const morceaux = []
  const kwc = ligne?.kwc
  if (typeof kwc === 'number' && kwc > 0) morceaux.push({ texte: `${FR(kwc, 2)} kWc`, fort: true })
  const nb = ligne?.layout_nb_panneaux
  if (typeof nb === 'number' && nb > 0) morceaux.push({ texte: `${nb} panneau${nb > 1 ? 'x' : ''}`, fort: false })
  const prod = ligne?.production_kwh_an
  if (typeof prod === 'number' && prod > 0) morceaux.push({ texte: `${FR(prod, 0)} kWh/an`, fort: false })
  return morceaux
}

const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
  'septembre', 'octobre', 'novembre', 'décembre']
const heure = (d) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
const jourDe = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()

/** « Modifié aujourd'hui à 14:41 » · « Modifié hier à 17:20 » · « Modifié 18 novembre »
    (l'année s'ajoute hors de l'année courante). `null` sans date servie. */
export function modifieDe(iso, maintenant = new Date()) {
  const d = iso ? new Date(iso) : null
  if (!d || Number.isNaN(d.getTime())) return null
  const ecart = Math.round((jourDe(maintenant) - jourDe(d)) / 86400000)
  if (ecart === 0) return `Modifié aujourd'hui à ${heure(d)}`
  if (ecart === 1) return `Modifié hier à ${heure(d)}`
  const annee = d.getFullYear() === maintenant.getFullYear() ? '' : ` ${d.getFullYear()}`
  return `Modifié ${d.getDate()} ${MOIS[d.getMonth()]}${annee}`
}

/** Initiales (2 lettres au plus) d'un nom complet ; `null` sans nom. */
export function initiales(nom) {
  const mots = String(nom || '').trim().split(/\s+/).filter(Boolean)
  if (!mots.length) return null
  return mots.slice(0, 2).map((m) => m[0]).join('').toUpperCase()
}

/** La ville de la carte : celle du client rattaché, à défaut celle du lead. */
export const villeDe = (ligne) => ligne?.client_apercu?.ville || ligne?.lead?.ville || null

/** « 6 projets » / « 1 projet » / « 0 projet » (le français n'accorde qu'au-delà de 1). */
export const nombreProjets = (n) => `${n} projet${n > 1 ? 's' : ''}`
