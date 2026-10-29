// SPL198 — Totaux canoniques de l'écran devis (options Sans/Avec, remise par
// panier, accessoires Huawei), aperçu multi-propriétés, prix/kWc et marge.
// DÉPLACEMENT PUR depuis features/ventes/solar.js (aucune logique changée).
// computeBuyCost lit prix_achat : réservé au générateur, jamais dans un PDF.

import { formatNumber } from '../../../lib/format.js'
// QJR567 — la population des totaux (ligne PRODUIT non optionnelle) vient de
// `ligneCompteDansTotaux` (remise.js, même règle que le noyau des totaux ;
// remise.js n'importe rien : aucun cycle).
import {
  ligneCompteDansTotaux, PAS_ARRONDI_DEVIS, totauxCanoniques, repartirRemiseParLigne,
} from '../remise.js'
import { SCENARIOS_VALIDES } from '../quote/scenarios.js'
import {
  TVA_STANDARD_DEFAUT, _norm, appartientAuPanierAvec, appartientAuPanierSans, htFromTtc,
  isAnyInverter, isBattery, isHybridInverter, isOffgridInverter, isReseauInverter, parseKw,
  tauxTvaOf, texteClassement,
} from '../solar.js'

// ── QJR402 — QF9 (Smart Meter / clé Wi-Fi Huawei-only) MIROIR DU NOYAU ──────
// Miroir exact de `apps/ventes/utils/options.py` `_panier_sert_huawei` /
// `retirer_accessoires_huawei` (QJR200/QF9), déclarée backend-only jusqu'ici :
// un panier dont l'onduleur n'est PAS de marque Huawei perd ses accessoires
// propres à Huawei (Smart Meter, clé Wi-Fi/dongle) — sans quoi le total
// affiché au vendeur compte un accessoire que ni le noyau monnaie ni le PDF
// ne facturent sur cette option (divergence atteinte via `autoFillLines`,
// dont la garde Huawei :2043-2047 raisonne sur le devis ENTIER, jamais
// panier par panier).
export const isSmartMeter = (d) => _norm(d).includes('smart meter')
// Miroir exact de `_WIFI_RE` (options.py) : « Wi-Fi » s'écrit de plusieurs
// façons, un simple `includes('wifi')` rate « Wi-Fi » avec trait d'union.
const _WIFI_RE = /wi[\s\-_.]*fi/
export const isWifiDongle = (d) => {
  const n = _norm(d)
  return n.includes('dongle') || _WIFI_RE.test(n)
}
const _estAccessoireHuawei = (d) => isSmartMeter(d) || isWifiDongle(d)

// True quand le panier `rows` est servi par un onduleur Huawei — miroir exact
// de `_panier_sert_huawei` : sans onduleur identifiable → False (on n'affiche
// pas ces accessoires par défaut) ; le moindre onduleur non-Huawei dans le
// panier suffit à les retirer (conservateur).
function _panierSertHuawei(rows, produits) {
  const onduleurs = rows.filter(l => isAnyInverter(texteClassement(l, produits)))
  if (onduleurs.length === 0) return false
  let huaweiVu = false
  for (const l of onduleurs) {
    if (_norm(texteClassement(l, produits)).includes('huawei')) {
      huaweiVu = true
    } else {
      return false
    }
  }
  return huaweiVu
}

// `rows` privé de ses accessoires Huawei orphelins — miroir exact de
// `retirer_accessoires_huawei`.
function _retirerAccessoiresHuawei(rows, produits) {
  if (_panierSertHuawei(rows, produits)) return rows
  return rows.filter(l => !_estAccessoireHuawei(texteClassement(l, produits)))
}

// ── ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER — miroir EXACT de
// `apps/ventes/selectors.py` `_canonical_totaux` (la chaîne que le PDF, le BC
// et la facture appliquent) sur les lignes TELLES QUE L'ÉCRAN LES PERSISTE :
// prix unitaire HT = `htFromTtc(prix_unit_ttc, taux)` (2 décimales), quantité
// au centième (DecimalField 2 déc.), taux de la ligne (repli 20). Arithmétique
// ENTIÈRE (BigInt) et arrondi ROUND_HALF_UP, comme `Decimal` côté serveur —
// jamais un flottant arrondi à la fin. Rend le TTC en MAD (2 décimales).
// QJR529 — la remise PAR LIGNE stockée (`remise`, %) entre comme côté serveur
// (`LigneDevis.total_ht` = q × pu × (1 − remise/100), exact, avant la chaîne
// d'arrondis) : les montants internes sont en 1e-8 MAD (×10 000 pour porter
// le facteur (10 000 − remise×100) sans perte). Remise absente/nulle ⇒
// résultat strictement inchangé (mise à l'échelle entière exacte).
// QJR642 — la chaîne de totaux vit dans `remise.totauxCanoniques` (UN noyau
// pour le générateur et la répartition de remise) : ici ne reste que la
// conversion TTC saisi → HT persisté, en nanos exacts (1e-8 MAD × 10).
// ARRONDI-100 — `arrondiPas` (MAD) : le TTC ramené au palier inférieur,
// exactement comme le noyau (`_absorber_arrondi`) ; absent = TTC exact.
export function totauxCanoniquesTtc(lines, discountPct = 0, arrondiPas = 0) {
  const lignes = (lines || []).map((l) => {
    const qH = BigInt(Math.round((parseFloat(l?.quantite) || 0) * 100))
    const taux = parseFloat(l?.taux_tva ?? TVA_STANDARD_DEFAUT)
    const tauxLigne = Number.isFinite(taux) ? taux : TVA_STANDARD_DEFAUT
    const htC = BigInt(Math.round(parseFloat(htFromTtc(l?.prix_unit_ttc, l?.taux_tva ?? TVA_STANDARD_DEFAUT)) * 100))
    const remH = BigInt(Math.round((parseFloat(l?.remise) || 0) * 100)) // % × 100
    return {
      // quantité ×100 · prix HT en centimes · (1 − remise) ×10 000 = 1e-8 MAD
      htNano: qH * htC * (10000n - remH) * 10n,
      taux: tauxLigne,
      typeLigne: l?.typeLigne ?? l?.type_ligne,
      optionnelle: l?.optionnelle,
    }
  })
  return totauxCanoniques(lignes, discountPct, { arrondiPas }).ttc
}

// ── Totaux par option, TTC (port exact de updateTotals de app.js) ────────────
// Option 1 SANS batterie : exclut Batterie + Onduleur hybride.
// Option 2 AVEC batterie : exclut Onduleur réseau.
// ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — les trois libellés qui DÉCLARENT
// une alternative commerciale (le noyau sert alors UNE option, panier filtré
// ET règle QF9 appliquée) : la liste vit dans `quote/scenarios.js`.
export const SCENARIOS_ALTERNATIVE = SCENARIOS_VALIDES

// Miroir de `familles_des_lignes` + `familles_servables` + la condition
// « alternative déclarée » de `deux_options_depuis_paniers` (utils/options.py) :
// le scénario déclaré ne suffit pas, l'ÉQUIPEMENT doit servir les deux
// paniers (onduleur réseau d'un côté ; hybride avec batterie ou réseau, ou
// autonome avec batterie, de l'autre). Seules les lignes produit non
// optionnelles de quantité > 0 comptent, comme au noyau.
export function alternativeDeclareeServable(lines, scenario, produits) {
  if (!SCENARIOS_ALTERNATIVE.includes(scenario)) return false
  const d = (lines || [])
    .filter(l => (parseFloat(l?.quantite) || 0) > 0 && !l?.optionnelle
      && l?.typeLigne !== 'section' && l?.typeLigne !== 'note')
    .map(l => texteClassement(l, produits))
  const hasReseau = d.some(isReseauInverter)
  const hasHybride = d.some(isHybridInverter)
  const hasOffgrid = d.some(isOffgridInverter)
  const hasBatterie = d.some(isBattery)
  const avecOk = (hasHybride && (hasBatterie || hasReseau)) || (hasOffgrid && hasBatterie)
  return hasReseau && avecOk
}

// `options.scenario` (facultatif) — le scénario DÉCLARÉ par l'écran. Absent :
// comportement historique inchangé (QF9 réservée aux lignes variantées).
export function optionTotalsTTC(lines, discountPct, { scenario, produits } = {}) {
  // QJR567 — MÊME population que le noyau (`ligne_compte_dans_totaux`) : une
  // ligne optionnelle (add-on non activé) et les sections / notes ne
  // comptent JAMAIS — sans ce filtre le rail, le prix/kWc, la marge et
  // l'étude C&I persistée comptaient un add-on que le document exclut.
  lines = (lines || []).filter(ligneCompteDansTotaux)
  // F14 (26/08) — une ligne DÉCLARÉE ('sans'/'avec') tranche SEULE, plus de
  // second filtre mot-clé sur elle (voir `appartientAuPanierSans/Avec` :
  // miroir exact de builder.py `_repartir_options` et de
  // `apps/ventes/utils/options.py`). Une ligne SANS `variante` retombe sur
  // les mots-clés, mot pour mot comme avant.
  let linesSans = lines.filter(l => appartientAuPanierSans(l, produits))
  let linesAvec = lines.filter(l => appartientAuPanierAvec(l, produits))
  // QJR402/QJR300 — QF9 ne s'applique QUE sur un VRAI devis à deux options
  // DÉCLARÉES (miroir de `deux_options`/`alternative_declaree` au noyau) :
  // la seule trace, côté lignes, d'une alternative déclarée est `variante`
  // ('sans'/'avec'), posée uniquement par `fusionnerVariantes` pour un
  // scénario « Les deux ». Un devis SANS aucune ligne variantée (mono-
  // composition, y compris l'artefact « deux onduleurs non déclarés ») garde
  // TOUTES ses lignes, comportement historique strictement inchangé.
  // ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — …ET sur un devis dont le
  // SCÉNARIO déclare l'alternative (miroir de `deux_options_declarees` :
  // `alternative_declaree or variantes`). Sans cette branche, un devis « Les
  // deux » à lignes non variantées affichait l'option AVEC avec le Smart
  // Meter + la clé Wi-Fi Huawei que le noyau et le PDF retirent (3 000 MAD
  // d'écart mesurés entre le formulaire et le devis persisté).
  if (lines.some(l => l?.variante === 'sans' || l?.variante === 'avec')
      || alternativeDeclareeServable(lines, scenario, produits)) {
    linesSans = _retirerAccessoiresHuawei(linesSans, produits)
    linesAvec = _retirerAccessoiresHuawei(linesAvec, produits)
  }
  // ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER — LA CHAÎNE CANONIQUE DU NOYAU, plus
  // une somme de TTC arrondis ligne à ligne remisée ensuite. Le chiffre facturé
  // (PDF/BC/facture) est `selectors._canonical_totaux` sur les lignes
  // PERSISTÉES (HT = `htFromTtc`, exactement ce que l'écran envoie) : HT brut →
  // remise globale → TVA par taux → TTC, au centime. L'écran le reproduit à
  // l'identique (`totauxCanoniquesTtc` ci-dessous) : avant, 36/200 devis du
  // corpus figé divergeaient d'un centime. Le « brut » est la même chaîne
  // sans remise (la valeur que le noyau facture à 0 %).
  // ARRONDI-100 — chaque total (avant ET après remise) est ramené au palier de
  // 100 MAD inférieur, comme le devis enregistré et son PDF : sans remise, le
  // « brut » et le « net » restent donc égaux (aucun prix barré fantôme).
  const pct = parseFloat(discountPct) || 0
  const pas = PAS_ARRONDI_DEVIS
  const totalSansBrut = totauxCanoniquesTtc(linesSans, 0, pas)
  const totalAvecBrut = totauxCanoniquesTtc(linesAvec, 0, pas)
  const totalSans = totauxCanoniquesTtc(linesSans, pct, pas)
  const totalAvec = totauxCanoniquesTtc(linesAvec, pct, pas)
  return { totalSansBrut, totalAvecBrut, totalSans, totalAvec }
}

// ATOT25 — LA REMISE « PAR LIGNE » DE L'ÉCRAN = CELLE DU PDF, PAR PANIER.
// Miroir de `builder._annoter_remise` : chaque option (panier Sans / Avec,
// même population que `optionTotalsTTC`) répartit SA remise sur les HT
// PERSISTÉS de ses lignes (`htFromTtc` au centime × quantité × remise de
// ligne), par `repartirRemiseParLigne` (miroir de
// `argent.repartir_remise_par_ligne`, plus fort reste), puis chaque part HT
// passe au TTC à son propre taux, au centime. L'« Arrondi commercial » est ce
// qui sépare la somme des lignes affichées du total (palier ARRONDI-100) :
// Σ lignes + arrondi = total affiché, toujours.
//
// Rend `{ parLigne, sans: {total, sommeLignes, arrondi}, avec: {...} }` ;
// `parLigne` est ALIGNÉ sur `lines` (montant TTC remisé, ou `null` pour une
// ligne qui ne compte pas) — une ligne des deux paniers prend la valeur du
// panier de l'option effective (`option`).
export function lignesRemiseesParPanier(lines, discountPct, { scenario, option = 'sans', produits } = {}) {
  const tous = lines || []
  const comptees = tous.filter(ligneCompteDansTotaux)
  let lignesSans = comptees.filter(l => appartientAuPanierSans(l, produits))
  let lignesAvec = comptees.filter(l => appartientAuPanierAvec(l, produits))
  if (comptees.some(l => l?.variante === 'sans' || l?.variante === 'avec')
      || alternativeDeclareeServable(comptees, scenario, produits)) {
    lignesSans = _retirerAccessoiresHuawei(lignesSans, produits)
    lignesAvec = _retirerAccessoiresHuawei(lignesAvec, produits)
  }
  const pct = parseFloat(discountPct) || 0
  const centimes = (v) => BigInt(Math.round((Number(v) || 0) * 100))
  const panier = (rows) => {
    const valeurs = new Map()
    if (pct > 0) {
      const parts = repartirRemiseParLigne(rows.map((l) => {
        const qH = BigInt(Math.round((parseFloat(l?.quantite) || 0) * 100))
        const htC = BigInt(Math.round(parseFloat(htFromTtc(l?.prix_unit_ttc, l?.taux_tva ?? TVA_STANDARD_DEFAUT)) * 100))
        const remH = BigInt(Math.round((parseFloat(l?.remise) || 0) * 100))
        // q ×100 · HT centimes · (1 − remise) ×10 000 = 1e-8 MAD → MAD
        return { totalHt: Number(qH * htC * (10000n - remH)) / 1e8 }
      }), pct)
      rows.forEach((l, k) => {
        const taux = parseFloat(l?.taux_tva ?? TVA_STANDARD_DEFAUT)
        const t = Number.isFinite(taux) ? taux : TVA_STANDARD_DEFAUT
        // TTC = q(part HT × (1 + taux)), moitié vers le haut, en centimes entiers.
        const partC = centimes(parts[k])
        const num = partC * BigInt(Math.round((100 + t) * 100))
        const ttcC = num >= 0n ? (num + 5000n) / 10000n : -((-num + 5000n) / 10000n)
        valeurs.set(l, Number(ttcC) / 100)
      })
    } else {
      rows.forEach((l) => {
        valeurs.set(l, Math.round((parseFloat(l?.quantite) || 0) * (parseFloat(l?.prix_unit_ttc) || 0) * 100) / 100)
      })
    }
    const total = totauxCanoniquesTtc(rows, pct, PAS_ARRONDI_DEVIS)
    const sommeC = [...valeurs.values()].reduce((acc, v) => acc + centimes(v), 0n)
    return { valeurs, total, sommeLignes: Number(sommeC) / 100, arrondi: Number(centimes(total) - sommeC) / 100 }
  }
  const sans = panier(lignesSans)
  const avec = panier(lignesAvec)
  const [premier, second] = option === 'avec' ? [avec, sans] : [sans, avec]
  const parLigne = tous.map((l) => (premier.valeurs.has(l) ? premier.valeurs.get(l)
    : (second.valeurs.has(l) ? second.valeurs.get(l) : null)))
  const resume = ({ total, sommeLignes, arrondi }) => ({ total, sommeLignes, arrondi })
  return { parLigne, sans: resume(sans), avec: resume(avec) }
}

// ── QJ31 — Multi-propriétés : aperçu écran (TTC) miroir du backend QJ29 ──────
// Deux modes, tous deux additifs et mutuellement exclusifs à l'écran (un seul
// devis, jamais scindé) :
//   (A) ×N villas identiques : `nombreProprietes` multiplie le total TTC.
//   (B) villas différentes : les lignes portent `groupeIndex`/`groupeLabel`
//       (0 = commun) → sous-total par villa + total général, comme
//       `multi_villa_totaux` (selectors.py) mais en TTC (écran) plutôt qu'en
//       HT→TVA→TTC (backend, qui reste la source AUTORITAIRE au moment du PDF).
// Retourne null quand aucun des deux modes n'est utilisé (aperçu inchangé).
const _foisN = (ttc, n) => (Math.round((Number(ttc) || 0) * 100) * n) / 100
// ATOT24 — l'aperçu suit la CHAÎNE DU RAIL : (A) l'option EFFECTIVE (celle
// que le rail affiche) et le scénario (même population que `optionTotalsTTC`
// du rail : accessoires Huawei retirés d'un « Les deux ») ; (B) chaque villa =
// totaux canoniques de SES lignes (HT → remise → TVA → TTC, option exclue),
// les lignes sans groupe forment le groupe « Hors groupe », et le total
// général est la chaîne canonique de TOUTES les lignes au palier
// ARRONDI-100 — exactement `multi_villa_totaux` (selectors.py).
export function multiPropertyPreviewTTC(lines, {
  nombreProprietes, discountPct, scenario, option,
} = {}) {
  const n = parseInt(nombreProprietes, 10)
  if (Number.isFinite(n) && n > 1) {
    const { totalSans, totalAvec, totalSansBrut, totalAvecBrut } = optionTotalsTTC(lines, discountPct, { scenario })
    const opt = option === 'avec' || option === 'sans'
      ? option : (scenario === 'Avec batterie' ? 'avec' : 'sans')
    const totalUnitaire = opt === 'avec' ? totalAvec : totalSans
    return {
      mode: 'multiplicateur',
      nombreProprietes: n,
      option: opt,
      totalUnitaire,
      totalMulti: _foisN(totalUnitaire, n),
      totalUnitaireSans: totalSans, totalUnitaireAvec: totalAvec,
      // ERR-QAC-MULTIVILLA-TOTAL-XN — ×N AU CENTIME, comme le backend
      // (`selectors.totaux_multi_proprietes` / `builder._scale_tot`) : ce
      // total est désormais celui facturé. Unitaire en centimes entiers × N
      // (jamais un flottant arrondi au dirham).
      totalMultiSans: _foisN(totalSans, n), totalMultiAvec: _foisN(totalAvec, n),
      totalUnitaireSansBrut: totalSansBrut, totalUnitaireAvecBrut: totalAvecBrut,
    }
  }

  const tous = lines || []
  const grouped = tous.filter(l => l.groupeIndex != null)
  if (!grouped.length) return null

  const pct = parseFloat(discountPct) || 0
  const byIndex = new Map()
  for (const l of grouped) {
    const idx = l.groupeIndex
    if (!byIndex.has(idx)) byIndex.set(idx, { lignes: [], label: '' })
    const bucket = byIndex.get(idx)
    bucket.lignes.push(l)
    if (!bucket.label && (l.groupeLabel || '').trim()) bucket.label = l.groupeLabel.trim()
  }
  const groupes = [...byIndex.keys()].sort((a, b) => a - b).map(idx => {
    const bucket = byIndex.get(idx)
    return {
      index: idx,
      label: bucket.label || (idx === 0 ? 'Équipement commun' : `Villa ${idx}`),
      totalTtc: totauxCanoniquesTtc(bucket.lignes, pct, 0),
    }
  })
  const horsGroupe = tous.filter(l => l.groupeIndex == null && ligneCompteDansTotaux(l))
  if (horsGroupe.length) {
    groupes.push({ index: null, label: 'Hors groupe', totalTtc: totauxCanoniquesTtc(horsGroupe, pct, 0) })
  }
  const grandTotalTtc = totauxCanoniquesTtc(tous, pct, PAS_ARRONDI_DEVIS)
  return { mode: 'villas', groupes, grandTotalTtc }
}

// ── Prix par kWc, prix cible et marge ─────────────────────────────────────────
export function prixParKwc(totalTtc, kwp) {
  if (!(kwp > 0) || !(totalTtc > 0)) return null
  return Math.round(totalTtc / kwp)
}

// Remise (%) impliquée par un prix cible /kWc — appliquée via la remise
// globale existante, jamais en réécrivant les prix des lignes.
export function discountForTarget(cibleKwc, kwp, totalBrutTtc) {
  const implied = (parseFloat(cibleKwc) || 0) * kwp
  if (!(implied > 0) || !(totalBrutTtc > 0)) return null
  const pct = (1 - implied / totalBrutTtc) * 100
  return Math.round(pct * 100) / 100
}

// Coût d'achat TTC des lignes dont le produit a un prix d'achat renseigné,
// ET le nombre de lignes CHIFFRÉES (prix de vente > 0) qui n'en ont pas
// (AGR134) : la marge est alors PARTIELLE (le coût y est sous-estimé).
// `cost` est null si AUCUN prix d'achat n'existe (alors on n'affiche rien).
// Le TTC d'achat suit le taux TVA du produit (10 % panneaux, 20 % le reste).
export function computeBuyCostDetail(lines, produits) {
  const byId = new Map(produits.map(p => [String(p.id), p]))
  let cost = 0
  let any = false
  let sansAchat = 0
  // QJR567 — même population que les totaux : ni optionnelle, ni section/note.
  for (const l of (lines || []).filter(ligneCompteDansTotaux)) {
    const p = byId.get(String(l.produit))
    const achat = p ? (parseFloat(p.prix_achat) || 0) : 0
    if (achat > 0) {
      any = true
      cost += (parseFloat(l.quantite) || 0) * achat * (1 + tauxTvaOf(p) / 100)
    } else if ((parseFloat(l.quantite) || 0) > 0 && (parseFloat(l.prix_unit_ttc) || 0) > 0) {
      sansAchat += 1
    }
  }
  return { cost: any ? Math.round(cost) : null, sansAchat }
}

// Appelants inchangés : le seul coût (ou null).
export function computeBuyCost(lines, produits) {
  return computeBuyCostDetail(lines, produits).cost
}

// ── Disponibilité de l'option « avec batterie » ───────────────────────────────
// Règle dure (alignée moteur PDF) : une option ne se rend jamais sans onduleur.
// Composer des hybrides en parallèle est raisonnable jusqu'à MAX_HYBRID_UNITS.
export const MAX_HYBRID_UNITS = 8

export function avecBatterieAvailability(lines, produits, kwp) {
  // AGNR36 — chaque ligne classée sur désignation + nom du produit lié.
  const t = (l) => texteClassement(l, produits)
  const hasHyb = lines.some(l =>
    isHybridInverter(t(l)) && parseFloat(l.quantite) > 0)
  const hasBat = lines.some(l =>
    isBattery(t(l)) && parseFloat(l.quantite) > 0)
  const hasRes = lines.some(l =>
    isReseauInverter(t(l)) && parseFloat(l.quantite) > 0)
  if (hasHyb && hasBat) return { available: true, batterieDifferee: false }
  // BAT-DIFF (fondateur, 17/09/2026) — même règle que le noyau
  // (`utils.options.familles_servables`, testée là-bas et ici par
  // `solar.avecBatterieAvailability.test.jsx`) : un hybride FACE à un réseau sert
  // l'option « avec » même sans batterie chiffrée (le client l'ajoutera plus
  // tard). Le document la nomme « Hybride, batterie plus tard » et calcule
  // ses économies sans stockage. Un hybride SEUL reste mono-option (Z1).
  if (hasHyb && hasRes) return { available: true, batterieDifferee: true }
  // Diagnostic : le plus gros hybride du stock suffit-il, même composé ?
  const maxKw = Math.max(0, ...produits
    .filter(p => isHybridInverter(p.nom))
    .map(p => parseKw(p.nom) || 0))
  const unitsNeeded = maxKw > 0 ? Math.ceil((kwp || 0) / maxKw) : Infinity
  let reason
  if (!hasHyb && maxKw > 0 && unitsNeeded > MAX_HYBRID_UNITS) {
    reason = `pour ${formatNumber(Math.round((Number(kwp) || 0) * 100) / 100)} kWc il faudrait ${unitsNeeded} onduleurs hybrides de ${formatNumber(maxKw)} kW `
      + `(au plus ${MAX_HYBRID_UNITS} en parallèle) — réduisez la taille ou ajoutez au catalogue un onduleur hybride plus puissant`
  } else if (!hasHyb) {
    reason = 'aucun onduleur hybride dans les lignes du devis — cliquez « Auto-remplir » ou ajoutez-en un'
  } else {
    reason = 'aucune batterie dans les lignes du devis — ajoutez-en une'
  }
  return { available: false, reason }
}
