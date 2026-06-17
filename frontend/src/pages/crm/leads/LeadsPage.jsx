import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useSearchParams } from 'react-router-dom'
import { fetchLeads, updateLead, leadStagePatched } from '../../../features/crm/store/crmSlice'
import crmApi from '../../../api/crmApi'
import { filterLeads, EMPTY_FILTERS, archivedParam, CONVERSION_STAGE } from '../../../features/crm/stages'
import {
  toggleId, toggleAll, pruneSelection, bulkResultMessage,
} from '../../../features/crm/bulk'
import LeadForm from '../LeadForm'
import ExcelImport from '../../../components/ExcelImport'
import '../../../components/assigneepicker.css'
import FilterBar from './FilterBar'
import BulkActionBar from './BulkActionBar'
import ViewSwitcher from './ViewSwitcher'
import DoublonsPanel from './DoublonsPanel'
import SigneDialog from './SigneDialog'
import KanbanView from './views/KanbanView'
import ListView from './views/ListView'
import CalendarView from './views/CalendarView'
import ChartsView from './views/ChartsView'
import './leadspage.css'

const VIEW_KEY = 'taqinor.leads.view'
const VALID_VIEWS = ['kanban', 'liste', 'calendrier', 'graphique']

export default function LeadsPage() {
  const dispatch = useDispatch()
  const [searchParams, setSearchParams] = useSearchParams()
  const { leads, leadsLoading, error } = useSelector(s => s.crm)

  // Employés assignables (avatar + nom) pour les sélecteurs de responsable des
  // cartes kanban et de la liste. Ouvert à la Commerciale (endpoint dédié).
  const [users, setUsers] = useState([])
  useEffect(() => {
    crmApi.getAssignableUsers()
      .then(r => setUsers(r.data.results ?? r.data)).catch(() => {})
  }, [])

  // Vue active, persistée (kanban par défaut, façon Odoo).
  const [view, setView] = useState(() => {
    try {
      const saved = localStorage.getItem(VIEW_KEY)
      return VALID_VIEWS.includes(saved) ? saved : 'kanban'
    } catch {
      return 'kanban'
    }
  })
  useEffect(() => {
    try { localStorage.setItem(VIEW_KEY, view) } catch { /* stockage indisponible */ }
  }, [view])

  // Filtres partagés par les quatre vues.
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const filtered = useMemo(() => filterLeads(leads, filters), [leads, filters])

  // Formulaire lead (création / édition).
  const [showForm, setShowForm] = useState(false)
  const [editLead, setEditLead] = useState(null)
  // Intention « ouvrir directement le devis » à l'ouverture de la fiche (⚡).
  const [formDevisIntent, setFormDevisIntent] = useState(null)
  // Atelier doublons (modal).
  const [showDoublons, setShowDoublons] = useState(false)
  // Import CSV/XLSX (T9).
  const [showImport, setShowImport] = useState(false)

  // Export Excel de la liste filtrée courante (T9) — respecte les filtres.
  const exportFiltered = async () => {
    const ids = filtered.map((l) => l.id)
    if (!ids.length) return
    try {
      const res = await crmApi.exportLeadsXlsx(ids)
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url; a.download = 'leads.xlsx'
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch { /* ignore */ }
  }

  // Changement d'étape optimiste avec retour-arrière.
  const [busyLeadId, setBusyLeadId] = useState(null)
  const [stageError, setStageError] = useState(null)
  // A2 — lead en attente de confirmation « Signé » (choix du devis + option).
  const [signeLead, setSigneLead] = useState(null)

  // ── Sélection multiple (actions en masse, T3) ───────────────────────────
  const [selected, setSelected] = useState(() => new Set())
  const [bulkBusy, setBulkBusy] = useState(false)
  const [bulkMsg, setBulkMsg] = useState(null)
  const role = useSelector((s) => s.auth.role)
  const canDelete = role === 'admin'

  // Le filtre « Archivés » est une dimension SERVEUR : on refait l'appel avec
  // le bon paramètre quand il change (les autres filtres restent côté client).
  const refetch = () => dispatch(fetchLeads(archivedParam(filters.archived)))
  useEffect(() => {
    dispatch(fetchLeads(archivedParam(filters.archived)))
  }, [dispatch, filters.archived])

  // Lien profond depuis les ventes : /crm/leads?lead=<id> ouvre la fiche du
  // lead (état dérivé, aucun effet) ; fermer retire le paramètre de l'URL
  // pour que la fiche ne se ré-ouvre pas.
  const wantedLeadId = searchParams.get('lead')
  const deepLead = useMemo(() => {
    if (!wantedLeadId) return null
    return leads.find(l => String(l.id) === String(wantedLeadId)) ?? null
  }, [wantedLeadId, leads])

  useEffect(() => {
    if (!stageError) return undefined
    const t = setTimeout(() => setStageError(null), 6000)
    return () => clearTimeout(t)
  }, [stageError])

  // Le bilan d'une action en masse disparaît après quelques secondes.
  useEffect(() => {
    if (!bulkMsg) return undefined
    const t = setTimeout(() => setBulkMsg(null), 8000)
    return () => clearTimeout(t)
  }, [bulkMsg])

  // Sélection effective : on ignore (sans muter l'état) les leads disparus
  // après un refetch/filtre. Dérivé → pas d'effet ni de rendu en cascade.
  const visibleSelected = useMemo(
    () => pruneSelection(selected, leads.map((l) => l.id)),
    [selected, leads],
  )

  const onToggleSelect = (id) => setSelected((s) => toggleId(s, id))
  const onToggleAll = (visibleIds) =>
    setSelected((s) => toggleAll(s, visibleIds))
  const clearSelection = () => setSelected(new Set())

  // Action en masse : la règle métier (funnel, garde-fous, Historique) vit
  // côté serveur. On rafraîchit, on affiche le bilan et on garde la sélection
  // (élaguée aux leads encore présents par l'effet ci-dessus).
  const runBulk = async (action, params = {}) => {
    if (!visibleSelected.size) return
    setBulkBusy(true)
    try {
      const { data } = await crmApi.bulkLeads({
        ids: [...visibleSelected], action, ...params,
      })
      setBulkMsg(bulkResultMessage(data))
      refetch()
    } catch (err) {
      setBulkMsg(err?.response?.data?.detail
        ?? "L'action en masse a échoué — réessayez.")
    } finally {
      setBulkBusy(false)
    }
  }

  const exportSelection = async () => {
    if (!visibleSelected.size) return
    setBulkBusy(true)
    try {
      const res = await crmApi.exportLeadsXlsx([...visibleSelected])
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'leads.xlsx'
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch {
      setBulkMsg("Export indisponible — réessayez.")
    } finally {
      setBulkBusy(false)
    }
  }

  const openNew = () => { setEditLead(null); setFormDevisIntent(null); setShowForm(true) }
  const onOpenLead = (lead) => { setEditLead(lead); setFormDevisIntent(null); setShowForm(true) }
  const closeForm = () => {
    setShowForm(false)
    setEditLead(null)
    setFormDevisIntent(null)
    // Nettoie le lien profond ?lead=<id> pour ne pas ré-ouvrir la fiche.
    if (searchParams.has('lead')) {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev)
        next.delete('lead')
        return next
      }, { replace: true })
    }
  }
  const onSaved = () => refetch()

  // ⚡ depuis une carte / la liste : ouvre la FICHE et y lance le devis auto
  // (tout reste dans la fiche du lead — aucune navigation ailleurs).
  const onAutoQuote = (lead) => {
    setEditLead(lead)
    setFormDevisIntent('auto')
    setShowForm(true)
  }

  // (Ré)assignation rapide du responsable depuis la carte / la liste. Le PATCH
  // journalise ancien → nouveau côté serveur (Historique) et est ouvert à la
  // Commerciale comme à l'admin.
  const reassign = async (lead, ownerId) => {
    try {
      await dispatch(updateLead({ id: lead.id, data: { owner: ownerId } })).unwrap()
      refetch()
    } catch { /* erreur silencieuse */ }
  }

  // Édition en place d'un champ de la liste (T4) : PATCH d'UN seul champ.
  // perform_update journalise ancien → nouveau dans l'Historique côté serveur.
  // Renvoie la promesse pour qu'InlineEdit restaure la valeur si ça échoue.
  const onInlineSave = (lead, field, value) => {
    // A2 — passer un lead en « Signé » en place ouvre le dialogue d'acceptation
    // (choix du devis + option) au lieu de modifier l'étape directement.
    if (field === 'stage' && value === CONVERSION_STAGE) {
      setSigneLead(lead)
      return Promise.resolve()
    }
    return dispatch(updateLead({ id: lead.id, data: { [field]: value } }))
      .unwrap()
      .then(() => { refetch() })
  }

  const changeStage = async (lead, newStage) => {
    if (!lead || lead.stage === newStage) return
    // A2 — déplacer un lead dans « Signé » exige de choisir le devis accepté
    // et l'option : on ouvre le dialogue au lieu de déplacer l'étape.
    if (newStage === CONVERSION_STAGE) {
      setSigneLead(lead)
      return
    }
    const prev = lead.stage
    setBusyLeadId(lead.id)
    dispatch(leadStagePatched({ id: lead.id, stage: newStage }))
    try {
      await dispatch(updateLead({ id: lead.id, data: { stage: newStage } })).unwrap()
    } catch {
      dispatch(leadStagePatched({ id: lead.id, stage: prev }))
      setStageError("Le changement d'étape n'a pas pu être enregistré — vérifiez votre connexion et réessayez.")
    } finally {
      setBusyLeadId(null)
    }
  }

  // Only blank the page on the FIRST load. A background refetch (after saving a
  // bill, generating a devis, changing a stage…) must NOT unmount the page —
  // doing so tore down any open lead modal / inline devis preview mid-action.
  if (leadsLoading && leads.length === 0) return <p className="page-loading">Chargement des leads...</p>
  if (error) return <p className="page-error">Erreur : {JSON.stringify(error)}</p>

  const viewProps = {
    leads: filtered,
    onOpenLead,
    onChangeStage: changeStage,
    onAutoQuote,
    onRefetch: refetch,
    busyLeadId,
    users,
    onReassign: reassign,
    selected: visibleSelected,
    onToggleSelect,
    onToggleAll,
    onInlineSave,
  }

  return (
    <div className="page lp-page">
      <div className="page-header lp-header">
        <h2>
          Pipeline
          <span className="count-badge">{filtered.length}</span>
        </h2>
        <div className="page-header-actions lp-header-actions">
          <button className="btn btn-primary" onClick={openNew}>+ Nouveau lead</button>
          <button className="btn btn-outline" onClick={() => setShowDoublons(true)}>
            🔀 Doublons
          </button>
          <button className="btn btn-outline" onClick={() => setShowImport(true)}>
            ⬆ Importer
          </button>
          <button className="btn btn-outline" onClick={exportFiltered}>
            ⬇ Exporter Excel
          </button>
          <ViewSwitcher view={view} setView={setView} />
        </div>
      </div>

      <FilterBar filters={filters} setFilters={setFilters} leads={leads} />

      {visibleSelected.size > 0 && (
        <BulkActionBar
          count={visibleSelected.size}
          users={users}
          canDelete={canDelete}
          busy={bulkBusy}
          onAction={runBulk}
          onExport={exportSelection}
          onClear={clearSelection}
        />
      )}

      {bulkMsg && (
        <div className="lp-bulk-msg" role="status">
          <span>{bulkMsg}</span>
          <button
            type="button"
            className="lp-stage-error-close"
            aria-label="Fermer le message"
            onClick={() => setBulkMsg(null)}
          >
            ✕
          </button>
        </div>
      )}

      {stageError && (
        <div className="lp-stage-error" role="alert">
          <span>{stageError}</span>
          <button
            type="button"
            className="lp-stage-error-close"
            aria-label="Fermer le message d'erreur"
            onClick={() => setStageError(null)}
          >
            ✕
          </button>
        </div>
      )}

      <div className="lp-view-area">
        {view === 'kanban' && <KanbanView {...viewProps} />}
        {view === 'liste' && <ListView {...viewProps} />}
        {view === 'calendrier' && <CalendarView {...viewProps} />}
        {view === 'graphique' && <ChartsView {...viewProps} />}
      </div>

      {(showForm || deepLead) && (
        <LeadForm
          lead={showForm ? editLead : deepLead}
          onClose={closeForm}
          onSaved={onSaved}
          initialDevis={showForm ? formDevisIntent : null}
        />
      )}

      {showDoublons && (
        <DoublonsPanel
          onClose={() => setShowDoublons(false)}
          onAnyMerge={refetch}
        />
      )}

      {showImport && (
        <ExcelImport
          target="leads"
          onClose={() => setShowImport(false)}
          onDone={refetch}
        />
      )}

      {signeLead && (
        <SigneDialog
          lead={signeLead}
          onClose={() => { setSigneLead(null); refetch() }}
          onConfirmed={() => { setSigneLead(null); refetch() }}
        />
      )}
    </div>
  )
}
