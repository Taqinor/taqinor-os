// Solar math + catalogue auto-fill, ported 1:1 from RedaSolar/devis-simulator
// (constants.py, roi_router.py, autofill.py / autofill_router.py, app.js).
// The simulator is the source of truth: prices are handled in TTC (like the
// simulator UI) and only converted to HT at save time. Pure functions, no I/O.
// The premium PDF engine computes its own figures server-side — never fed here.

// ── Constantes Maroc (irradiance GHI mensuelle + tarif ONEE) ──────────────────
export const GHI = [
  83.99, 96.79, 133.43, 155.30, 175.28, 179.62,
  179.56, 161.17, 137.03, 111.59, 81.91, 74.61,
]
// Libellés des mois : grille des factures (complets) vs graphique (courts),
// exactement comme dans le simulateur (MONTHS_FR vs labels du chart).
export const MONTHS_FR = [
  'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
  'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc',
]
export const CHART_MONTHS = [
  'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
  'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc',
]
export const EFFICIENCY = 0.8 // rendement global
export const KWH_PRICE = 1.75 // MAD/kWh ONEE — usage interne, jamais affiché

// Factures mensuelles affichées au chargement (initApp du simulateur)
export const DEFAULT_MONTHLY_BILLS = [500, 450, 400, 380, 360, 500, 700, 680, 580, 480, 430, 480]

// Autoconsommation par défaut selon le type d'installation
export const DAY_USAGE_DEFAULTS = {
  'Résidentielle': 60,
  'Commerciale': 80,
  'Industrielle': 80,
  'Agricole': 100,
}

// ── Format monétaire (port exact de formatMoney) ─────────────────────────────
export function formatMoney(val) {
  if (val === null || val === undefined || isNaN(val)) return '0 MAD'
  return Math.round(val).toLocaleString('fr-MA') + ' MAD'
}

// ── Estimation des factures mensuelles depuis hiver/été ──────────────────────
export function interpolerFactures(hiver, ete) {
  if (!ete || ete <= 0) return Array(12).fill(hiver)
  const premiere = Array.from({ length: 7 }, (_, i) => hiver + (ete - hiver) / 6 * i)
  const seconde = Array.from({ length: 5 }, (_, i) => ete - (ete - hiver) / 4 * i)
  return [...premiere, ...seconde]
}

// Les mois affichés sont toujours arrondis à l'entier (renderMonthlyInputs)
export function estimerMois(hiver, ete) {
  return interpolerFactures(hiver, ete).map(v => Math.round(v))
}

// 8 panneaux par tranche de 900 MAD de facture hiver
export function estimerPanneaux(factureHiver) {
  return Math.floor(factureHiver / 900) * 8
}

// ── Simulation ROI (port exact de /api/roi/calculate du simulateur) ──────────
export function computeROI({ kwp, factures, dayUsagePct, totalSans, totalAvec, batteryKwh }) {
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

  for (let i = 0; i < 12; i++) {
    const prodKwh = GHI[i] * kwp * EFFICIENCY
    productionAnnuelle += prodKwh
    const selfConsumed = prodKwh * dayPct
    const ecoSans = selfConsumed * KWH_PRICE
    const ecoAvec = ecoSans + (batteryKwh ?? 0) * 60 // 60 MAD/kWh batterie/mois
    ecoSansMonthly.push(ecoSans)
    ecoAvecMonthly.push(ecoAvec)
    monthlyDetail.push({
      month: CHART_MONTHS[i],
      facture: bills[i],
      eco_sans: ecoSans,
      eco_avec: ecoAvec,
    })
  }

  const ecoAnnuelleSans = ecoSansMonthly.reduce((s, v) => s + v, 0)
  const ecoAnnuelleAvec = ecoAvecMonthly.reduce((s, v) => s + v, 0)

  const paybackSans = (ecoAnnuelleSans > 0 && totalSans > 0)
    ? Math.round(totalSans / ecoAnnuelleSans * 10) / 10 : null
  const paybackAvec = (ecoAnnuelleAvec > 0 && totalAvec > 0)
    ? Math.round(totalAvec / ecoAnnuelleAvec * 10) / 10 : null

  return {
    production_annuelle_kwh: Math.round(productionAnnuelle * 10) / 10,
    monthly_detail: monthlyDetail,
    eco_annuelle_sans: ecoAnnuelleSans,
    eco_annuelle_avec: ecoAnnuelleAvec,
    eco_sans_monthly: ecoSansMonthly,
    eco_avec_monthly: ecoAvecMonthly,
    payback_sans: paybackSans,
    payback_avec: paybackAvec,
  }
}

// ── Classification des lignes/produits (mêmes mots-clés que le moteur PDF) ───
const _norm = (s) =>
  (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export const isBattery = (d) => _norm(d).includes('batterie')
export const isHybridInverter = (d) => _norm(d).includes('onduleur') && _norm(d).includes('hybride')
export const isReseauInverter = (d) => {
  const n = _norm(d)
  return n.includes('onduleur') && (n.includes('reseau') || n.includes('injection'))
}
export const isPanel = (d) => _norm(d).includes('panneau')

const WATT_RE = /(\d{3,4})\s*(?:wc|w)\b/i
const KW_RE = /(\d+(?:[.,]\d+)?)\s*(?:kw|kva)\b/i
const KWH_RE = /(\d+(?:[.,]\d+)?)\s*kwh\b/i

export function parseWatt(text) {
  const m = WATT_RE.exec(text || '')
  return m ? parseInt(m[1], 10) : null
}
export function parseKw(text) {
  // " 5 kWh" matcherait kW — exclure les kWh d'abord
  const cleaned = (text || '').replace(KWH_RE, ' ')
  const m = KW_RE.exec(cleaned)
  return m ? parseFloat(m[1].replace(',', '.')) : null
}
export function parseKwh(text) {
  const m = KWH_RE.exec(text || '')
  return m ? parseFloat(m[1].replace(',', '.')) : null
}
// Phase depuis le nom produit ; défaut Monophase comme le catalogue simulateur
export function parsePhaseIsTri(text) {
  return /tri\s*phas/i.test(text || '')
}

export function classifyProduct(nom) {
  const n = _norm(nom)
  if (!n) return null
  if (n.includes('onduleur') && n.includes('hybride')) return 'onduleur_hybride'
  // mêmes mots-clés que le moteur PDF : un onduleur sans « réseau/injection »
  // (ex. micro-onduleur) n'est pas classé et reste sélectionnable à la main
  if (n.includes('onduleur') && (n.includes('reseau') || n.includes('injection'))) {
    return 'onduleur_reseau'
  }
  if (n.includes('panneau')) return 'panneau'
  if (n.includes('batterie')) return 'batterie'
  if (n.includes('structure')) return 'structure'
  if (n.includes('socle')) return 'socle'
  if (n.includes('smart meter')) return 'smart_meter'
  if (n.includes('wifi') || n.includes('dongle')) return 'wifi_dongle'
  if (n.includes('accessoire')) return 'accessoires'
  if (n.includes('tableau')) return 'tableau'
  if (n.includes('suivi')) return 'suivi'
  if (n.includes('installation')) return 'installation'
  if (n.includes('transport')) return 'transport'
  return null
}

// Prix TTC affiché depuis le prix de vente HT du stock (TVA 20 %)
export function ttcFromHt(prixVenteHt) {
  return Math.round((parseFloat(prixVenteHt) || 0) * 1.2)
}

// Conversion inverse au moment de l'enregistrement : le modèle stocke des
// prix HT à 2 décimales. Pour tout TTC saisi à la dirham près, l'aller-retour
// TTC → HT(2 déc.) → TTC réaffiché redonne exactement la valeur tapée.
export function htFromTtc(ttc, tauxTva = 20) {
  const factor = 1 + (parseFloat(tauxTva) || 20) / 100
  return ((parseFloat(ttc) || 0) / factor).toFixed(2)
}

// Capacité batterie totale depuis les lignes (port de app.js — défaut 5 kWh/ligne)
export function batteryKwhFromLines(lines) {
  return lines.reduce((sum, l) => {
    if (!isBattery(l.designation)) return sum
    const qty = parseFloat(l.quantite) || 0
    return sum + qty * (parseKwh(l.designation) ?? 5.0)
  }, 0)
}

// ── Totaux par option, TTC (port exact de updateTotals de app.js) ────────────
// Option 1 SANS batterie : exclut Batterie + Onduleur hybride.
// Option 2 AVEC batterie : exclut Onduleur réseau.
export function optionTotalsTTC(lines, discountPct) {
  const ttc = (l) => (parseFloat(l.quantite) || 0) * (parseFloat(l.prix_unit_ttc) || 0)
  const totalSansBrut = lines
    .filter(l => !isBattery(l.designation) && !isHybridInverter(l.designation))
    .reduce((s, l) => s + ttc(l), 0)
  const totalAvecBrut = lines
    .filter(l => !isReseauInverter(l.designation))
    .reduce((s, l) => s + ttc(l), 0)

  const pct = parseFloat(discountPct) || 0
  const totalSans = pct > 0 ? Math.round(totalSansBrut * (1 - pct / 100)) : totalSansBrut
  const totalAvec = pct > 0 ? Math.round(totalAvecBrut * (1 - pct / 100)) : totalAvecBrut
  return { totalSansBrut, totalAvecBrut, totalSans, totalAvec }
}

// ── Indexation par type des produits du stock ─────────────────────────────────
function indexProduits(produits) {
  const byType = {}
  for (const p of produits) {
    const type = classifyProduct(p.nom)
    if (!type) continue
    if (!byType[type]) byType[type] = []
    byType[type].push(p)
  }
  return byType
}

const lineFrom = (p, quantite, ttcOverride = null) => ({
  produit: p ? String(p.id) : '',
  designation: p ? p.nom : '',
  quantite,
  prix_unit_ttc: p || ttcOverride != null
    ? (ttcOverride != null ? ttcOverride : ttcFromHt(p.prix_vente))
    : 0,
})

// Ligne vide placeholder (désignation canonique, pas de produit)
const placeholder = (designation, quantite) => ({
  produit: '', designation, quantite, prix_unit_ttc: 0,
})

// ── Table par défaut au chargement (port de getDefaultProductLines) ──────────
// Quantités par défaut du simulateur ; les lignes « spéciales » (onduleurs,
// panneaux, batteries) restent à choisir, les autres pointent sur le produit
// canonique du stock avec son prix TTC (équivalent de autofillRowPrice).
export function defaultProductLines(produits) {
  const byType = indexProduits(produits)
  const first = (type) => (byType[type] ?? [])[0] ?? null
  const exactOr = (type, needle) => {
    const pool = byType[type] ?? []
    return pool.find(p => _norm(p.nom).includes(needle)) ?? null
  }
  const row = (p, designation, quantite) =>
    p ? lineFrom(p, quantite) : placeholder(designation, quantite)

  return [
    placeholder('Onduleur réseau', 1),
    placeholder('Onduleur hybride', 1),
    row(first('smart_meter'), 'Smart Meter', 0),
    row(first('wifi_dongle'), 'Wifi Dongle', 0),
    placeholder('Panneaux', 0),
    placeholder('Batterie', 1),
    placeholder('Batterie', 0),
    row(exactOr('structure', 'acier'), 'Structures acier', 0),
    row(exactOr('structure', 'alu'), 'Structures aluminium', 0),
    row(first('socle'), 'Socles', 0),
    row(first('accessoires'), 'Accessoires', 1),
    row(first('tableau'), 'Tableau De Protection AC/DC', 1),
    row(first('installation'), 'Installation', 1),
    row(first('transport'), 'Transport', 1),
    row(first('suivi'), 'Suivi journalier, maintenance chaque 12 mois pendent 2 ans', 1),
  ]
}

// ── Auto-remplissage (port exact de auto_fill_from_power + autofill_router) ───
// Retourne la table complète dans l'ordre canonique du simulateur, lignes à
// quantité nulle comprises (elles s'affichent mais ne sont pas enregistrées).
export function autoFillLines(produits, { kwp, panelW, structureType }) {
  if (!kwp || kwp <= 0) return []
  const byType = indexProduits(produits)

  const nbPanneaux = Math.max(1, Math.round(kwp * 1000 / panelW))
  const threshold = kwp * 0.8

  // Sélection onduleur : plus petit modèle >= 80 % de la puissance, sinon le
  // plus gros du catalogue ; à puissance égale, Triphasé si >= 10 kW sinon Mono.
  const pickInverter = (pool) => {
    const cands = (pool ?? [])
      .map(p => ({ p, kw: parseKw(p.nom), tri: parsePhaseIsTri(p.nom) }))
      .filter(x => x.kw != null && x.kw > 0)
      .sort((a, b) => a.kw - b.kw || a.p.id - b.p.id)
    if (!cands.length) return null
    let valid = cands.filter(x => x.kw >= threshold)
    if (!valid.length) valid = [cands[cands.length - 1]]
    const bestPower = valid[0].kw
    const same = valid.filter(x => x.kw === bestPower)
    const preferTri = bestPower >= 10
    const preferred = same.filter(x => x.tri === preferTri)
    return (preferred[0] ?? same[0])
  }
  const inverterQty = (kw) =>
    (!kw || kw >= threshold) ? 1 : Math.max(1, Math.ceil(kwp / kw))

  const reseau = pickInverter(byType.onduleur_reseau)
  const hybride = pickInverter(byType.onduleur_hybride)

  // Panneaux : wattage saisi (défaut 710 → Canadien Solar 710 du catalogue)
  const panels = (byType.panneau ?? [])
    .map(p => ({ p, w: parseWatt(p.nom) }))
    .filter(x => x.w != null)
  let panel = panels.filter(x => x.w === parseFloat(panelW))
    .sort((a, b) => (_norm(a.p.nom).includes('canadien') ? -1 : 1) - (_norm(b.p.nom).includes('canadien') ? -1 : 1))[0]
  if (!panel && panels.length) {
    panel = [...panels].sort((a, b) =>
      Math.abs(a.w - panelW) - Math.abs(b.w - panelW))[0]
  }

  // Batteries : cible = kWc arrondi au multiple de 5 (min 5 kWh),
  // ligne 1 = Deyness 5 kWh (qté nb_5), ligne 2 = Deyness 10 kWh (qté nb_10).
  const target = Math.max(5, Math.round(kwp / 5) * 5)
  let nb10 = Math.floor(target / 10)
  let nb5 = (target % 10) >= 5 ? 1 : 0
  const bats = (byType.batterie ?? []).map(p => ({ p, cap: parseKwh(p.nom) }))
  const deyness = bats.filter(x => _norm(x.p.nom).includes('deyness'))
  const batPool = deyness.length ? deyness : bats
  const bat5 = batPool.find(x => x.cap === 5)
  const bat10 = batPool.find(x => x.cap === 10)
  if (!bat10 && bat5 && nb10 > 0) {
    // pas de module 10 kWh au catalogue → tout en modules 5 kWh
    nb5 = Math.max(1, Math.round(target / 5))
    nb10 = 0
  }

  // Structures : type choisi par radio, 1 par panneau (prix catalogue)
  const structures = byType.structure ?? []
  const wanted = structureType === 'aluminium' ? 'alu' : 'acier'
  const other = structureType === 'aluminium' ? 'acier' : 'alu'
  const structChosen = structures.find(p => _norm(p.nom).includes(wanted)) ?? null
  const structOther = structures.find(p => _norm(p.nom).includes(other)) ?? null

  // Accessoires / Tableau / Installation : prix indexés sur la puissance
  // (blocs de 5 kWc), exactement comme auto_fill_from_power. TTC.
  const blocks = Math.max(1, Math.round(kwp / 5))
  const prixAccessoires = blocks * 1000
  const prixTableau = blocks * 1500
  const prixInstallation = (blocks + 1) * 2400

  // Smart Meter + Wifi Dongle : qté 1 dès qu'un onduleur réseau est retenu
  const smQty = reseau ? 1 : 0
  const wifiQty = reseau ? 1 : 0

  const first = (type) => (byType[type] ?? [])[0] ?? null
  const row = (p, designation, quantite, ttcOverride = null) =>
    p ? lineFrom(p, quantite, ttcOverride)
      : { ...placeholder(designation, quantite), prix_unit_ttc: ttcOverride ?? 0 }

  const acierRow = structureType === 'aluminium'
    ? row(structOther, 'Structures acier', 0)
    : row(structChosen, 'Structures acier', nbPanneaux)
  const aluRow = structureType === 'aluminium'
    ? row(structChosen, 'Structures aluminium', nbPanneaux)
    : row(structOther, 'Structures aluminium', 0)

  return [
    row(reseau?.p ?? null, 'Onduleur réseau', reseau ? inverterQty(reseau.kw) : 1),
    row(hybride?.p ?? null, 'Onduleur hybride', hybride ? Math.max(1, inverterQty(hybride.kw)) : 1),
    row(first('smart_meter'), 'Smart Meter', smQty),
    row(first('wifi_dongle'), 'Wifi Dongle', wifiQty),
    row(panel?.p ?? null, 'Panneaux', nbPanneaux),
    row(bat5?.p ?? null, 'Batterie', nb5),
    row(bat10?.p ?? null, 'Batterie', nb10),
    acierRow,
    aluRow,
    row(first('socle'), 'Socles', nbPanneaux * 2),
    row(first('accessoires'), 'Accessoires', 1, prixAccessoires),
    row(first('tableau'), 'Tableau De Protection AC/DC', 1, prixTableau),
    row(first('installation'), 'Installation', 1, prixInstallation),
    row(first('transport'), 'Transport', 1),
    row(first('suivi'), 'Suivi journalier, maintenance chaque 12 mois pendent 2 ans', 0),
  ]
}
