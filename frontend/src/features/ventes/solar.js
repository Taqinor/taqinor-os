// Solar math + catalogue auto-fill, ported from RedaSolar/devis-simulator
// (constants.py, roi_router.py, autofill_router.py / autofill.py, app.js).
// Pure functions, no I/O. Powers the live ROI preview and the auto-fill on the
// quote-generator screen. The premium PDF engine computes its own figures
// server-side (apps/ventes/quote_engine) — this module never feeds the PDF.

// ── Constantes Maroc (irradiance GHI mensuelle + tarif ONEE) ──────────────────
export const GHI = [
  83.99, 96.79, 133.43, 155.30, 175.28, 179.62,
  179.56, 161.17, 137.03, 111.59, 81.91, 74.61,
]
export const MONTHS_FR = [
  'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
  'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc',
]
export const EFFICIENCY = 0.8 // rendement global
export const KWH_PRICE = 1.75 // MAD/kWh ONEE — usage interne, jamais affiché

// ── Estimation des factures mensuelles depuis hiver/été ──────────────────────
export function interpolerFactures(hiver, ete) {
  if (!ete || ete <= 0) return Array(12).fill(hiver)
  const premiere = Array.from({ length: 7 }, (_, i) => hiver + (ete - hiver) / 6 * i)
  const seconde = Array.from({ length: 5 }, (_, i) => ete - (ete - hiver) / 4 * i)
  return [...premiere, ...seconde]
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
      month: MONTHS_FR[i],
      facture: Math.round(bills[i] * 100) / 100,
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
  if (n.includes('accessoire')) return 'accessoires'
  if (n.includes('tableau')) return 'tableau'
  if (n.includes('installation')) return 'installation'
  if (n.includes('transport')) return 'transport'
  return null
}

// Capacité batterie totale depuis les lignes (port de app.js — défaut 5 kWh/ligne)
export function batteryKwhFromLines(lines) {
  return lines.reduce((sum, l) => {
    if (!isBattery(l.designation)) return sum
    const qty = parseFloat(l.quantite) || 0
    return sum + qty * (parseKwh(l.designation) ?? 5.0)
  }, 0)
}

// ── Totaux par option, TTC (port de updateTotals de app.js) ──────────────────
// Option 1 SANS batterie : exclut Batterie + Onduleur hybride.
// Option 2 AVEC batterie : exclut Onduleur réseau.
export function optionTotalsTTC(lines, tauxTva, discountPct) {
  const ttc = (l) => {
    const qte = parseFloat(l.quantite) || 0
    const pu = parseFloat(l.prix_unitaire) || 0
    const rem = parseFloat(l.remise) || 0
    return qte * pu * (1 - rem / 100) * (1 + (parseFloat(tauxTva) || 0) / 100)
  }
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

// ── Auto-remplissage depuis le catalogue stock (port de autofill.py) ──────────
// `produits` : produits du module stock de l'entreprise. Retourne des lignes
// prêtes pour l'API devis : { produit, designation, quantite, prix_unitaire, remise }.
export function autoFillLines(produits, { kwp, panelW, structureType }) {
  if (!kwp || kwp <= 0) return []
  const byType = {}
  for (const p of produits) {
    const type = classifyProduct(p.nom)
    if (!type) continue
    if (!byType[type]) byType[type] = []
    byType[type].push(p)
  }

  const lines = []
  const pushLine = (p, quantite, prixOverride = null) => {
    lines.push({
      produit: p.id,
      designation: p.nom,
      quantite,
      prix_unitaire: prixOverride != null ? prixOverride : parseFloat(p.prix_vente) || 0,
      remise: 0,
    })
  }

  const nbPanneaux = Math.max(1, Math.round(kwp * 1000 / panelW))

  // Panneaux : produit dont le wattage est le plus proche de la valeur saisie
  const panneaux = (byType.panneau ?? [])
    .map(p => ({ p, w: parseWatt(p.nom) }))
    .filter(x => x.w != null)
    .sort((a, b) => Math.abs(a.w - panelW) - Math.abs(b.w - panelW))
  if (panneaux.length) pushLine(panneaux[0].p, nbPanneaux)
  else if ((byType.panneau ?? []).length) pushLine(byType.panneau[0], nbPanneaux)

  // Onduleurs : plus petit modèle couvrant >= 80 % de la puissance, sinon le
  // plus gros disponible ; quantité = 1 ou ceil(kwp / puissance onduleur).
  const pickInverter = (cands) => {
    const withKw = cands
      .map(p => ({ p, kw: parseKw(p.nom) }))
      .filter(x => x.kw != null && x.kw > 0)
      .sort((a, b) => a.kw - b.kw)
    if (!withKw.length) return cands.length ? { p: cands[0], kw: null } : null
    const threshold = kwp * 0.8
    return withKw.find(x => x.kw >= threshold) ?? withKw[withKw.length - 1]
  }
  const inverterQty = (kw) => {
    if (!kw || kw >= kwp * 0.8) return 1
    return Math.max(1, Math.ceil(kwp / kw))
  }
  const reseau = pickInverter(byType.onduleur_reseau ?? [])
  if (reseau) pushLine(reseau.p, inverterQty(reseau.kw))
  const hybride = pickInverter(byType.onduleur_hybride ?? [])
  if (hybride) pushLine(hybride.p, inverterQty(hybride.kw))

  // Batteries : capacité cible = puissance arrondie au multiple de 5 (min 5 kWh),
  // composée en modules 10 kWh + 5 kWh quand le catalogue les propose.
  const batteries = (byType.batterie ?? [])
    .map(p => ({ p, cap: parseKwh(p.nom) }))
    .filter(x => x.cap != null && x.cap > 0)
  if (batteries.length) {
    const target = Math.max(5, Math.round(kwp / 5) * 5)
    const bat10 = batteries.find(x => x.cap === 10)
    const bat5 = batteries.find(x => x.cap === 5)
    if (bat10 || bat5) {
      const nb10 = Math.floor(target / 10)
      const nb5 = (target % 10) >= 5 ? 1 : 0
      if (bat10 && nb10 > 0) pushLine(bat10.p, nb10)
      if (bat5 && (nb5 > 0 || (!bat10 && nb10 > 0))) {
        // pas de module 10 kWh au catalogue → tout en modules 5 kWh
        pushLine(bat5.p, bat10 ? nb5 : Math.max(1, Math.round(target / 5)))
      }
    } else {
      const best = batteries.sort((a, b) => b.cap - a.cap)[0]
      pushLine(best.p, Math.max(1, Math.round(target / best.cap)))
    }
  }

  // Structures : type choisi par l'utilisateur, 1 par panneau
  const structures = byType.structure ?? []
  const wanted = structureType === 'aluminium' ? 'alu' : 'acier'
  const struct = structures.find(p => _norm(p.nom).includes(wanted)) ?? structures[0]
  if (struct) pushLine(struct, nbPanneaux)

  // Socles : 2 par panneau
  if ((byType.socle ?? []).length) pushLine(byType.socle[0], nbPanneaux * 2)

  // Accessoires / Tableau / Installation : prix indexés sur la puissance
  // (blocs de 5 kWc, TTC dans le simulateur → converti en HT, TVA 20 %)
  const blocks = Math.max(1, Math.round(kwp / 5))
  const htFromTtc = (ttc) => Math.round(ttc / 1.2 * 100) / 100
  if ((byType.accessoires ?? []).length) {
    pushLine(byType.accessoires[0], 1, htFromTtc(blocks * 1000))
  }
  if ((byType.tableau ?? []).length) {
    pushLine(byType.tableau[0], 1, htFromTtc(blocks * 1500))
  }
  if ((byType.installation ?? []).length) {
    pushLine(byType.installation[0], 1, htFromTtc((blocks + 1) * 2400))
  }
  if ((byType.transport ?? []).length) pushLine(byType.transport[0], 1)

  return lines
}
