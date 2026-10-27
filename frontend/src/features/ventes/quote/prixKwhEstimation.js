// RGEN10 — prix du kWh du modèle « estimation » (devis sans consommation),
// miroir de la cascade que le PDF applique : `pricing.py::calculate_savings_roi`
// appelé par `etude_chiffrage.py` (build_quote_data) — le serveur fait foi
// (décision RHOR 27/10, règle #4). Fonction pure (aucun import) : la grille
// nationale et la facture mensuelle sont INJECTÉES par `solar.js::computeROI`.
//
// Cascade serveur (premier qui répond) :
//   1. table tarifaire = barème SOCIÉTÉ (`_reglages_tarifaires`, posé quel que
//      soit le distributeur) sinon grille nationale si un distributeur est
//      NOMMÉ (`_resolve_tranches`, Q7/CAD167) ; table présente ⇒ prix pondéré
//      à conso/12 (`_weighted_kwh_price`), ou SANS conso le prix de la 1re
//      tranche (QJR156, étiqueté estimation) ;
//   2. aucune table ⇒ `fallback_tarif_kwh` = `tariff_for(company).onee_tarif_kwh`
//      (défaut 1,75 sans profil — `kwhPrice` absent ⇒ `defaut`) ;
//   3. réglage société nul ⇒ `_FALLBACK_KWH_PRICE` 1,20 (`repli`).
// `tarif_kwh_override` (AMOT47) n'est posé par aucun devis : hors cascade.
//
// Distributeur REÇU par le serveur : sans consommation, `etatDevis.entreesDeEtat`
// n'enregistre que les distributeurs ≠ « onee » (le défaut du sélecteur) — le
// « onee » de l'écran sans conso n'existe donc pas côté PDF (jumeau de cette règle).
function prixPondere(table, consoAnnuelleKwh, factureMensuelle) {
  const kwhMois = (parseFloat(consoAnnuelleKwh) || 0) / 12
  if (!(kwhMois > 0)) return table[0][1]
  return factureMensuelle(kwhMois, table) / kwhMois
}

export function prixKwhEstimation({
  utility, tranches, consoAnnuelleKwh, kwhPrice,
}, { grilleNationale, factureMensuelle, defaut, repli }) {
  const conso = parseFloat(consoAnnuelleKwh) || 0
  const nom = String(utility ?? '').trim().toLowerCase()
  const nomRecu = conso > 0 ? nom : (nom === 'onee' ? '' : nom)
  const table = (tranches && tranches.length) ? tranches : (nomRecu ? grilleNationale : null)
  if (table) return prixPondere(table, conso, factureMensuelle)
  if (kwhPrice == null || kwhPrice === '') return defaut
  const societe = Number(kwhPrice)
  return Number.isFinite(societe) && societe > 0 ? societe : repli
}
