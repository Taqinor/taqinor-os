import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { fetchLeads, updateLead, leadStagePatched } from '../../../features/crm/store/crmSlice'
import { filterLeads, EMPTY_FILTERS } from '../../../features/crm/stages'
import LeadForm from '../LeadForm'
import FilterBar from './FilterBar'
import ViewSwitcher from './ViewSwitcher'
import KanbanView from './views/KanbanView'
import ListView from './views/ListView'
import CalendarView from './views/CalendarView'
import ChartsView from './views/ChartsView'
import './leadspage.css'

const VIEW_KEY = 'taqinor.leads.view'
const VALID_VIEWS = ['kanban', 'liste', 'calendrier', 'graphique']

export default function LeadsPage() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { leads, leadsLoading, error } = useSelector(s => s.crm)

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

  // « Devis auto » — remise puis lancement du générateur.
  const [autoLead, setAutoLead] = useState(null)
  const [autoDiscount, setAutoDiscount] = useState('0')

  // Changement d'étape optimiste avec retour-arrière.
  const [busyLeadId, setBusyLeadId] = useState(null)
  const [stageError, setStageError] = useState(null)

  useEffect(() => { dispatch(fetchLeads()) }, [dispatch])

  useEffect(() => {
    if (!stageError) return undefined
    const t = setTimeout(() => setStageError(null), 6000)
    return () => clearTimeout(t)
  }, [stageError])

  const openNew = () => { setEditLead(null); setShowForm(true) }
  const onOpenLead = (lead) => { setEditLead(lead); setShowForm(true) }
  const closeForm = () => { setShowForm(false); setEditLead(null) }
  const onSaved = () => dispatch(fetchLeads())

  const onAutoQuote = (lead) => { setAutoLead(lead); setAutoDiscount('0') }
  const launchAutoQuote = () => {
    const id = autoLead.id
    const d = autoDiscount !== '' ? autoDiscount : '0'
    setAutoLead(null)
    navigate(`/ventes/devis/nouveau?lead=${id}&discount=${encodeURIComponent(d)}&auto=1`)
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
    busyLeadId,
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

      {showForm && (
        <LeadForm lead={editLead} onClose={closeForm} onSaved={onSaved} />
      )}

      {/* ── Devis automatique : remise puis lancement ── */}
      {autoLead && (
        <div className="modal-overlay" onClick={() => setAutoLead(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                ⚡ Devis automatique — {autoLead.nom} {autoLead.prenom || ''}
              </h3>
              <button type="button" className="modal-close" onClick={() => setAutoLead(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p className="gen-hint">
                Le devis sera dimensionné automatiquement depuis la facture du lead
                ({autoLead.facture_hiver
                  ? `${autoLead.facture_hiver} MAD${autoLead.ete_differente && autoLead.facture_ete ? ` hiver / ${autoLead.facture_ete} MAD été` : '/mois'}`
                  : 'aucune facture enregistrée — saisissez-la d\'abord via Éditer'}),
                avec l'équipement auto-rempli depuis le stock, puis créé en brouillon
                lié à ce lead.
              </p>
              <div className="form-group">
                <label className="form-label">Réduction (%) — optionnelle</label>
                <input type="number" min="0" max="100" step="any" className="form-control"
                       value={autoDiscount}
                       onChange={e => setAutoDiscount(e.target.value)} />
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-outline" onClick={() => setAutoLead(null)}>
                Annuler
              </button>
              <button type="button" className="btn btn-primary"
                      disabled={!autoLead.facture_hiver}
                      onClick={launchAutoQuote}>
                ⚡ Créer le devis automatique
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
