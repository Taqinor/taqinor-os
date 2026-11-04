// Logique pure du dialogue « Signé » (SigneDialog.jsx), importable par son test.
import { PAS_ARRONDI_DEVIS } from '../../../features/ventes/remise.js'

// Une désignation de ligne désigne-t-elle une batterie ? (même mot-clé que le
// moteur PDF / solar.js — accents neutralisés.)
const isBatteryLine = (d) =>
  (d || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .includes('batterie')

// TTC d'une ligne : qté × P.U. HT × (1 − remise ligne) × (1 + TVA), au taux de
// la ligne s'il est défini, sinon le taux du devis.
function ligneTtc(l, devisTva) {
  const qte = parseFloat(l.quantite) || 0
  const pu = parseFloat(l.prix_unitaire) || 0
  const rem = parseFloat(l.remise) || 0
  const tva = (l.taux_tva != null && l.taux_tva !== '')
    ? (parseFloat(l.taux_tva) || 0)
    : (parseFloat(devisTva) || 0)
  return qte * pu * (1 - rem / 100) * (1 + tva / 100)
}

// ARRONDI-100 — tout total de devis finit par deux zéros (palier inférieur).
// ADVS3 (D-ADVS-4) — à moins d'1 MAD sous une centaine, le TTC y remonte, comme le
// noyau (`montee` faux : devis au niveau de règles < 11, il garde le total reçu).
const auPalier = (ttc, montee) => {
  if (ttc < PAS_ARRONDI_DEVIS) return ttc
  const inferieur = Math.floor(ttc / PAS_ARRONDI_DEVIS) * PAS_ARRONDI_DEVIS
  return montee && inferieur + PAS_ARRONDI_DEVIS - ttc < 1 ? inferieur + PAS_ARRONDI_DEVIS : inferieur
}

// Détail par option d'un devis à deux options : kWc estimé (panneaux × 0,71) et
// total TTC de chacune (remise globale appliquée). « Sans batterie » = lignes
// hors batterie, « Avec batterie » = toutes les lignes. Indicatif, calculé à
// l'écran pour aider le choix — le PDF reste la source canonique : quand le
// serveur sert `comparaison_options` (mêmes totaux que le PDF), ils priment.
export function optionsDetail(devis) {
  const lignes = devis?.lignes ?? []
  if (!lignes.length) return null
  const tva = devis?.taux_tva
  const remGlobale = parseFloat(devis?.remise_globale) || 0
  const factor = 1 - remGlobale / 100
  const canon = devis?.comparaison_options
  const montee = (devis?.regles_calcul ?? 0) >= 11
  const ttcAvec = canon?.avec?.ttc != null ? parseFloat(canon.avec.ttc)
    : auPalier(lignes.reduce((s, l) => s + ligneTtc(l, tva), 0) * factor, montee)
  const ttcSans = canon?.sans?.ttc != null ? parseFloat(canon.sans.ttc)
    : auPalier(lignes
      .filter((l) => !isBatteryLine(l.designation))
      .reduce((s, l) => s + ligneTtc(l, tva), 0) * factor, montee)
  const nbPanneaux = lignes
    .filter((l) => (l.designation || '').toLowerCase().includes('panneau'))
    .reduce((s, l) => s + (parseFloat(l.quantite) || 0), 0)
  const kwc = nbPanneaux > 0 ? Math.round(nbPanneaux * 0.71 * 100) / 100 : null
  return {
    sans_batterie: { ttc: ttcSans, kwc },
    avec_batterie: { ttc: ttcAvec, kwc },
  }
}
