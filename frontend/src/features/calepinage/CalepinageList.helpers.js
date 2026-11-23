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
    un chiffre fabriqué. Rend `[{ texte, fort }]` ; le kWc (`fort`) porte aussi `nombre` et `unite`,
    dessinés en grand chiffre et petite unité (langage v2). */
export function morceauxMesures(ligne) {
  const morceaux = []
  const kwc = ligne?.kwc
  if (typeof kwc === 'number' && kwc > 0) {
    morceaux.push({ texte: `${FR(kwc, 2)} kWc`, fort: true, nombre: FR(kwc, 2), unite: 'kWc' })
  }
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

/** Ce que la carte dit du projet, comme une personne le lit (maquette « Liste » :
    « Villa Bennani » puis « Casablanca ») : le NOM du client rattaché (à défaut celui du
    lead) en titre, la ville dessous ; le nom propre du calepinage (technique) descend en
    petit seulement quand il diffère. Sans rattachement, le nom propre reste le titre. */
export function identiteCarte(ligne) {
  const lie = ligne?.client_apercu?.nom || ligne?.client?.nom || ligne?.lead?.nom || null
  const propre = ligne?.nom || ligne?.reference || 'Calepinage'
  return { titre: lie || propre, ville: villeDe(ligne), propre: lie && lie !== propre ? propre : null }
}

/** Vrai quand les pixels d'un aperçu (RGBA, échantillon réduit) sont TOUS blancs ou
    transparents : un rendu qui n'a rien dessiné — mieux vaut « Aucun aperçu ». */
export function apercuVide(rgba) {
  if (!rgba || !rgba.length) return false
  for (let i = 0; i + 3 < rgba.length; i += 4) {
    const [r, g, b, a] = [rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]]
    if (a > 8 && (r < 245 || g < 245 || b < 245)) return false
  }
  return true
}

/** ACAL1333 — le signal du pied de carte, lu sur le verdict « Prêt à envoyer ? » RANGÉ :
    « N points à régler » (N > 0), « À relire » quand le document a changé depuis, sinon rien
    (jamais lu, ou rien à régler : aucun signal inventé). */
export function signalCarte(ligne) {
  const n = ligne?.points_a_regler
  if (typeof n === 'number' && n > 0) return { ton: 'regler', texte: `${n} point${n > 1 ? 's' : ''} à régler` }
  if (ligne?.points_a_regler_perime === true) return { ton: 'relire', texte: 'À relire' }
  return null
}

/** « 6 projets » / « 1 projet » / « 0 projet » (le français n'accorde qu'au-delà de 1). */
export const nombreProjets = (n) => `${n} projet${n > 1 ? 's' : ''}`
