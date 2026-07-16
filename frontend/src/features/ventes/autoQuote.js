/* Création du « devis automatique » — logique PARTAGÉE entre le générateur
   complet (DevisGenerator) et le panneau devis inline de la fiche lead
   (LeadDevisPanel). Source unique : on ne duplique JAMAIS le calcul de prix.

   Sensible au marché du lead : résidentiel (historique), agricole (pompage,
   mêmes appels que le flux manuel) ou industriel (dimensionnement factures +
   étude d'autoconsommation). Lit le lead directement (pas d'état React). */
import { createDevis, addLigneDevis } from './store/ventesSlice'
import {
  estimerPanneaux, estimerMois, htFromTtc, ttcFromHt, optionTotalsTTC,
  autoFillLines, computeEtudeIndustrielle, panneauxPourKwc,
  autoFillPompage, pompageSelection, HEURES_POMPAGE_DEFAUT,
  KWH_PRICE, EFFICIENCY, DAY_USAGE_DEFAULTS,
} from './solar'

// QX19 — préférence de structure du lead (acier/aluminium) → structureType
// d'autoFillLines/autoFillPompage. Défaut historique 'acier' quand non renseigné.
const structFromLead = (lead) =>
  (lead && lead.structure_pref === 'aluminium') ? 'aluminium' : 'acier'

// ERR107 — Cohérence d'arrondi écran : une ligne est ENREGISTRÉE en HT 2 déc.
// (htFromTtc), donc le TTC RÉAFFICHÉ d'une ligne est ttcFromHt(htFromTtc(ttc)),
// qui peut différer du TTC brut saisi d'1 MAD. Pour que le total d'étude affiché
// à l'écran corresponde exactement à la somme des lignes telles que l'écran les
// recompose, on aligne d'abord chaque prix_unit_ttc sur ce même aller-retour.
// (Écran uniquement — le PDF backend recalcule de façon autoritaire.)
const screenTtc = (r) => ttcFromHt(htFromTtc(r.prix_unit_ttc, r.taux_tva ?? 20), r.taux_tva ?? 20)
const roundTripRowsTtc = (rows) => rows.map((r) => ({ ...r, prix_unit_ttc: screenTtc(r) }))

// QX52 — parité 4 modes : `commercial` route désormais vers son PROPRE mode
// (plus le repli historique vers `industriel`). Aucun mode ne tombe dans un
// libellé/comportement d'un autre.
export const LEAD_TYPE_TO_MODE = {
  residentiel: 'residentiel', commercial: 'commercial',
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
 * @param {number}   pumpHours    Heures de pompage/jour (réglage entreprise
 *                                agricole_pump_hours) ; défaut historique sinon
 * @param {function} onEtude      Rappel facultatif recevant les chiffres clés de
 *                                l'étude industrielle (autoconso/éco/payback)
 *                                AVANT enregistrement — pour les afficher
 */
export async function createAutoQuote({ lead, produits, discountStr, dispatch,
                                        quoteLogic, pumpHours, onEtude }) {
  // Logique de devis éditable (Paramètres → Avancé) ; sans valeur = défauts.
  const kwhPrice = (Number(quoteLogic?.kwhPrice) > 0) ? Number(quoteLogic.kwhPrice) : KWH_PRICE
  const efficiency = (Number(quoteLogic?.efficiency) > 0) ? Number(quoteLogic.efficiency) : EFFICIENCY
  const perTranche = (Number(quoteLogic?.panneauxParTranche) > 0) ? Number(quoteLogic.panneauxParTranche) : 8
  // Heures de pompage effectives : réglage entreprise (agricole_pump_hours) si
  // fourni, sinon le défaut marché historique — comme le générateur manuel.
  const heuresPompage = (Number(pumpHours) > 0) ? Number(pumpHours) : HEURES_POMPAGE_DEFAUT
  const mode = LEAD_TYPE_TO_MODE[lead.type_installation] || 'residentiel'
  const extra = {}
  let rows
  if (mode === 'agricole') {
    const opts = {
      cv: lead.pompe_cv != null ? String(lead.pompe_cv) : '',
      alim: 'tri', typePompe: 'immergee', distance: '20',
      // QX19 — respecte la préférence de structure du lead (défaut acier).
      structureType: structFromLead(lead),
      hmt: lead.pompe_hmt_m != null ? String(lead.pompe_hmt_m) : '',
      debit: lead.pompe_debit_m3h != null ? String(lead.pompe_debit_m3h) : '',
      heures: String(heuresPompage),
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
    // QX19 — priorité à la taille souhaitée par le lead (kWc) quand elle est
    // renseignée ; sinon dérivation historique depuis la facture d'hiver.
    const tailleKwc = parseFloat(lead.taille_souhaitee_kwc) || 0
    const panels = tailleKwc > 0
      ? panneauxPourKwc(tailleKwc, 710)
      : (estimerPanneaux(hiver, perTranche) || 8)
    const kwpAuto = panels * 710 / 1000
    rows = autoFillLines(produits, {
      kwp: kwpAuto, panelW: 710, nbPanneaux: panels,
      // QX19 — respecte la préférence de structure du lead (défaut acier).
      structureType: structFromLead(lead),
    })
    // QX19 — scénario batterie SEMÉ depuis batterie_souhaitee du lead : porté
    // dans etude_params pour que le PDF (builder QF6) restreigne le document au
    // choix du client (« sans »/« avec »/« les deux »). Défaut « les deux »
    // (comportement historique) quand non renseigné.
    const _bat = lead.batterie_souhaitee
    extra.etude_params = {
      ...(extra.etude_params || {}),
      scenario: _bat === 'sans' ? 'Sans batterie'
        : _bat === 'avec' ? 'Avec batterie'
          : 'Les deux (Sans + Avec)',
    }
    // QX52 — industriel ET commercial partagent l'étude d'autoconsommation ; le
    // day-share diffère (industriel 80 % vs commercial 80 % archétype par défaut)
    // et chaque mode garde SON `mode_installation` (jamais un repli croisé).
    if (mode === 'industriel' || mode === 'commercial') {
      const ete = (lead.ete_differente && lead.facture_ete)
        ? parseFloat(lead.facture_ete) : hiver
      const moisAuto = hiver > 0 ? estimerMois(hiver, ete) : []
      const avgAuto = moisAuto
        .reduce((s, v) => s + (parseFloat(v) || 0), 0) / 12
      const conso = (parseFloat(lead.conso_mensuelle_kwh) || 0)
        || (avgAuto > 0 ? Math.round(avgAuto / kwhPrice) : 0)
      extra.mode_installation = mode
      const _dayUsage = mode === 'commercial'
        ? DAY_USAGE_DEFAULTS['Commerciale'] : DAY_USAGE_DEFAULTS['Industrielle']
      const _scenarioPrev = extra.etude_params?.scenario
      const _etudeInd = (kwpAuto > 0 && conso > 0)
        ? computeEtudeIndustrielle({
            kwp: kwpAuto, consoMensuelleKwh: conso,
            dayUsagePct: _dayUsage,
            totalTtc: optionTotalsTTC(roundTripRowsTtc(rows), discountStr || '0').totalSans,
            kwhPrice, efficiency,
          })
        : null
      // QX19 — préserve le scénario batterie semé du lead (défaut industriel :
      // sans batterie, réseau) même quand l'étude industrielle est calculée.
      extra.etude_params = {
        ...(_etudeInd || {}),
        scenario: lead.batterie_souhaitee ? _scenarioPrev : 'Sans batterie',
      }
      // Surface les chiffres clés (taux d'autoconsommation, économies, payback)
      // AVANT enregistrement, pour que l'appelant puisse les afficher.
      if (extra.etude_params && typeof onEtude === 'function') {
        onEtude({
          taux_autoconso: extra.etude_params.taux_autoconso,
          economies_annuelles: extra.etude_params.economies_annuelles,
          payback: extra.etude_params.payback,
        })
      }
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
