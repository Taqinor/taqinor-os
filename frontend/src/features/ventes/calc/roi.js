// SPL199 — Économies, retour sur investissement et cashflow 25 ans de l'écran
// devis (computeROI, paybackMoteurHoraire, computeCashflowPayback).
// DÉPLACEMENT PUR depuis features/ventes/solar.js (aucune logique changée).

import { economieAvecNette } from '../quote/economieAvecNette.js'
import { prixKwhEstimation } from '../quote/prixKwhEstimation.js'
import { ONEE_TRANCHES, monthlyBillFromKwh, FALLBACK_KWH_PRICE, twoBillsSavings } from './tarifs.js'
import {
  CHART_MONTHS, EFFICIENCY, GHI, KWH_PRICE, PRODUCTIBLE_NET_FACTOR, appartientAuPanierAvec,
  appartientAuPanierSans, inverterCostFromLines,
} from '../solar.js'

// Taux d'autoconsommation par option — miroir pricing.py AUTOCONSO_SANS/AVEC.
// Utilisés UNIQUEMENT par le modèle « deux factures » (QF5) ; l'estimation
// historique ci-dessous continue d'utiliser dayUsagePct (comportement inchangé).
export const AUTOCONSO_SANS = 0.60
// ORDRE FONDATEUR (18/08) — le forfait « 85 % avec batterie » n'est PLUS le
// modèle : une batterie ne relève pas un taux, elle décale une quantité
// d'énergie RÉELLE égale à sa capacité, une fois par jour. AUTOCONSO_AVEC ne
// survit que comme REPLI documenté : devis explicitement « avec batterie »
// dont la capacité est inconnue (aucune ligne batterie chiffrable) — le seul
// cas où l'on n'a rien de réel à additionner. Dès qu'une capacité existe, le
// taux est DÉRIVÉ (autoconsoAvecRatio ci-dessous), jamais forfaitaire.
export const AUTOCONSO_AVEC = 0.85

// ── Modèle batterie ADDITIF (ordre fondateur 18/08) — MIROIR pricing.py ──────
// autoconsommé_avec = 60 % × production + capacité_kWh × 1 cycle/jour.
// PLAFONDS (honnêteté : on ne vend jamais de l'énergie qui n'existe pas) :
//   • jamais plus que la production (la batterie ne décale que l'existant) ;
//   • jamais plus que la consommation réelle quand elle est connue (QF5).
export const BATTERY_CYCLES_PER_DAY = 1
export const DAYS_PER_YEAR = 365
export const DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

/**
 * Taux d'autoconsommation EFFECTIF de l'option « avec batterie », DÉRIVÉ de la
 * capacité réellement chiffrée (miroir exact de pricing.autoconso_avec_ratio).
 *
 * @param productionAnnuelleKwh production annuelle (kWh/an)
 * @param batteryKwh capacité batterie totale du devis (kWh) — 0/inconnue → repli
 * @param base taux sans batterie (défaut AUTOCONSO_SANS)
 * @param fallback taux de repli quand aucune capacité n'est connue
 * @param consoAnnuelleKwh consommation réelle (kWh/an) quand elle est connue
 */
export function autoconsoAvecRatio(productionAnnuelleKwh, batteryKwh, {
  base = AUTOCONSO_SANS, fallback = AUTOCONSO_AVEC, consoAnnuelleKwh = null,
} = {}) {
  const prod = parseFloat(productionAnnuelleKwh) || 0
  const cap = parseFloat(batteryKwh) || 0
  const conso = parseFloat(consoAnnuelleKwh) || 0
  if (prod <= 0) return fallback
  let ratio = cap > 0
    ? (parseFloat(base) || 0) + (cap * BATTERY_CYCLES_PER_DAY * DAYS_PER_YEAR) / prod
    : fallback
  ratio = Math.min(1, ratio)                      // plafond production
  if (conso > 0) ratio = Math.min(ratio, conso / prod)  // plafond consommation
  return ratio
}

// ── QX39 — cashflow 25 ans honnête (MIROIR backend pricing.py) ───────────────
// Mêmes hypothèses documentées : dégradation panneau, tarif CONSTANT (aucune
// hausse supposée), rendement batterie, remplacement onduleur optionnel. Le payback = croisement
// du cumul à zéro. Écran, PDF et proposition web affichent le MÊME payback.
export const CASHFLOW_YEARS = 25
export const PANEL_DEGRADATION = 0.005
// ALIGNEMENT 18/08 — QRES54 (aucune hausse tarifaire supposée) n'avait été
// appliqué qu'au backend : l'écran promettait +2 %/an alors que le PDF et la
// page proposition écrivent « projection à tarif constant ». On dit VRAI des
// deux côtés — la constante reste exportée, à 0 (miroir pricing.py).
// Toute hausse réelle du tarif ne peut qu'améliorer le résultat du client.
export const TARIFF_ESCALATION = 0.0
export const BATTERY_ROUNDTRIP = 0.90
// Q1 (décision fondateur du 20/08/2026) — PROVISION DE REMPLACEMENT ONDULEUR :
// le principe mi-vie (année 12, IEA PVPS) est confirmé, mais le MONTANT n'est
// plus un pourcentage forfaitaire du CAPEX (l'ancien ≈ 8 % ne correspondait au
// prix d'AUCUN onduleur réel) — c'est le PRIX TTC RÉEL de la ligne onduleur du
// devis (`inverterReplaceCost`, résolu par `inverterCostFromLines`/`isAnyInverter`
// ci-dessous). Aucune ligne onduleur identifiable ⇒ AUCUNE provision — jamais
// un pourcentage de repli.
export const INVERTER_REPLACE_YEAR = 12

export function computeCashflowPayback(investment, economieAnnee1, {
  battery = false,
  // Z5 (ORDRE FONDATEUR, 20/08/2026) — PART de l'économie qui transite
  // RÉELLEMENT par la batterie (0..1). Le rendement aller-retour ne frappe QUE
  // elle, jamais le socle autoconsommé directement au fil du soleil (qui ne
  // subit aucune perte de charge/décharge). `null` (défaut) conserve le
  // forfait historique (0,90 sur 100 % de l'économie) pour un appelant direct
  // sans la décomposition sans/avec.
  batteryShare = null,
  // Q1 — prix TTC RÉEL de l'onduleur de cette option, retranché à
  // INVERTER_REPLACE_YEAR. `null`/0 ⇒ aucune provision.
  inverterReplaceCost = null,
  // QJR137 (miroir `pricing`) — rendement aller-retour PROUVÉ par la fiche
  // batterie quand le moteur horaire le publie, sinon l'hypothèse de référence.
  batteryRoundtrip = BATTERY_ROUNDTRIP,
} = {}) {
  const inv = parseFloat(investment) || 0
  const base = parseFloat(economieAnnee1) || 0
  if (base <= 0 || inv <= 0) {
    return { paybackYears: null, cumulative: [], netGain: 0, years: CASHFLOW_YEARS, jamaisRembourse: false }
  }
  // Z5 — facteur batterie EFFECTIF : la perte aller-retour ne frappe que la
  // part réellement stockée puis restituée. `batteryShare=null` → forfait
  // historique (0,90 sur tout) ; `0` → aucune perte ; `1` → identique au forfait.
  const rt = (parseFloat(batteryRoundtrip) > 0 && parseFloat(batteryRoundtrip) <= 1)
    ? parseFloat(batteryRoundtrip) : BATTERY_ROUNDTRIP
  let battFactor = 1
  if (battery) {
    if (batteryShare === null || batteryShare === undefined) {
      battFactor = rt
    } else {
      const part = Math.max(0, Math.min(1, parseFloat(batteryShare) || 0))
      battFactor = 1 - (1 - rt) * part
    }
  }
  const invCost = parseFloat(inverterReplaceCost) || 0
  const cumulative = []
  let cumul = -inv
  let payback = null
  let prev = -inv
  for (let y = 1; y <= CASHFLOW_YEARS; y++) {
    const prodFactor = (1 - PANEL_DEGRADATION) ** (y - 1)
    const tarifFactor = (1 + TARIFF_ESCALATION) ** (y - 1)
    let yearSaving = base * prodFactor * tarifFactor
    if (battery) yearSaving *= battFactor
    let yearCf = yearSaving
    if (INVERTER_REPLACE_YEAR && invCost > 0 && y === INVERTER_REPLACE_YEAR) {
      yearCf -= invCost
    }
    prev = cumul
    cumul += yearCf
    cumulative.push(Math.round(cumul))
    if (payback === null && cumul >= 0) {
      const span = cumul - prev
      const frac = span ? (0 - prev) / span : 0
      payback = Math.round(((y - 1) + frac) * 10) / 10
    }
  }
  // ERR-QAC-PAYBACK-JAMAIS-REMBOURSE-25-ANS — miroir de `pricing` : la
  // sentinelle numérique reste (comparaisons), le drapeau pilote l'affichage.
  const jamaisRembourse = payback === null
  if (jamaisRembourse) payback = CASHFLOW_YEARS
  return { paybackYears: payback, cumulative, netGain: Math.round(cumul), years: CASHFLOW_YEARS, jamaisRembourse }
}

// ERR-QAH-FIG-PAYBACK-FORMULE-ECRAN — le payback de l'écran quand l'étude
// horaire SERVEUR a répondu : la formule du MOTEUR (`pricing.calculate_savings_roi`
// → `compute_cashflow_payback`, cashflow 25 ans QX39 : dégradation, rendement
// batterie sur la seule part stockée, remplacement onduleur au prix réel),
// appliquée à l'économie servie par le serveur — jamais `coût ÷ économie`
// (écran 13,43 / 8,95 ans contre 8,2 / 5,5 au document).
// `annuel` = `etude.annuel` du serveur (taux d'autoconsommation, production,
// consommation) : la part batterie se dérive comme dans `pricing` (plafond
// sans ≤ conso/production, plancher avec ≥ sans). Rend
// `{ paybackYears, jamaisRembourse, netGain }`, ou `null` sans coût ni économie.
// AMOT72 — miroir du moteur CORRIGÉ (AMOT58, `rendement_une_fois`) : en modèle
// horaire, le rendement aller-retour de la batterie est DÉJÀ dans l'économie
// servie (`etude_horaire` borne le restitué) ; la part batterie du cashflow
// vaut donc 0 — plus de seconde déduction. Flux année 1 = économie servie.
// `annuel` et `rendementBatterie` restent acceptés (appelants inchangés).
export function paybackMoteurHoraire(total, ecoAnnuelle, {
  annuel = null, rendementBatterie = null, stockage = false, inverterReplaceCost = null,
} = {}) {
  void annuel
  const t = parseFloat(total) || 0
  const eco = parseFloat(ecoAnnuelle) || 0
  if (!(t > 0) || !(eco > 0)) return null
  const cf = computeCashflowPayback(t, eco, {
    battery: !!stockage, batteryShare: 0, inverterReplaceCost,
    batteryRoundtrip: rendementBatterie ?? BATTERY_ROUNDTRIP,
  })
  return { paybackYears: cf.paybackYears, jamaisRembourse: !!cf.jamaisRembourse, netGain: cf.netGain }
}

// ── Simulation ROI (port exact de /api/roi/calculate du simulateur) ──────────
// QF5 — quand une consommation annuelle RÉELLE + un distributeur connu sont
// fournis (`consoAnnuelleKwh`/`utility`, capturés par QF4), l'économie bascule
// sur le modèle « deux factures » par tranche (miroir EXACT du backend QF2) :
// l'écran affiche alors la MÊME économie que le PDF pour les mêmes entrées.
// Sans ces données, comportement HISTORIQUE inchangé (estimation production ×
// autoconsommation diurne × tarif) — jamais de régression pour un devis existant.
export function computeROI({
  kwp, factures, dayUsagePct, totalSans, totalAvec, batteryKwh, kwhPrice, efficiency,
  consoAnnuelleKwh, utility, productible,
  // AGNR35 — barème EFFECTIF de la société (`baremeDepuisProfil`) : grille et
  // redevance réglées ; absent ⇒ constantes nationales (inchangé).
  bareme = null,
  // Q1 (fondateur 20/08/2026) — lignes RÉELLES du devis, pour retrouver le
  // prix TTC de l'onduleur de chaque option (provision de remplacement à
  // l'année 12). Optionnel : sans lignes, aucune provision (jamais un
  // pourcentage de repli) — comportement inchangé pour un appelant qui ne les
  // fournit pas (encore).
  lines = [],
  // AGNR36 — catalogue de l'écran : chaque ligne se classe sur désignation + nom du produit lié (`texteClassement`). Absent ⇒ désignation seule.
  // RGEN5 — `reglesCalcul` (`Devis.regles_calcul`) ≥ 3 : économie « avec » nette (absent ⇒ brut, inchangé).
  produits = [], reglesCalcul = 0,
}) {
  // RGEN10 — prix du kWh « estimation » = cascade du PDF (barème société → grille du distributeur reçu → tarif société → 1,20).
  const PRICE = prixKwhEstimation({ utility, tranches: bareme?.tranches, consoAnnuelleKwh, kwhPrice }, { grilleNationale: ONEE_TRANCHES, factureMensuelle: monthlyBillFromKwh, defaut: KWH_PRICE, repli: FALLBACK_KWH_PRICE })
  const EFF = (Number.isFinite(Number(efficiency)) && Number(efficiency) > 0) ? Number(efficiency) : EFFICIENCY
  // QX38 — productible CANONIQUE (kWh/kWc/an) : quand il est fourni (PVGIS par
  // ville, source unique partagée avec le PDF/web), la production annuelle vaut
  // productible × kwp, répartie par la FORME saisonnière GHI (le graphe mensuel
  // garde sa saisonnalité). Sans productible, comportement HISTORIQUE inchangé
  // (GHI[i] × kwp × rendement) — jamais de régression pour un devis existant.
  const PROD = Number(productible)
  const useProductible = Number.isFinite(PROD) && PROD > 0
  const GHI_SUM = GHI.reduce((s, v) => s + v, 0)
  let bills = [...(factures ?? [])]
  if (bills.length < 12) {
    const last = bills.length ? bills[bills.length - 1] : 500
    bills = bills.concat(Array(12 - bills.length).fill(last))
  }
  bills = bills.slice(0, 12)

  const dayPct = (dayUsagePct ?? 50) / 100
  const monthlyDetail = []
  const ecoSansMonthly = []
  const ecoAvecMonthly = []
  let productionAnnuelle = 0
  let batteryShiftAnnuel = 0   // kWh réellement décalés par la batterie

  for (let i = 0; i < 12; i++) {
    const prodKwh = useProductible
      // Productible stocké (net à 14 %) ramené aux 20 % de pertes TOTALES du
      // fondateur (PRODUCTIBLE_NET_FACTOR), puis réparti par la forme GHI.
      ? (PROD * PRODUCTIBLE_NET_FACTOR * kwp) * (GHI[i] / GHI_SUM)
      : GHI[i] * kwp * EFF   // chemin historique : EFFICIENCY = 0,8 EST déjà 20 %
    productionAnnuelle += prodKwh
    const selfConsumed = prodKwh * dayPct
    const ecoSans = selfConsumed * PRICE
    // ORDRE FONDATEUR (18/08) — apport batterie en ÉNERGIE, plus le forfait
    // 60 MAD/kWh/mois : capacité × 1 cycle/jour × jours du mois, plafonné par
    // ce qu'il reste de production ce mois-là (on ne stocke que l'existant),
    // puis valorisé au tarif — même dérivation du taux que pricing.py,
    // VERROUILLÉE par les tests jumeaux solar.batterie/test_battery_autoconso.
    const stockable = Math.max(0, prodKwh - selfConsumed)
    const batteryShift = Math.min(
      Math.max(0, parseFloat(batteryKwh) || 0) * BATTERY_CYCLES_PER_DAY * DAYS_IN_MONTH[i],
      stockable)
    batteryShiftAnnuel += batteryShift
    const ecoAvec = ecoSans + batteryShift * PRICE
    ecoSansMonthly.push(ecoSans)
    ecoAvecMonthly.push(ecoAvec)
    monthlyDetail.push({
      month: CHART_MONTHS[i],
      facture: bills[i],
      eco_sans: ecoSans,
      eco_avec: ecoAvec,
    })
  }

  let ecoAnnuelleSans = ecoSansMonthly.reduce((s, v) => s + v, 0)
  let ecoAnnuelleAvec = ecoAvecMonthly.reduce((s, v) => s + v, 0)

  // QF2/QF5 — modèle « deux factures » (réel, par tranche) quand consommation
  // ET barème sont disponibles. Remplace l'estimation ci-dessus par l'économie
  // réelle facture_sans − facture_avec (jamais les deux mélangés).
  // PARITÉ ÉCRAN/PDF AU DIRHAM : le moteur PDF arrondit la production annuelle
  // à l'entier AVANT le modèle par tranches (pricing.calculate_savings_roi).
  // L'écran fait donc pareil — sinon les deux tombent de part et d'autre d'un
  // arrondi de tranche et affichent 1 MAD d'écart pour les mêmes entrées.
  const productionCanonique = Math.round(productionAnnuelle)
  // Le taux « avec batterie » est DÉRIVÉ de la capacité réelle du devis
  // (ordre fondateur 18/08) : 60 % + capacité × 1 cycle/jour, plafonné par la
  // production ET par la consommation. Sans capacité connue → repli documenté.
  const autoconsoAvec = autoconsoAvecRatio(productionCanonique, batteryKwh, {
    consoAnnuelleKwh,
  })
  // Taux EFFECTIVEMENT appliqués (pour affichage/transparence) : dans le
  // chemin « estimation » la part sans batterie est la part diurne saisie
  // (dayUsagePct) et la part avec batterie ajoute les kWh réellement décalés.
  let autoconsoSansEff = dayPct
  let autoconsoAvecEff = productionAnnuelle > 0
    ? Math.min(1, dayPct + batteryShiftAnnuel / productionAnnuelle)
    : dayPct
  // ── PLAFOND CONSOMMATION DU CÔTÉ « SANS » — MIROIR EXACT de
  // pricing.calculate_savings_roi (correctif 18/08) ────────────────────────
  // Le côté AVEC batterie est déjà borné par la consommation réelle
  // (`autoconsoAvecRatio`) ; le côté SANS, lui, était un pourcentage de la
  // seule PRODUCTION, borné par rien. Sur une petite conso face à une grosse
  // production, l'option BATTERIE « économisait » donc MOINS que l'option
  // sans batterie (8 kWc / 5 000 kWh/an / 10 kWh : 6 644 MAD sans contre
  // 6 000 MAD avec côté PDF). On borne les DEUX côtés aux kWh RÉELLEMENT
  // consommés, puis on tient l'invariant « avec ≥ sans ».
  //   sans = min(part_diurne × production, conso)
  //   avec = max(min(part_diurne × production + décalage_batterie, conso), sans)
  // Les séries mensuelles sont mises à l'échelle du MÊME facteur, pour que
  // leur somme reste l'économie annuelle affichée.
  const consoPlafond = parseFloat(consoAnnuelleKwh) || 0
  if (consoPlafond > 0 && productionAnnuelle > 0) {
    const kwhSansBrut = productionAnnuelle * dayPct
    const kwhAvecBrut = kwhSansBrut + batteryShiftAnnuel
    const kwhSans = Math.min(kwhSansBrut, consoPlafond)
    const kwhAvec = Math.max(Math.min(kwhAvecBrut, consoPlafond), kwhSans)
    const fSans = kwhSansBrut > 0 ? kwhSans / kwhSansBrut : 1
    const fAvec = kwhAvecBrut > 0 ? kwhAvec / kwhAvecBrut : 1
    if (fSans < 1 || fAvec < 1) {
      for (let i = 0; i < 12; i++) {
        ecoSansMonthly[i] *= fSans
        ecoAvecMonthly[i] *= fAvec
        monthlyDetail[i].eco_sans = ecoSansMonthly[i]
        monthlyDetail[i].eco_avec = ecoAvecMonthly[i]
      }
      ecoAnnuelleSans = ecoSansMonthly.reduce((s, v) => s + v, 0)
      ecoAnnuelleAvec = ecoAvecMonthly.reduce((s, v) => s + v, 0)
    }
    autoconsoSansEff = kwhSans / productionAnnuelle
    autoconsoAvecEff = kwhAvec / productionAnnuelle
  }
  // Modèle « factures » : même plafond, même plancher (miroir pricing.py, qui
  // passe `autoconso_sans_eff` à `two_bills_savings` et planchéise le taux
  // AVEC). Sur les factures c'est un NO-OP de VALEUR — `twoBillsSavings` borne
  // déjà les kWh autoconsommés à la conso — mais le taux AFFICHÉ devient
  // honnête et l'invariant « avec ≥ sans » est verrouillé des deux côtés.
  const autoconsoSansPlaf = (consoPlafond > 0 && productionCanonique > 0)
    ? Math.min(AUTOCONSO_SANS, consoPlafond / productionCanonique)
    : AUTOCONSO_SANS
  const autoconsoAvecPlanche = Math.max(autoconsoAvec, autoconsoSansPlaf)
  let savingsModel = 'estimation'
  let factureSans = null, factureAvecSans = null, factureAvecAvec = null
  if (productionAnnuelle > 0 && consoAnnuelleKwh > 0 && utility) {
    const tbSans = twoBillsSavings(productionCanonique, consoAnnuelleKwh, autoconsoSansPlaf, utility,
      bareme?.tranches, bareme?.chargesFixes)
    const tbAvec = twoBillsSavings(productionCanonique, consoAnnuelleKwh, autoconsoAvecPlanche, utility,
      bareme?.tranches, bareme?.chargesFixes)
    if (tbSans && tbAvec) {
      savingsModel = 'factures'
      autoconsoSansEff = autoconsoSansPlaf
      autoconsoAvecEff = autoconsoAvecPlanche
      ecoAnnuelleSans = tbSans.economie
      ecoAnnuelleAvec = tbAvec.economie
      factureSans = tbSans.factureSans
      factureAvecSans = tbSans.factureAvec
      factureAvecAvec = tbAvec.factureAvec
      // AGNR23 — la série mensuelle est RÉPARTIE depuis l'annuel FINAL (clé
      // de répartition = la forme de production de la série estimée, comme
      // la clé solaire mensuelle du serveur) : Σ des 12 points = la carte.
      const repartir = (serie, cible) => {
        const somme = serie.reduce((s, v) => s + v, 0)
        if (!(somme > 0)) return
        for (let i = 0; i < 12; i++) serie[i] = serie[i] * (cible / somme)
      }
      repartir(ecoSansMonthly, ecoAnnuelleSans)
      repartir(ecoAvecMonthly, ecoAnnuelleAvec)
      for (let i = 0; i < 12; i++) {
        monthlyDetail[i].eco_sans = ecoSansMonthly[i]
        monthlyDetail[i].eco_avec = ecoAvecMonthly[i]
      }
    }
  }

  // AGNR25 — chemin « estimation » : l'apport batterie se calcule sur
  // l'ANNÉE par `autoconsoAvecRatio` (part diurne + capacité × 1 cycle/jour ×
  // 365, plafonné production / conso), exactement `calculate_savings_roi`
  // (production arrondie × taux × tarif) — plus la borne MENSUELLE du
  // stockable, qui sous-estimait les grosses batteries (12 408 au lieu de
  // 12 854 MAD/an). La série mensuelle « avec » est répartie depuis l'annuel.
  if (savingsModel === 'estimation' && (parseFloat(batteryKwh) || 0) > 0 && productionCanonique > 0) {
    const ratioAvec = Math.max(
      autoconsoAvecRatio(productionCanonique, batteryKwh, { base: dayPct, consoAnnuelleKwh }),
      autoconsoSansEff)
    // Invariant « avec ≥ sans » (la part sans batterie de l'écran porte la
    // production non arrondie).
    ecoAnnuelleAvec = Math.max(productionCanonique * ratioAvec * PRICE, ecoAnnuelleSans)
    batteryShiftAnnuel = Math.max(0, (ratioAvec - autoconsoSansEff) * productionCanonique)
    autoconsoAvecEff = ratioAvec
    const sommeAvec = ecoAvecMonthly.reduce((acc, v) => acc + v, 0)
    if (sommeAvec > 0) {
      for (let i = 0; i < 12; i++) {
        ecoAvecMonthly[i] = ecoAvecMonthly[i] * (ecoAnnuelleAvec / sommeAvec)
        monthlyDetail[i].eco_avec = ecoAvecMonthly[i]
      }
    }
  }

  // Q1 — prix TTC RÉEL des lignes onduleur de CHAQUE option (miroir builder.py
  // sans_items/avec_items : « sans » exclut batterie + onduleur hybride,
  // « avec » exclut l'onduleur réseau — mêmes filtres que optionTotalsTTC).
  // L-2OPT (fondateur 24/08) — `variante` ('' commun | 'sans' | 'avec', posée
  // par `fusionnerVariantes`) écarte D'ABORD la ligne taguée pour l'AUTRE
  // option ; F14 (26/08) — une ligne DÉCLARÉE ('sans'/'avec') TRANCHE SEULE
  // et NE repasse PLUS par le filtre mot-clé (avant F14, une batterie taguée
  // 'sans' était encore retirée du panier « sans » par le second filtre —
  // contradiction avec builder.py où la déclaration prime). Seule une ligne
  // SANS `variante` (tout devis hors « Les deux ») retombe sur les mots-clés,
  // exactement comme avant.
  const linesSans = lines.filter(l => appartientAuPanierSans(l, produits))
  const linesAvec = lines.filter(l => appartientAuPanierAvec(l, produits))
  const inverterCostSans = inverterCostFromLines(linesSans, produits)
  const inverterCostAvec = inverterCostFromLines(linesAvec, produits)

  // M9 — l'option 2 porte-t-elle RÉELLEMENT du stockage ? Dérivé des VRAIES
  // lignes (`batteryKwh` = `batteryKwhFromLines(...)` chez l'appelant), jamais
  // codé en dur : un devis sans batterie ne subit plus la perte d'un
  // équipement absent.
  const stockagePresent = (parseFloat(batteryKwh) || 0) > 0

  // Z5 — PART de l'économie qui transite RÉELLEMENT par la batterie : le
  // socle autoconsommé directement (autoconsoSansEff) n'entre jamais dans la
  // batterie ; seul le supplément apporté par la capacité batterie
  // (autoconsoAvecEff − autoconsoSansEff) est stocké puis restitué.
  let battPart = autoconsoAvecEff > 0 ? Math.max(0, autoconsoAvecEff - autoconsoSansEff) / autoconsoAvecEff : 0
  // RGEN5 — niveau 3 : même règle que le PDF (RHOR6, économie nette) ; le cashflow lit le net (part 0).
  ;({ economie: ecoAnnuelleAvec, factureAvec: factureAvecAvec, partStockee: battPart } = economieAvecNette(ecoAnnuelleAvec, factureAvecAvec, battPart, { nette: reglesCalcul >= 3 && stockagePresent, roundtrip: BATTERY_ROUNDTRIP, series: [{ valeurs: ecoAvecMonthly }, { valeurs: monthlyDetail, cle: 'eco_avec' }] }))

  // QX39 — payback par croisement du cumul du cashflow 25 ans (miroir backend),
  // pas un ratio année-1 : écran/PDF/proposition affichent le MÊME payback.
  const cfSans = computeCashflowPayback(totalSans, ecoAnnuelleSans, {
    inverterReplaceCost: inverterCostSans,
  })
  const cfAvec = computeCashflowPayback(totalAvec, ecoAnnuelleAvec, {
    battery: stockagePresent, batteryShare: battPart, inverterReplaceCost: inverterCostAvec,
  })
  const paybackSans = (ecoAnnuelleSans > 0 && totalSans > 0) ? cfSans.paybackYears : null
  const paybackAvec = (ecoAnnuelleAvec > 0 && totalAvec > 0) ? cfAvec.paybackYears : null

  return {
    production_annuelle_kwh: Math.round(productionAnnuelle * 10) / 10,
    monthly_detail: monthlyDetail,
    eco_annuelle_sans: ecoAnnuelleSans,
    eco_annuelle_avec: ecoAnnuelleAvec,
    eco_sans_monthly: ecoSansMonthly,
    eco_avec_monthly: ecoAvecMonthly,
    payback_sans: paybackSans,
    payback_avec: paybackAvec,
    // ERR-QAC-PAYBACK-JAMAIS-REMBOURSE-25-ANS — mêmes drapeaux que le PDF.
    payback_sans_jamais: paybackSans !== null && !!cfSans.jamaisRembourse,
    payback_avec_jamais: paybackAvec !== null && !!cfAvec.jamaisRembourse,
    // QX39 — cumul cashflow 25 ans + gain net (mêmes clés que le PDF).
    cashflow_sans: cfSans.cumulative,
    cashflow_avec: cfAvec.cumulative,
    net_gain_sans: cfSans.netGain,
    net_gain_avec: cfAvec.netGain,
    // QF5 — transparence : le PDF (builder.py) porte les mêmes clés
    // (savings_model/facture_sans/facture_avec_s/facture_avec_a).
    savings_model: savingsModel,
    facture_sans: factureSans,
    facture_avec_sans: factureAvecSans,
    facture_avec_avec: factureAvecAvec,
    // Transparence (mêmes clés que le PDF) : taux d'autoconsommation retenus.
    // `autoconso_avec` est DÉRIVÉ de la capacité batterie, jamais forfaitaire.
    autoconso_sans: autoconsoSansEff,
    autoconso_avec: autoconsoAvecEff,
    // kWh annuels réellement décalés par la batterie (chemin estimation).
    battery_shift_kwh: Math.round(batteryShiftAnnuel),
  }
}
