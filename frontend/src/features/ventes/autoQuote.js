/* Création du « devis automatique » — logique PARTAGÉE entre le générateur
   complet (DevisGenerator) et le panneau devis inline de la fiche lead
   (LeadDevisPanel). Source unique : on ne duplique JAMAIS le calcul de prix.

   Sensible au marché du lead : résidentiel (historique), agricole (pompage,
   mêmes appels que le flux manuel) ou industriel (dimensionnement factures +
   étude d'autoconsommation). Lit le lead directement (pas d'état React). */
import { createDevis, addLigneDevis } from './store/ventesSlice'
import {
  estimerPanneaux, estimerMois, htFromTtc, optionTotalsTTC,
  autoFillLines, computeEtudeIndustrielle,
  autoFillPompage, pompageSelection, HEURES_POMPAGE_DEFAUT,
  KWH_PRICE, DAY_USAGE_DEFAULTS,
} from './solar'

export const LEAD_TYPE_TO_MODE = {
  residentiel: 'residentiel', commercial: 'industriel',
  industriel: 'industriel', agricole: 'agricole',
}

// Paramètres d'étude pompage stockés avec le devis : chiffres canoniques
// calculés UNE fois, le PDF les rend tels quels. Partagé entre la création
// manuelle (DevisGenerator.handleSubmit) et le devis auto — mêmes expressions.
export const buildEtudePompage = (sel, { typePompe, alim, hmt, debit, heures,
                                         profondeur, distance }) => ({
  pompe_cv: String(sel.cv),
  pompe_kw: sel.kw,
  pompe_nom: sel.pump?.nom || null,
  type_pompe: typePompe,
  alim,
  hmt_m: hmt || null,
  debit_souhaite_m3h: debit || null,
  debit_hmt_m3h: sel.debitHmt,
  heures_pompage: sel.m3Jour != null ? (parseFloat(heures) || null) : null,
  m3_jour: sel.m3Jour,
  profondeur_m: profondeur || null,
  distance_m: distance || null,
  champ_kwc: sel.dims.champKwc,
})

/**
 * Crée un devis auto-dimensionné depuis un lead. Retourne l'id du devis créé.
 * Lève { detail } si le lead n'a pas les données requises (mêmes règles que la
 * garde serveur POST /devis-auto/).
 *
 * @param {object}   lead         Lead complet (facture_hiver, pompe_*, etc.)
 * @param {object[]} produits     Catalogue stock
 * @param {string}   discountStr  Remise globale en %
 * @param {function} dispatch     Redux dispatch
 */
export async function createAutoQuote({ lead, produits, discountStr, dispatch }) {
  const mode = LEAD_TYPE_TO_MODE[lead.type_installation] || 'residentiel'
  const extra = {}
  let rows
  if (mode === 'agricole') {
    const opts = {
      cv: lead.pompe_cv != null ? String(lead.pompe_cv) : '',
      alim: 'tri', typePompe: 'immergee', distance: '20',
      structureType: 'acier',
      hmt: lead.pompe_hmt_m != null ? String(lead.pompe_hmt_m) : '',
      debit: lead.pompe_debit_m3h != null ? String(lead.pompe_debit_m3h) : '',
      heures: String(HEURES_POMPAGE_DEFAUT),
    }
    rows = autoFillPompage(produits, opts)
    if (!rows.some(r => r.produit && parseFloat(r.quantite) > 0)) {
      throw {
        detail: 'Devis auto impossible : renseignez sur le lead la puissance '
          + 'pompe (CV) ou la HMT et le débit souhaité, puis réessayez.',
      }
    }
    extra.mode_installation = 'agricole'
    extra.etude_params = buildEtudePompage(
      pompageSelection(produits, opts), { ...opts, profondeur: '' })
  } else {
    const hiver = parseFloat(lead.facture_hiver) || 0
    const panels = estimerPanneaux(hiver) || 8
    const kwpAuto = panels * 710 / 1000
    rows = autoFillLines(produits, {
      kwp: kwpAuto, panelW: 710, structureType: 'acier',
    })
    if (mode === 'industriel') {
      const ete = (lead.ete_differente && lead.facture_ete)
        ? parseFloat(lead.facture_ete) : hiver
      const moisAuto = hiver > 0 ? estimerMois(hiver, ete) : []
      const avgAuto = moisAuto
        .reduce((s, v) => s + (parseFloat(v) || 0), 0) / 12
      const conso = (parseFloat(lead.conso_mensuelle_kwh) || 0)
        || (avgAuto > 0 ? Math.round(avgAuto / KWH_PRICE) : 0)
      extra.mode_installation = 'industriel'
      extra.etude_params = (kwpAuto > 0 && conso > 0)
        ? computeEtudeIndustrielle({
            kwp: kwpAuto, consoMensuelleKwh: conso,
            dayUsagePct: DAY_USAGE_DEFAULTS['Industrielle'],
            totalTtc: optionTotalsTTC(rows, discountStr || '0').totalSans,
          })
        : null
    }
  }
  const devis = await dispatch(createDevis({
    lead: lead.id,
    statut: 'brouillon',
    taux_tva: '20.00',
    remise_globale: discountStr || '0',
    note: null,
    ...extra,
  })).unwrap()
  await Promise.all(rows
    .filter(r => r.produit && parseFloat(r.quantite) > 0)
    .map(r => dispatch(addLigneDevis({
      devis: devis.id,
      produit: parseInt(r.produit),
      designation: r.designation,
      quantite: String(r.quantite),
      prix_unitaire: htFromTtc(r.prix_unit_ttc, r.taux_tva ?? 20),
      remise: '0',
      taux_tva: String(r.taux_tva ?? 20),
    })).unwrap()))
  return devis.id
}
