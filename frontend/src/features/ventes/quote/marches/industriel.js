// QJR89 — STRATÉGIE DE MARCHÉ : INDUSTRIEL (module PUR).
// ---------------------------------------------------------------------------
// Interface commune aux quatre marchés :
//   { cle, defautScenario, champsRequis, dimensionner(etat, deps),
//     composer(etat, deps), etudePersistee(etat) }
//
// Ce marché HÉBERGE `computeEtudeIndustrielle` : le calcul lui-même n'est PAS
// recopié — il reste la fonction unique de `solar.js` (une seconde copie serait
// un second endroit où les chiffres peuvent diverger) ; c'est le SITE D'APPEL
// de `DevisGenerator.jsx:3103-3111` qui est recopié ici, à l'identique.
//
// AUCUN MOTEUR SERVEUR n'existe pour ce marché (`etudeHoraireCorps` est
// verrouillé sur le résidentiel, `DevisGenerator.jsx:964/:984` ; l'extension
// est le chantier séparé QJR113, décision fondateur D10). Le moteur JS est
// donc le SEUL calcul d'économies qui tourne jamais ici : chacun de ses
// chiffres sort SIGNÉ `apercu` (QJR86) et sera rendu avec la puce
// « estimation d'exemple » — jamais mêlé à un chiffre serveur.
//
// LE CORRECTIF QJR34 DEVENU STRUCTUREL : `etudePersistee` rend
// `absent('aucune consommation saisie')` tant que l'entrée de consommation
// n'est pas SIGNÉE `saisie`. Ce n'est plus un `if` qu'on peut oublier — c'est
// la seule porte d'entrée du calcul.
//
// Module AJOUTÉ TESTÉ, IMPORTÉ PAR PERSONNE (vague M4).
import { computeEtudeIndustrielle } from '../../solar.js'
import { apercu, absent, estFait } from '../valeur.js'

export const cle = 'industriel'

/**
 * L'auto-remplissage de ce marché met batterie + onduleur hybride à ZÉRO :
 * le double scénario n'y est pas servable (`DevisGenerator.jsx:1209-1216`).
 */
export const defautScenario = 'Sans batterie'

/** L'étude EXIGE la consommation réelle du client (`validate()`, :2743). */
export const champsRequis = Object.freeze(['conso_mensuelle_kwh'])

/** Motif FR unique du refus de calcul faute d'entrée signée. */
export const MOTIF_SANS_CONSO = 'aucune consommation saisie'

/**
 * DIMENSIONNEMENT — aucun moteur serveur : le balayage LOCAL par paliers est
 * la seule source de taille de ce marché, et il exige le catalogue → il est
 * résolu par l'appelant et arrive dans `deps.computeAutoSizing`. Rien n'est
 * chiffré ici : sans résultat, `sizing` vaut `null` (jamais une supposition).
 */
export function dimensionnerLocalement(etat = {}, deps = {}, marche = cle) {
  const sizing = typeof deps.computeAutoSizing === 'function'
    ? deps.computeAutoSizing(etat.factureHiver, etat.factureEte)
    : null
  return {
    mode: 'local',
    raison: `aucun moteur de dimensionnement serveur pour le marché ${marche}`
      + ' — balayage local par paliers',
    sizing: (sizing && Number(sizing.nbPanneaux) > 0) ? sizing : null,
  }
}

export const dimensionner = (etat, deps) => dimensionnerLocalement(etat, deps, cle)

/**
 * COMPOSITION — locale, comme aujourd'hui (aucun dry-run serveur pour ce
 * marché). Le module décrit les paramètres ; le producteur de lignes reste
 * `autoFillLines`, fourni par l'appelant (`deps.autoFillLines`), pour que ce
 * module n'ait pas à connaître le catalogue.
 */
export function composerLocalement(etat = {}, deps = {}, marche = cle) {
  const params = {
    kwp: Number.parseFloat(etat.kwc) || 0,
    panelW: Number.parseFloat(etat.panelW) || 710,
    structureType: etat.structure ?? 'acier',
    marques: etat.marques ?? null,
    ordreLignes: etat.ordreLignes ?? null,
  }
  const raison = `aucun dry-run serveur pour le marché ${marche} — composition locale`
  if (typeof deps.autoFillLines !== 'function' || !(params.kwp > 0)) {
    return { mode: 'local', raison, params, lignes: null }
  }
  return { mode: 'local', raison, params, lignes: deps.autoFillLines(deps.produits ?? [], params) }
}

export const composer = (etat, deps) => composerLocalement(etat, deps, cle)

/**
 * ÉTUDE D'AUTOCONSOMMATION — la porte UNIQUE du calcul, partagée avec le
 * marché commercial (qui ne change que le taux d'usage diurne). Rend une
 * VALEUR SIGNÉE :
 *   · `absent('aucune consommation saisie')` tant que l'entrée de consommation
 *     n'est pas signée `saisie` (correctif QJR34, rendu structurel) ;
 *   · `absent(motif)` quand il n'y a pas de kWc à étudier ;
 *   · sinon `apercu(etude)` — un chiffre du moteur JS, donc étiqueté.
 */
export function etudeAutoconsommation(etat = {}, { dayUsagePct } = {}) {
  const conso = etat.consommation
  if (!estFait(conso) || conso.source !== 'saisie') return absent(MOTIF_SANS_CONSO)
  const consoMensuelleKwh = Number.parseFloat(conso.valeur) || 0
  if (!(consoMensuelleKwh > 0)) return absent(MOTIF_SANS_CONSO)
  const kwp = Number.parseFloat(etat.kwc) || 0
  if (!(kwp > 0)) {
    return absent('aucun kWc à étudier : renseignez le nombre de panneaux')
  }
  // Site d'appel recopié de `DevisGenerator.jsx:3105-3110`, à l'identique.
  const etude = computeEtudeIndustrielle({
    kwp,
    consoMensuelleKwh,
    dayUsagePct,
    totalTtc: etat.totalTtc,
    kwhPrice: etat.kwhPrice,
    efficiency: etat.efficiency,
    injectionEnabled: etat.injectionEnabled ?? false,
    tensionRaccordement: etat.tension ?? 'bt',
    repartitionMt: etat.repartitionMt ?? null,
  })
  if (!etude) return absent('aucun kWc à étudier : renseignez le nombre de panneaux')
  return apercu(etude)
}

/** ÉTUDE PERSISTÉE — taux d'usage diurne du type d'installation industriel. */
export function etudePersistee(etat = {}) {
  return etudeAutoconsommation(etat, {
    dayUsagePct: etat.dayUsagePct,
  })
}

export default {
  cle, defautScenario, champsRequis, dimensionner, composer, etudePersistee,
}
