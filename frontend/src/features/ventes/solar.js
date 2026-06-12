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

// ── Catégories du catalogue simulateur (clés de brand_catalog.json) ──────────
// Le sélecteur de produits est groupé exactement selon ces catégories.
export const PRODUCT_CATEGORIES = [
  ['onduleur_reseau', 'Onduleur Injection'],
  ['onduleur_hybride', 'Onduleur Hybride'],
  ['panneau', 'Panneaux'],
  ['batterie', 'Batterie'],
  ['structure_acier', 'Structures acier'],
  ['structure_alu', 'Structures aluminium'],
  ['socle', 'Socles'],
  ['smart_meter', 'Smart Meter'],
  ['wifi_dongle', 'Wifi Dongle'],
  ['accessoires', 'Accessoires'],
  ['tableau', 'Tableau De Protection AC/DC'],
  ['installation', 'Installation'],
  ['transport', 'Transport'],
  ['suivi', 'Suivi journalier, maintenance chaque 12 mois pendent 2 ans'],
]

export function groupProduitsByCategory(produits) {
  const buckets = new Map(PRODUCT_CATEGORIES.map(([key]) => [key, []]))
  const autres = []
  for (const p of produits) {
    let type = classifyProduct(p.nom)
    if (type === 'structure') {
      type = _norm(p.nom).includes('alu') ? 'structure_alu' : 'structure_acier'
    }
    if (type && buckets.has(type)) buckets.get(type).push(p)
    else autres.push(p)
  }
  const groups = PRODUCT_CATEGORIES
    .map(([key, label]) => ({ label, items: buckets.get(key) }))
    .filter(g => g.items.length)
  if (autres.length) groups.push({ label: 'Autres', items: autres })
  return groups
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

// ══ Multi-marchés (2026-06) ═══════════════════════════════════════════════════

// ── Étude industrielle / commerciale (autoconsommation) ──────────────────────
export function computeEtudeIndustrielle({ kwp, consoMensuelleKwh, dayUsagePct, totalTtc }) {
  if (!kwp || kwp <= 0) return null
  const prodM = GHI.map(g => g * kwp * EFFICIENCY)
  const prodA = prodM.reduce((a, b) => a + b, 0)
  const consoMois = parseFloat(consoMensuelleKwh) || 0
  const consoA = consoMois > 0 ? consoMois * 12 : 0
  const dayPct = ((parseFloat(dayUsagePct) || 80)) / 100
  let autoconsomme, tauxAuto, tauxCouv = null
  if (consoA > 0) {
    // énergie solaire réellement consommée sur site (part diurne de la conso)
    autoconsomme = Math.min(prodA, consoA * dayPct)
    tauxAuto = prodA > 0 ? (autoconsomme / prodA) * 100 : 0
    tauxCouv = (autoconsomme / consoA) * 100
  } else {
    autoconsomme = prodA * dayPct
    tauxAuto = dayPct * 100
  }
  const economies = autoconsomme * KWH_PRICE
  const payback = (economies > 0 && totalTtc > 0)
    ? Math.round(totalTtc / economies * 10) / 10 : null
  return {
    kwc: Math.round(kwp * 100) / 100,
    production_annuelle: Math.round(prodA),
    conso_annuelle: consoA ? Math.round(consoA) : null,
    taux_autoconso: Math.round(tauxAuto * 10) / 10,
    taux_couverture: tauxCouv != null ? Math.round(tauxCouv * 10) / 10 : null,
    economies_annuelles: Math.round(economies),
    payback,
    prix_kwc: (kwp > 0 && totalTtc > 0) ? Math.round(totalTtc / kwp) : null,
    prod_mensuelle: prodM.map(v => Math.round(v)),
    conso_mensuelle: consoA ? Array(12).fill(Math.round(consoMois)) : null,
  }
}

// ── Pompage solaire (mode Agricole) ───────────────────────────────────────────
export const CV_TO_KW = 0.7355
// Heures de pompage effectives par défaut (champ 1.4× surdimensionné →
// la pompe tourne à régime nominal bien au-delà des heures équivalentes
// plein-soleil ; ~7 h/jour est l'hypothèse marché retenue — modifiable).
export const HEURES_POMPAGE_DEFAUT = 7

// Champ PV ≈ 1.4 × puissance pompe (approche marché 1.3–1.5×), panneaux 710 W
export function champFromKw(kw) {
  const champKw = Math.round(kw * 1.4 * 100) / 100
  const nbPanneaux = Math.max(2, Math.ceil(champKw * 1000 / 710))
  return {
    kw: Math.round(kw * 100) / 100,
    champKw,
    nbPanneaux,
    champKwc: Math.round(nbPanneaux * 710 / 10) / 100,
  }
}

export function computePompage(cv) {
  return champFromKw((parseFloat(cv) || 0) * CV_TO_KW)
}

// ── Courbe de performance : débit délivré (m³/h) à une HMT donnée ─────────────
// courbe = { debits_m3h: [0, 12, ...], hmt_m: [91, 85, ...] } — la HMT décroît
// quand le débit monte. Interpolation linéaire entre les points constructeur.
export function debitAtHmt(courbe, hmt) {
  const H = parseFloat(hmt)
  if (!courbe || !Array.isArray(courbe.debits_m3h) || !Array.isArray(courbe.hmt_m)) return null
  const d = courbe.debits_m3h.map(Number)
  const h = courbe.hmt_m.map(Number)
  if (d.length < 2 || d.length !== h.length || !(H > 0)) return null
  if (H > h[0]) return 0                       // au-delà de la capacité de la pompe
  if (H <= h[h.length - 1]) return d[d.length - 1]  // borné au dernier point mesuré
  for (let i = 0; i < h.length - 1; i++) {
    if (H <= h[i] && H > h[i + 1]) {
      const t = (h[i] - H) / (h[i] - h[i + 1])
      return Math.round((d[i] + t * (d[i + 1] - d[i])) * 10) / 10
    }
  }
  return null
}

const _hasPrix = (p) => (parseFloat(p.prix_vente) || 0) > 0

// Pompe à courbe : la plus petite (kW) qui délivre ≥ le débit souhaité (m³/h)
// à la HMT demandée. Jamais de produit sans prix sur un devis : si seules des
// pompes « prix à renseigner » conviennent, on le dit au lieu d'en chiffrer une.
export function selectPompeByCurve(produits, { hmt, debit, typePompe }) {
  const H = parseFloat(hmt)
  const Q = parseFloat(debit)
  if (!(H > 0) || !(Q > 0)) return { pump: null, sansPrix: [] }
  const wantSurface = typePompe === 'surface'
  const cands = produits
    .map(p => ({
      p, n: _norm(p.nom),
      kw: parseFloat(p.pompe_kw) || 0,
      q: debitAtHmt(p.courbe_pompe, H),
    }))
    .filter(x => x.p.courbe_pompe && x.kw > 0 && x.q != null && x.q >= Q)
    .filter(x => wantSurface ? x.n.includes('surface') : x.n.includes('immerg'))
    .sort((a, b) => a.kw - b.kw
      || (parseFloat(a.p.prix_vente) || 0) - (parseFloat(b.p.prix_vente) || 0))
  const priced = cands.filter(x => _hasPrix(x.p))
  if (priced.length) {
    const best = priced[0]
    return { pump: best.p, kw: best.kw, debitHmt: best.q, sansPrix: [] }
  }
  return { pump: null, sansPrix: cands.map(x => x.p.nom) }
}

// Variateur VEICHI : le plus petit dont kW ≥ kW pompe, tension assortie
// (mono 220 V / tri 380 V). L'afficheur (sans kW) n'est jamais candidat.
export function selectVariateurVeichi(produits, kw, alim) {
  const want = alim === 'mono' ? 220 : 380
  const volts = (p) => {
    if (p.tension_v) return Number(p.tension_v)
    if (/220\s*v/i.test(p.nom)) return 220
    if (/380\s*v/i.test(p.nom)) return 380
    return null
  }
  const cands = produits
    .map(p => ({ p, n: _norm(p.nom), kw: parseFloat(p.pompe_kw) || 0, v: volts(p) }))
    .filter(x => x.n.includes('variateur') && !x.n.includes('afficheur')
      && x.kw > 0 && x.v === want && _hasPrix(x.p))
    .sort((a, b) => a.kw - b.kw
      || (parseFloat(a.p.prix_vente) || 0) - (parseFloat(b.p.prix_vente) || 0))
  return cands.find(x => x.kw >= kw)?.p ?? cands[cands.length - 1]?.p ?? null
}

export function findAfficheurVariateur(produits) {
  return produits.find(p =>
    _norm(p.nom).includes('afficheur') && _hasPrix(p)) ?? null
}

// ── Dimensionnement pompage unifié (source unique écran + devis + PDF) ────────
// Si HMT + débit souhaité sont renseignés et qu'une pompe à courbe convient,
// elle pilote tout (kW réels, débit interpolé, m³/jour). Sinon : sélection
// historique par CV, débit manuel, pas de m³/jour (jamais de chiffre inventé).
export function pompageSelection(produits, { cv, typePompe, hmt, debit, heures }) {
  const sel = selectPompeByCurve(produits, { hmt, debit, typePompe })
  if (sel.pump) {
    const kw = sel.kw
    const cvP = parseFloat(sel.pump.pompe_cv)
      || Math.round(kw / CV_TO_KW * 10) / 10
    const hrs = parseFloat(heures) || 0
    return {
      mode: 'courbe',
      pump: sel.pump,
      cv: cvP,
      kw,
      dims: champFromKw(kw),
      debitHmt: sel.debitHmt,
      m3Jour: hrs > 0 ? Math.round(sel.debitHmt * hrs) : null,
      sansPrix: [],
    }
  }
  const cvNum = parseFloat(cv) || 0
  return {
    mode: 'cv',
    pump: null,
    cv: cvNum,
    kw: Math.round(cvNum * CV_TO_KW * 100) / 100,
    dims: computePompage(cv),
    debitHmt: null,
    m3Jour: null,
    sansPrix: sel.sansPrix,
  }
}

const _isPompe = (n) => n.includes('pompe ') || n.startsWith('pompe')
const _isVfdPompage = (n) =>
  (n.includes('variateur') || n.includes('coffret')) && n.includes('pompage')
const _isCableMetre = (n) => n.includes('cable') && n.includes('metre')

// Équipement pompage : pompe + variateur assorti (+ afficheur) + champ PV
// + structures/socles + câble à la distance — PAS de batterie ni d'onduleur
// réseau/hybride. Jamais de produit « prix à renseigner » sur un devis.
export function autoFillPompage(produits, { cv, alim, typePompe, distance, structureType,
                                            hmt, debit, heures }) {
  const sel = pompageSelection(produits, { cv, alim, typePompe, hmt, debit, heures })
  const cvNum = sel.cv
  if (cvNum <= 0) return []
  const wantTri = alim === 'tri'
  const wantSurface = typePompe === 'surface'

  let pump = null
  if (sel.pump) {
    pump = { p: sel.pump }
  } else if (!sel.sansPrix.length) {
    // Sélection historique par CV (pompes sans courbe, débit manuel)
    const pumps = produits
      .map(p => ({ p, n: _norm(p.nom), cv: parseFloat(p.pompe_cv) || null, tri: parsePhaseIsTri(p.nom) }))
      .filter(x => _isPompe(x.n) && !_isVfdPompage(x.n) && x.cv != null && _hasPrix(x.p))
      .filter(x => wantSurface ? x.n.includes('surface') : x.n.includes('immerg'))
      .sort((a, b) => a.cv - b.cv || a.p.id - b.p.id)
    pump = pumps.find(x => x.cv === cvNum && x.tri === wantTri)
      ?? pumps.find(x => x.cv === cvNum)
      ?? pumps.find(x => x.cv >= cvNum)
      ?? pumps[pumps.length - 1] ?? null
  }
  // sel.sansPrix non vide → seules des pompes sans prix conviennent :
  // on n'en chiffre AUCUNE (l'écran l'explique), le reste du système est rempli.

  // Variateur : VEICHI par kW + tension d'abord, anciens coffrets par CV sinon
  let vfdP = selectVariateurVeichi(produits, sel.kw, alim)
  if (!vfdP) {
    const vfds = produits
      .map(p => ({ p, n: _norm(p.nom), cv: parseFloat(p.pompe_cv) || null, tri: parsePhaseIsTri(p.nom) }))
      .filter(x => _isVfdPompage(x.n) && x.cv != null && _hasPrix(x.p))
      .sort((a, b) => a.cv - b.cv || a.p.id - b.p.id)
    vfdP = (vfds.find(x => x.cv >= cvNum && x.tri === wantTri)
      ?? vfds.find(x => x.cv >= cvNum)
      ?? vfds[vfds.length - 1] ?? null)?.p ?? null
  }
  const afficheur = vfdP && /veichi/i.test(vfdP.nom) ? findAfficheurVariateur(produits) : null

  const dims = sel.dims
  const byType = {}
  for (const p of produits) {
    const t = classifyProduct(p.nom)
    if (!t) continue
    if (!byType[t]) byType[t] = []
    byType[t].push(p)
  }
  const panels = (byType.panneau ?? [])
    .map(p => ({ p, w: parseWatt(p.nom) }))
    .filter(x => x.w === 710)
  const panel = panels[0]?.p ?? (byType.panneau ?? [])[0] ?? null

  const structures = byType.structure ?? []
  const wanted = structureType === 'aluminium' ? 'alu' : 'acier'
  const struct = structures.find(p => _norm(p.nom).includes(wanted)) ?? structures[0] ?? null

  const cable = produits.find(p => _isCableMetre(_norm(p.nom))) ?? null
  const distM = parseFloat(distance) || 0

  const line = (p, designation, quantite) => ({
    produit: p ? String(p.id) : '',
    designation: p ? p.nom : designation,
    quantite,
    prix_unit_ttc: p ? ttcFromHt(p.prix_vente) : 0,
  })

  const rows = []
  if (pump?.p) rows.push(line(pump.p, 'Pompe solaire', 1))
  if (vfdP) rows.push(line(vfdP, 'Variateur solaire', 1))
  if (afficheur) rows.push(line(afficheur, 'Afficheur variateur', 1))
  rows.push(
    line(panel, 'Panneaux', dims.nbPanneaux),
    line(struct, 'Structures', dims.nbPanneaux),
  )
  if ((byType.socle ?? []).length) rows.push(line(byType.socle[0], 'Socles', dims.nbPanneaux * 2))
  if (cable && distM > 0) rows.push(line(cable, 'Câble solaire (m)', distM))
  if ((byType.installation ?? []).length) rows.push(line(byType.installation[0], 'Installation', 1))
  if ((byType.transport ?? []).length) rows.push(line(byType.transport[0], 'Transport', 1))
  return rows
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

// Coût d'achat TTC des lignes dont le produit a un prix d'achat renseigné.
// Retourne null si AUCUN prix d'achat n'existe (alors on n'affiche rien).
export function computeBuyCost(lines, produits) {
  const byId = new Map(produits.map(p => [String(p.id), p]))
  let cost = 0
  let any = false
  for (const l of lines) {
    const p = byId.get(String(l.produit))
    const achat = p ? (parseFloat(p.prix_achat) || 0) : 0
    if (achat > 0) {
      any = true
      cost += (parseFloat(l.quantite) || 0) * achat * 1.2
    }
  }
  return any ? Math.round(cost) : null
}

// ── Disponibilité de l'option « avec batterie » ───────────────────────────────
// Règle dure (alignée moteur PDF) : une option ne se rend jamais sans onduleur.
// Composer des hybrides en parallèle est raisonnable jusqu'à MAX_HYBRID_UNITS.
export const MAX_HYBRID_UNITS = 8

export function avecBatterieAvailability(lines, produits, kwp) {
  const hasHyb = lines.some(l =>
    isHybridInverter(l.designation) && parseFloat(l.quantite) > 0)
  const hasBat = lines.some(l =>
    isBattery(l.designation) && parseFloat(l.quantite) > 0)
  if (hasHyb && hasBat) return { available: true }
  // Diagnostic : le plus gros hybride du stock suffit-il, même composé ?
  const maxKw = Math.max(0, ...produits
    .filter(p => isHybridInverter(p.nom))
    .map(p => parseKw(p.nom) || 0))
  const unitsNeeded = maxKw > 0 ? Math.ceil((kwp || 0) / maxKw) : Infinity
  let reason
  if (!hasHyb && maxKw > 0 && unitsNeeded > MAX_HYBRID_UNITS) {
    reason = `puissance requise ${kwp} kWc — il faudrait ${unitsNeeded} onduleurs `
      + `hybrides de ${maxKw} kW en parallèle (déraisonnable au-delà de ${MAX_HYBRID_UNITS})`
  } else if (!hasHyb) {
    reason = 'aucun onduleur hybride dans la liste'
  } else {
    reason = 'aucune batterie dans la liste'
  }
  return { available: false, reason }
}
