// Étape « Panneaux » — les chiffres qui ne se lisent pas sur les contrôles `rp9-*` : chacun a UNE source
// nommée (réponse servie), jamais un nombre supposé.
import { estIncomplet } from '../../../../production/BandeauProvenanceProduction.helpers'
import { formatNumber } from '../../../../../../lib/format'

export const fmtKwc = (kw) => `${formatNumber(kw, { decimals: 2 })} kWc`

/**
 * LA taille tirée des FACTURES du lead, servie par `GET cible-factures/` (`cible_factures`, H3 — hors du design-context,
 * calculée côté serveur par
 * la fonction du garde R2-17 : `services/devis.py::_cible_du_calepinage` → `ventes.selectors.cible_depuis_lead`).
 * Accesseur UNIQUE de l'atelier (étape Panneaux, puce de l'étape Toit) : `{ panneaux, kwc, moduleWc }` ou `null`.
 */
export function cibleFactures(contexte) {
  const c = contexte?.cible_factures
  if (!c || !(Number(c.panneaux) > 0)) return null
  return { panneaux: Number(c.panneaux), kwc: typeof c.kwc === 'number' ? c.kwc : null, moduleWc: c.module_wc ?? null }
}

/**
 * La production PUBLIÉE (GET resultat/) quand elle est fraîche (`simule`, `simulation_perimee === false`) ET complète
 * (un résultat incomplet est traité comme périmé par le devis : `calepinage/selectors_devis.py` ~55-61) : libellé de
 * l'étape Résultats (« Production la première année »), avec la pose simulée. `null` sinon — la puce garde alors
 * l'estimation du navigateur, nommée « estimation ».
 */
/** T4-X2-002 — la simulation de la pose est périmée : la bande le dit (jamais un chiffre simulé remplacé en silence). */
export { simulationARefaire } from '../../../../production/BandeauProvenanceProduction.helpers'

export function productionPubliee(resultat) {
  const total = resultat?.production?.total
  if (resultat?.simule !== true || resultat?.simulation_perimee !== false) return null
  if (typeof total?.p50_kwh !== 'number' || estIncomplet(total) || total.complete !== true) return null
  // Panneaux POSÉS et kWc POSÉ vont ensemble : `total.kwc` ne compte que les raccordés depuis ACAL1602.
  const kwc = resultat?.pose?.kwc ?? total.kwc
  return {
    libelle: 'Production la première année',
    p50: total.p50_kwh,
    panneaux: resultat?.pose?.total_modules ?? null,
    kwc: typeof kwc === 'number' ? fmtKwc(kwc) : null,
  }
}

/**
 * ACAL1914 — la simulation FRAÎCHE mais INCOMPLÈTE (`total.complete === false`, p50 servi : borne haute, des panneaux ne
 * sont pas comptés) : `productionPubliee` la tait, la carte gardait l'estimation seule. Ici sa production servie, à DIRE à
 * côté de l'estimation (jamais à sa place : elle est incomplète). `null` sinon (rien de simulé, périmée, ou complète).
 */
export function simulationIncomplete(resultat) {
  const total = resultat?.production?.total
  if (resultat?.simule !== true || resultat?.simulation_perimee !== false) return null
  if (typeof total?.p50_kwh !== 'number' || !estIncomplet(total)) return null
  return { p50: total.p50_kwh }
}

/**
 * Le module RÉELLEMENT posé sur chaque pan selon le serveur (`entree-electrique` → `materiel.modules_par_pan`,
 * ACAL359 ; à défaut `materiel.module`) — la même source que le schéma. Rend les désignations distinctes avec
 * leur produit, `[]` si rien n'est servi.
 */
export function modulesServis(entree) {
  const materiel = entree?.materiel ?? {}
  const lignes = Array.isArray(materiel.modules_par_pan) && materiel.modules_par_pan.length
    ? materiel.modules_par_pan : (materiel.module ? [materiel.module] : [])
  const vus = new Map()
  for (const l of lignes) {
    const nom = (l?.designation ?? '').trim()
    if (nom && !vus.has(nom)) vus.set(nom, { designation: nom, produitId: l.produit_id ?? null })
  }
  return [...vus.values()]
}
