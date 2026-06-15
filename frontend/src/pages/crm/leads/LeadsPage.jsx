import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useSearchParams } from 'react-router-dom'
import { fetchLeads, updateLead, leadStagePatched } from '../../../features/crm/store/crmSlice'
import crmApi from '../../../api/crmApi'
import { filterLeads, EMPTY_FILTERS, archivedParam } from '../../../features/crm/stages'
import LeadForm from '../LeadForm'
import '../../../components/assigneepicker.css'
import FilterBar from './FilterBar'
import ViewSwitcher from './ViewSwitcher'
import DoublonsPanel from './DoublonsPanel'
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

  // Changement d'étape optimiste avec retour-arrière.
  const [busyLeadId, setBusyLeadId] = useState(null)
  const [stageError, setStageError] = useState(null)

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

  const changeStage = async (lead, newStage) => {
    if (!lead || lead.stage === newStage) return
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

  if (leadsLoading) return <p className="page-loading">Chargement des leads...</p>
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
          <ViewSwitcher view={view} setView={setView} />
        </div>
      </div>

      <FilterBar filters={filters} setFilters={setFilters} leads={leads} />

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
    </div>
  )
}
