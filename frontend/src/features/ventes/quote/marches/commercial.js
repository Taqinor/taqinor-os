// QJR89 — STRATÉGIE DE MARCHÉ : COMMERCIAL (module PUR).
// ---------------------------------------------------------------------------
// Même moteur d'autoconsommation que l'industriel (QX44), à UNE différence
// près : le taux d'usage diurne vient de l'ARCHÉTYPE de la catégorie
// (hôtel 55 ≠ bureau 80) — à facture égale, une étude hôtel diffère d'une
// étude bureau. Le calcul est IMPORTÉ d'`industriel.js`, jamais recopié : deux
// copies = deux endroits où les chiffres peuvent diverger.
//
// Aucun moteur serveur ici non plus (chantier séparé QJR113, décision D10) :
// tout chiffre sort SIGNÉ `apercu`, donc étiqueté « estimation d'exemple ».
//
// Module AJOUTÉ TESTÉ, IMPORTÉ PAR PERSONNE (vague M4).
import { commercialDayShare } from '../../solar.js'
import {
  etudeAutoconsommation, MOTIF_SANS_CONSO,
  dimensionnerLocalement, composerLocalement,
} from './industriel.js'

export const cle = 'commercial'

/** Comme l'industriel : autoconsommation réseau sans batterie par défaut. */
export const defautScenario = 'Sans batterie'

export const champsRequis = Object.freeze(['conso_mensuelle_kwh', 'categorie_commerciale'])

export { MOTIF_SANS_CONSO }

/** Aucun moteur serveur : même balayage local que l'industriel. */
export const dimensionner = (etat, deps) => dimensionnerLocalement(etat, deps, cle)

/** Aucun dry-run serveur : même composition locale que l'industriel. */
export const composer = (etat, deps) => composerLocalement(etat, deps, cle)

/**
 * ÉTUDE PERSISTÉE — MÊME porte unique que l'industriel (donc le même
 * `absent('aucune consommation saisie')` tant que l'entrée n'est pas signée
 * `saisie`), avec le day-share de la catégorie commerciale.
 */
export function etudePersistee(etat = {}) {
  return etudeAutoconsommation(etat, {
    dayUsagePct: commercialDayShare(etat.categorieCommerciale),
  })
}

export default {
  cle, defautScenario, champsRequis, dimensionner, composer, etudePersistee,
}
