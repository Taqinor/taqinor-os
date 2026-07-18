import { createElement, useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import api from '../../../api/axios'
import crmApi from '../../../api/crmApi'
import {
  createLead, archiveLead, restoreLead,
} from '../store/crmSlice'
import {
  Button, IconButton, Switch,
  Dialog, DialogContent, DialogTitle,
  Sheet, SheetContent, SheetTitle,
} from '../../../ui'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
import { useServerFieldErrors } from '../../../hooks/useServerFieldErrors'
import { isTypingTarget } from '../../../providers/shortcuts'
import { useFocusedRecordShortcuts, LEAD_STAGE_SHORTCUTS } from '../../../providers/focusedRecordShortcuts'
import { useLeadDraft, rememberVille } from './useLeadDraft'
import { schedulePrefetch } from './leadPrefetch'
import { getField } from './draftCore'
import IdentityRail from './IdentityRail'
import SectionsPane from './SectionsPane'
import ContextRail from './ContextRail'
// Satellites INCHANGÉS de place (blueprint) — importés par le shell.
import LeadDevisPanel from '../../../pages/crm/leads/LeadDevisPanel'
import SigneDialog from '../../../pages/crm/leads/SigneDialog'
import PlanActiviteDialog from '../../../pages/crm/leads/PlanActiviteDialog'
import ConvertirClientDialog from '../../../pages/crm/leads/ConvertirClientDialog'

// LW10 — Le shell `LeadWorkspace` : UNE fenêtre, deux enveloppes (Dialog quasi
// plein écran depuis la liste/kanban ; pleine page à /crm/leads/:id), le scroll
// JUSTE PAR CONSTRUCTION (grille rows auto/1fr, min-height:0, chaque zone son
// propre overflow). Contrat de props identique à LeadForm — les appelants ne
// changent pas (bascule en LW13). LW12 complète le mode création.

// Validation e-mail minimale (le formulaire est noValidate) — miroir LeadForm.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// VX224/VX92 — « Créer un autre » : persisté par utilisateur (localStorage),
// défaut OFF. Une session de qualification en rafale = 20-40 leads/j.
const CREER_UN_AUTRE_KEY = 'taqinor.leadForm.creerUnAutre'
const lireCreerUnAutre = () => {
  try { return localStorage.getItem(CREER_UN_AUTRE_KEY) === '1' } catch { return false }
}
const ecrireCreerUnAutre = (v) => {
  try { localStorage.setItem(CREER_UN_AUTRE_KEY, v ? '1' : '0') } catch { /* best-effort */ }
}

// Chip d'état de sauvegarde (autosauvegarde D2). Jamais de spinner bloquant.
function SaveChip({ saveState, onRetry }) {
  if (saveState === 'saving') {
    return <span className="lw-savechip lw-savechip--saving" role="status" aria-live="polite">Enregistrement…</span>
  }
  if (saveState === 'saved') {
    return <span className="lw-savechip lw-savechip--saved" role="status" aria-live="polite">✓ Enregistré</span>
  }
  if (saveState === 'error') {
    return (
      <button type="button" className="lw-savechip lw-savechip--error" onClick={onRetry}>
        ⚠ Non enregistré — Réessayer
      </button>
    )
  }
  return null
}

export default function LeadWorkspace({
  lead = null, onClose, onSaved,
  leadsQueue = null, onNavigateLead = null,
  initialDevis = null, focusSection = null,
  onOpenDuplicate = null,
  variant = 'dialog',
}) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  const mode = lead ? 'edit' : 'create'
  const currentUserId = useSelector((s) => s.auth?.user?.id)

  const draft = useLeadDraft(lead, { mode, currentUserId, onSaved })
  const {
    state, field, setField, saveState, leaveGuard, changeStage,
  } = draft
  // Primitives STABLES hoistées : le compilateur React (lint v7) refuse de
  // préserver un useCallback dont les deps mêlent optional-chaining et objet
  // entier — on ne dépend que de scalaires.
  const leadId = lead?.id ?? null
  const leadArchived = !!lead?.is_archived
  const { errors, setErrors, setFromResponse } = useServerFieldErrors()

  // ── Données de référence (partagées avec les rails / sections) ────────────
  const [users, setUsers] = useState([])
  const [tagOptions, setTagOptions] = useState([])
  const [motifOptions, setMotifOptions] = useState([])
  const [historique, setHistorique] = useState([])
  const [dups, setDups] = useState([])

  useEffect(() => {
    crmApi.getAssignableUsers().then((r) => setUsers(r.data.results ?? r.data)).catch(() => {})
    crmApi.getTags().then((r) => setTagOptions((r.data.results ?? r.data).filter((t) => !t.archived))).catch(() => {})
    crmApi.getMotifsPerte().then((r) => setMotifOptions((r.data.results ?? r.data).filter((m) => !m.archived))).catch(() => {})
  }, [])

  const refreshHistorique = useCallback(() => {
    if (!leadId) return
    api.get(`/crm/leads/${leadId}/historique/`).then((r) => setHistorique(r.data)).catch(() => {})
  }, [leadId])

  useEffect(() => {
    if (mode !== 'edit' || !leadId) return
    refreshHistorique()
    crmApi.getLeadDuplicates(leadId).then((r) => setDups(r.data)).catch(() => {})
  }, [mode, leadId, refreshHistorique])

  // ── Satellites (dialogues) ────────────────────────────────────────────────
  const [devisPanel, setDevisPanel] = useState(null)
  const [panelDevisId, setPanelDevisId] = useState(null)
  const [signeOpen, setSigneOpen] = useState(false)
  const [planOpen, setPlanOpen] = useState(false)
  const [convertOpen, setConvertOpen] = useState(false)
  const [archiveBusy, setArchiveBusy] = useState(false)

  // Ouverture directe sur un mode devis (⚡ d'une carte / liste).
  const devisIntentRan = useRef(false)
  useEffect(() => {
    if (mode === 'edit' && initialDevis && !devisIntentRan.current) {
      devisIntentRan.current = true
      setDevisPanel(initialDevis)
    }
  }, [mode, initialDevis])

  // Archivage : passe TOUJOURS par leaveGuard (flush d'abord) — l'archivage ne
  // peut plus structurellement jeter des éditions non sauvées (tue P1#3).
  const doArchive = useCallback(() => {
    if (!leadId) return
    leaveGuard(async () => {
      setArchiveBusy(true)
      try {
        if (leadArchived) await dispatch(restoreLead(leadId)).unwrap()
        else await dispatch(archiveLead(leadId)).unwrap()
        onSaved?.()
        onClose?.()
      } catch { /* silencieux */ } finally { setArchiveBusy(false) }
    })
  }, [leadId, leadArchived, leaveGuard, dispatch, onSaved, onClose])

  // Contrat d'action des rails (IdentityRail/ContextRail — autres lanes) :
  // toutes les sorties/points de mutation passent par ici.
  const onAction = useCallback((type, payload) => {
    switch (type) {
      case 'archive': return doArchive()
      case 'convert': return setConvertOpen(true)
      case 'plan': return setPlanOpen(true)
      case 'signe': return setSigneOpen(true)
      case 'toiture-3d':
        return leaveGuard(() => { if (leadId) navigate(`/devis-design/${leadId}`) })
      case 'open-devis': return setDevisPanel(payload || 'auto')
      case 'view-devis': setPanelDevisId(payload); return setDevisPanel('view')
      case 'refresh': return draft.refreshServer()
      case 'close': return leaveGuard(onClose)
      default: return undefined
    }
  }, [doArchive, leaveGuard, leadId, navigate, draft, onClose])

  // ── File de rafale (◀▶ + J/K), gardée par leaveGuard (draft flushé) ───────
  const queueIndex = (leadsQueue && mode === 'edit')
    ? leadsQueue.findIndex((l) => l.id === lead.id) : -1
  const prevInQueue = queueIndex > 0 ? leadsQueue[queueIndex - 1] : null
  const nextInQueue = (queueIndex >= 0 && queueIndex < leadsQueue.length - 1)
    ? leadsQueue[queueIndex + 1] : null

  const goToLead = useCallback((target) => {
    if (!target || !onNavigateLead) return
    leaveGuard(() => onNavigateLead(target))
  }, [onNavigateLead, leaveGuard])

  // J/K façon Gmail — effet AVEC dep array (corrige le smell recon 01 §6.4 :
  // ré-abonnement à chaque rendu) + garde isTypingTarget.
  useEffect(() => {
    if (mode !== 'edit' || !leadsQueue || !onNavigateLead) return undefined
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (isTypingTarget(e.target)) return
      if (e.key === 'j' || e.key === 'J') { e.preventDefault(); goToLead(nextInQueue) }
      else if (e.key === 'k' || e.key === 'K') { e.preventDefault(); goToLead(prevInQueue) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mode, leadsQueue, onNavigateLead, goToLead, nextInQueue, prevInQueue])

  // ── LW24 : pré-chargement en idle des voisins de file (J/K instantané) ────
  // Se contente d'ALIMENTER le cache module-level (leadPrefetch.js) — la
  // CONSOMMATION (premier rendu instantané) vit dans useLeadDraft.js
  // (LOAD_LEAD). Annulé proprement si la file change avant le déclenchement.
  useEffect(() => {
    if (mode !== 'edit' || !leadsQueue) return undefined
    const ids = [prevInQueue?.id, nextInQueue?.id].filter((id) => id != null)
    if (!ids.length) return undefined
    return schedulePrefetch(ids, (id) => crmApi.getLead(id).then((r) => r.data))
  }, [mode, leadsQueue, prevInQueue, nextInQueue])

  // ── LW23 : registre de raccourcis propre (a/d/n/1-4) ──────────────────────
  // `a` archiver (leaveGuard déjà structurel dans doArchive), `d` focus le
  // picker Responsable de l'IdentityRail (hook DOM stable `.ap-trigger` —
  // fichier d'une autre lane, jamais importé), `n` bascule Historique +
  // focus composer (événement `lw:open-note-composer`, ContextRail — LW19-21
  // — DOIT écouter), `1`-`4` = StageControl (LEAD_STAGE_SHORTCUTS, jamais
  // SIGNED/COLD). Handlers mémoïsés → `useFocusedRecordShortcuts` reçoit un
  // objet STABLE, donc son propre effet clavier (dep array réparé,
  // providers/focusedRecordShortcuts.jsx) ne se réabonne plus à chaque rendu.
  const onStageShortcut = useCallback((def) => { changeStage(def.stage) }, [changeStage])
  const focusedHandlers = useMemo(() => ({
    a: () => doArchive(),
    d: () => { document.querySelector('.ap-trigger')?.focus() },
    n: () => { window.dispatchEvent(new CustomEvent('lw:open-note-composer', { detail: { leadId } })) },
    '1': onStageShortcut,
    '2': onStageShortcut,
    '3': onStageShortcut,
    '4': onStageShortcut,
  }), [doArchive, onStageShortcut, leadId])
  useFocusedRecordShortcuts('leadForm', focusedHandlers, mode === 'edit')

  // ── Fermeture (✕/overlay/Escape) via leaveGuard ──────────────────────────
  const requestClose = useCallback(() => { leaveGuard(onClose) }, [leaveGuard, onClose])

  // ── Création : le formulaire rapide (défauts VX93, « créer un autre ») ────
  const [saving, setSaving] = useState(false)
  const [creerUnAutre, setCreerUnAutre] = useState(() => mode === 'create' && lireCreerUnAutre())
  const [savedConfirm, setSavedConfirm] = useState(false)
  const savedConfirmTimer = useRef(null)
  useEffect(() => () => { if (savedConfirmTimer.current) clearTimeout(savedConfirmTimer.current) }, [])

  const CREATE_FORM_ID = 'lw-create-form'
  const handleCreateSubmit = async (e) => {
    e.preventDefault()
    // Validation client identique à LeadForm (nom requis, email regex,
    // perdu→motif requis). SIGNED est structurellement impossible en création
    // (pas de StageControl, stage=NEW par défaut).
    const ve = {}
    if (!String(field('nom') || '').trim()) ve.nom = 'Nom requis'
    const email = String(field('email') || '').trim()
    if (email && !EMAIL_RE.test(email)) ve.email = 'Email invalide'
    if (field('perdu') && !String(field('motif_perte') || '').trim()) {
      ve.motif_perte = 'Indiquez le motif de perte'
    }
    if (Object.keys(ve).length) { setErrors(ve); return }
    setSaving(true)
    try {
      await dispatch(createLead(draft.createPayload())).unwrap()
      rememberVille(field('ville')) // VX93 — mémorise la ville pour le prochain lead
      onSaved?.()
      if (creerUnAutre) {
        // Reset COMPLET vers les défauts VX93 frais (owner=moi, ville mémorisée,
        // canal walk_in) — customData INCLUS (parité LW4, purgé par LOAD_LEAD) —
        // puis refocus #lf-nom, au lieu de fermer.
        draft.resetForCreate()
        setErrors({})
        if (savedConfirmTimer.current) clearTimeout(savedConfirmTimer.current)
        setSavedConfirm(true)
        savedConfirmTimer.current = setTimeout(() => setSavedConfirm(false), 2000)
        setTimeout(() => document.getElementById('lf-nom')?.focus(), 0)
      } else {
        onClose?.()
      }
    } catch (err) {
      setFromResponse(err)
    } finally {
      setSaving(false)
    }
  }

  const nomTitre = mode === 'edit'
    ? `Lead — ${getField(state, 'nom') || ''} ${getField(state, 'prenom') || ''}`.trim()
    : 'Nouveau lead'

  // ── Rendu du contenu (partagé dialog / sheet / page) ──────────────────────
  const renderBody = (TitleComp) => (
    <div className="lw-root">
      <header className="lw-topbar">
        <div className="lw-topbar-left">
          {mode === 'edit' && leadsQueue && (
            <span className="lw-nav">
              <IconButton
                label="Lead précédent (touche K)" variant="ghost" size="icon-sm"
                disabled={!prevInQueue} onClick={() => goToLead(prevInQueue)}
              >
                ◀
              </IconButton>
              {queueIndex >= 0 && (
                <span className="lw-nav-pos">{queueIndex + 1} / {leadsQueue.length}</span>
              )}
              <IconButton
                label="Lead suivant (touche J)" variant="ghost" size="icon-sm"
                disabled={!nextInQueue} onClick={() => goToLead(nextInQueue)}
              >
                ▶
              </IconButton>
            </span>
          )}
          {/* createElement explicite : le pipeline compilateur+no-unused-vars
              perd la référence du paramètre quand il est utilisé comme balise
              JSX dynamique (faux positif « TitleComp is never used ») —
              l'appel de fonction direct est, lui, toujours compté. */}
          {createElement(
            TitleComp,
            { className: 'modal-title lw-title' },
            nomTitre,
            (mode === 'edit' && lead?.is_archived)
              ? <span key="arch" className="lw-archived-badge">Archivé</span>
              : null,
          )}
        </div>
        <div className="lw-topbar-right">
          {mode === 'edit' && <SaveChip saveState={saveState} onRetry={draft.retry} />}
          <button type="button" className="modal-close" onClick={requestClose} aria-label="Fermer">✕</button>
        </div>
      </header>

      {state.restored && (
        <div role="status" className="lw-banner lw-banner--info">
          <span>Brouillon restauré — vos modifications non enregistrées ont été récupérées.</span>
          <Button type="button" size="sm" variant="ghost" onClick={draft.clearRestored}>OK</Button>
        </div>
      )}

      {state.stale && (
        <div role="alert" className="lw-banner lw-banner--warning">
          <span>
            Modifié par {state.stale.theirs || 'un autre utilisateur'} pendant votre édition —
            {' '}vérifiez avant d&apos;enregistrer.
          </span>
          <span className="lw-banner-actions">
            <Button type="button" size="sm" variant="outline" onClick={draft.dismissStale}>Revoir</Button>
            <Button type="button" size="sm" variant="outline" onClick={draft.saveAnyway}>Enregistrer quand même</Button>
          </span>
        </div>
      )}

      <div className={`lw-body ${mode === 'create' ? 'lw-body--create' : 'lw-body--edit'}`}>
        {mode === 'edit' && (
          <IdentityRail state={state} onAction={onAction} users={users} archiveBusy={archiveBusy} />
        )}
        <SectionsPane
          state={state}
          setField={setField}
          errors={errors}
          mode={mode}
          focusSection={focusSection}
          formId={CREATE_FORM_ID}
          onSubmit={handleCreateSubmit}
          refData={{
            users, tagOptions, motifOptions, dups,
            leadId: lead?.id ?? null, onOpenDuplicate, suggested: draft.suggested,
          }}
        />
        {mode === 'edit' && (
          <ContextRail
            state={state}
            users={users}
            historique={historique}
            refreshHistorique={refreshHistorique}
            onAction={onAction}
          />
        )}
      </div>

      {mode === 'create' && (
        <footer className="lw-footer">
          {/* VX224/VX92 — « Créer un autre » : création uniquement, persisté. */}
          <label className="mr-auto flex items-center gap-2 text-sm text-muted-foreground">
            <Switch
              checked={creerUnAutre}
              onCheckedChange={(v) => { setCreerUnAutre(v); ecrireCreerUnAutre(v) }}
              aria-label="Créer un autre"
            />
            Créer un autre
          </label>
          {savedConfirm && (
            <span className="lw-savechip lw-savechip--saved" role="status" aria-live="polite">
              ✓ Enregistré
            </span>
          )}
          {errors.submit && <span className="lw-footer-error" role="alert">{errors.submit}</span>}
          <Button type="button" variant="outline" onClick={requestClose}>Annuler</Button>
          <Button type="submit" form={CREATE_FORM_ID} loading={saving} disabled={saving}>
            {saving ? 'Enregistrement…' : 'Créer le lead'}
          </Button>
        </footer>
      )}
    </div>
  )

  // ── Satellites montés hors flux (édition uniquement) ─────────────────────
  const satellites = mode === 'edit' && (
    <>
      {devisPanel && (
        <LeadDevisPanel
          lead={state.server}
          mode={devisPanel}
          existingDevisId={devisPanel === 'view' ? panelDevisId : null}
          onDevisChanged={draft.refreshServer}
          onClose={() => { setDevisPanel(null); setPanelDevisId(null); draft.refreshServer() }}
        />
      )}
      {signeOpen && (
        <SigneDialog
          lead={state.server}
          onClose={() => setSigneOpen(false)}
          onConfirmed={() => { setSigneOpen(false); onSaved?.(); onClose?.() }}
        />
      )}
      {planOpen && (
        <PlanActiviteDialog
          lead={state.server}
          onClose={() => setPlanOpen(false)}
          onApplied={() => onSaved?.()}
        />
      )}
      {convertOpen && (
        <ConvertirClientDialog
          lead={state.server}
          onClose={() => setConvertOpen(false)}
          onConverted={draft.refreshServer}
        />
      )}
    </>
  )

  // ── Enveloppes ────────────────────────────────────────────────────────────
  if (variant === 'page') {
    return (
      <div className="lw-page">
        {renderBody('h1')}
        {satellites}
      </div>
    )
  }

  if (isMobile) {
    return (
      <>
        <Sheet open onOpenChange={(o) => { if (!o) requestClose() }}>
          <SheetContent side="bottom" showClose={false} className="lw-sheet p-0">
            {renderBody(SheetTitle)}
          </SheetContent>
        </Sheet>
        {satellites}
      </>
    )
  }

  return (
    <>
      <Dialog open onOpenChange={(o) => { if (!o) requestClose() }}>
        <DialogContent showClose={false} className="lw-dialog p-0 gap-0 overflow-hidden">
          {renderBody(DialogTitle)}
        </DialogContent>
      </Dialog>
      {satellites}
    </>
  )
}
