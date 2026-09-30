// QAH-PROP (feature #3 du lot QA « détecter les bugs AVANT la production ») —
// PROPRIÉTÉS MÉTAMORPHIQUES / DE DIRECTION sur les VRAIES fonctions de calcul
// de `solar.js`, avec des entrées GÉNÉRÉES (PRNG seedé, aucun `Math.random()`,
// aucune dépendance nouvelle — `fast-check` est interdit par la règle du
// dépôt) au lieu d'exemples fixes.
//
// POURQUOI. Un exemple fixe ne prouve que lui-même : les huit bugs de tarifs /
// factures / économies trouvés avant ce lot vivaient tous dans une BRANCHE que
// personne n'avait choisie comme exemple (aucun distributeur, « autre »,
// facture nulle, été ≠ hiver…). Ici chaque propriété est une LOI qui doit
// tenir pour TOUTE entrée valide ; les générateurs visent exprès les branches
// limites (voir `genFactures` / `genUtility`).
//
// RÈGLE SUR LES VRAIS BUGS (fondateur). Une propriété qui échoue sur une
// entrée LÉGITIME est un BUG RÉEL : on ne corrige PAS le code de production ici
// et on n'affaiblit PAS la propriété — on l'enregistre dans `KNOWN_VIOLATIONS`
// avec son exemple minimal. Un test exige que chaque violation listée SE
// REPRODUISE encore : une violation corrigée doit donc être RETIRÉE de la liste
// (la liste ne peut que rétrécir, comme `KNOWN_DIVERGENCES` côté Python).
//
// Run : `node --test src/features/ventes/solar.properties.test.mjs`
// (le runner `node --test "src/**/*.test.mjs"` de la CI le collecte tel quel).
import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  ONEE_TRANCHES, FALLBACK_KWH_PRICE,
  monthlyBillFromKwh, kwhFromBill, consoAnnuelleDepuisFactures,
  factureMad, tppanMad, twoBillsSavings, computeROI, computeCashflowPayback,
  computeEtudeIndustrielle, productibleForCity, PRODUCTIBLE_NET_FACTOR,
  panneauxPourKwc, estimerKwcDepuisFacture, optimalKwcByPayback,
  totauxCanoniquesTtc, ttcFromHt, htFromTtc,
  debitAtHmt, selectPompeByCurve, pompageSelection, autoFillPompage,
  champFromKw, isBattery, isAnyInverter, isHybridInverter, isReseauInverter,
  isOffgridInverter,
} from './solar.js'
import { forAll, premierNonFini } from './proprietes.aleatoire.js'

// ── VIOLATIONS RÉELLES CONNUES — jamais un test assoupli ─────────────────────
// id → { resume, exemple }. Le test `KNOWN_VIOLATIONS se reproduisent encore`
// exige que chacune échoue toujours ; une violation corrigée DOIT être retirée.
// Chaque entrée a son propre test `verifier(id, …)` ci-dessous.
export const KNOWN_VIOLATIONS = {
  'ERR-QAH-PROP-JS-CONSO-FACTURE-TOTALE': {
    resume: 'consoAnnuelleDepuisFactures inverse une facture TOTALE avec le '
      + 'barème ÉNERGIE SEULE (kwhFromBill), alors que factureMad/twoBillsSavings '
      + 'retarifent avec lignes fixes + TPPAN : re-tarifer la consommation '
      + 'dérivée ne redonne PAS les factures saisies (I9 de l\'audit COUV-HOR).',
    exemple: 'factures = 12 × 500 MAD, distributeur « onee » → '
      + 'twoBillsSavings(…).factureSans ≠ 6 000',
  },
  'ERR-QAH-PROP-JS-KWH-HORS-PLAGE': {
    resume: 'kwhFromBill ne porte PAS la garde QJR158(e) du miroir Python : une '
      + 'facture qu\'aucune consommation ≤ 1e6 kWh/mois ne produit rend ~1e6 kWh '
      + '(la borne de boucle) présentés comme un résultat exact '
      + '(estimation:false).',
    exemple: 'kwhFromBill(5_000_000, \'onee\') → ≈ 1 000 000 kWh, estimation:false',
  },
}
// (ERR-QAH-PROP-JS-TOTAUX-REMISE-100-NEGATIF corrigée : HT net borné à 0 dans
// totauxCanoniquesTtc, comme selectors._canonical_totaux — test ci-dessous.)
const CONNUE = (id) => Object.prototype.hasOwnProperty.call(KNOWN_VIOLATIONS, id)

// `verifier` : propriété attendue VRAIE, sauf si son id est dans
// KNOWN_VIOLATIONS — alors elle doit encore ÉCHOUER (sinon : la retirer).
function verifier(id, nom, params) {
  const echec = forAll(params)
  if (CONNUE(id)) {
    assert.ok(echec, `${id} : la violation connue « ${nom} » ne se reproduit plus — `
      + 'RETIRER l\'entrée de KNOWN_VIOLATIONS (la liste ne peut que rétrécir).')
    return
  }
  if (echec) {
    assert.fail(`PROPRIÉTÉ VIOLÉE « ${nom} » (seed=${echec.seed}, essai=${echec.essai}) : `
      + `${echec.message}\ncas minimal : ${JSON.stringify(echec.cas_minimal)}`)
  }
}

// ── Générateurs qui VISENT les branches limites ──────────────────────────────
// Distributeurs : aucun (undefined/''/blanc), les trois nommés, « autre », des
// SRM régionales, casse mixte — toutes les branches de `resolveTranches`.
const UTILITIES = [undefined, null, '', '   ', 'onee', 'ONEE', 'lydec', 'redal',
  'autre', 'srm-casablanca-settat', 'SRM Souss-Massa', 'Amendis']
const genUtility = (g) => g.pick(UTILITIES)
const NOMME = UTILITIES.filter((u) => String(u ?? '').trim())

// 12 factures : zéro partout, UN SEUL mois, été ≠ hiver, énormes, plates.
function genFactures(g) {
  const forme = g.pick(['plate', 'hiver_ete', 'aleatoire', 'un_mois', 'zeros', 'enorme', 'dix_mois'])
  const base = Math.round(g.logFloat(30, 6000))
  switch (forme) {
    case 'plate': return Array(12).fill(base)
    case 'hiver_ete': {
      const ete = Math.round(base * g.float(1.2, 3))
      return Array.from({ length: 12 }, (_, i) => (i >= 5 && i <= 8 ? ete : base))
    }
    case 'un_mois': {
      const f = Array(12).fill(0)
      f[g.int(0, 11)] = base
      return f
    }
    case 'zeros': return Array(12).fill(0)
    case 'enorme': return Array.from({ length: 12 }, () => Math.round(g.logFloat(1e4, 4e5)))
    case 'dix_mois': return Array.from({ length: 10 }, () => Math.round(g.logFloat(30, 6000)))
    default: return Array.from({ length: 12 }, () => Math.round(g.logFloat(30, 6000)))
  }
}

// Tables de tranches : la grille ONEE sélective + des grilles progressives
// aléatoires (barème vendeur collé à la main) + ouvertes / fermées.
function genTable(g) {
  if (g.bool(0.4)) return ONEE_TRANCHES
  const n = g.int(1, 6)
  let plafond = 0
  let prix = g.float(0.5, 1.2)
  const table = []
  for (let i = 0; i < n; i++) {
    plafond += g.int(30, 250)
    prix += g.float(0, 0.4) // prix non décroissants, comme un barème réel
    table.push([i === n - 1 && g.bool(0.7) ? null : plafond, Math.round(prix * 1e4) / 1e4])
  }
  return table
}

const RUNS = 250

// ══ 1. TARIFS PAR TRANCHE ════════════════════════════════════════════════════

test('facture mensuelle : monotone non décroissante en kWh, ≥ 0, finie, 0 kWh → 0 MAD', () => {
  verifier('', 'monthlyBillFromKwh monotone', {
    seed: 101, runs: RUNS,
    gen: (g) => ({ table: genTable(g), k1: g.logFloat(0.1, 5000), dk: g.float(0, 400) }),
    verifie: ({ table, k1, dk }) => {
      const a = monthlyBillFromKwh(k1, table)
      const b = monthlyBillFromKwh(k1 + dk, table)
      if (!Number.isFinite(a) || !Number.isFinite(b)) return `non fini ${a} ${b}`
      if (a < 0) return `facture négative ${a}`
      if (b + 1e-9 < a) return `facture(${k1 + dk})=${b} < facture(${k1})=${a}`
      if (monthlyBillFromKwh(0, table) !== 0) return 'facture(0) != 0'
      return null
    },
  })
})

test('la facture ne dépasse jamais « conso × tarif de la dernière tranche »', () => {
  verifier('', 'plafond de facture', {
    seed: 102, runs: RUNS,
    gen: (g) => ({ table: genTable(g), k: g.logFloat(1, 5000) }),
    verifie: ({ table, k }) => {
      const maxPrix = Math.max(...table.map((b) => b[1]))
      const f = monthlyBillFromKwh(k, table)
      // Le plancher sélectif (facture progressive au seuil) peut dépasser
      // k × prix pour k juste au-dessus du seuil : borne = max des deux.
      const seuil = table.selectif ? table.selectif.seuil : 0
      const borne = Math.max(k, seuil) * maxPrix + 1e-6
      return f <= borne ? null : `facture ${f} > borne ${borne}`
    },
  })
})

// ══ 2. FACTURES → CONSOMMATION (inversion) ═══════════════════════════════════

test('kwhFromBill est l\'INVERSE du barème pour chaque distributeur (aucun, SRM, autre, ONEE…)', () => {
  // Loi : k = kwhFromBill(b) ⇒ facture(k + 0,1) ≥ b − ε et facture(k − 0,1) ≤ b + ε
  // (inf{k : facture(k) ≥ b}, à l'arrondi 0,1 kWh près — un « trou » sélectif
  // est résolu à sa borne basse, jamais fabriqué). Sans distributeur : prix
  // plat FALLBACK_KWH_PRICE, estimation:true.
  verifier('', 'kwhFromBill inverse du barème', {
    seed: 201, runs: RUNS,
    gen: (g) => ({ bill: g.logFloat(1, 900000), utility: genUtility(g) }),
    verifie: ({ bill, utility }) => {
      const r = kwhFromBill(bill, utility)
      if (premierNonFini(r)) return `sortie non finie ${premierNonFini(r)}`
      const nomme = String(utility ?? '').trim() !== ''
      if (!nomme) {
        if (!r.estimation) return 'sans distributeur : estimation devrait être true'
        return Math.abs(r.kwhMensuel - bill / FALLBACK_KWH_PRICE) <= 0.051 ? null
          : `repli plat ${r.kwhMensuel} vs ${bill / FALLBACK_KWH_PRICE}`
      }
      if (r.estimation) return 'distributeur nommé : estimation devrait être false'
      const table = ONEE_TRANCHES
      const haut = monthlyBillFromKwh(r.kwhMensuel + 0.1, table)
      const bas = monthlyBillFromKwh(Math.max(0, r.kwhMensuel - 0.1), table)
      if (haut < bill - 1e-6) return `facture(k+0,1)=${haut} < ${bill}`
      if (bas > bill + 1e-6) return `facture(k-0,1)=${bas} > ${bill}`
      return null
    },
  })
})

test('kwhFromBill : monotone non décroissante en facture, table progressive vendeur comprise', () => {
  verifier('', 'kwhFromBill monotone', {
    seed: 202, runs: RUNS,
    gen: (g) => ({ table: genTable(g), b1: g.logFloat(1, 30000), db: g.float(0, 3000) }),
    verifie: ({ table, b1, db }) => {
      const a = kwhFromBill(b1, 'onee', table).kwhMensuel
      const b = kwhFromBill(b1 + db, 'onee', table).kwhMensuel
      return b + 0.1001 >= a ? null : `kwh(${b1 + db})=${b} < kwh(${b1})=${a}`
    },
  })
})

test('facture nulle / négative / illisible → 0 kWh étiqueté estimation, jamais NaN', () => {
  for (const bill of [0, -5, '', null, undefined, 'abc', NaN]) {
    for (const u of UTILITIES) {
      const r = kwhFromBill(bill, u)
      assert.equal(r.kwhMensuel, 0, `bill=${String(bill)} u=${String(u)}`)
      assert.equal(r.estimation, true)
    }
  }
})

test('consommation annuelle dérivée des factures : monotone (factures ↑ ⇒ conso ↑), finie, ≥ 0', () => {
  verifier('', 'conso monotone en factures', {
    seed: 203, runs: RUNS,
    gen: (g) => ({ f: genFactures(g), utility: genUtility(g), coef: g.float(1, 4) }),
    verifie: ({ f, utility, coef }) => {
      const a = consoAnnuelleDepuisFactures(f, utility)
      const b = consoAnnuelleDepuisFactures(f.map((x) => x * coef), utility)
      if (!Number.isFinite(a) || !Number.isFinite(b)) return `non fini ${a} ${b}`
      if (a < 0) return `conso négative ${a}`
      // arrondi final à l'entier (Math.round du total) : tolérance 1 kWh.
      return b + 1 >= a ? null : `conso(×${coef})=${b} < conso=${a}`
    },
  })
})

test('douze factures nulles → consommation 0 (l\'appelant OMET, il n\'invente pas)', () => {
  for (const u of UTILITIES) assert.equal(consoAnnuelleDepuisFactures(Array(12).fill(0), u), 0)
  assert.equal(consoAnnuelleDepuisFactures([], 'onee'), 0)
  assert.equal(consoAnnuelleDepuisFactures(null, 'onee'), 0)
})

test('aller-retour énergie-seule : facture → kWh → facture redonne la facture (par mois, distributeur nommé ou non)', () => {
  // Le SEUL aller-retour que ce module garantit est énergie-seule
  // (kwhFromBill ↔ monthlyBillFromKwh). Les lignes fixes + TPPAN sont l'objet
  // de la violation connue plus bas.
  verifier('', 'aller-retour énergie', {
    seed: 204, runs: RUNS,
    gen: (g) => ({ bills: genFactures(g), utility: g.pick(NOMME) }),
    verifie: ({ bills, utility }) => {
      for (const b of bills) {
        if (!(b > 0)) continue
        const k = kwhFromBill(b, utility).kwhMensuel
        const haut = monthlyBillFromKwh(k + 0.1, ONEE_TRANCHES)
        if (haut < b - 1e-6) return `mois ${b} : facture(k+0,1)=${haut}`
      }
      return null
    },
  })
})

test('KNOWN_VIOLATION ERR-QAH-PROP-JS-CONSO-FACTURE-TOTALE — re-tarifer la conso dérivée des factures redonne ces factures (tolérance 2 %)', () => {
  // Une facture SAISIE est un TOTAL (énergie + lignes fixes + TPPAN). La conso
  // dérivée puis re-tarifiée par le MÊME modèle que l'écran affiche
  // (twoBillsSavings → factureMad) devrait redonner ~ ces factures.
  verifier('ERR-QAH-PROP-JS-CONSO-FACTURE-TOTALE', 'facture_sans ≈ Σ factures', {
    seed: 205, runs: 120,
    gen: (g) => ({ montant: Math.round(g.logFloat(150, 4000)), utility: g.pick(NOMME) }),
    verifie: ({ montant, utility }) => {
      const factures = Array(12).fill(montant)
      const conso = consoAnnuelleDepuisFactures(factures, utility)
      if (!(conso > 0)) return null // hors sujet : rien à re-tarifer
      // production/ratio choisis pour que TOUTE la conso reste facturée « sans » :
      const r = twoBillsSavings(1e9, conso, 1e-9, utility)
      if (!r) return 'twoBillsSavings a rendu null'
      const attendu = montant * 12
      const ecart = Math.abs(r.factureSans - attendu) / attendu
      return ecart <= 0.02 ? null
        : `Σ factures saisies ${attendu} MAD vs facture_sans re-tarifée ${r.factureSans} (${(ecart * 100).toFixed(1)} %)`
    },
  })
})

test('KNOWN_VIOLATION ERR-QAH-PROP-JS-KWH-HORS-PLAGE — facture hors plage inversable ⇒ estimation, jamais la borne de boucle', () => {
  verifier('ERR-QAH-PROP-JS-KWH-HORS-PLAGE', 'facture hors plage ⇒ estimation', {
    seed: 206, runs: 80,
    gen: (g) => ({ bill: g.logFloat(2e6, 5e7), utility: g.pick(NOMME) }),
    verifie: ({ bill, utility }) => {
      const r = kwhFromBill(bill, utility)
      // Côté Python (QJR158 e) : kwh_mensuel = 0 et estimation = True.
      return (r.estimation === true && r.kwhMensuel === 0) ? null
        : `kwhFromBill(${bill}) = ${r.kwhMensuel} kWh, estimation=${r.estimation}`
    },
  })
})

// ══ 3. CONSOMMATION → FACTURE, ÉCONOMIES ═════════════════════════════════════

test('facture détaillée : composantes finies, total = énergie + fixes + TPPAN, monotone en kWh', () => {
  verifier('', 'factureMad', {
    seed: 301, runs: RUNS,
    gen: (g) => ({ kwh: g.logFloat(0.5, 4000), dk: g.float(0, 300), jours: g.pick([28, 30, 31]) }),
    verifie: ({ kwh, dk, jours }) => {
      const a = factureMad(kwh, ONEE_TRANCHES, jours)
      const b = factureMad(kwh + dk, ONEE_TRANCHES, jours)
      if (premierNonFini(a)) return `non fini ${premierNonFini(a)}`
      if (Math.abs(a.totalMad - (a.energieMad + a.locationEntretienMad + a.tppanMad)) > 1e-9) return 'total != somme'
      if (a.tppanMad < 0 || a.tppanMad > 100 + 1e-9) return `TPPAN hors [0,100] : ${a.tppanMad}`
      // la TPPAN est plafonnée et exonérée ≤ 50 kWh ; le total reste monotone
      // à jours FIXES.
      return b.totalMad + 1e-9 >= a.totalMad ? null : `total(${kwh + dk}) < total(${kwh})`
    },
  })
})

test('TPPAN : exonérée ≤ 50 kWh, plafonnée à 100 MAD, monotone', () => {
  verifier('', 'tppanMad', {
    seed: 302, runs: RUNS,
    gen: (g) => ({ k: g.float(0, 3000), dk: g.float(0, 500), jours: g.pick([28, 30, 31, 60]) }),
    verifie: ({ k, dk, jours }) => {
      const a = tppanMad(k, jours)
      const b = tppanMad(k + dk, jours)
      if (k <= 50 && a !== 0) return `TPPAN(${k}) devrait être 0`
      if (a < 0 || a > 100 + 1e-9) return `TPPAN hors bornes ${a}`
      return b + 1e-9 >= a ? null : `TPPAN non monotone ${a} → ${b}`
    },
  })
})

test('économies (deux factures) : 0 ≤ économie ≤ facture actuelle, avec ≤ sans, chaîne exacte au dirham, aucun NaN', () => {
  verifier('', 'twoBillsSavings bornes', {
    seed: 303, runs: RUNS,
    gen: (g) => ({
      prod: g.logFloat(200, 300000), conso: g.logFloat(200, 500000),
      ratio: g.pick([0.05, 0.3, 0.6, 0.85, 1, 1.5]) * g.float(0.9, 1.1),
      utility: g.pick(NOMME),
    }),
    verifie: ({ prod, conso, ratio, utility }) => {
      const r = twoBillsSavings(prod, conso, ratio, utility)
      if (r === null) return null // entrées non exploitables : l'appelant dégrade
      if (premierNonFini(r)) return `non fini ${premierNonFini(r)}`
      if (r.economie < 0) return `économie négative ${r.economie}`
      if (r.economie > r.factureSans) return `économie ${r.economie} > facture actuelle ${r.factureSans}`
      if (r.factureAvec > r.factureSans) return `facture avec ${r.factureAvec} > sans ${r.factureSans}`
      if (r.economie !== Math.max(0, r.factureSans - r.factureAvec)) return 'chaîne sans − avec ≠ économie'
      if (r.autoconsoKwh > Math.round(conso)) return `autoconso ${r.autoconsoKwh} > conso ${conso}`
      return null
    },
  })
})

test('économies : plus de production OU plus d\'autoconsommation ⇒ économie jamais plus basse', () => {
  verifier('', 'twoBillsSavings monotone', {
    seed: 304, runs: RUNS,
    gen: (g) => ({
      prod: g.logFloat(500, 100000), conso: g.logFloat(500, 100000),
      ratio: g.float(0.1, 0.95), dRatio: g.float(0, 0.3), dProd: g.float(0, 50000),
      utility: g.pick(NOMME),
    }),
    verifie: ({ prod, conso, ratio, dRatio, dProd, utility }) => {
      const base = twoBillsSavings(prod, conso, ratio, utility)
      const plusRatio = twoBillsSavings(prod, conso, ratio + dRatio, utility)
      const plusProd = twoBillsSavings(prod + dProd, conso, ratio, utility)
      if (!base || !plusRatio || !plusProd) return null
      // ±1 MAD : les deux factures sont arrondies au dirham.
      if (plusRatio.economie + 1 < base.economie) return `ratio ↑ : ${plusRatio.economie} < ${base.economie}`
      if (plusProd.economie + 1 < base.economie) return `production ↑ : ${plusProd.economie} < ${base.economie}`
      return null
    },
  })
})

test('sans consommation, sans production ou sans distributeur : twoBillsSavings rend null (jamais un chiffre inventé)', () => {
  assert.equal(twoBillsSavings(5000, 0, 0.6, 'onee'), null)
  assert.equal(twoBillsSavings(0, 5000, 0.6, 'onee'), null)
  assert.equal(twoBillsSavings(5000, 5000, 0, 'onee'), null)
  assert.equal(twoBillsSavings(5000, 5000, 0.6, undefined), null)
  assert.equal(twoBillsSavings(5000, 5000, 0.6, ''), null)
})

// ══ 4. ROI / PAYBACK / COUVERTURE ════════════════════════════════════════════

function genRoi(g) {
  const kwp = g.pick([1, 3, 5, 8, 10, 20, 50, 200]) * g.float(0.8, 1.2)
  const avecConso = g.bool(0.6)
  const utility = g.bool(0.75) ? g.pick(NOMME) : undefined
  return {
    kwp,
    factures: g.bool(0.85) ? genFactures(g).map((x) => Math.min(x, 1e5)) : undefined,
    dayUsagePct: g.pick([undefined, 10, 40, 60, 80, 100]),
    totalSans: Math.round(kwp * g.float(6000, 14000)),
    batteryKwh: g.pick([0, 0, 5, 10, 15.36]),
    consoAnnuelleKwh: avecConso ? Math.round(g.logFloat(500, 400000)) : undefined,
    utility,
    productible: g.pick([undefined, 1550, 1651, 1687]),
    kwhPrice: g.pick([undefined, 1.2, 1.75]),
    facteurAvec: g.float(1.05, 1.5),
  }
}
const roiDe = (c, kwp = c.kwp) => computeROI({
  kwp, factures: c.factures, dayUsagePct: c.dayUsagePct,
  totalSans: c.totalSans, totalAvec: Math.round(c.totalSans * c.facteurAvec),
  batteryKwh: c.batteryKwh, kwhPrice: c.kwhPrice,
  consoAnnuelleKwh: c.consoAnnuelleKwh, utility: c.utility, productible: c.productible,
})

test('computeROI : aucune sortie NaN/±inf, économies ≥ 0, avec ≥ sans, taux d\'autoconsommation dans [0,1], payback fini', () => {
  verifier('', 'computeROI bornes', {
    seed: 401, runs: RUNS,
    gen: genRoi,
    verifie: (c) => {
      const r = roiDe(c)
      const nf = premierNonFini(r)
      if (nf) return `sortie non finie : ${nf}`
      if (r.eco_annuelle_sans < 0 || r.eco_annuelle_avec < 0) return 'économie négative'
      if (r.eco_annuelle_avec + 1e-6 < r.eco_annuelle_sans) return `avec ${r.eco_annuelle_avec} < sans ${r.eco_annuelle_sans}`
      for (const k of ['autoconso_sans', 'autoconso_avec']) {
        if (r[k] < -1e-9 || r[k] > 1 + 1e-9) return `${k} hors [0,1] : ${r[k]}`
      }
      for (const k of ['payback_sans', 'payback_avec']) {
        if (r[k] !== null && !(r[k] > 0 && r[k] <= 25)) return `${k}=${r[k]} hors ]0,25]`
      }
      if (r.savings_model === 'factures') {
        if (r.eco_annuelle_sans > r.facture_sans) return `économie ${r.eco_annuelle_sans} > facture actuelle ${r.facture_sans}`
        if (r.eco_annuelle_avec > r.facture_sans) return `économie avec ${r.eco_annuelle_avec} > facture actuelle ${r.facture_sans}`
      }
      return null
    },
  })
})

test('computeROI : plus de kWc ⇒ production ↑, jamais moins ; production = kWc × productible × facteur (±0,1 kWh)', () => {
  verifier('', 'production monotone en kWc', {
    seed: 402, runs: RUNS,
    gen: (g) => ({ ...genRoi(g), productible: g.pick([1500, 1651, 1687]), dKwp: g.float(0, 20) }),
    verifie: (c) => {
      const a = roiDe(c)
      const b = roiDe(c, c.kwp + c.dKwp)
      if (b.production_annuelle_kwh + 1e-9 < a.production_annuelle_kwh) {
        return `production(${c.kwp + c.dKwp}) < production(${c.kwp})`
      }
      const attendu = c.kwp * c.productible * PRODUCTIBLE_NET_FACTOR
      return Math.abs(a.production_annuelle_kwh - attendu) <= 0.06 + attendu * 1e-9 ? null
        : `production ${a.production_annuelle_kwh} vs ${attendu}`
    },
  })
})

test('payback : > 0 et fini dès que l\'économie > 0 et l\'investissement > 0 ; jamais > 25 ans', () => {
  verifier('', 'computeCashflowPayback', {
    seed: 403, runs: RUNS,
    gen: (g) => ({
      inv: Math.round(g.logFloat(8000, 3e6)), eco: Math.round(g.logFloat(500, 4e5)),
      battery: g.bool(), share: g.pick([null, 0, 0.5, 1]), invCost: g.pick([null, 0, 15000]),
    }),
    verifie: ({ inv, eco, battery, share, invCost }) => {
      // Domaine RÉALISTE : l'économie annuelle ne dépasse pas 3× l'investissement
      // (payback ≥ ~4 mois) — au-delà, l'arrondi 0,1 an peut rendre 0.
      if (eco > inv * 3) return null
      const r = computeCashflowPayback(inv, eco, { battery, batteryShare: share, inverterReplaceCost: invCost })
      if (premierNonFini(r)) return `non fini ${premierNonFini(r)}`
      if (!(r.paybackYears > 0 && r.paybackYears <= 25)) return `payback ${r.paybackYears}`
      return r.cumulative.length === 25 ? null : 'cashflow ≠ 25 ans'
    },
  })
})

test('payback : plus d\'économie ⇒ payback jamais plus long', () => {
  verifier('', 'payback monotone en économie', {
    seed: 404, runs: RUNS,
    gen: (g) => ({ inv: Math.round(g.logFloat(8000, 1e6)), eco: Math.round(g.logFloat(800, 2e5)), coef: g.float(1, 3) }),
    verifie: ({ inv, eco, coef }) => {
      const a = computeCashflowPayback(inv, eco).paybackYears
      const b = computeCashflowPayback(inv, eco * coef).paybackYears
      return b <= a + 1e-9 ? null : `payback(×${coef})=${b} > payback=${a}`
    },
  })
})

test('étude industrielle : couverture et autoconsommation dans [0,100] %, aucune sortie non finie', () => {
  verifier('', 'computeEtudeIndustrielle', {
    seed: 405, runs: RUNS,
    gen: (g) => ({
      kwp: g.logFloat(3, 2000), conso: g.pick([0, g.logFloat(200, 500000)]),
      day: g.pick([10, 40, 80, 100]),
    }),
    verifie: ({ kwp, conso, day }) => {
      // Prix RÉALISTE au kWc (5 000 – 14 000 MAD/kWc) : un total sans rapport
      // avec la puissance ferait un payback arrondi à 0,0 sans que ce soit un bug.
      const total = Math.round(kwp * (5000 + (kwp * 7919) % 9000))
      const r = computeEtudeIndustrielle({ kwp, consoMensuelleKwh: conso, dayUsagePct: day, totalTtc: total })
      const nf = premierNonFini(r)
      if (nf) return `non fini ${nf}`
      if (r.taux_autoconso < 0 || r.taux_autoconso > 100.05) return `autoconso ${r.taux_autoconso}`
      if (r.taux_couverture !== null && (r.taux_couverture < 0 || r.taux_couverture > 100.05)) return `couverture ${r.taux_couverture}`
      if (r.payback !== null && !(r.payback > 0)) return `payback ${r.payback}`
      return null
    },
  })
})

test('étude industrielle : plus de kWc ⇒ production et énergie autoconsommée jamais plus basses', () => {
  verifier('', 'étude industrielle monotone', {
    seed: 406, runs: RUNS,
    gen: (g) => ({ kwp: g.logFloat(3, 900), d: g.float(0, 300), conso: g.logFloat(500, 300000), day: g.pick([30, 60, 80, 100]) }),
    verifie: ({ kwp, d, conso, day }) => {
      const p = { consoMensuelleKwh: conso, dayUsagePct: day, totalTtc: 1e6 }
      const a = computeEtudeIndustrielle({ kwp, ...p })
      const b = computeEtudeIndustrielle({ kwp: kwp + d, ...p })
      if (b.production_annuelle < a.production_annuelle) return 'production ↓'
      if (b.economies_annuelles + 1 < a.economies_annuelles) return `économies ↓ ${a.economies_annuelles} → ${b.economies_annuelles}`
      return null
    },
  })
})

// ══ 5. DIMENSIONNEMENT ═══════════════════════════════════════════════════════

test('panneaux : plus de kWc demandés ⇒ jamais moins de panneaux, et N × W ≥ kWc demandé', () => {
  verifier('', 'panneauxPourKwc', {
    seed: 501, runs: RUNS,
    gen: (g) => ({ kwc: g.logFloat(0.5, 500), d: g.float(0, 60), w: g.pick([400, 455, 550, 585, 625, 710]) }),
    verifie: ({ kwc, d, w }) => {
      const a = panneauxPourKwc(kwc, w)
      const b = panneauxPourKwc(kwc + d, w)
      if (b < a) return `panneaux(${kwc + d})=${b} < panneaux(${kwc})=${a}`
      if (a < 1) return 'moins d\'un panneau pour un kWc > 0'
      return a * w / 1000 + 1e-6 >= kwc ? null : `${a} × ${w} W < ${kwc} kWc demandés`
    },
  })
})

test('besoin lu sur la facture d\'hiver : monotone, multiple du palier de 5 kWc', () => {
  verifier('', 'estimerKwcDepuisFacture', {
    seed: 502, runs: RUNS,
    gen: (g) => ({ f: g.logFloat(1, 60000), d: g.float(0, 20000) }),
    verifie: ({ f, d }) => {
      const a = estimerKwcDepuisFacture(f)
      const b = estimerKwcDepuisFacture(f + d)
      if (a % 5 !== 0 || b % 5 !== 0) return 'hors palier de 5 kWc'
      return b >= a ? null : `besoin(${f + d})=${b} < besoin(${f})=${a}`
    },
  })
})

// Catalogue de dimensionnement (le même que solar.dimensionnement.test.mjs).
const ht = (ttc) => (ttc / 1.2).toFixed(2)
let _id = 0
const P = (nom, ttc, extra = {}) => ({ id: ++_id, nom, prix_vente: ht(ttc), ...extra })
const CATALOGUE_RESIDENTIEL = [
  P('Onduleur réseau Huawei 5kW Monophasé', 14000),
  P('Onduleur réseau Huawei 10kW Monophasé', 18000),
  P('Onduleur réseau Huawei 12kW Monophasé', 20000),
  P('Onduleur réseau Huawei 15kW Triphasé', 23000),
  P('Onduleur réseau Huawei 20kW Triphasé', 28000),
  P('Onduleur réseau Huawei 25kW Triphasé', 35000),
  P('Onduleur hybride Deye 5kW Monophasé', 17000),
  P('Onduleur hybride Deye 10kW Monophasé', 28000),
  P('Onduleur hybride Deye 15kW Triphasé', 36000),
  P('Onduleur hybride Deye 20kW Triphasé', 48000),
  P('Panneau Canadien Solar 710W', 1400),
  P('Batterie Dyness 5 kWh', 17000),
  P('Structures acier', 500), P('Structures aluminium', 850), P('Socles', 80),
  P('Smart Meter', 1800), P('Wifi Dongle', 1200), P('Accessoires', 2000),
  P('Tableau De Protection AC/DC', 2000), P('Installation', 4800),
  P('Transport', 1000), P('Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 5000),
]

test('taille recommandée : factures ↑ (toutes les autres entrées égales) ⇒ kWc recommandé jamais plus bas', () => {
  verifier('', 'optimalKwcByPayback monotone en consommation', {
    seed: 503, runs: 60,
    gen: (g) => ({
      base: Math.round(g.logFloat(400, 4000)), coef: g.float(1, 2.5),
      ete: g.float(1, 1.8), utility: g.pick(NOMME), day: g.pick([40, 60, 80]),
    }),
    verifie: ({ base, coef, ete, utility, day }) => {
      const facturesDe = (k) => Array.from({ length: 12 }, (_, i) => Math.round(
        base * k * (i >= 5 && i <= 8 ? ete : 1)))
      const recommande = (k) => {
        const f = facturesDe(k)
        const besoinKwc = estimerKwcDepuisFacture(Math.max(...f.slice(0, 5), f[9], f[10], f[11]))
        const conso = consoAnnuelleDepuisFactures(f, utility)
        return optimalKwcByPayback({
          produits: CATALOGUE_RESIDENTIEL, factures: f, dayUsagePct: day, panelW: 710,
          structureType: 'acier', besoinKwc, consoAnnuelleKwh: conso, utility,
        }).kwcOptimal
      }
      const a = recommande(1)
      const b = recommande(coef)
      return b >= a ? null : `kWc recommandé ↓ : ${a} kWc → ${b} kWc quand les factures ×${coef}`
    },
  })
})

// ══ 6. TOTAUX (chaîne monétaire) ═════════════════════════════════════════════

function genLignes(g) {
  const n = g.int(1, 8)
  return Array.from({ length: n }, () => {
    const taux = g.pick([10, 20, 20, 0, 14, 7])
    const ht = Math.round(g.logFloat(1, 60000) * 100) / 100
    return {
      quantite: g.pick([1, 1, 2, 3, 10, 22, 0.5, 2.25]),
      taux_tva: taux,
      prix_unit_ttc: Math.round(ht * (1 + taux / 100) * 100) / 100,
    }
  })
}

test('totaux TTC : remise ↑ (jusqu à 99,99 %) ⇒ total TTC jamais plus haut ; ≥ 0 ; fini', () => {
  verifier('', 'totauxCanoniquesTtc monotone en remise', {
    seed: 601, runs: RUNS,
    gen: (g) => ({ lignes: genLignes(g), d1: g.pick([0, 2, 2.5, 5, 7.5, 10, 33.33]), dd: g.pick([0, 0.5, 2, 10, 40]) }),
    verifie: ({ lignes, d1, dd }) => {
      const a = totauxCanoniquesTtc(lignes, d1)
      const b = totauxCanoniquesTtc(lignes, Math.min(99.99, d1 + dd))
      if (!Number.isFinite(a) || !Number.isFinite(b)) return `non fini ${a} ${b}`
      if (a < 0 || b < 0) return 'total négatif'
      return b <= a + 1e-9 ? null : `TTC(${d1 + dd} %)=${b} > TTC(${d1} %)=${a}`
    },
  })
})

test('ERR-QAH-PROP-JS-TOTAUX-REMISE-100-NEGATIF (corrigée) — remise 100 % ⇒ total TTC exactement 0, jamais négatif', () => {
  assert.equal(totauxCanoniquesTtc([
    { quantite: 0.5, taux_tva: 0, prix_unit_ttc: 9.71 },
    { quantite: 1, taux_tva: 14, prix_unit_ttc: 21170.47 },
  ], 100), 0)
  verifier('', 'remise 100 % ⇒ TTC = 0', {
    seed: 604, runs: RUNS,
    gen: (g) => ({ lignes: genLignes(g) }),
    verifie: ({ lignes }) => {
      const t = totauxCanoniquesTtc(lignes, 100)
      return t === 0 ? null : `remise 100 % ⇒ TTC ${t}`
    },
  })
})

test('totaux TTC : encadrés par HT net × (1 + taux mini/maxi) à 2 centimes près, au centime', () => {
  verifier('', 'totauxCanoniquesTtc encadré', {
    seed: 602, runs: RUNS,
    gen: (g) => ({ lignes: genLignes(g), d: g.pick([0, 2, 2.5, 5, 7.5, 10]) }),
    verifie: ({ lignes, d }) => {
      const htBrut = lignes.reduce((s, l) => s + l.quantite * Number(htFromTtc(l.prix_unit_ttc, l.taux_tva)), 0)
      const htNet = htBrut * (1 - d / 100)
      const taux = lignes.map((l) => l.taux_tva)
      const t = totauxCanoniquesTtc(lignes, d)
      const bas = htNet * (1 + Math.min(...taux) / 100) - 0.05 * lignes.length
      const haut = htNet * (1 + Math.max(...taux) / 100) + 0.05 * lignes.length
      if (t < bas || t > haut) return `TTC ${t} hors [${bas.toFixed(2)}, ${haut.toFixed(2)}]`
      return Math.abs(t * 100 - Math.round(t * 100)) < 1e-6 ? null : `TTC ${t} pas au centime`
    },
  })
})

test('TTC ↔ HT : ttcFromHt(htFromTtc(x)) redonne x à ±1 dirham près, pour tout taux légal', () => {
  verifier('', 'aller-retour TTC/HT', {
    seed: 603, runs: RUNS,
    gen: (g) => ({ ttc: Math.round(g.logFloat(1, 500000)), taux: g.pick([0, 7, 10, 14, 20]) }),
    verifie: ({ ttc, taux }) => {
      const retour = ttcFromHt(htFromTtc(ttc, taux), taux || 20)
      // `taux: 0` retombe sur le défaut 20 des deux côtés (parseFloat(0) || 20).
      const ref = taux === 0 ? ttcFromHt(htFromTtc(ttc, 0), 0) : retour
      return Math.abs(ref - ttc) <= 1 ? null : `${ttc} → ${ref}`
    },
  })
})

// ══ 7. POMPAGE ═══════════════════════════════════════════════════════════════

function genCourbe(g) {
  const n = g.int(2, 7)
  const debits = [0]
  const hmts = [g.int(40, 120)]
  for (let i = 1; i < n; i++) {
    debits.push(debits[i - 1] + g.int(1, 8))
    hmts.push(Math.max(1, hmts[i - 1] - g.int(2, 25)))
  }
  return { debits_m3h: debits, hmt_m: hmts }
}

function genCatalogue(g) {
  const pompes = Array.from({ length: g.int(0, 9) }, (_, i) => {
    const kw = g.pick([0.75, 1.1, 1.5, 2.2, 3, 4, 5.5, 7.5, 11])
    const v = g.pick([220, 380, null])
    return {
      id: 100 + i, nom: `Pompe ${g.pick(['immergée', 'immergée', 'de surface'])} OSP ${i} ${kw}kW`,
      prix_vente: g.pick([0, ht(g.int(3000, 30000)), ht(g.int(3000, 30000))]),
      courbe_pompe: g.bool(0.85) ? genCourbe(g) : null, pompe_kw: kw, pompe_cv: Math.round(kw / 0.7355 * 10) / 10,
      tension_v: v,
    }
  })
  const variateurs = Array.from({ length: g.int(0, 6) }, (_, i) => {
    const kw = g.pick([0.75, 1.5, 2.2, 4, 5.5, 7.5, 11])
    return {
      id: 200 + i, nom: `Variateur VEICHI SVF3 ${kw}kW`,
      prix_vente: g.pick([0, ht(g.int(2000, 12000))]), pompe_kw: kw, tension_v: g.pick([220, 380]),
    }
  })
  const commun = [
    P('Afficheur SI22', 700), P('Panneau Canadien Solar 710W', 1400),
    P('Structures acier', 500), P('Structures aluminium', 850), P('Socles', 80),
    P('Installation', 4800), P('Transport', 1000),
    // Pièges : des équipements qui NE DOIVENT JAMAIS entrer dans un pompage.
    P('Onduleur réseau Huawei 10kW Monophasé', 18000),
    P('Onduleur hybride Deye 10kW Monophasé', 28000),
    P('Batterie Dyness 5 kWh', 17000),
  ]
  return [...pompes, ...variateurs, ...commun]
}

test('pompage : débit délivré (m³/h) NON CROISSANT quand la HMT monte, ≥ 0, borné au dernier point', () => {
  verifier('', 'debitAtHmt monotone', {
    seed: 701, runs: RUNS,
    gen: (g) => ({ courbe: genCourbe(g), h: g.float(0.5, 200), dh: g.float(0, 80) }),
    verifie: ({ courbe, h, dh }) => {
      const a = debitAtHmt(courbe, h)
      const b = debitAtHmt(courbe, h + dh)
      if (a === null || b === null) return 'null sur une courbe valide et une HMT > 0'
      if (a < 0 || b < 0) return 'débit négatif'
      const max = courbe.debits_m3h[courbe.debits_m3h.length - 1]
      if (a > max + 1e-9) return `débit ${a} > dernier point ${max}`
      // Arrondi 0,1 m³/h dans l'interpolation : tolérance 0,1.
      return b <= a + 0.1001 ? null : `débit(${h + dh} m)=${b} > débit(${h} m)=${a}`
    },
  })
})

test('pompage : HMT ↑ au même débit ⇒ kW de la pompe retenue jamais plus bas ; introuvable le reste', () => {
  verifier('', 'selectPompeByCurve monotone en HMT', {
    seed: 702, runs: RUNS,
    gen: (g) => ({
      cat: genCatalogue(g), hmt: g.float(5, 110), dh: g.float(0, 50), debit: g.float(1, 30),
      typePompe: g.pick(['immerge', 'surface']), alim: g.pick([undefined, 'mono', 'tri']),
    }),
    verifie: ({ cat, hmt, dh, debit, typePompe, alim }) => {
      const a = selectPompeByCurve(cat, { hmt, debit, typePompe, alim })
      const b = selectPompeByCurve(cat, { hmt: hmt + dh, debit, typePompe, alim })
      if (a.pump && a.kw !== parseFloat(a.pump.pompe_kw)) return 'kw retenu ≠ pompe_kw'
      if (!a.pump && b.pump) return 'aucune pompe à la HMT basse mais une à la HMT haute'
      if (a.pump && b.pump && b.kw + 1e-9 < a.kw) return `kW(${hmt + dh} m)=${b.kw} < kW(${hmt} m)=${a.kw}`
      return null
    },
  })
})

test('pompage : la pompe retenue délivre bien le débit demandé à la HMT, est pricée, et de la bonne tension', () => {
  verifier('', 'selectPompeByCurve cohérente', {
    seed: 703, runs: RUNS,
    gen: (g) => ({
      cat: genCatalogue(g), hmt: g.float(5, 110), debit: g.float(1, 30),
      typePompe: g.pick(['immerge', 'surface']), alim: g.pick([undefined, 'mono', 'tri']),
    }),
    verifie: ({ cat, hmt, debit, typePompe, alim }) => {
      const r = selectPompeByCurve(cat, { hmt, debit, typePompe, alim })
      if (!r.pump) return null
      if (!(parseFloat(r.pump.prix_vente) > 0)) return `pompe sans prix retenue : ${r.pump.nom}`
      if (!(debitAtHmt(r.pump.courbe_pompe, hmt) >= debit)) return 'débit délivré < débit demandé'
      const v = r.pump.tension_v
      if (alim && v != null && v !== (alim === 'mono' ? 220 : 380)) return `tension ${v} pour alim ${alim}`
      return null
    },
  })
})

test('pompage : m³/jour = débit@HMT × heures (arrondi) ; jamais de m³/jour sans courbe ni sans heures', () => {
  verifier('', 'pompageSelection m3Jour', {
    seed: 704, runs: RUNS,
    gen: (g) => ({
      cat: genCatalogue(g), hmt: g.float(5, 110), debit: g.float(1, 30),
      heures: g.pick([0, undefined, 5, 6, 7, 8, 9.5]), cv: g.pick([0, 3, 5, 7.5]),
      typePompe: g.pick(['immerge', 'surface']), alim: g.pick(['mono', 'tri']),
    }),
    verifie: ({ cat, hmt, debit, heures, cv, typePompe, alim }) => {
      const s = pompageSelection(cat, { cv, typePompe, hmt, debit, heures, alim })
      if (s.mode === 'courbe') {
        const hrs = parseFloat(heures) || 0
        const attendu = hrs > 0 ? Math.round(s.debitHmt * hrs) : null
        if (s.m3Jour !== attendu) return `m³/jour ${s.m3Jour} ≠ ${attendu}`
        if (!(s.debitHmt >= debit)) return 'débit@HMT < débit demandé en mode courbe'
      } else if (s.m3Jour !== null || s.debitHmt !== null) {
        return `mode ${s.mode} : m³/jour=${s.m3Jour}, débit=${s.debitHmt} (jamais sans courbe)`
      }
      return premierNonFini(s.dims) ? `dims non finies ${premierNonFini(s.dims)}` : null
    },
  })
})

test('pompage : la composition n\'a JAMAIS d\'onduleur ni de batterie, ni de produit sans prix', () => {
  verifier('', 'autoFillPompage composition', {
    seed: 705, runs: RUNS,
    gen: (g) => ({
      cat: genCatalogue(g), hmt: g.pick([undefined, g.float(5, 110)]), debit: g.pick([undefined, g.float(1, 30)]),
      cv: g.pick([0, 3, 5, 7.5, 10]), heures: g.pick([undefined, 7]),
      typePompe: g.pick(['immerge', 'surface']), alim: g.pick(['mono', 'tri']),
      distance: g.pick([0, 20, 60]), structureType: g.pick(['acier', 'aluminium']),
    }),
    verifie: ({ cat, hmt, debit, cv, heures, typePompe, alim, distance, structureType }) => {
      const rows = autoFillPompage(cat, { cv, alim, typePompe, distance, structureType, hmt, debit, heures })
      const parId = new Map(cat.map((p) => [String(p.id), p]))
      for (const l of rows) {
        const d = l.designation
        if (isBattery(d) || isAnyInverter(d) || isHybridInverter(d) || isReseauInverter(d) || isOffgridInverter(d)) {
          return `équipement interdit dans un pompage : « ${d} »`
        }
        if (l.produit) {
          const p = parId.get(l.produit)
          if (!p) return `ligne « ${d} » : produit ${l.produit} hors catalogue`
          if (!(parseFloat(p.prix_vente) > 0)) return `produit SANS PRIX quoté : « ${p.nom} »`
          if (!(l.prix_unit_ttc > 0)) return `ligne « ${d} » à prix TTC ${l.prix_unit_ttc}`
        }
        if (!(l.quantite > 0) || !Number.isFinite(l.quantite)) return `quantité ${l.quantite} sur « ${d} »`
      }
      return null
    },
  })
})

test('pompage : champ PV = 1,4 × kW pompe, panneaux couvrent le champ, jamais moins de 2', () => {
  verifier('', 'champFromKw', {
    seed: 706, runs: RUNS,
    gen: (g) => ({ kw: g.logFloat(0.3, 60), d: g.float(0, 20) }),
    verifie: ({ kw, d }) => {
      const a = champFromKw(kw)
      const b = champFromKw(kw + d)
      if (premierNonFini(a)) return `non fini ${premierNonFini(a)}`
      if (a.nbPanneaux < 2) return `${a.nbPanneaux} panneaux`
      if (Math.abs(a.champKw - kw * 1.4) > 0.006 + kw * 1e-9) return `champ ${a.champKw} ≠ 1,4 × ${kw}`
      if (a.nbPanneaux * 0.710 + 1e-6 < a.champKw) return 'panneaux ne couvrent pas le champ'
      return b.nbPanneaux >= a.nbPanneaux && b.champKw + 1e-9 >= a.champKw ? null : 'champ non monotone en kW'
    },
  })
})

// ══ 8. PRODUCTIBLE ═══════════════════════════════════════════════════════════

test('productible : toujours > 0 et fini, quel que soit la ville (inconnue, vide, accentuée) ou l\'override', () => {
  verifier('', 'productibleForCity', {
    seed: 801, runs: RUNS,
    gen: (g) => ({
      ville: g.pick(['Casablanca', 'rabat', ' TANGER ', 'Agadir', 'Salé', 'Témara', '', null, undefined, 'Atlantide', 'Essaouira']),
      ov: g.pick([null, undefined, 0, -3, 1600, 1450, 1750, 'abc']),
    }),
    verifie: ({ ville, ov }) => {
      const p = productibleForCity(ville, ov)
      return Number.isFinite(p) && p > 0 ? null : `productible ${p}`
    },
  })
})

// ══ Verrou : la liste des violations ne peut que rétrécir ═══════════════════

test('KNOWN_VIOLATIONS : chaque entrée a son test de reproduction (aucune orpheline)', () => {
  // Les deux tests ci-dessus portent l'id dans leur nom : si on retire
  // l'entrée sans corriger le code, ils passent en « propriété attendue vraie »
  // et ROUGISSENT ; si on corrige le code sans retirer l'entrée, ils rougissent
  // avec « RETIRER l'entrée ». Ce test vérifie seulement la forme.
  for (const [id, v] of Object.entries(KNOWN_VIOLATIONS)) {
    assert.match(id, /^ERR-QAH-PROP-JS-[A-Z0-9-]+$/)
    assert.ok(v.resume.length > 20 && v.exemple.length > 5)
  }
})
