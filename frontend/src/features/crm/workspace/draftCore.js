// LW9 — Moteur d'état PUR du Lead Workspace (blueprint D2).
//
// « La perte de données devient structurellement impossible. » Ce module ne
// contient AUCUN import (zéro React, zéro navigateur) : c'est un réducteur pur
// + quelques aides, testable en `node --test` (draftCore.test.mjs). Tout l'état
// mutable d'UN lead vit dans un seul objet keyé par `leadId`, remplacé
// ATOMIQUEMENT à la navigation (`LOAD_LEAD`) — aucun état satellite ne peut
// donc structurellement fuiter d'un lead à l'autre (bugs recon 05 P1#2/#4,
// P2#7/#8 tués par construction).
//
// Le hook React (`useLeadDraft.js`) branche les effets (PATCH réseau, debounce,
// miroir sessionStorage, garde stale) au-dessus de ce réducteur.

// Canal posé par défaut à la création (jamais null) — miroir de LeadForm.jsx.
export const DEFAULT_CANAL = 'walk_in'

// Les clés de CHAMP éditables du lead (miroir strict de buildInitialFields).
// `stage` en fait partie pour la LECTURE (valeur affichée), mais n'entre JAMAIS
// dans le `draft` (SET_FIELD l'ignore — c'est une action du StageControl).
export const TRACKED_KEYS = [
  // Contact
  'nom', 'prenom', 'societe', 'email', 'telephone', 'whatsapp', 'adresse',
  'ville', 'gps_lat', 'gps_lng',
  // Suivi commercial
  'stage', 'owner', 'canal', 'contact_preference', 'priorite', 'langue_preferee',
  'tags', 'motif_perte', 'perdu', 'relance_date', 'type_installation',
  'montant_estime', 'date_cloture_prevue',
  // Énergie
  'facture_hiver', 'facture_ete', 'ete_differente', 'conso_mensuelle_kwh',
  'tranche_onee', 'raccordement', 'regularisation_8221',
  // Pompage (agricole)
  'pompe_cv', 'pompe_hmt_m', 'pompe_debit_m3h',
  // Toiture & site
  'type_toiture', 'surface_toiture_m2', 'orientation', 'inclinaison_deg',
  'ombrage', 'ombrage_notes', 'nb_etages', 'structure_pref',
  'taille_souhaitee_kwc', 'batterie_souhaitee',
  // Visite
  'visite_prevue_le', 'visite_effectuee', 'visite_notes',
  // Divers
  'note', 'custom_data',
]

// ── canonEq — égalité CANONIQUE (le cœur du « fini le phantom dirty ») ───────
// Compare deux valeurs de champ comme le ferait le serveur : '' ≡ null ≡
// undefined (vides), '30' ≡ 30 (numériques), objets par contenu (custom_data).
// Sans ça, un champ numérique re-tapé identique (30 → '30') resterait « dirty »
// et un `JSON.stringify` de ~50 clés à chaque rendu (smell recon 01 §6.6)
// prétendrait des modifications inexistantes.
function isEmpty(v) {
  return v === '' || v === null || v === undefined
}

function isNumericLike(v) {
  if (typeof v === 'number') return Number.isFinite(v)
  if (typeof v === 'string') {
    const t = v.trim()
    return t !== '' && !Number.isNaN(Number(t))
  }
  return false
}

// Sérialisation déterministe (clés triées) — pour comparer deux objets
// custom_data indépendamment de l'ordre d'insertion des clés.
function stableStringify(o) {
  if (o === null || typeof o !== 'object') return JSON.stringify(o)
  if (Array.isArray(o)) return `[${o.map(stableStringify).join(',')}]`
  const keys = Object.keys(o).sort()
  return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify(o[k])}`).join(',')}}`
}

export function canonEq(a, b) {
  const ea = isEmpty(a)
  const eb = isEmpty(b)
  if (ea || eb) return ea && eb
  if (typeof a === 'boolean' || typeof b === 'boolean') return Boolean(a) === Boolean(b)
  if (typeof a === 'object' || typeof b === 'object') return stableStringify(a) === stableStringify(b)
  if (isNumericLike(a) && isNumericLike(b)) return Number(a) === Number(b)
  return String(a) === String(b)
}

// ── Sélecteurs purs (draft superposé au serveur) ─────────────────────────────
const has = (obj, k) => obj != null && Object.prototype.hasOwnProperty.call(obj, k)

// Valeur AFFICHÉE d'un champ : la frappe non sauvée (`draft`) l'emporte, sinon
// la dernière vérité serveur.
export function getField(state, key) {
  if (has(state.draft, key)) return state.draft[key]
  return state.server ? state.server[key] : undefined
}

// L'ensemble complet des champs éditables actuels (draft ∪ serveur), pour la
// soumission en création et le calcul de couplage été/hiver.
export function currentFields(state) {
  const out = {}
  for (const k of TRACKED_KEYS) out[k] = getField(state, k)
  return out
}

export function dirtyKeys(state) {
  return Object.keys(state.draft || {})
}

export function isDirty(state) {
  return dirtyKeys(state).length > 0
}

// VX249(b) — un champ « suggéré » : à la CRÉATION uniquement, une valeur par
// défaut VX93 (owner=moi, dernière ville) non encore touchée. Dérivé de l'état
// (pas d'état `touched` séparé) : dès que l'utilisateur édite, la clé entre
// dans `draft` et cesse d'être suggérée.
export function isSuggested(state, key) {
  return state.mode === 'create'
    && !has(state.draft, key)
    && !!(state.server && state.server[key])
}

// ── Transformation de charge utile (PATCH partiel / création) ────────────────
// Miroir du transform de LeadForm.handleSubmit : '' | undefined → null, les
// booléens passent tels quels, et l'été suit l'hiver quand `ete_differente`
// est faux. `subset` = clés dirty (flush) OU tous les champs (création).
export function toPayload(subset) {
  const nullable = (v) => (v === '' || v === undefined ? null : v)
  const out = {}
  for (const [k, v] of Object.entries(subset)) {
    out[k] = typeof v === 'boolean' ? v : nullable(v)
  }
  if (has(out, 'ete_differente') && out.ete_differente === false) {
    out.facture_ete = null
  }
  return out
}

// ── Défauts de création (port 1:1 de buildInitialFields(null, uid)) ──────────
// Pur : la lecture localStorage de la dernière ville (VX93) est faite par le
// hook et passée en argument (`lastVille`).
export function buildCreateDefaults({ currentUserId = null, lastVille = '' } = {}) {
  return {
    nom: '', prenom: '', societe: '', email: '', telephone: '', whatsapp: '',
    adresse: '', ville: lastVille || '', gps_lat: '', gps_lng: '',
    stage: 'NEW',
    owner: currentUserId != null ? String(currentUserId) : '',
    canal: DEFAULT_CANAL,
    contact_preference: '',
    priorite: 'normale', langue_preferee: '', tags: '', motif_perte: '',
    perdu: false, relance_date: '', type_installation: '',
    montant_estime: '', date_cloture_prevue: '',
    facture_hiver: '', facture_ete: '', ete_differente: false,
    conso_mensuelle_kwh: '', tranche_onee: '', raccordement: '',
    regularisation_8221: false,
    pompe_cv: '', pompe_hmt_m: '', pompe_debit_m3h: '',
    type_toiture: '', surface_toiture_m2: '', orientation: '', inclinaison_deg: '',
    ombrage: '', ombrage_notes: '', nb_etages: '', structure_pref: '',
    taille_souhaitee_kwc: '', batterie_souhaitee: '',
    visite_prevue_le: '', visite_effectuee: false, visite_notes: '',
    note: '', custom_data: {},
  }
}

// ── initState — construit l'état ENTIER d'un lead (utilisé par LOAD_LEAD) ─────
// `restoredDraft` (optionnel) = brouillon orphelin retrouvé en sessionStorage
// ({ draft, note }) restauré avec le chip « Brouillon restauré ».
export function initState({
  lead = null,
  mode = lead ? 'edit' : 'create',
  currentUserId = null,
  lastVille = '',
  restoredDraft = null,
} = {}) {
  const server = mode === 'create'
    ? buildCreateDefaults({ currentUserId, lastVille })
    : (lead || {})
  const restored = !!(restoredDraft
    && restoredDraft.draft
    && Object.keys(restoredDraft.draft).length)
  return {
    leadId: lead && lead.id != null ? lead.id : null,
    mode,
    server,
    // draft SPARSE : uniquement les clés touchées.
    draft: restored ? { ...restoredDraft.draft } : {},
    inflight: null,          // { clé: valeur } envoyée, en attente | null
    saveState: 'idle',       // 'idle' | 'saving' | 'saved' | 'error'
    saveError: null,
    stale: null,             // { theirs, at } | null (garde VX243c, keyée)
    restored,                // chip « Brouillon restauré »
    composer: { note: restoredDraft && restoredDraft.note ? restoredDraft.note : '', file: null },
    wa: { selected: [], langue: (lead && lead.langue_preferee) || 'fr', preview: null },
    bill: { editing: false, hiver: '', ete: '', error: null },
  }
}

// ── applyFlushSuccess — la garde de navigation + « typed-during-flight » ─────
// Extrait pour être testable directement. `res` = lead renvoyé par le PATCH.
export function applyFlushSuccess(state, res) {
  // Garde de navigation : une réponse pour un AUTRE lead est JETÉE — elle ne
  // peut pas corrompre le lead courant (course refreshLead/quickChangeStage,
  // recon 01 §6.3).
  if (res && res.id != null && state.leadId != null && res.id !== state.leadId) {
    return state
  }
  const inflight = state.inflight || {}
  const draft = { ...state.draft }
  for (const k of Object.keys(inflight)) {
    // « typed-during-flight » : une frappe DURANT le vol (draft[k] a changé)
    // reste dirty et repart au prochain flush. Sinon la clé est nettoyée et le
    // champ lit désormais la valeur (canonisée) du serveur.
    if (draft[k] === inflight[k]) delete draft[k]
  }
  return {
    ...state,
    server: res || state.server,
    draft,
    inflight: null,
    saveState: 'saved',
    saveError: null,
    restored: false,
  }
}

// ── Le réducteur PUR ─────────────────────────────────────────────────────────
export function reducer(state, action) {
  switch (action.type) {
    // Remplacement ATOMIQUE de l'état entier (navigation J/K/◀▶, ouverture,
    // reset « créer un autre »). Rien ne survit d'un lead à l'autre.
    case 'LOAD_LEAD':
      return initState(action.payload || {})

    case 'SET_FIELD': {
      const { key, value } = action
      // `stage` n'entre JAMAIS dans le draft : c'est une action du StageControl
      // (flush-puis-PATCH dédié). Le bug LW2 (« blanchiment » d'édition) est
      // impossible ici par construction.
      if (key === 'stage') return state
      const draft = { ...state.draft }
      if (canonEq(value, state.server ? state.server[key] : undefined)) delete draft[key]
      else draft[key] = value
      // Une frappe après une confirmation « ✓ Enregistré » remet le chip global
      // à « idle » ; on ne dégrade jamais 'saving'/'error' ici.
      const saveState = state.saveState === 'saved' ? 'idle' : state.saveState
      return { ...state, draft, saveState }
    }

    case 'FLUSH_START': {
      const keys = action.keys && action.keys.length ? action.keys : Object.keys(state.draft)
      const inflight = {}
      for (const k of keys) inflight[k] = state.draft[k]
      return { ...state, inflight, saveState: 'saving', saveError: null }
    }

    case 'FLUSH_SUCCESS':
      return applyFlushSuccess(state, action.res)

    case 'FLUSH_ERROR': {
      const inflight = state.inflight || {}
      // `inflight` retourne dans `draft` SANS écraser une frappe-en-vol : rien
      // n'est jamais perdu, le champ reste éditable.
      const draft = { ...inflight, ...state.draft }
      return {
        ...state,
        draft,
        inflight: null,
        saveState: 'error',
        saveError: action.error || "Échec d'enregistrement",
      }
    }

    // Écriture PONCTUELLE (changement d'étape, facture inline, refresh) : met à
    // jour la vérité serveur SANS toucher au draft — les éditions non sauvées
    // sont préservées (ne peut plus « blanchir » une édition, tue P1#1).
    case 'SET_SERVER': {
      const { res } = action
      if (res && res.id != null && state.leadId != null && res.id !== state.leadId) return state
      return { ...state, server: res || state.server }
    }

    case 'SET_STALE':
      return { ...state, stale: { theirs: action.theirs ?? null, at: action.at ?? null } }
    case 'CLEAR_STALE':
      return { ...state, stale: null }

    case 'CLEAR_RESTORED':
      return { ...state, restored: false }

    case 'SET_COMPOSER':
      return { ...state, composer: { ...state.composer, ...(action.patch || {}) } }
    case 'RESET_COMPOSER':
      return { ...state, composer: { note: '', file: null } }

    case 'WA_TOGGLE': {
      const set = new Set(state.wa.selected)
      if (set.has(action.id)) set.delete(action.id)
      else set.add(action.id)
      return { ...state, wa: { ...state.wa, selected: [...set] } }
    }
    case 'WA_LANGUE':
      return { ...state, wa: { ...state.wa, langue: action.langue } }
    case 'WA_PREVIEW':
      return { ...state, wa: { ...state.wa, preview: action.preview } }
    case 'WA_RESET':
      return { ...state, wa: { ...state.wa, selected: [], preview: null } }

    case 'BILL_START':
      return { ...state, bill: { editing: true, hiver: action.hiver ?? '', ete: action.ete ?? '', error: null } }
    case 'BILL_CANCEL':
      return { ...state, bill: { editing: false, hiver: '', ete: '', error: null } }
    case 'BILL_SET':
      return { ...state, bill: { ...state.bill, ...(action.patch || {}), error: null } }
    case 'BILL_ERROR':
      return { ...state, bill: { ...state.bill, error: action.error } }

    case 'SET_SAVE_STATE':
      return { ...state, saveState: action.saveState, saveError: action.error ?? null }

    default:
      return state
  }
}

export default reducer

// Champs d'origine web (taqinor.ma) en LECTURE SEULE — capturés par le site,
// jamais édités dans la fiche. Vit ICI (module logique pur) et non dans
// SectionDivers.jsx : exporter une constante depuis un fichier de composants
// casse la règle react-refresh/only-export-components du lint CI.
export const WEB_ORIGIN_FIELDS = [
  'bill_range_bucket', 'roi_band', 'utm_source', 'utm_medium', 'utm_campaign', 'fbclid',
]
