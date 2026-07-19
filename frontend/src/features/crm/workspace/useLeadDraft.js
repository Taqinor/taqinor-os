import { useReducer, useRef, useEffect, useCallback } from 'react'
import crmApi from '../../../api/crmApi'
import { toast } from '../../../ui'
import { useDirtyGuard, confirmLeaveIfDirty } from '../../../ui/useDirtyGuard'
import {
  reducer, initState, getField, isDirty, dirtyKeys, isSuggested,
  toPayload, currentFields,
} from './draftCore'
import { getPrefetched } from './leadPrefetch'

// LW9/LW12 — Hook moteur d'état du Lead Workspace : branche les effets (PATCH
// réseau, debounce d'autosauvegarde, miroir sessionStorage, garde stale,
// leaveGuard) AU-DESSUS du réducteur pur `draftCore.js`. Tout l'état mutable
// vit dans le store keyé par `leadId` — la navigation J/K/◀▶ remplace l'état
// ENTIER atomiquement (LOAD_LEAD), donc aucun satellite ne fuit d'un lead à
// l'autre (bugs recon 05 tués par construction).

// Debounce d'autosauvegarde : ~1 PATCH par champ QUITTÉ, jamais par frappe
// (blueprint D2#9). Le flush-au-blur borne encore la fréquence.
const AUTOSAVE_DEBOUNCE_MS = 1500

// VX93 — dernière ville saisie (création). Miroir de LeadForm.jsx.
const LAST_VILLE_KEY = 'vx93.lead.ville'
const readLastVille = () => {
  try { return localStorage.getItem(LAST_VILLE_KEY) || '' } catch { return '' }
}
export const rememberVille = (v) => {
  try { if (v && v.trim()) localStorage.setItem(LAST_VILLE_KEY, v.trim()) } catch { /* best-effort */ }
}

// Miroir sessionStorage `taqinor.lead.draft.<id>` (blueprint D2#6) : le draft
// (+ note du composer) y est recopié à chaque changement, purgé au flush
// réussi. Même un crash d'onglet ne perd plus une frappe.
const MIRROR_PREFIX = 'taqinor.lead.draft.'
function readMirror(id) {
  try {
    const raw = window.sessionStorage.getItem(MIRROR_PREFIX + id)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed && parsed.draft && Object.keys(parsed.draft).length) return parsed
    return null
  } catch { return null }
}
function writeMirror(id, data) {
  try { window.sessionStorage.setItem(MIRROR_PREFIX + id, JSON.stringify(data)) } catch { /* best-effort */ }
}
function clearMirror(id) {
  try { window.sessionStorage.removeItem(MIRROR_PREFIX + id) } catch { /* best-effort */ }
}

// LW24 — voisin déjà pré-chargé en idle (cf. leadPrefetch.js) : premier rendu
// INSTANTANÉ avec la donnée COMPLÈTE en cache, superposée à la ligne partielle
// reçue (le cache gagne sur les clés qu'il connaît). Le GET frais repart
// TOUJOURS en arrière-plan et remplace via SET_SERVER — ce cache n'est jamais
// la source de vérité.
function withPrefetched(lead, mode) {
  const id = lead && lead.id != null ? lead.id : null
  if (mode !== 'edit' || id == null) return lead
  const cached = getPrefetched(id)
  return cached ? { ...lead, ...cached } : lead
}

export function useLeadDraft(lead, { mode = lead ? 'edit' : 'create', currentUserId = null, onSaved, onFieldErrors } = {}) {
  const [state, dispatch] = useReducer(reducer, undefined, () => {
    const effectiveLead = withPrefetched(lead, mode)
    const id = effectiveLead && effectiveLead.id != null ? effectiveLead.id : null
    const restoredDraft = (mode === 'edit' && id != null) ? readMirror(id) : null
    return initState({ lead: effectiveLead, mode, currentUserId, lastVille: readLastVille(), restoredDraft })
  })

  // Refs pour des callbacks STABLES (jamais de closure périmée ni de timer de
  // debounce réarmé à chaque rendu du parent).
  const stateRef = useRef(state)
  const leadRef = useRef(lead)
  const onSavedRef = useRef(onSaved)
  const onFieldErrorsRef = useRef(onFieldErrors)
  // Rafraîchis en EFFET (jamais pendant le rendu — react-hooks/refs, lint CI).
  // Les lecteurs (debounce, leaveGuard, timers) tournent tous APRÈS commit,
  // donc voient toujours la dernière valeur committée.
  useEffect(() => {
    stateRef.current = state
    leadRef.current = lead
    onSavedRef.current = onSaved
    onFieldErrorsRef.current = onFieldErrors
  })
  // Fraîcheur VX243c : `date_modification` connu à l'ouverture (ou après notre
  // dernière écriture réussie).
  // Fraîcheur keyée par LEAD (critique Fable #3-bis) : {id, at} — une réponse
  // tardive du lead A ne peut plus écraser la baseline de fraîcheur du lead B.
  const openedAtRef = useRef({ id: lead && lead.id, at: lead && lead.date_modification })
  const setOpenedAt = (id, at) => {
    if (openedAtRef.current.id === id && at) openedAtRef.current = { id, at }
  }
  // Suivi du lead/mode chargé, pour ne LOAD_LEAD qu'à un vrai changement.
  const loadedRef = useRef(lead && lead.id != null ? lead.id : null)
  const loadedModeRef = useRef(mode)

  // Filet navigateur (beforeunload) — même contrat que les 7 adoptants VX166.
  useDirtyGuard(isDirty(state))

  const setField = useCallback((key, value) => {
    dispatch({ type: 'SET_FIELD', key, value })
  }, [])

  // ── flush : le PATCH partiel (blueprint D2#3) ────────────────────────────
  const flightRef = useRef(null)
  const flush = useCallback(async ({ force = false, checkStale = false } = {}) => {
    let st = stateRef.current
    if (st.mode !== 'edit') return true          // création = pas d'autosave
    // Un flush déjà en vol ? On l'ATTEND puis on ré-évalue (critique Fable #4 :
    // « return true » mentait — leaveGuard fermait avec des frappes-en-vol
    // jamais envoyées). Boucle bornée : chaque tour attend un vrai vol.
    for (let i = 0; i < 5 && st.inflight && flightRef.current; i += 1) {
      await flightRef.current.catch(() => {})
      st = stateRef.current
    }
    let keys = dirtyKeys(st)
    if (!keys.length) return true
    // Règle métier (critique Fable #6) : « perdu » sans motif ne part JAMAIS —
    // l'ancien formulaire bloquait la soumission ; en autosauvegarde on retient
    // la clé et on marque le champ motif jusqu'à ce qu'il soit rempli.
    if (keys.includes('perdu') && getField(st, 'perdu')
        && !String(getField(st, 'motif_perte') || '').trim()) {
      keys = keys.filter((k) => k !== 'perdu')
      onFieldErrorsRef.current?.({ motif_perte: 'Motif requis pour marquer le lead perdu.' })
      if (!keys.length) return false
    }
    // Garde stale (VX243c) — uniquement sur les flushs manuels / de sortie
    // (jamais un GET par frappe débouncée). Un échec de vérif ne bloque JAMAIS.
    if (checkStale && !force && st.leadId != null) {
      try {
        const latest = (await crmApi.getLead(st.leadId)).data
        const latestAt = latest && latest.date_modification
        if (latestAt && openedAtRef.current.id === st.leadId
            && openedAtRef.current.at && latestAt !== openedAtRef.current.at) {
          dispatch({
            type: 'SET_STALE',
            theirs: (latest && (latest.updated_by_nom || latest.archived_by_nom)) || null,
            at: latestAt,
          })
          return false
        }
      } catch { /* best-effort : ne jamais bloquer une sauvegarde légitime */ }
    }
    const subset = {}
    for (const k of keys) subset[k] = st.draft[k]
    dispatch({ type: 'FLUSH_START', keys })
    const flight = crmApi.updateLead(st.leadId, toPayload(subset)).then((r) => r.data)
    flightRef.current = flight
    try {
      const res = await flight
      dispatch({ type: 'FLUSH_SUCCESS', res })
      // Écho serveur pour NOTRE lead uniquement (une réponse d'un autre lead
      // est jetée par le réducteur, on ne touche alors ni le miroir ni onSaved).
      if (res && res.id === st.leadId) {
        setOpenedAt(st.leadId, res.date_modification)
        clearMirror(st.leadId)
        onSavedRef.current?.()
      }
      return true
    } catch (err) {
      dispatch({
        type: 'FLUSH_ERROR',
        error: err?.response?.data?.detail ?? "Échec d'enregistrement — réessayez.",
      })
      // Erreurs PAR CHAMP d'un 400 DRF (critique Fable #6) : sans ce relais,
      // l'utilisateur ne savait jamais QUEL champ bloquait l'autosauvegarde.
      if (err?.response?.status === 400 && err.response.data) {
        onFieldErrorsRef.current?.(err.response.data)
      }
      return false
    } finally {
      if (flightRef.current === flight) flightRef.current = null
    }
  }, [])

  // « Réessayer » (bandeau d'erreur) et « Enregistrer quand même » (bandeau stale).
  const retry = useCallback(() => flush({ force: true }), [flush])
  const saveAnyway = useCallback(() => { dispatch({ type: 'CLEAR_STALE' }); return flush({ force: true }) }, [flush])
  const dismissStale = useCallback(() => dispatch({ type: 'CLEAR_STALE' }), [])
  const clearRestored = useCallback(() => dispatch({ type: 'CLEAR_RESTORED' }), [])

  // ── leaveGuard : flush-puis-agir pour TOUTES les sorties (blueprint D2#5) ──
  const leaveGuard = useCallback(async (action) => {
    const st = stateRef.current
    if (st.mode === 'create') {
      // On ne crée pas un lead à moitié saisi en douce.
      if (confirmLeaveIfDirty(isDirty(st))) { action?.(); return true }
      return false
    }
    if (!isDirty(st)) { action?.(); return true }
    // Sortie = flush AVEC garde de fraîcheur (VX243c — critique Fable #3 :
    // checkStale n'avait AUCUN appelant, le bandeau stale était mort).
    const ok = await flush({ checkStale: true })
    if (ok) { action?.(); return true }
    if (stateRef.current.stale) {
      // Conflit de fraîcheur détecté : on RESTE — le bandeau stale s'affiche
      // (« Revoir » / « Enregistrer quand même »), jamais le confirm d'échec.
      return false
    }
    // Le flush a échoué → l'utilisateur tranche : abandonner ou rester.
    if (window.confirm("L'enregistrement a échoué. Quitter en abandonnant les modifications non enregistrées ?")) {
      action?.()
      return true
    }
    return false
  }, [flush])

  // ── changeStage : action du StageControl (blueprint D2#4) ─────────────────
  // `stage` n'entre jamais dans le draft : on vide d'abord les éditions en
  // cours, puis PATCH {stage} dédié. Le succès met à jour server.stage SEUL.
  // SIGNED est intercepté en amont par StageControl (SigneDialog). Un recul de
  // funnel remonte un 400 côté serveur — géré ICI, UN SEUL endroit pour les
  // DEUX appelants (raccourci clavier « 1-4 » LW23, StageControl LW16) :
  // jamais dupliqué au point d'appel.
  const changeStage = useCallback(async (newStage) => {
    const st = stateRef.current
    if (st.mode !== 'edit' || getField(st, 'stage') === newStage) return
    await flush({})
    try {
      const res = (await crmApi.updateLead(st.leadId, { stage: newStage })).data
      dispatch({ type: 'SET_SERVER', res })
      if (res) setOpenedAt(res.id, res.date_modification)
      onSavedRef.current?.()
    } catch (err) {
      if (err?.response?.status === 400) {
        toast.error("Retour d'étape non autorisé")
      }
      // Autre échec (réseau/serveur) : silencieux, comme le reste du moteur
      // (best-effort) — le stage affiché reste simplement l'ancien (server
      // jamais mis à jour), rien à réconcilier.
    }
  }, [flush])

  // LW25/LW24 — GET complet systématique à l'ouverture (skeleton pendant le
  // vol côté LeadWorkspace) ET rejoué en arrière-plan à chaque navigation
  // J/K, MÊME sur un voisin déjà rendu depuis le cache LW24 (le cache n'est
  // qu'un premier rendu, jamais la source de vérité). Distinct de
  // `refreshServer` : ne notifie PAS `onSaved` (ouvrir/naviguer une fiche
  // n'est pas un enregistrement — `onSaved` sert au parent à rafraîchir SA
  // liste après une vraie mutation, pas à chaque simple consultation).
  const loadFresh = useCallback(async (id) => {
    if (id == null) return
    try {
      const res = (await crmApi.getLead(id)).data
      dispatch({ type: 'SET_SERVER', res })
      if (res && res.id === id) setOpenedAt(id, res.date_modification)
    } catch { /* best-effort — le premier rendu (ligne/cache) reste affiché */ }
  }, [])

  // Recharge la vérité serveur sans toucher au draft (après devis/facture/fusion).
  const refreshServer = useCallback(async () => {
    const st = stateRef.current
    if (st.mode !== 'edit' || st.leadId == null) return
    try {
      const res = (await crmApi.getLead(st.leadId)).data
      dispatch({ type: 'SET_SERVER', res })
      if (res) setOpenedAt(res.id, res.date_modification)
      onSavedRef.current?.()
    } catch { /* best-effort */ }
  }, [])

  // Écriture ponctuelle générique (ex. StageControl/point-write d'un autre lane).
  const patchServer = useCallback((res) => dispatch({ type: 'SET_SERVER', res }), [])

  // LW12 — reset « créer un autre » : rebâtit les défauts VX93 frais (owner=moi,
  // dernière ville mémorisée) et vide le draft — customData inclus par
  // construction (server.custom_data redevient {}).
  const resetForCreate = useCallback(() => {
    dispatch({
      type: 'LOAD_LEAD',
      payload: { lead: null, mode: 'create', currentUserId, lastVille: readLastVille() },
    })
  }, [currentUserId])

  const createPayload = useCallback(() => toPayload(currentFields(stateRef.current)), [])

  // ── LOAD_LEAD à chaque VRAI changement de lead/mode (navigation) ──────────
  useEffect(() => {
    const id = leadRef.current && leadRef.current.id != null ? leadRef.current.id : null
    if (loadedRef.current === id && loadedModeRef.current === mode) return
    loadedRef.current = id
    loadedModeRef.current = mode
    const restoredDraft = (mode === 'edit' && id != null) ? readMirror(id) : null
    // LW24 — navigation J/K vers un voisin déjà pré-chargé : premier rendu
    // instantané avec la donnée complète en cache (cf. withPrefetched
    // ci-dessus) au lieu de la seule ligne partielle de `leadsQueue`.
    const effectiveLead = withPrefetched(leadRef.current, mode)
    openedAtRef.current = { id: effectiveLead && effectiveLead.id, at: effectiveLead && effectiveLead.date_modification }
    dispatch({
      type: 'LOAD_LEAD',
      payload: { lead: effectiveLead, mode, currentUserId, lastVille: readLastVille(), restoredDraft },
    })
    // On lit `leadRef.current` (jamais `lead` directement) pour ne recharger
    // qu'à un VRAI changement d'id/mode (un simple re-rendu du parent ne doit
    // pas clobberer les éditions en cours — cf. commentaire liveLead LeadForm).
  }, [lead?.id, mode, currentUserId])

  // ── Autosauvegarde débouncée (édition seulement) ─────────────────────────
  // `dirty` dérivé des seules tranches listées en deps — jamais `state` entier
  // (exhaustive-deps) : le timer de debounce ne doit se réarmer QUE quand le
  // draft bouge réellement, pas quand saveState/stale/composer changent.
  const draftDirty = isDirty(state)
  useEffect(() => {
    if (state.mode !== 'edit') return undefined
    if (!draftDirty || state.inflight) return undefined
    const t = setTimeout(() => { flush({}) }, AUTOSAVE_DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [state.mode, state.draft, draftDirty, state.inflight, flush])

  // ── Miroir sessionStorage (défense anti-perte) ───────────────────────────
  useEffect(() => {
    if (state.mode !== 'edit' || state.leadId == null) return
    if (draftDirty || state.composer.note) {
      writeMirror(state.leadId, { draft: state.draft, note: state.composer.note })
    } else {
      clearMirror(state.leadId)
    }
  }, [state.mode, state.leadId, state.draft, draftDirty, state.composer.note])

  return {
    state,
    dispatch,
    // Sélecteurs pratiques (les sections lisent `field`/`suggested`).
    field: (k) => getField(state, k),
    setField,
    suggested: (k) => isSuggested(state, k),
    dirty: isDirty(state),
    saveState: state.saveState,
    // Actions
    flush,
    retry,
    saveAnyway,
    dismissStale,
    clearRestored,
    leaveGuard,
    changeStage,
    refreshServer,
    loadFresh,
    patchServer,
    resetForCreate,
    createPayload,
  }
}

export default useLeadDraft
