import {
  useEffect, useMemo, useState, useCallback, useDeferredValue, lazy, Suspense,
} from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useSearchParams } from 'react-router-dom'
// VX45 — ⚡/🔀 (emoji fonctionnels, rendu variable selon l'OS) remplacés par
// Zap/GitMerge (GitMerge = même icône que la section « Doublons » de
// LeadForm.jsx, features/crm/stages : un seul vocabulaire visuel).
import { Upload, Download, X, Plus, MoreHorizontal, Zap, GitMerge } from 'lucide-react'
import { useIsAdmin } from '../../../hooks/useHasPermission'
import { fetchLeads, updateLead, leadStagePatched } from '../../../features/crm/store/crmSlice'
import crmApi from '../../../api/crmApi'
import { downloadBlobInGesture } from '../../../utils/downloadBlob'
import { filterLeads, EMPTY_FILTERS, archivedParam, CONVERSION_STAGE } from '../../../features/crm/stages'
import {
  toggleId, toggleAll, pruneSelection, bulkResultMessage,
} from '../../../features/crm/bulk'
import {
  Button, IconButton, Spinner, FloatingActionButton,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../../ui'
import { errorMessageFrom, toastWithUndo, toastError } from '../../../lib/toast'
import { useSavedViews } from '../../../hooks/useSavedViews'
import useDocumentTitle from '../../../hooks/useDocumentTitle'
import LeadForm from '../LeadForm'
import ExcelImport from '../../../components/ExcelImport'
import SavedViewsBar, { SaveViewButton } from '../../../components/SavedViewsBar'
import FilterBar from './FilterBar'
import BulkActionBar from './BulkActionBar'
import ViewSwitcher from './ViewSwitcher'
import DoublonsPanel from './DoublonsPanel'
import SigneDialog from './SigneDialog'
import LeadExpressModal from './LeadExpressModal'
// VX186 — KanbanView reste STATIQUE (vue par défaut la plus fréquente, zéro
// flash de chargement au premier rendu). Les 4 autres vues + Prévision sont
// désormais `lazy` : LeadsPage était le PLUS GROS chunk de route du repo
// (CarteView embarque leaflet, ChartsView embarque recharts) alors qu'une
// seule vue à la fois est visible.
import KanbanView from './views/KanbanView'
const ListView = lazy(() => import('./views/ListView'))
const CalendarView = lazy(() => import('./views/CalendarView'))
const ChartsView = lazy(() => import('./views/ChartsView'))
const CarteView = lazy(() => import('./views/CarteView'))  // FG37
const ForecastView = lazy(() => import('./views/ForecastView'))  // XSAL15

const VIEW_KEY = 'taqinor.leads.view'
const FILTERS_KEY = 'taqinor.leads.filters'
const SAVED_VIEWS_KEY = 'taqinor.leads.savedViews'
const VALID_VIEWS = ['kanban', 'liste', 'calendrier', 'graphique', 'carte', 'prevision']  // FG37, XSAL15

// loadSavedViews inlined removed — now using useSavedViews hook (FG11).

// Filtres persistés en localStorage : on fusionne avec EMPTY_FILTERS pour
// tolérer un schéma plus ancien (clés manquantes/en trop ignorées).
function loadFilters() {
  try {
    const raw = localStorage.getItem(FILTERS_KEY)
    if (!raw) return EMPTY_FILTERS
    const parsed = JSON.parse(raw)
    return { ...EMPTY_FILTERS, ...(parsed && typeof parsed === 'object' ? parsed : {}) }
  } catch {
    return EMPTY_FILTERS
  }
}

export default function LeadsPage() {
  // VX82 — titre d'onglet dédié (chrome navigateur vivant).
  useDocumentTitle('Leads')
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

  // Filtres partagés par les quatre vues — persistés en localStorage (comme la
  // vue active) pour survivre à un rechargement de page.
  const [filters, setFilters] = useState(loadFilters)
  useEffect(() => {
    try {
      localStorage.setItem(FILTERS_KEY, JSON.stringify(filters))
    } catch { /* stockage indisponible */ }
  }, [filters])
  // VX187 — `filterLeads` recalculait en SYNCHRONE dans le commit de CHAQUE
  // frappe de la recherche (le filtre est mis à jour à chaque `onChange`) :
  // `useDeferredValue` dérive `filtered` d'une valeur qui suit `filters` avec
  // un léger retard (React garde l'input dans la lane URGENTE, le recalcul
  // lourd dans la lane DIFFÉRÉE). `isFiltersStale` (repli visuel possible :
  // atténuer la liste pendant que React rattrape) est vrai UNIQUEMENT durant
  // la fenêtre transitoire — jamais persistant.
  const deferredFilters = useDeferredValue(filters)
  const isFiltersStale = deferredFilters !== filters
  const filtered = useMemo(() => filterLeads(leads, deferredFilters), [leads, deferredFilters])

  // Vues enregistrées nommées (FG11 — useSavedViews hook).
  const { savedViews, saveView, deleteView: deleteSavedView } = useSavedViews(SAVED_VIEWS_KEY)
  const saveCurrentView = () => {
    const name = window.prompt('Nom de la vue enregistrée :')
    saveView(name, { filters, view })
  }
  const applySavedView = (v) => {
    setFilters({ ...EMPTY_FILTERS, ...(v.state?.filters || v.filters || {}) })
    const savedView = v.state?.view ?? v.view
    if (VALID_VIEWS.includes(savedView)) setView(savedView)
  }

  // Formulaire lead (création / édition).
  const [showForm, setShowForm] = useState(false)
  const [editLead, setEditLead] = useState(null)
  // Intention « ouvrir directement le devis » à l'ouverture de la fiche (⚡).
  const [formDevisIntent, setFormDevisIntent] = useState(null)
  // QX25 — section à cibler à l'ouverture de la fiche (« Planifier une
  // relance » depuis la carte kanban → section « Suivi commercial »).
  const [formFocusSection, setFormFocusSection] = useState(null)
  // Atelier doublons (modal).
  const [showDoublons, setShowDoublons] = useState(false)
  // Nombre de groupes de doublons détectés (badge sur le bouton « Doublons »).
  const [doublonsCount, setDoublonsCount] = useState(0)
  const refreshDoublonsCount = () => {
    crmApi.getDoublons()
      .then(r => setDoublonsCount(Array.isArray(r.data) ? r.data.length : 0))
      .catch(() => setDoublonsCount(0))
  }
  useEffect(() => { refreshDoublonsCount() }, [])
  // Import CSV/XLSX (T9).
  const [showImport, setShowImport] = useState(false)
  // FG35 — Lead express quick capture modal.
  const [showExpressModal, setShowExpressModal] = useState(false)

  // Export Excel de la liste filtrée courante (T9) — respecte les filtres.
  // VX172 — geste ouvert AVANT le premier `await` (voir downloadBlob.js).
  const exportFiltered = async () => {
    const ids = filtered.map((l) => l.id)
    if (!ids.length) return
    const pending = downloadBlobInGesture()
    try {
      const res = await crmApi.exportLeadsXlsx(ids)
      pending.deliver(new Blob([res.data]), 'leads.xlsx')
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
  const canDelete = useIsAdmin()

  // Le filtre « Archivés » est une dimension SERVEUR : on refait l'appel avec
  // le bon paramètre quand il change (les autres filtres restent côté client).
  const refetch = () => dispatch(fetchLeads(archivedParam(filters.archived)))
  // VX55 — annule la requête en vol au démontage / changement de filtre : sans
  // ça, une réponse tardive (3G qui cale) peut écraser l'état d'un AUTRE écran
  // après navigation. `thunk.abort()` coupe le signal jusqu'à axios.
  useEffect(() => {
    const thunk = dispatch(fetchLeads(archivedParam(filters.archived)))
    return () => thunk?.abort?.()
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

  // Au moins un lead archivé dans la sélection ? Sert à griser « Restaurer »
  // (sans effet en vue « Actifs » où aucun lead n'est archivé).
  const hasArchivedSelected = useMemo(
    () => leads.some((l) => visibleSelected.has(l.id) && l.is_archived),
    [leads, visibleSelected],
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
    const ids = [...visibleSelected]
    setBulkBusy(true)
    try {
      const { data } = await crmApi.bulkLeads({ ids, action, ...params })
      setBulkMsg(bulkResultMessage(data))
      refetch()
      // VX95 — archivage en masse déjà commis serveur : « Annuler » relance
      // l'action inverse (unarchive) sur le même lot d'ids.
      if (action === 'archive' || action === 'unarchive') {
        const reverse = action === 'archive' ? 'unarchive' : 'archive'
        toastWithUndo({
          message: action === 'archive' ? 'Leads archivés.' : 'Leads restaurés.',
          onUndo: async () => {
            try {
              await crmApi.bulkLeads({ ids, action: reverse })
              refetch()
            } catch { toastError('Annulation impossible.') }
          },
        })
      }
    } catch (err) {
      setBulkMsg(err?.response?.data?.detail
        ?? "L'action en masse a échoué — réessayez.")
    } finally {
      setBulkBusy(false)
    }
  }

  const exportSelection = async () => {
    if (!visibleSelected.size) return
    const pending = downloadBlobInGesture()
    setBulkBusy(true)
    try {
      const res = await crmApi.exportLeadsXlsx([...visibleSelected])
      pending.deliver(new Blob([res.data]), 'leads.xlsx')
    } catch {
      setBulkMsg("Export indisponible — réessayez.")
    } finally {
      setBulkBusy(false)
    }
  }

  const openNew = () => { setEditLead(null); setFormDevisIntent(null); setFormFocusSection(null); setShowForm(true) }
  // VX187 — `useCallback` : cette fonction est passée à CHAQUE carte/ligne
  // via `viewProps` (LeadCard, ListView) ; recréée à chaque rendu de
  // LeadsPage, elle cassait React.memo(LeadCard) (nouvelle référence de prop
  // à chaque frappe ailleurs sur la page → re-rendu de TOUTES les cartes).
  // Les seules dépendances sont des setters `useState` — stables par
  // définition, `[]` suffit.
  const onOpenLead = useCallback((lead) => {
    setEditLead(lead); setFormDevisIntent(null); setFormFocusSection(null); setShowForm(true)
  }, [])
  const closeForm = () => {
    setShowForm(false)
    setEditLead(null)
    setFormDevisIntent(null)
    setFormFocusSection(null)
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

  // Ouvrir un doublon depuis l'avertissement du formulaire : on charge la fiche
  // complète puis on bascule le formulaire dessus (même panneau, autre lead).
  const onOpenDuplicate = (id) => {
    crmApi.getLead(id)
      .then(r => { setEditLead(r.data); setFormDevisIntent(null); setFormFocusSection(null); setShowForm(true) })
      .catch(() => {})
  }

  // ⚡ depuis une carte / la liste : ouvre la FICHE et y lance le devis auto
  // (tout reste dans la fiche du lead — aucune navigation ailleurs).
  // VX187 — useCallback (même raison que onOpenLead ci-dessus).
  const onAutoQuote = useCallback((lead) => {
    setEditLead(lead)
    setFormDevisIntent('auto')
    setFormFocusSection(null)
    setShowForm(true)
  }, [])

  // QX25 — « Planifier une relance » (bouton jusqu'ici inerte sur la carte
  // kanban, LeadCard.jsx) : ouvre la fiche du lead directement sur la section
  // « Suivi commercial » (relance_date), même machinerie que les autres
  // ouvertures de fiche (setEditLead/setShowForm).
  const onPlanifierRelance = (lead) => {
    setEditLead(lead)
    setFormDevisIntent(null)
    setFormFocusSection('pipeline')
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

  // VX187 — useCallback (même raison que onOpenLead/onAutoQuote ci-dessus) :
  // passé à chaque carte/ligne comme `onChangeStage`. Seule dépendance externe
  // réelle : `dispatch` (stable, useDispatch) — `setStageError`/`setBusyLeadId`
  // sont des setters `useState`, également stables.
  const changeStage = useCallback(async (lead, newStage) => {
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
      // VX95 — ce chemin n'est atteint QUE par le drop kanban (drag-and-drop
      // en avant, jamais un recul — gardé par KanbanView avant l'appel, ni
      // SIGNED — gardé ci-dessus par SigneDialog). « Annuler » restaure
      // l'étape antérieure EXACTE en contournant volontairement le
      // recul-guard : c'est l'undo de sa propre action, pas un recul manuel.
      toastWithUndo({
        message: 'Étape modifiée.',
        onUndo: async () => {
          dispatch(leadStagePatched({ id: lead.id, stage: prev }))
          try {
            await dispatch(updateLead({ id: lead.id, data: { stage: prev } })).unwrap()
          } catch {
            dispatch(leadStagePatched({ id: lead.id, stage: newStage }))
            toastError("Annulation impossible — vérifiez votre connexion.")
          }
        },
      })
    } catch {
      dispatch(leadStagePatched({ id: lead.id, stage: prev }))
      setStageError("Le changement d'étape n'a pas pu être enregistré — vérifiez votre connexion et réessayez.")
    } finally {
      setBusyLeadId(null)
    }
  }, [dispatch])

  // Only blank the page on the FIRST load. A background refetch (after saving a
  // bill, generating a devis, changing a stage…) must NOT unmount the page —
  // doing so tore down any open lead modal / inline devis preview mid-action.
  if (leadsLoading && leads.length === 0) {
    return (
      <p className="page-loading"><Spinner /> Chargement des leads…</p>
    )
  }
  // ERR61 — message FR lisible plutôt qu'un objet d'erreur brut sérialisé. Le
  // slice stocke déjà `err.response.data ?? err.message` ; on reconstruit la
  // forme attendue par `errorMessageFrom` (qui lit `error.response.data`).
  if (error) return (
    <p className="page-error">
      Erreur : {errorMessageFrom({ response: { data: error } }, 'Impossible de charger les leads.')}
    </p>
  )

  const viewProps = {
    leads: filtered,
    onOpenLead,
    onChangeStage: changeStage,
    onAutoQuote,
    onPlanifierRelance,
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
          <Button onClick={openNew}>+ Nouveau lead</Button>
          <Button
            variant="outline"
            title="Saisie express : nom + téléphone + canal"
            onClick={() => setShowExpressModal(true)}
          ><Zap aria-hidden="true" size={14} /> Express</Button>
          {/* VX145(b) — Doublons/Importer/Exporter sont des fréquences basses
              face aux 2 contrôles ci-dessus ; démotés dans un menu « ⋯ »
              (pattern DropdownMenu déjà importé dans ListView.jsx). */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" title="Plus d'actions" aria-label="Plus d'actions">
                <MoreHorizontal />
                {doublonsCount > 0 && (
                  <span className="count-badge" title="Groupes de doublons détectés">
                    {doublonsCount}
                  </span>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => setShowDoublons(true)}>
                <GitMerge aria-hidden="true" /> Doublons
                {doublonsCount > 0 && (
                  <span className="count-badge" title="Groupes de doublons détectés">
                    {doublonsCount}
                  </span>
                )}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setShowImport(true)}>
                <Upload /> Importer
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={exportFiltered}>
                <Download /> Exporter Excel
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {/* VX145(c) — le déclencheur vit dans la rangée d'en-tête déjà
              existante ; SavedViewsBar (chips) ne rend une rangée dédiée que
              s'il y a au moins une vue enregistrée. */}
          <SaveViewButton onSave={saveCurrentView} />
          <div className="lp-header-sep" role="separator" aria-orientation="vertical" />
          <ViewSwitcher view={view} setView={setView} />
        </div>
      </div>

      <FilterBar filters={filters} setFilters={setFilters} leads={leads} />

      <SavedViewsBar
        savedViews={savedViews}
        onApply={applySavedView}
        onDelete={deleteSavedView}
      />

      {visibleSelected.size > 0 && (
        <BulkActionBar
          count={visibleSelected.size}
          users={users}
          canDelete={canDelete}
          hasArchivedSelected={hasArchivedSelected}
          busy={bulkBusy}
          onAction={runBulk}
          onExport={exportSelection}
          onClear={clearSelection}
        />
      )}

      {bulkMsg && (
        <div className="lp-bulk-msg" role="status">
          <span>{bulkMsg}</span>
          <IconButton
            variant="ghost"
            className="lp-stage-error-close"
            label="Fermer le message"
            onClick={() => setBulkMsg(null)}
          >
            <X />
          </IconButton>
        </div>
      )}

      {stageError && (
        <div className="lp-stage-error" role="alert">
          <span>{stageError}</span>
          <IconButton
            variant="ghost"
            className="lp-stage-error-close"
            label="Fermer le message d'erreur"
            onClick={() => setStageError(null)}
          >
            <X />
          </IconButton>
        </div>
      )}

      {/* VX187 — atténuation discrète pendant que React rattrape le filtre
          différé (jamais sur l'input lui-même, seulement la liste rendue). */}
      <div className="lp-view-area" style={isFiltersStale ? { opacity: 0.6 } : undefined}>
        {view === 'kanban' && <KanbanView {...viewProps} />}
        {/* VX186 — Suspense autour des vues lazy uniquement (Kanban reste
            synchrone, jamais de flash sur le rendu par défaut). */}
        <Suspense fallback={<div className="lp-view-loading"><Spinner /> Chargement de la vue…</div>}>
          {view === 'liste' && <ListView {...viewProps} />}
          {view === 'calendrier' && <CalendarView {...viewProps} />}
          {view === 'graphique' && (
            <ChartsView
              {...viewProps}
              totalLeads={leads.length}
              onClearFilters={() => setFilters(EMPTY_FILTERS)}
            />
          )}
          {/* FG37 — Vue carte : leads par GPS, colorés par étape */}
          {view === 'carte' && (
            <CarteView
              leads={filtered}
              onOpenLead={onOpenLead}
            />
          )}
          {/* XSAL15 — Vue prévision : leads ouverts groupés par mois de clôture
              prévue, glisser une carte replanifie le mois. */}
          {view === 'prevision' && <ForecastView {...viewProps} />}
        </Suspense>
      </div>

      {(showForm || deepLead) && (
        <LeadForm
          lead={showForm ? editLead : deepLead}
          onClose={closeForm}
          onSaved={onSaved}
          onOpenDuplicate={onOpenDuplicate}
          initialDevis={showForm ? formDevisIntent : null}
          focusSection={showForm ? formFocusSection : null}
        />
      )}

      {showDoublons && (
        <DoublonsPanel
          onClose={() => { setShowDoublons(false); refreshDoublonsCount() }}
          onAnyMerge={() => { refetch(); refreshDoublonsCount() }}
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

      {/* FG35 — Lead express quick capture */}
      {showExpressModal && (
        <LeadExpressModal
          onClose={() => setShowExpressModal(false)}
          onSaved={() => { setShowExpressModal(false); refetch() }}
        />
      )}

      {/* VX42 — FAB mobile : le pouce vit dans le tiers bas de l'écran ; le
          bouton « + Nouveau lead » du header n'y est pas toujours atteignable
          sans faire défiler. Même action que le bouton desktop (openNew). */}
      <FloatingActionButton
        label="Nouveau lead"
        icon={<Plus className="size-5" aria-hidden="true" />}
        onClick={openNew} />
    </div>
  )
}
