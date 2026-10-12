// ENF22 — helpers extraits de SaisiePente.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

const DEG = 180 / Math.PI

function nombre(brut) {
  if (brut === null || brut === undefined || brut === '') return null
  const v = Number(brut)
  return Number.isFinite(v) ? v : null
}

/** CAL58 — pente en degrés, telle quelle (aucun arrondi, aucune borne). */
export function penteDepuisDegres(degres) {
  return nombre(degres)
}

/**
 * CAL58 — pente en degrés depuis un POURCENTAGE de pente (hauteur/portée).
 * 100 % = 45°, 57,735 % = 30°. Un pourcentage négatif est accepté tel quel
 * (un plan peut décrire une contre-pente) : on ne refuse pas une saisie.
 */
export function penteDepuisPourcentage(pourcentage) {
  const p = nombre(pourcentage)
  if (p === null) return null
  return Math.atan(p / 100) * DEG
}

/**
 * CAL58 — pente en degrés depuis les COTES mesurées : portée (l'horizontale)
 * et hauteur de faîtage (la verticale). Portée nulle ou absente ⇒ `null` :
 * une division par zéro ne produit pas une pente, elle produit un mensonge.
 */
export function penteDepuisCotes(porteeM, hauteurFaitageM) {
  const portee = nombre(porteeM)
  const hauteur = nombre(hauteurFaitageM)
  if (portee === null || hauteur === null || portee === 0) return null
  return Math.atan(hauteur / portee) * DEG
}

/** CAL58 — la réciproque, pour afficher la pente retenue en pourcentage. */
export function pourcentageDepuisPente(degres) {
  const d = nombre(degres)
  if (d === null) return null
  return Math.tan(d / DEG) * 100
}

/**
 * CAL58 — LA VALEUR RETENUE et SA PROVENANCE, depuis la saisie des trois
 * modes. Le mode ACTIF tranche : deux modes remplis ne se moyennent pas (une
 * moyenne serait un quatrième chiffre que personne n'a mesuré).
 */
export function penteRetenue(mode, saisie = {}) {
  if (mode === 'pourcentage') {
    const degres = penteDepuisPourcentage(saisie.pourcentage)
    return degres === null ? null : { degres, source: 'pourcentage' }
  }
  if (mode === 'cotes') {
    const degres = penteDepuisCotes(saisie.porteeM, saisie.hauteurFaitageM)
    return degres === null ? null : { degres, source: 'cotes' }
  }
  const degres = penteDepuisDegres(saisie.degres)
  return degres === null ? null : { degres, source: 'degres' }
}

/* ACAL252 — la pente est celle d'UN PAN (`zones[i].pitchDeg` + `pitchSource`), jamais une
   clé racine du document. `pitchSource` dit d'où elle vient (schéma `pitchSource`) : le mode
   et SES champs ; `provenance: 'visite'` s'y ajoute quand la valeur vient de la visite. */
export function zonesDuDocument(document) {
  return (Array.isArray(document?.zones) ? document.zones : [])
    .filter((z) => z && z.id !== undefined && z.id !== null)
}

/** Le pan proposé par défaut : le pan ACTIF de l'atelier, sinon le premier. */
export function panParDefaut(document) {
  const zones = zonesDuDocument(document)
  const actif = zones.find((z) => String(z.id) === String(document?.activeAreaId))
  return String((actif ?? zones[0])?.id ?? '')
}

const texte = (v) => (v === null || v === undefined ? '' : String(v))

/** La saisie (mode + champs) qui reproduit ce que le pan a enregistré. */
export function saisieDuPan(zone) {
  const vide = { degres: '', pourcentage: '', porteeM: '', hauteurFaitageM: '' }
  const source = zone?.pitchSource
  const deg = zone?.pitchDeg
  if (source && typeof source === 'object') {
    const mode = source.mode === 'pourcentage' || source.mode === 'cotes' ? source.mode : 'degres'
    return {
      mode,
      saisie: {
        degres: texte(source.degres ?? (mode === 'degres' ? deg : null)),
        pourcentage: texte(source.pourcentage),
        porteeM: texte(source.porteeM),
        hauteurFaitageM: texte(source.hauteurFaitageM),
      },
    }
  }
  if (typeof deg === 'number' && Number.isFinite(deg)) {
    return { mode: 'degres', saisie: { ...vide, degres: String(deg) } }
  }
  return { mode: 'degres', saisie: vide }
}

/** `pitchSource` à écrire : le mode retenu et ses SEULS champs (valeurs exactes). */
export function sourceDePente(retenue, saisie, deVisite = false) {
  const n = (v) => nombre(v)
  let source
  if (retenue.source === 'pourcentage') {
    source = { mode: 'pourcentage', pourcentage: n(saisie.pourcentage) }
  } else if (retenue.source === 'cotes') {
    source = {
      mode: 'cotes', porteeM: n(saisie.porteeM), hauteurFaitageM: n(saisie.hauteurFaitageM),
    }
  } else {
    source = { mode: 'degres', degres: retenue.degres }
  }
  return deVisite && source.mode === 'degres' ? { ...source, provenance: 'visite' } : source
}

/* ACAL208 — l'orientation d'une visite est un CHOIX de la rose des vents ; son azimut
   boussole est le centre du secteur, sa précision la demi-largeur du secteur (22,5°).
   Proposition affichée, jamais appliquée d'office (D7). */
const ROSE = {
  nord: ['nord', 0], nord_est: ['nord-est', 45], est: ['est', 90], sud_est: ['sud-est', 135],
  sud: ['sud', 180], sud_ouest: ['sud-ouest', 225], ouest: ['ouest', 270],
  nord_ouest: ['nord-ouest', 315],
}

const PRECISION_SECTEUR_DEG = 22.5

/** Les mesures de la visite reprise utiles à l'onglet : pente et orientation (ou `null`). */
export function mesuresDeVisite(etat) {
  const mesures = Array.isArray(etat?.mesures) ? etat.mesures : []
  const trouver = (code) => mesures.find((m) => m?.code === code)?.valeur
  const pente = nombre(trouver('pente_deg'))
  const choix = ROSE[trouver('orientation')]
  return {
    penteDeg: pente,
    orientation: choix
      ? { libelle: choix[0], azimutDeg: choix[1], precisionDeg: PRECISION_SECTEUR_DEG }
      : null,
  }
}

/**
 * ACAL66 — les suggestions de pente IGN EN ATTENTE du document : un pan dont
 * `pitchSuggestion.status` vaut `suggeree`. Lecture PURE du document (la
 * suggestion y est persistée par `POST suggestions-pente/`, ACAL65) : rouvrir
 * l'onglet retrouve la même liste.
 */
export function suggestionsEnAttente(document) {
  const zones = Array.isArray(document?.zones) ? document.zones : []
  return zones
    .filter((z) => z?.pitchSuggestion?.status === 'suggeree')
    .map((z) => ({
      zoneId: String(z.id ?? ''),
      valeurDeg: z.pitchSuggestion.valeurDeg ?? null,
      source: z.pitchSuggestion.source ?? '',
      suggestedAt: z.pitchSuggestion.suggestedAt ?? '',
    }))
}
