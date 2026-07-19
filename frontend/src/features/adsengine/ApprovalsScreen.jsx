import { useEffect, useState, useCallback } from 'react'
import { Check, X, ClipboardCheck, AlertTriangle, PlusCircle, RefreshCw } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  actionTypeLabel, budgetDiff, actionCreative, formatMAD, REJECTION_REASONS,
  actionWarnings, editCopyDiff,
} from './adsengine'
import EditCopyComposer from './EditCopyComposer'
// PUB10 — la console montrait Approuver/Rejeter à tout `responsable` alors que
// le back exige `adsengine_approve` (permission DISTINCTE de proposer,
// ENG19) — découverte en 403 seulement. Masque/grise les contrôles.
import { useAdsPermissions } from './useAdsPermissions'
import AlertCenter from './AlertCenter'
import CommandPalette from './CommandPalette'
import SyncStatusBanner from './SyncStatusBanner'
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling'

/* ============================================================================
   PUB51 — Raccourcis clavier (« pile d'approbations traitable sans souris »).
   ----------------------------------------------------------------------------
   J/K déplacent le focus visuel entre les cartes ; A approuve la carte
   focalisée ; R ouvre son panneau de rejet structuré (jamais un rejet
   direct — le motif reste requis, comportement inchangé). JAMAIS déclenché
   pendant qu'un champ texte/select est focalisé (le rejet ouvre justement un
   ``<select>`` — taper dedans ne doit jamais être intercepté). PUB10 — A/R
   respectent la même permission `adsengine_approve` que les boutons (un
   utilisateur sans droit d'approbation ne doit pas pouvoir approuver au
   clavier) ; J/K restent libres de toute permission (navigation seule).
   ========================================================================== */
const TYPING_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT'])
function isTypingTarget(el) {
  if (!el) return false
  if (TYPING_TAGS.has(el.tagName)) return true
  return !!el.isContentEditable
}

// PUB41 — sondage doux (poll_ms) de la boîte d'approbation : l'écran-vaisseau-
// amiral doit refléter une nouvelle proposition sans que le fondateur ait à
// rafraîchir la page. Suspendu onglet masqué (`useVisibilityAwarePolling`,
// VX56) ; rafraîchissement IMMÉDIAT au retour au premier plan.
const APPROVALS_POLL_MS = 20000

/* ============================================================================
   ENG25 — Boîte d'approbation (l'écran-vaisseau-amiral).
   ----------------------------------------------------------------------------
   Doctrine (scope-features.md — la boîte d'approbation EST le produit) : chaque
   carte `EngineAction` montre l'ARTEFACT RÉEL (préview du créatif, diff budget
   avant→après) + `reason_fr` (le « pourquoi »), et l'humain approuve/rejette via
   des CONTRÔLES STRUCTURÉS — JAMAIS un chat libre. Le rejet passe par un motif
   choisi dans une liste (REJECTION_REASONS), pas une zone de texte ouverte.
   Vue batch : toggle par item, approbation de la sélection (batch PARTIEL
   possible). Une action appliquée QUITTE la boîte immédiatement.
   Approuver reste une permission distincte de proposer (ENG19, gated backend) :
   si l'API refuse, l'action reste dans la boîte et une erreur s'affiche.
   ========================================================================== */

export default function ApprovalsScreen() {
  // PUB10 — adsengine_approve gate Approuver/Rejeter (batch inclus) ;
  // adsengine_manage gate le composeur (propose une nouvelle EngineAction).
  const { has } = useAdsPermissions()
  const canApprove = has('adsengine_approve')
  const canManage = has('adsengine_manage')
  const [actions, setActions] = useState([])
  // PUB41 — `loading` ne couvre QUE le tout premier chargement : un sondage
  // en arrière-plan ne doit jamais faire clignoter l'écran-vaisseau-amiral
  // (« poll doux »). `loadError` distingue une PANNE (message dédié) d'une
  // boîte réellement vide (jamais un silence — l'écran le plus critique).
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [selected, setSelected] = useState(() => new Set()) // ids du batch
  const [rejectingId, setRejectingId] = useState(null)
  const [rejectReason, setRejectReason] = useState(REJECTION_REASONS[0].value)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  // ADSDEEP35 — composeur EDIT_COPY (avant/après + envoi comme proposition).
  const [showComposer, setShowComposer] = useState(false)

  const load = useCallback(() => {
    adsengineApi.actions.pending()
      .then(r => {
        const raw = Array.isArray(r.data) ? r.data : (r.data?.results || [])
        // L'API EngineAction expose le genre dans `kind` ; les libellés / le
        // diff EDIT_COPY (adsengine.js) lisent `type`. On normalise ici (sans
        // écraser un `type` déjà présent) pour que la carte affiche le bon
        // libellé et le diff avant/après contre les vraies données.
        setActions(raw.map(a => ({ ...a, type: a.type ?? a.kind })))
        setLoadError(false)
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }, [])

  // PUB41 — sondage doux : amorçage immédiat au montage (comme l'ancien
  // `useEffect(load)`), puis toutes les `APPROVALS_POLL_MS`, suspendu onglet
  // masqué, rafraîchissement immédiat au retour.
  const { resume } = useVisibilityAwarePolling(
    [{ fn: load, intervalMs: APPROVALS_POLL_MS }])

  // Retire une (ou plusieurs) action(s) appliquée(s) de la boîte + du batch.
  const removeApplied = (ids) => {
    const set = new Set(ids)
    setActions(list => list.filter(a => !set.has(a.id)))
    setSelected(sel => {
      const next = new Set(sel)
      ids.forEach(id => next.delete(id))
      return next
    })
  }

  const approve = async (id) => {
    setBusy(true); setErr('')
    try {
      await adsengineApi.actions.approve(id)
      removeApplied([id])
    } catch {
      setErr("Approbation refusée (permission ?). L'action reste dans la boîte.")
    } finally {
      setBusy(false)
    }
  }

  const openReject = (id) => {
    setRejectingId(id)
    setRejectReason(REJECTION_REASONS[0].value)
  }

  // PUB51 — focus visuel pour les raccourcis clavier (jamais de souris requise).
  const [focusedIndex, setFocusedIndex] = useState(0)

  // Le focus reste dans les bornes quand la liste change (approbation/rejet
  // retire une carte, chargement initial…).
  useEffect(() => {
    setFocusedIndex(i => (actions.length === 0 ? 0 : Math.min(i, actions.length - 1)))
  }, [actions.length])

  useEffect(() => {
    const onKey = (e) => {
      // Jamais pendant qu'un champ texte/select est focalisé (ex. le motif
      // de rejet structuré) — ni avec un modificateur (laisse Ctrl-K/copier/
      // coller… intacts).
      if (isTypingTarget(document.activeElement)) return
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const key = e.key.toLowerCase()
      if (key === 'j') {
        e.preventDefault()
        setFocusedIndex(i => Math.min(i + 1, Math.max(actions.length - 1, 0)))
      } else if (key === 'k') {
        e.preventDefault()
        setFocusedIndex(i => Math.max(i - 1, 0))
      } else if (key === 'a') {
        // PUB10 — même garde que le bouton Approuver : sans adsengine_approve,
        // le raccourci clavier ne doit pas contourner la permission.
        if (!canApprove) return
        const current = actions[focusedIndex]
        if (current) { e.preventDefault(); approve(current.id) }
      } else if (key === 'r') {
        // PUB10 — même garde que le bouton Rejeter.
        if (!canApprove) return
        const current = actions[focusedIndex]
        if (current) { e.preventDefault(); openReject(current.id) }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [actions, focusedIndex, approve, openReject, canApprove])

  const confirmReject = async (id) => {
    setBusy(true); setErr('')
    try {
      await adsengineApi.actions.reject(id, { reason: rejectReason })
      setRejectingId(null)
      removeApplied([id])
    } catch {
      setErr("Rejet impossible. L'action reste dans la boîte.")
    } finally {
      setBusy(false)
    }
  }

  const toggleSelect = (id) => setSelected(sel => {
    const next = new Set(sel)
    if (next.has(id)) next.delete(id); else next.add(id)
    return next
  })

  // Batch PARTIEL : n'approuve QUE les cases cochées.
  const approveSelected = async () => {
    const ids = actions.map(a => a.id).filter(id => selected.has(id))
    if (ids.length === 0) return
    setBusy(true); setErr('')
    try {
      await Promise.all(ids.map(id => adsengineApi.actions.approve(id)))
      removeApplied(ids)
    } catch {
      setErr("Une partie de la sélection n'a pu être approuvée.")
      load()
    } finally {
      setBusy(false)
    }
  }

  const selectedCount = actions.filter(a => selected.has(a.id)).length

  return (
    <div className="page ae-approvals">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <ClipboardCheck size={20} aria-hidden="true" /> Boîte d&apos;approbation
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {/* PUB41 — reprise manuelle du sondage (ex. après une panne prolongée). */}
          <button type="button" className="btn btn-light" data-testid="ae-approvals-refresh"
            onClick={resume}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
            <RefreshCw size={15} aria-hidden="true" /> Actualiser
          </button>
          <button type="button" className="btn btn-light ae-toggle-composer"
            data-testid="ae-toggle-composer"
            disabled={!showComposer && !canManage}
            title={!showComposer && !canManage
              ? "Nécessite la permission de gestion (adsengine_manage)." : undefined}
            onClick={() => setShowComposer(v => !v)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
            <PlusCircle size={15} aria-hidden="true" />
            {showComposer ? 'Fermer le composeur' : "Éditer le texte d'une ad"}
          </button>
          {/* PUB48 — centre de notifications persistant de la console */}
          <AlertCenter />
          {/* PUB51 — palette de commandes (Ctrl-K) */}
          <CommandPalette />
        </div>
      </div>

      {/* PUB41 — bandeau global « Meta ne répond plus… » (fraîcheur/panne). */}
      <SyncStatusBanner />

      {/* PUB51 — rappel des raccourcis clavier (jamais requis, juste visible) */}
      {actions.length > 0 && (
        <p className="ae-shortcuts-hint" data-testid="ae-shortcuts-hint"
          style={{ color: '#94a3b8', fontSize: '0.8rem', margin: '0 0 0.6rem' }}>
          Raccourcis : <kbd>J</kbd>/<kbd>K</kbd> naviguer · <kbd>A</kbd> approuver · <kbd>R</kbd> rejeter · <kbd>Ctrl</kbd>+<kbd>K</kbd> palette
        </p>
      )}

      {showComposer && (
        <EditCopyComposer onProposed={() => { setShowComposer(false); load() }} />
      )}

      {err && <p data-testid="ae-approvals-err" style={{ color: '#dc2626' }}>{err}</p>}

      {/* PUB41 — état-ERREUR distinct de l'état-vide : jamais un silence sur
          l'écran le plus critique (l'approbation dépend de le voir). */}
      {loadError && (
        <p data-testid="ae-approvals-load-error" role="alert" style={{ color: '#dc2626' }}>
          Chargement des propositions impossible — panne de synchronisation possible.
          {actions.length > 0 ? ' Liste peut-être obsolète (nouvelle tentative automatique en cours).' : ''}
        </p>
      )}

      {/* Barre de batch (toggle par item ci-dessous) */}
      {selectedCount > 0 && (
        <div className="ae-batch-bar" data-testid="ae-batch-bar"
          style={{ display: 'flex', alignItems: 'center', gap: '0.75rem',
            background: '#eef2ff', padding: '0.6rem 0.9rem', borderRadius: 8, marginBottom: '1rem' }}>
          <span data-testid="ae-batch-count">{selectedCount} sélectionnée(s)</span>
          <button type="button" className="btn btn-primary" data-testid="ae-batch-approve"
            disabled={busy || !canApprove}
            title={!canApprove ? "Nécessite la permission d'approbation (adsengine_approve)." : undefined}
            onClick={approveSelected}
            style={{ minHeight: 44, minWidth: 44, padding: '0.6rem 1.1rem' }}>
            Approuver la sélection
          </button>
        </div>
      )}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : actions.length === 0
          ? (!loadError && (
              <p data-testid="ae-approvals-empty" style={{ color: '#64748b' }}>
                Aucune action en attente d&apos;approbation.</p>
            ))
          : (
            <div style={{ display: 'grid', gap: '1rem' }}>
              {actions.map((a, i) => {
                const diff = budgetDiff(a)
                const creative = actionCreative(a)
                const warnings = actionWarnings(a)
                const copyDiff = editCopyDiff(a)
                // PUB51 — carte visuellement focalisée pour la navigation J/K.
                const focused = i === focusedIndex
                return (
                  <article key={a.id}
                    className={`card ae-action-card${focused ? ' ae-action-card-focused' : ''}`}
                    data-testid="ae-action-card" aria-current={focused ? 'true' : undefined}
                    style={{ padding: '1rem',
                      border: focused ? '2px solid #2563eb' : '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem' }}>
                      {/* PUB56 — cible tactile ≥44×44px (le checkbox visuel
                          reste petit ; la zone cliquable, elle, ne l'est
                          pas) : un label enveloppant sert de zone de tap. */}
                      <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
                        minWidth: 44, minHeight: 44, cursor: 'pointer', flexShrink: 0 }}>
                        <input type="checkbox" className="ae-batch-toggle"
                          data-testid={`ae-batch-toggle-${a.id}`}
                          checked={selected.has(a.id)} onChange={() => toggleSelect(a.id)}
                          aria-label={`Sélectionner l'action ${actionTypeLabel(a.type)}`}
                          style={{ width: 18, height: 18 }} />
                      </label>
                      <div style={{ flex: 1 }}>
                        <h3 style={{ margin: 0 }}>{actionTypeLabel(a.type)}</h3>

                        {/* Le « pourquoi » — reason_fr */}
                        <p data-testid="ae-action-reason" style={{ margin: '0.35rem 0', color: '#334155' }}>
                          {a.reason_fr || 'Aucune raison fournie.'}
                        </p>

                        {/* Artefact réel — diff budget avant→après */}
                        {diff && (
                          <div className="ae-artifact-budget" data-testid="ae-artifact-budget"
                            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem',
                              background: '#f8fafc', padding: '0.5rem 0.75rem', borderRadius: 6 }}>
                            <span>{formatMAD(diff.avant)}</span>
                            <span aria-hidden="true">→</span>
                            <strong style={{
                              color: diff.direction === 'up' ? '#b91c1c'
                                : diff.direction === 'down' ? '#15803d' : '#334155' }}>
                              {formatMAD(diff.apres)}
                            </strong>
                            <span style={{ color: '#64748b', fontSize: '0.85rem' }}>
                              ({diff.delta > 0 ? '+' : ''}{formatMAD(diff.delta)})
                            </span>
                          </div>
                        )}

                        {/* ADSDEEP31/32/34 — avertissements (reset d'apprentissage,
                            perte de preuve sociale, immutabilité d'étude…) : PORTÉS
                            par le backend, jamais recalculés ici. */}
                        {warnings.length > 0 && (
                          <div className="ae-warnings" data-testid="ae-warnings"
                            style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', margin: '0.4rem 0' }}>
                            {warnings.map((w, i) => (
                              <span key={i} className="ae-warning-chip" data-testid="ae-warning-chip"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
                                  background: '#fff7ed', color: '#9a3412', border: '1px solid #fed7aa',
                                  borderRadius: 999, padding: '0.2rem 0.6rem', fontSize: '0.8rem' }}>
                                <AlertTriangle size={12} aria-hidden="true" /> {w}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* ADSDEEP35 — avant/après côte à côte (EDIT_COPY) */}
                        {copyDiff && (
                          <div className="ae-edit-copy-diff" data-testid="ae-edit-copy-diff"
                            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem',
                              background: '#f8fafc', padding: '0.6rem', borderRadius: 6, margin: '0.5rem 0' }}>
                            <div data-testid="ae-edit-copy-before">
                              <strong style={{ fontSize: '0.8rem', color: '#64748b' }}>Actuel</strong>
                              <p style={{ margin: '0.2rem 0' }}>{copyDiff.before.body || '—'}</p>
                            </div>
                            <div data-testid="ae-edit-copy-after">
                              <strong style={{ fontSize: '0.8rem', color: '#64748b' }}>Proposé</strong>
                              <p style={{ margin: '0.2rem 0' }}>{copyDiff.after.body || '—'}</p>
                            </div>
                          </div>
                        )}

                        {/* Artefact réel — préview du créatif */}
                        {creative && (
                          <div className="ae-artifact-creative" data-testid="ae-artifact-creative"
                            style={{ marginTop: '0.5rem' }}>
                            {creative.url
                              ? <img src={creative.url} alt={creative.designation}
                                  style={{ maxWidth: 240, maxHeight: 160, borderRadius: 6, display: 'block' }} />
                              : <div style={{ padding: '0.75rem', background: '#f1f5f9',
                                  borderRadius: 6, color: '#475569' }}>
                                  {creative.designation}{creative.type ? ` (${creative.type})` : ''}
                                </div>}
                          </div>
                        )}

                        {/* Contrôles STRUCTURÉS — jamais du chat.
                            PUB56 — cibles tactiles ≥44px (min-height/width
                            explicites, au-delà du min-height 36px de .btn). */}
                        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
                          <button type="button" className="btn btn-success ae-approve"
                            data-testid={`ae-approve-${a.id}`} disabled={busy || !canApprove}
                            title={!canApprove ? "Nécessite la permission d'approbation (adsengine_approve)." : undefined}
                            onClick={() => approve(a.id)}
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
                              minHeight: 44, minWidth: 44, padding: '0.6rem 1.1rem' }}>
                            <Check size={15} aria-hidden="true" /> Approuver
                          </button>
                          <button type="button" className="btn btn-danger-outline ae-reject"
                            data-testid={`ae-reject-${a.id}`} disabled={busy || !canApprove}
                            title={!canApprove ? "Nécessite la permission d'approbation (adsengine_approve)." : undefined}
                            onClick={() => openReject(a.id)}
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
                              minHeight: 44, minWidth: 44, padding: '0.6rem 1.1rem' }}>
                            <X size={15} aria-hidden="true" /> Rejeter
                          </button>
                        </div>

                        {/* Motif de rejet STRUCTURÉ (select — jamais du texte libre) */}
                        {rejectingId === a.id && (
                          <div className="ae-reject-panel" data-testid={`ae-reject-panel-${a.id}`}
                            style={{ display: 'flex', gap: '0.5rem', marginTop: '0.6rem', flexWrap: 'wrap',
                              alignItems: 'center' }}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <span style={{ fontSize: '0.85rem', color: '#475569' }}>Motif</span>
                              <select className="form-input ae-reject-reason"
                                data-testid={`ae-reject-reason-${a.id}`}
                                value={rejectReason}
                                onChange={e => setRejectReason(e.target.value)}
                                style={{ minHeight: 44 }}>
                                {REJECTION_REASONS.map(r => (
                                  <option key={r.value} value={r.value}>{r.label}</option>
                                ))}
                              </select>
                            </label>
                            <button type="button" className="btn btn-danger ae-reject-confirm"
                              data-testid={`ae-reject-confirm-${a.id}`} disabled={busy || !canApprove}
                              onClick={() => confirmReject(a.id)}
                              style={{ minHeight: 44, minWidth: 44, padding: '0.6rem 1.1rem' }}>
                              Confirmer le rejet
                            </button>
                            <button type="button" className="btn btn-light"
                              onClick={() => setRejectingId(null)}
                              style={{ minHeight: 44, minWidth: 44, padding: '0.6rem 1.1rem' }}>
                              Annuler</button>
                          </div>
                        )}
                      </div>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
    </div>
  )
}
