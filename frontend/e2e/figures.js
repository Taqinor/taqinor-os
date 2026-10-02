// QA-FIGURES — jumeau JS du lecteur/comparateur de chiffres client.
// ---------------------------------------------------------------------------
// LA source de vérité est backend/django_core/apps/ventes/quote_engine/
// figures.py (vocabulaire FIGURE_KEYS, convention data-figure, tolérances,
// mappeurs JSON). Ce fichier en est la copie MINIMALE dont Playwright a besoin
// pour lire l'écran ; `clesDuVocabulairePython()` relit la liste des clés dans
// figures.py pour qu'une dérive entre les deux fasse échouer la spec au lieu
// de passer en silence.
//
// Convention : un élément porte `data-figure="<clé>"` (+ `data-figure-option`
// « sans »/« avec », + `data-figure-taux` pour une ligne de TVA) ; sa valeur est
// `data-figure-value` s'il existe, sinon son texte.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const ARGENT = 0.01
const POINT = 1
const KWH = 1
const KWC = 0.01
const ANS = 0.05
const FIN = 0.1

// clé → { tolerance, absolu } — miroir de FIGURE_KEYS (figures.py).
export const FIGURE_KEYS = {
  sous_total_ht: { tolerance: ARGENT },
  remise: { tolerance: ARGENT, absolu: true },
  // ARRONDI-100 — la baisse au palier de 100 MAD (figures.py).
  arrondi: { tolerance: ARGENT, absolu: true },
  total_ht: { tolerance: ARGENT },
  tva: { tolerance: ARGENT },
  tva_taux: { tolerance: ARGENT },
  total_ttc: { tolerance: ARGENT },
  total_affiche: { tolerance: ARGENT },
  prix_kwc: { tolerance: POINT },
  puissance_kwc: { tolerance: KWC },
  production_annuelle_kwh: { tolerance: KWH },
  economie_annuelle: { tolerance: ARGENT },
  payback_ans: { tolerance: ANS },
  facture_annuelle_avant: { tolerance: ARGENT },
  facture_annuelle_apres: { tolerance: ARGENT },
  facture_mensuelle_avant: { tolerance: ARGENT },
  facture_mensuelle_apres: { tolerance: ARGENT },
  reduction_facture_pct: { tolerance: POINT },
  couverture_pct: { tolerance: POINT },
  autoconsommation_pct: { tolerance: POINT },
  pompe_hmt_m: { tolerance: FIN },
  pompe_debit_m3h: { tolerance: FIN },
  pompe_volume_m3_jour: { tolerance: POINT },
}

const FIGURES_PY = fileURLToPath(new URL(
  '../../backend/django_core/apps/ventes/quote_engine/figures.py', import.meta.url))

/** Les clés déclarées dans figures.py (lecture par regex, aucun import). */
export function clesDuVocabulairePython() {
  const src = readFileSync(FIGURES_PY, 'utf8')
  return [...src.matchAll(/^\s{4}"([a-z0-9_]+)": Cle\(/gm)].map((m) => m[1]).sort()
}

const OPTIONS = ['sans', 'avec']
const ESPACES = '      '
const NOMBRE_RE = new RegExp(
  `([-−–]?)\\s*(\\d{1,3}(?:[${ESPACES}]\\d{3})+|\\d+)(?:[,.](\\d+))?`)

/** « 117 391,16 MAD » → { valeur: 117391.16, resolution: 0.01 } ; illisible → valeur null. */
export function normaliser(texte) {
  if (texte === null || texte === undefined || typeof texte === 'boolean') {
    return { valeur: null, resolution: 0 }
  }
  if (typeof texte === 'number') {
    return Number.isFinite(texte) ? { valeur: texte, resolution: 0 } : { valeur: null, resolution: 0 }
  }
  const m = String(texte).match(NOMBRE_RE)
  if (!m) return { valeur: null, resolution: 0 }
  const entier = m[2].replace(new RegExp(`[${ESPACES}]`, 'g'), '')
  const dec = m[3] || ''
  let valeur = Number(dec ? `${entier}.${dec}` : entier)
  if (m[1]) valeur = -valeur
  return { valeur, resolution: dec ? 10 ** -dec.length : 1 }
}

export function identite(cle, option, taux) {
  let id = cle
  if (taux !== null && taux !== undefined && taux !== '') id += `:${Number(taux)}`
  if (option) id += `@${option}`
  return id
}

export const cleDe = (id) => id.split('@')[0].split(':')[0]

function mesure(texte) {
  return { ...normaliser(texte), texte: String(texte) }
}

function ajouter(figs, id, texte) {
  ;(figs[id] ||= []).push(mesure(texte))
}

/** Toutes les figures VISIBLES de la page (ou des ancres data-figure-value). */
export async function lireFiguresPage(page) {
  const brutes = await page.$$eval('[data-figure]', (els) => els
    .filter((e) => e.hasAttribute('data-figure-value')
      || (typeof e.checkVisibility === 'function' ? e.checkVisibility() : true))
    .map((e) => ({
      cle: e.getAttribute('data-figure'),
      option: e.getAttribute('data-figure-option'),
      taux: e.getAttribute('data-figure-taux'),
      texte: e.getAttribute('data-figure-value') ?? e.textContent.trim(),
    })))
  const figs = {}
  for (const b of brutes) ajouter(figs, identite(b.cle, b.option, b.taux), b.texte)
  return figs
}

export function clesInconnues(figs) {
  return Object.keys(figs).filter((id) => !(cleDe(id) in FIGURE_KEYS)).sort()
}

/** Même règle que compare_surfaces (figures.py) : chaque lecture contre la
 * plus précise, écart ≤ max(tolérance, pas d'affichage / 2). */
export function comparer(surfaces) {
  const ecarts = []
  const parId = {}
  for (const [nom, figs] of Object.entries(surfaces)) {
    for (const [id, mesures] of Object.entries(figs || {})) {
      for (const m of mesures) (parId[id] ||= []).push([nom, m])
    }
  }
  for (const id of Object.keys(parId).sort()) {
    const cle = FIGURE_KEYS[cleDe(id)]
    const lisibles = []
    for (const [nom, m] of parId[id]) {
      if (m.valeur === null) ecarts.push(`${id} : valeur illisible sur ${nom} (${JSON.stringify(m.texte)})`)
      else lisibles.push([nom, m])
    }
    if (lisibles.length < 2) continue
    const [refNom, ref] = lisibles.reduce((a, b) => (b[1].resolution < a[1].resolution ? b : a))
    const tol = cle ? cle.tolerance : 0
    const abs = (v) => (cle?.absolu ? Math.abs(v) : v)
    for (const [nom, m] of lisibles) {
      if (m === ref) continue
      const permis = Math.max(tol, Math.max(ref.resolution, m.resolution) / 2)
      const ecart = Math.abs(abs(m.valeur) - abs(ref.valeur))
      if (ecart > permis + 1e-9) {
        ecarts.push(`${id} : ${refNom} affiche ${JSON.stringify(ref.texte)}, ${nom} affiche `
          + `${JSON.stringify(m.texte)} (écart ${ecart.toFixed(2)}, tolérance ${permis})`)
      }
    }
  }
  return ecarts
}

/** Identités lues au moins deux fois (réellement confrontées). */
export function identitesComparees(surfaces) {
  const compte = {}
  for (const figs of Object.values(surfaces)) {
    for (const [id, mesures] of Object.entries(figs || {})) compte[id] = (compte[id] || 0) + mesures.length
  }
  return new Set(Object.keys(compte).filter((id) => compte[id] >= 2))
}

// ── Surfaces JSON (miroir des mappeurs de figures.py) ───────────────────────
function mettre(figs, cle, valeur, option, taux, { zeroOk = false } = {}) {
  if (valeur === null || valeur === undefined || typeof valeur === 'boolean') return
  const { valeur: v } = normaliser(typeof valeur === 'string' ? valeur : Number(valeur))
  if (v === null || Number.isNaN(v)) return
  if (!zeroOk && v === 0) return
  const texte = typeof valeur === 'number' ? String(Number(valeur.toFixed(6))) : String(valeur)
  ;(figs[identite(cle, option, taux)] ||= []).push({ valeur: v, resolution: 0, texte })
}

const num = (v) => {
  if (v === null || v === undefined) return null
  const { valeur } = normaliser(typeof v === 'string' ? v : Number(v))
  return valeur
}

function totaux(figs, t, option) {
  if (!t || typeof t !== 'object') return
  mettre(figs, 'sous_total_ht', t.ht_brut, option)
  mettre(figs, 'remise', t.remise, option)
  mettre(figs, 'arrondi', t.arrondi, option)
  mettre(figs, 'total_ht', t.ht_net, option)
  mettre(figs, 'tva', t.tva, option)
  for (const b of t.tva_par_taux || []) mettre(figs, 'tva_taux', b?.montant, option, b?.taux)
  mettre(figs, 'total_ttc', t.ttc, option)
}

function optionsAffichees(q) {
  if (q.deux_options ?? true) return OPTIONS
  return (q.avec_ok ?? true) ? ['avec'] : ['sans']
}

function divergent(q, cle) {
  if (!(q.panneaux_divergents && (q.deux_options ?? true))) return false
  const s = num(q[`${cle}_sans`])
  const a = num(q[`${cle}_avec`])
  return s !== null && a !== null && s > 0 && a > 0 && s !== a
}

/** GET /api/django/public/proposal/<token>/data/ → figures. */
export function figuresDepuisProposition(payload) {
  const figs = {}
  const p = payload || {}
  const q = p.quote || {}
  const ot = p.option_totals || {}
  const affichees = p.quote ? optionsAffichees(q) : OPTIONS
  for (const opt of OPTIONS) {
    if (affichees.includes(opt)) totaux(figs, ot[`${opt}_batterie`] || q[`totaux_${opt}`], opt)
  }
  totaux(figs, q.totaux_all, null)
  mettre(figs, 'total_affiche', ot.display_total ?? q.display_total)
  const kwcDiv = divergent(q, 'puissance_kwc')
  const prodDiv = divergent(q, 'prod_kwh')
  if (!kwcDiv) mettre(figs, 'puissance_kwc', q.puissance_kwc)
  if (!prodDiv) mettre(figs, 'production_annuelle_kwh', q.prod_kwh)
  for (const opt of affichees) {
    if (kwcDiv) mettre(figs, 'puissance_kwc', q[`puissance_kwc_${opt}`], opt)
    if (prodDiv) mettre(figs, 'production_annuelle_kwh', q[`prod_kwh_${opt}`], opt)
    const s = opt === 'sans' ? 's' : 'a'
    mettre(figs, 'economie_annuelle', q[`eco_${s}_ann`], opt)
    mettre(figs, 'payback_ans', q[`roi_${s}`], opt)
    const ttc = num((ot[`${opt}_batterie`] || q[`totaux_${opt}`] || {}).ttc)
    const kwc = (kwcDiv ? num(q[`puissance_kwc_${opt}`]) : null) || num(q.puissance_kwc)
    if (ttc && kwc) mettre(figs, 'prix_kwc', ttc / kwc, opt)
  }
  for (const opt of OPTIONS) {
    const v = num(q[`couverture_${opt}`])
    if (v !== null && v > 0 && v <= 1) mettre(figs, 'couverture_pct', v * 100, opt)
  }
  const ecoOpt = OPTIONS.includes(q.eco_option) ? q.eco_option
    : ((q.deux_options ?? true) || (q.avec_ok ?? true) ? 'avec' : 'sans')
  mettre(figs, 'reduction_facture_pct', p.pct_cut, ecoOpt, null, { zeroOk: true })
  mettre(figs, 'couverture_pct', p.coverage_pct, ecoOpt)
  const avant = num(p.annual_before)
  const apres = num(p.annual_after)
  mettre(figs, 'facture_annuelle_avant', avant)
  mettre(figs, 'facture_annuelle_apres', apres, ecoOpt, null, { zeroOk: true })
  if (avant !== null) mettre(figs, 'facture_mensuelle_avant', avant / 12)
  if (apres !== null) mettre(figs, 'facture_mensuelle_apres', apres / 12, ecoOpt, null, { zeroOk: true })
  const kpis = p.mode_kpis || {}
  const mode = String(p.mode_installation || q.mode_installation || '').trim().toLowerCase()
  if (mode === 'industriel' || mode === 'commercial') {
    mettre(figs, 'autoconsommation_pct', kpis.taux_autoconso)
    mettre(figs, 'couverture_pct', kpis.taux_couverture)
    mettre(figs, 'economie_annuelle', kpis.economies_annuelles)
    mettre(figs, 'payback_ans', kpis.payback)
  } else if (mode === 'agricole') {
    mettre(figs, 'pompe_hmt_m', kpis.hmt_m)
    mettre(figs, 'pompe_debit_m3h', kpis.debit_hmt_m3h)
    mettre(figs, 'pompe_volume_m3_jour', kpis.m3_jour)
  }
  return figs
}

/** GET /api/django/ventes/devis/<id>/ → figures. */
export function figuresDepuisDevisApi(detail) {
  const figs = {}
  const d = detail || {}
  mettre(figs, 'total_affiche', d.total_affiche ?? d.total_ttc)
  const comp = d.comparaison_options || {}
  for (const opt of OPTIONS) {
    const b = comp[opt] || {}
    mettre(figs, 'total_ttc', b.ttc, opt)
    mettre(figs, 'total_ht', b.ht_net, opt)
    mettre(figs, 'remise', b.remise, opt)
  }
  const roi = comp.roi || {}
  mettre(figs, 'production_annuelle_kwh', roi.prod_kwh)
  mettre(figs, 'economie_annuelle', roi.eco_s_ann, 'sans')
  mettre(figs, 'economie_annuelle', roi.eco_a_ann, 'avec')
  mettre(figs, 'payback_ans', roi.roi_s, 'sans')
  mettre(figs, 'payback_ans', roi.roi_a, 'avec')
  return figs
}
