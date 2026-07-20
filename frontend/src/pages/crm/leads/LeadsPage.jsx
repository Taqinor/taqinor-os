import {
  useEffect, useMemo, useRef, useState, useCallback, useDeferredValue, lazy, Suspense,
} from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useSearchParams } from 'react-router-dom'
// VX45 — ⚡/🔀 (emoji fonctionnels, rendu variable selon l'OS) remplacés par
// Zap/GitMerge (GitMerge = même icône que la section « Doublons » de
// LeadForm.jsx, features/crm/stages : un seul vocabulaire visuel).
import { Upload, Download, X, Plus, MoreHorizontal, Zap, GitMerge } from 'lucide-react'
import { useIsAdmin } from '../../../hooks/useHasPermission'
import StateBlock from '../../../components/StateBlock'
import { fetchLeads, updateLead, leadStagePatched } from '../../../features/crm/store/crmSlice'
import crmApi from '../../../api/crmApi'
import { downloadBlobInGesture } from '../../../utils/downloadBlob'
import { filterLeads, EMPTY_FILTERS, archivedParam, CONVERSION_STAGE } from '../../../features/crm/stages'
import {
  toggleId, toggleAll, pruneSelection, bulkResultMessage,
} from '../../../features/crm/bulk'
import {
  Button, IconButton, Spinner, FloatingActionButton,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator,
  FadeSwap, SkeletonCard, SkeletonTableRow,
} from '../../../ui'
// LB27 — squelette EN FORME dans le shell (blueprint I9), même hook que
// ClientList/DevisList/LeadWorkspace : rien avant 300ms (anti-flash), un
// spinner discret jusqu'à 500ms, puis un squelette au-delà.
import { useDelayedLoading } from '../../../hooks/useDelayedLoading'
import { errorMessageFrom, toastWithUndo, toastError } from '../../../lib/toast'
// LB49 — vues DE COMPTE (serveur, crm.SavedView) : useSavedViews
// (localStorage) reste aux autres écrans, la page leads passe au variant
// serveur — rang 1 = défaut de connexion, réordonnable.
import { useAccountViews } from '../../../hooks/useAccountViews'
// LB47 — le menu ⋯ porte le changement de vue sur mobile (une seule ligne
// de chrome) : même liste VIEWS que le sélecteur desktop, jamais une 2e.
import ViewSwitcher, { VIEWS } from './ViewSwitcher'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
// VX236 — `?equipe=<id>` (lien depuis MesEquipesCard) filtre la liste sur les
// membres de cette équipe — filtre client-side, aucun endpoint nouveau.
import { useEquipeMembreIds } from '../../../hooks/useEquipeMembreIds'
import useDocumentTitle from '../../../hooks/useDocumentTitle'
import LeadWorkspace from '../../../features/crm/workspace/LeadWorkspace'
import ExcelImport from '../../../components/ExcelImport'
import SavedViewsBar from '../../../components/SavedViewsBar'
import FilterBar from './FilterBar'
import LeadsKpiStrip from './LeadsKpiStrip'
import BulkActionBar from './BulkActionBar'
import DoublonsPanel from './DoublonsPanel'
import SigneDialog from './SigneDialog'
import LeadExpressModal from './LeadExpressModal'
import { SIGNE_INTERCEPT } from './signeIntercept'
// LB22 — URL partageable (blueprint D5/I7) : module PUR encode/decode
// filtres+vue ↔ URLSearchParams (urlFilters.js) — VALID_VIEWS y vit
// désormais en SEULE source (jamais une 2e liste déclarée ici).
import {
  VALID_VIEWS, hasUrlFilterState, readFiltersFromParams, readViewFromParams,
  writeFiltersToParams,
} from './urlFilters'
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

// LB49 — filtres persistés en SESSIONSTORAGE (plus localStorage) : l'état
// survit aux allers-retours vers d'autres modules DANS la session ; une
// NOUVELLE connexion repart propre → la vue rang 1 du compte s'applique.
function loadFilters() {
  try {
    const raw = sessionStorage.getItem(FILTERS_KEY)
    if (!raw) return EMPTY_FILTERS
    const parsed = JSON.parse(raw)
    return { ...EMPTY_FILTERS, ...(parsed && typeof parsed === 'object' ? parsed : {}) }
  } catch {
    return EMPTY_FILTERS
  }
}

// LB27 — squelette EN FORME de la vue active (blueprint I9) : 6 colonnes ×
// 3 SkeletonCard en kanban/prévision (la forme du board), SkeletonTableRow en
// liste ; calendrier/graphique/carte retombent sur le même bloc kanban (des
// vues moins fréquentes au premier chargement, une forme neutre suffit).
function LeadsViewSkeleton({ view }) {
  if (view === 'liste') {
    return (
      <div className="lp-skeleton-liste" aria-hidden="true">
        <table className="lv-table">
          <tbody>
            {Array.from({ length: 8 }).map((unused, i) => (
              <SkeletonTableRow key={i} columns={7} />
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  return (
    <div className="lp-skeleton-kanban" aria-hidden="true">
      {Array.from({ length: 6 }).map((unused, col) => (
        <div key={col} className="lp-skeleton-col">
          {Array.from({ length: 3 }).map((unused2, card) => (
            <SkeletonCard key={card} />
          ))}
        </div>
      ))}
    </div>
  )
}

export default function LeadsPage() {
  // VX82 — titre d'onglet dédié (chrome navigateur vivant).
  useDocumentTitle('Leads')
  const dispatch = useDispatch()
  const [searchParams, setSearchParams] = useSearchParams()
  const { leads, leadsLoading, error } = useSelector(s => s.crm)
  // VX224 — « Mes leads » par défaut : résout le toggle FilterBar.jsx contre
  // l'utilisateur COURANT (jamais un nom codé en dur) + décide du défaut par
  // rôle ci-dessous (normal=ON, manager=OFF, comportement historique inchangé).
  const currentUser = useSelector(s => s.auth.user)
  const roleTier = useSelector(s => s.auth.role)
  // LB47 — le gabarit décide du cockpit : desktop = tout en UNE ligne large ;
  // mobile = [titre|🔍|Filtres|⋯] et le reste (KPI, chips, vues, sélecteur)
  // déménage dans le panneau Filtres et le menu ⋯. Hook CANONIQUE.
  const isMobile = useIsMobile()
  // Employés assignables (avatar + nom) pour les sélecteurs de responsable des
  // cartes kanban et de la liste. Ouvert à la Commerciale (endpoint dédié).
  const [users, setUsers] = useState([])
  useEffect(() => {
    crmApi.getAssignableUsers()
      .then(r => setUsers(r.data.results ?? r.data)).catch(() => {})
  }, [])

  // Vue active, persistée (kanban par défaut, façon Odoo).
  // LB22 — priorité URL > localStorage > défaut (blueprint D5/I7) : une URL
  // collée (`?view=liste`) gagne toujours sur la vue persistée localement —
  // `readViewFromParams` renvoie `null` si `?view=` est absente/invalide, on
  // retombe alors sur le comportement historique (localStorage puis kanban).
  // LB49 — sources d'initialisation mémorisées UNE fois : le défaut de
  // connexion (vue rang 1 du compte) ne s'applique que si NI l'URL NI la
  // session n'ont déjà décidé.
  const [initSource] = useState(() => {
    let sessionView = false; let sessionFilters = false
    try {
      sessionView = sessionStorage.getItem(VIEW_KEY) != null
      sessionFilters = sessionStorage.getItem(FILTERS_KEY) != null
    } catch { /* stockage indisponible */ }
    return {
      url: !!readViewFromParams(searchParams) || hasUrlFilterState(searchParams),
      session: sessionView || sessionFilters,
    }
  })
  const [view, setView] = useState(() => {
    const fromUrl = readViewFromParams(searchParams)
    if (fromUrl) return fromUrl
    try {
      const saved = sessionStorage.getItem(VIEW_KEY)
      return VALID_VIEWS.includes(saved) ? saved : 'kanban'
    } catch {
      return 'kanban'
    }
  })
  useEffect(() => {
    try { sessionStorage.setItem(VIEW_KEY, view) } catch { /* stockage indisponible */ }
  }, [view])

  // Filtres partagés par les quatre vues — persistés en localStorage (comme la
  // vue active) pour survivre à un rechargement de page.
  // LB22 — priorité URL > localStorage > défauts (blueprint D5/I7) : une URL
  // collée (3 filtres + vue) reproduit EXACTEMENT l'écran, même en
  // navigation privée (aucun localStorage) — quand l'URL porte AU MOINS un
  // filtre géré, elle est la SEULE source retenue (jamais un mélange avec le
  // localStorage), le défaut « Mes leads » (VX224) ne s'applique alors pas
  // (un lien partagé est déjà une intention explicite).
  const [filters, setFilters] = useState(() => {
    if (hasUrlFilterState(searchParams)) return readFiltersFromParams(searchParams)
    const loaded = loadFilters()
    // VX224 — « Mes leads » ON par défaut pour le rôle `normal`, UNIQUEMENT
    // au tout premier chargement (aucun filtre encore persisté) — un choix
    // déjà fait par l'utilisateur (y compris désactivé) n'est JAMAIS écrasé.
    let hasPersisted = false
    try { hasPersisted = sessionStorage.getItem(FILTERS_KEY) != null } catch { /* no-op */ }
    return (!hasPersisted && roleTier === 'normal') ? { ...loaded, mesLeads: true } : loaded
  })
  useEffect(() => {
    try {
      sessionStorage.setItem(FILTERS_KEY, JSON.stringify(filters))
    } catch { /* stockage indisponible */ }
  }, [filters])
  // LB22 — URL partageable (blueprint D5, invariant I7 : une seule écriture
  // d'URL) : chaque changement de filtres/vue réécrit l'URL en `replace`
  // (jamais un spam d'historique — l'utilisatrice n'a jamais navigué),
  // débouncé 300ms pour ne pas fragmenter chaque frappe de recherche.
  // `applySavedView` (setFilters+setView) traverse ce même effet, aucun
  // câblage séparé nécessaire. `writeFiltersToParams` ne touche QUE ses
  // propres clés : les deep-links `?lead=`/`?new=`/`?equipe=` traversent
  // intacts (mise à jour fonctionnelle sur les derniers params réels, jamais
  // une valeur `searchParams` figée par une closure obsolète).
  useEffect(() => {
    const t = setTimeout(() => {
      setSearchParams((prev) => writeFiltersToParams(prev, filters, view), { replace: true })
    }, 300)
    return () => clearTimeout(t)
  }, [filters, view, setSearchParams])
  // VX187 — `filterLeads` recalculait en SYNCHRONE dans le commit de CHAQUE
  // frappe de la recherche (le filtre est mis à jour à chaque `onChange`) :
  // `useDeferredValue` dérive `filtered` d'une valeur qui suit `filters` avec
  // un léger retard (React garde l'input dans la lane URGENTE, le recalcul
  // lourd dans la lane DIFFÉRÉE). `isFiltersStale` (repli visuel possible :
  // atténuer la liste pendant que React rattrape) est vrai UNIQUEMENT durant
  // la fenêtre transitoire — jamais persistant.
  const deferredFilters = useDeferredValue(filters)
  const isFiltersStale = deferredFilters !== filters
  // VX236 — `?equipe=<id>` : filtre additif sur les membres de l'équipe
  // (posé APRÈS filterLeads, jamais une 2e logique de filtre dupliquée).
  const equipeId = searchParams.get('equipe')
  const equipeMembreIds = useEquipeMembreIds(equipeId)
  const filtered = useMemo(() => {
    const base = filterLeads(leads, deferredFilters, { myUsername: currentUser?.username })
    if (!equipeId || !equipeMembreIds) return base
    return base.filter((l) => equipeMembreIds.has(l.owner))
  }, [leads, deferredFilters, currentUser?.username, equipeId, equipeMembreIds])
  // Pool KPI : les leads APRÈS le filtre additif équipe (mais AVANT les
  // filtres utilisateur — la tuile force sa dimension par-dessus `filters`).
  const kpiPool = useMemo(() => {
    if (!equipeId || !equipeMembreIds) return leads
    return leads.filter((l) => equipeMembreIds.has(l.owner))
  }, [leads, equipeId, equipeMembreIds])

  // LB49 — vues enregistrées DE COMPTE (crm.SavedView) : listées par rang,
  // la n°1 est le défaut appliqué à toute nouvelle connexion, réordonnables
  // depuis les chips (▲▼). L'adaptateur conserve la forme {name, state}
  // attendue par SavedViewsBar/applySavedView/buildShareUrl.
  const {
    views: accountViews, loaded: viewsLoaded, saveView, deleteView, moveView,
  } = useAccountViews('crm.leads')
  const savedViews = useMemo(
    () => accountViews.map((v) => ({ id: v.id, name: v.name, state: v.payload })),
    [accountViews],
  )
  const saveCurrentView = async () => {
    const name = window.prompt('Nom de la vue enregistrée :')
    if (!name || !name.trim()) return
    const ok = await saveView(name, { filters, view })
    if (!ok) toastError('Enregistrement impossible — ce nom existe peut-être déjà.')
  }
  const deleteSavedView = (name) => {
    const v = savedViews.find((x) => x.name === name)
    if (v) deleteView(v.id)
  }
  const moveSavedView = (v, dir) => moveView(v.id, dir)
  const applySavedView = useCallback((v) => {
    setFilters({ ...EMPTY_FILTERS, ...(v.state?.filters || v.filters || {}) })
    const savedView = v.state?.view ?? v.view
    if (VALID_VIEWS.includes(savedView)) setView(savedView)
  }, [])
  // LB49 — défaut de connexion : la vue RANG 1 s'applique une seule fois,
  // uniquement quand ni l'URL ni la session n'ont déjà décidé (nouvelle
  // connexion nue) — jamais un écrasement d'un état choisi.
  const defaultViewApplied = useRef(false)
  useEffect(() => {
    if (defaultViewApplied.current || !viewsLoaded) return
    defaultViewApplied.current = true
    if (initSource.url || initSource.session) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réaction à l'ARRIVÉE des vues serveur (une seule fois, gardée par ref) : le défaut de connexion ne peut s'appliquer qu'après la réponse
    if (savedViews.length > 0) applySavedView(savedViews[0])
  }, [viewsLoaded, savedViews, initSource, applySavedView])
  // LB26 — « Copier le lien » d'une vue enregistrée (blueprint D5) : sérialise
  // via urlFilters.js (même module que l'URL live) sur une base VIERGE (pas
  // de `?lead=` résiduel dans un lien partagé) — le partage Reda→Meriem
  // devient un simple collage WhatsApp.
  const buildShareUrl = (v) => {
    const vFilters = { ...EMPTY_FILTERS, ...(v.state?.filters || v.filters || {}) }
    const vView = v.state?.view ?? v.view ?? 'kanban'
    const params = writeFiltersToParams(new URLSearchParams(), vFilters, vView)
    const qs = params.toString()
    return `${window.location.origin}${window.location.pathname}${qs ? `?${qs}` : ''}`
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
  // LB7 — bug recon2-03 #11 : catch silencieux (`/* ignore */`), l'export
  // échouait sans AUCUN signal visible. toastError FR désormais (I8).
  const exportFiltered = async () => {
    const ids = filtered.map((l) => l.id)
    if (!ids.length) return
    const pending = downloadBlobInGesture()
    try {
      const res = await crmApi.exportLeadsXlsx(ids)
      pending.deliver(new Blob([res.data]), 'leads.xlsx')
    } catch {
      toastError('Export indisponible — réessayez.')
    }
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
  // LB6 — useCallback : `refetch` entre dans `viewProps` (onRefetch) — une
  // référence fraîche à chaque rendu de LeadsPage cassait le memo() des vues
  // qui la reçoivent (bug #4).
  const refetch = useCallback(
    () => dispatch(fetchLeads(archivedParam(filters.archived))),
    [dispatch, filters.archived],
  )
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

  // Sélection effective : on ignore (sans muter l'état `selected`) les leads
  // disparus après un refetch OU masqués par un filtre. Dérivé → pas d'effet
  // ni de rendu en cascade.
  // LB8 — bug recon2-03 #6 : élaguait contre `leads` (TOUS les leads chargés,
  // filtre ou pas) — un lead sélectionné puis masqué par un filtre restait
  // bulk-actionnable EN INVISIBLE (la barre bulk agissait sur un lead que
  // l'utilisateur ne voyait plus à l'écran). Élague désormais contre
  // `filtered` (blueprint I5) : `selected` (l'état brut) N'EST PAS touché —
  // retirer le filtre fait réapparaître naturellement les leads déjà cochés.
  const visibleSelected = useMemo(
    () => pruneSelection(selected, filtered.map((l) => l.id)),
    [selected, filtered],
  )

  // Au moins un lead archivé dans la sélection ? Sert à griser « Restaurer »
  // (sans effet en vue « Actifs » où aucun lead n'est archivé).
  const hasArchivedSelected = useMemo(
    () => leads.some((l) => visibleSelected.has(l.id) && l.is_archived),
    [leads, visibleSelected],
  )

  // LB6 — useCallback : passées à CHAQUE carte/ligne via viewProps ;
  // `setSelected` (useState) est stable par définition, `[]` suffit (bug #4).
  const onToggleSelect = useCallback((id) => setSelected((s) => toggleId(s, id)), [])
  const onToggleAll = useCallback(
    (visibleIds) => setSelected((s) => toggleAll(s, visibleIds)),
    [],
  )
  // LB25 — useCallback : référence stable pour le raccourci Échap ci-dessous
  // (barre bulk flottante) sans le ré-abonner à chaque rendu.
  const clearSelection = useCallback(() => setSelected(new Set()), [])
  // LB25 — barre bulk FLOTTANTE (blueprint D5) : Échap la ferme, même geste
  // que le bouton « Effacer » — n'écoute que tant qu'une sélection existe
  // (jamais de listener global superflu sur le reste de la page).
  useEffect(() => {
    if (visibleSelected.size === 0) return undefined
    const onKeyDown = (e) => {
      if (e.key !== 'Escape') return
      // Critique Fable LB #6 : Échap ne vide la sélection que si RIEN d'autre
      // ne le consomme — un dialogue/menu/popover Radix ouvert (il pose
      // defaultPrevented ou vit dans [data-state="open"]) garde son Échap ;
      // sinon fermer un dialogue effacerait la sélection en silence.
      if (e.defaultPrevented) return
      if (document.querySelector(
        '[role="dialog"][data-state="open"], [role="menu"][data-state="open"], [data-radix-popper-content-wrapper]',
      )) return
      clearSelection()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [visibleSelected.size, clearSelection])

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

  // LB7 — même signal que exportFiltered (toastError FR, I8) : au lieu du
  // bandeau `bulkMsg` local (une bannière pensée pour le BILAN d'une action
  // en masse déjà commise, pas pour un échec réseau).
  const exportSelection = async () => {
    if (!visibleSelected.size) return
    const pending = downloadBlobInGesture()
    setBulkBusy(true)
    try {
      const res = await crmApi.exportLeadsXlsx([...visibleSelected])
      pending.deliver(new Blob([res.data]), 'leads.xlsx')
    } catch {
      toastError('Export indisponible — réessayez.')
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

  // VX220(b) — raccourci clavier « c l » (shortcuts.js/CommandPalette) navigue
  // vers /crm/leads?new=1 : câblage MINIMAL du paramètre — ouvre directement le
  // formulaire de création, jamais un deuxième mécanisme de quick-create
  // (NTUX possède la palette générique, périmètre réduit ici aux raccourcis
  // clavier directs, @coord NTUX9/10). Le paramètre est retiré une fois lu
  // pour ne pas rouvrir le formulaire à chaque re-render.
  useEffect(() => {
    if (searchParams.get('new') !== '1') return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- ouverture one-shot pilotée par ?new=1
    openNew()
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('new')
      return next
    }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

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
  // LB6 — useCallback : passée à CHAQUE carte/ligne via viewProps ; les
  // setters `useState` sont stables par définition, `[]` suffit (bug #4).
  const onPlanifierRelance = useCallback((lead) => {
    setEditLead(lead)
    setFormDevisIntent(null)
    setFormFocusSection('pipeline')
    setShowForm(true)
  }, [])

  // (Ré)assignation rapide du responsable depuis la carte / la liste. Le PATCH
  // journalise ancien → nouveau côté serveur (Historique) et est ouvert à la
  // Commerciale comme à l'admin.
  // LB6 — useCallback : passée à CHAQUE carte/ligne via viewProps (bug #4).
  // LB7 — bugs recon2-03 #5/#11 : plus de refetch intégral après ce PATCH
  // mono-lead (updateLead.fulfilled remplace déjà le lead au complet dans le
  // store) ; le catch silencieux toaste désormais (I8).
  const reassign = useCallback(async (lead, ownerId) => {
    try {
      await dispatch(updateLead({ id: lead.id, data: { owner: ownerId } })).unwrap()
    } catch {
      toastError('La réassignation a échoué — réessayez.')
    }
  }, [dispatch])

  // Édition en place d'un champ de la liste (T4) : PATCH d'UN seul champ.
  // perform_update journalise ancien → nouveau dans l'Historique côté serveur.
  // Renvoie la promesse pour qu'InlineEdit restaure la valeur si ça échoue.
  // LB3 — l'interception « Signé » est honnête (blueprint I3, bug #2) :
  // A2 — passer un lead en « Signé » en place ouvre le dialogue d'acceptation
  // (choix du devis + option) au lieu de modifier l'étape directement. Ancien
  // code : `return Promise.resolve()` (faux succès) laissait useOptimisticSave
  // GARDER l'étape optimiste 'SIGNED' + « Enregistré » alors que rien n'était
  // enregistré. On REJETTE avec la sentinelle SIGNE_INTERCEPT : le select
  // revient honnêtement à l'étape réelle (rollback), et l'onError de
  // StageMover avale spécifiquement cette sentinelle sans toaster.
  // LB6 — useCallback : passée à CHAQUE carte/ligne via viewProps (bug #4).
  // LB7 — bug recon2-03 #5 : plus de refetch intégral après ce PATCH
  // mono-lead. `updateLead.fulfilled` (crmSlice.js) remplace déjà le lead au
  // COMPLET dans le store (score recalculé, stage_since_days, devis…) — le
  // `.then(() => refetch())` re-déclenchait un GET /leads ENTIER pour un
  // changement d'UN champ sur UN lead, en pure perte réseau.
  const onInlineSave = useCallback((lead, field, value) => {
    if (field === 'stage' && value === CONVERSION_STAGE) {
      setSigneLead(lead)
      return Promise.reject(SIGNE_INTERCEPT)
    }
    return dispatch(updateLead({ id: lead.id, data: { [field]: value } })).unwrap()
  }, [dispatch])

  // LB5 — « ✗ Perdu » passe ENFIN par le store (blueprint I2, bug #3) :
  // LeadCard.confirmPerdu appelait crmApi.updateLead en DIRECT (contournait
  // Redux) puis `onChanged?.()`, une prop que ni KanbanView ni ForecastView
  // ne passaient JAMAIS — la carte restait active jusqu'à un refetch sans
  // rapport. Callback stable unique, partagé par LeadCard/ListView/
  // ForecastView : dispatch updateLead (le store se met à jour SEUL,
  // updateLead.fulfilled remplace déjà le lead au complet — AUCUN refetch),
  // toastError + relance l'erreur en échec (I8) pour que l'appelant garde la
  // popover ouverte plutôt que de perdre le motif saisi.
  const onMarkPerdu = useCallback((lead, motif) => (
    dispatch(updateLead({ id: lead.id, data: { perdu: true, motif_perte: motif } }))
      .unwrap()
      .catch((err) => {
        toastError('Le lead n’a pas pu être marqué perdu — réessayez.')
        throw err
      })
  ), [dispatch])

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

  // LB6 — useMemo : `viewProps` était un objet LITTÉRAL neuf à CHAQUE rendu
  // de LeadsPage — même avec des callbacks individuellement stables
  // (useCallback ci-dessus), l'objet conteneur changeait quand même de
  // référence, ce qui aurait cassé le memo() de toute vue qui le recevrait
  // en un seul bloc. Placé AVANT les retours anticipés loading/error : les
  // Hooks doivent s'exécuter dans le MÊME ORDRE à chaque rendu (règle des
  // Hooks), jamais après un retour conditionnel.
  const viewProps = useMemo(() => ({
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
    onMarkPerdu,
  }), [
    filtered, onOpenLead, changeStage, onAutoQuote, onPlanifierRelance, refetch,
    busyLeadId, users, reassign, visibleSelected, onToggleSelect, onToggleAll,
    onInlineSave, onMarkPerdu,
  ])

  // LB27 — squelette EN FORME dans le shell (blueprint I9) : au lieu de
  // blanchir la page ENTIÈRE au premier chargement (VX147's ancien retour
  // anticipé), le shell (en-tête + FilterBar + KPI) reste visible tout de
  // suite — seule la zone de vue affiche un squelette qui a la FORME de la
  // vue active. `useDelayedLoading` (même hook que ClientList/DevisList/
  // LeadWorkspace) absorbe l'anti-flash : rien avant 300ms, un spinner
  // discret jusqu'à 500ms, un squelette au-delà — jamais les deux ensemble.
  // Placé AVANT le retour anticipé error (règle des Hooks, même raison que
  // `viewProps` ci-dessus).
  const initialLoading = leadsLoading && leads.length === 0
  const { showSpinner, showSkeleton } = useDelayedLoading(initialLoading)

  // ERR61 — message FR lisible plutôt qu'un objet d'erreur brut sérialisé. Le
  // slice stocke déjà `err.response.data ?? err.message` ; on reconstruit la
  // forme attendue par `errorMessageFrom` (qui lit `error.response.data`).
  if (error) return (
    <StateBlock
      error={`Erreur : ${errorMessageFrom({ response: { data: error } }, 'Impossible de charger les leads.')}`}
    />
  )

  return (
    // LB2 — `data-view` pilote le contrat CSS de hauteur (index.css) : le
    // scrolleur change de propriétaire selon la vue active (board/liste vs
    // page-grow), sans dupliquer la logique en JS.
    <div className="page lp-page" data-view={view}>
      {/* LB43 (retour fondateur) — UNE ligne de contrôle façon Odoo (anatomie
          vérifiée à la source : boutons d'action → titre → recherche+facettes
          → navigation) : titre+compteur, la barre recherche/facettes/Filtres
          (FilterBar) au centre, et à droite ⋯ (Express/Doublons/Importer/
          Exporter/Enregistrer la vue — tout ce qui est basse fréquence),
          + Nouveau, et le sélecteur de vues. Plus jamais 3 rangées de chrome. */}
      {/* LB46 (fondateur) — TOUT le cockpit en UNE ligne large : titre →
          recherche+facettes+Filtres → KPI en chips compactes → chips de vues
          enregistrées → ⋯ / Nouveau / sélecteur. Sous ~1450px la ligne se
          replie en 2 lignes MINCES ; au téléphone (LB47) il ne reste que
          [titre|🔍|Filtres|⋯] — KPI et chips vivent dans le panneau Filtres,
          les vues et le changement de vue dans ⋯, la création dans le FAB. */}
      <div className="page-header lp-header lp-controlbar">
        <h2 className="lp-cb-title">
          Pipeline
          <span className="count-badge">{filtered.length}</span>
        </h2>
        <FilterBar
          filters={filters}
          setFilters={setFilters}
          leads={leads}
          mobile={isMobile}
          panelTop={isMobile ? (
            <LeadsKpiStrip
              leads={kpiPool}
              filters={filters}
              setFilters={setFilters}
              myUsername={currentUser?.username}
            />
          ) : null}
        />
        {/* LB24→LB46 — bandeau KPI = filtres (blueprint D5), compacté en chips
            DANS la ligne (critique Fable LB #3 : pool kpiPool, jamais leads
            brut). Sur mobile il rend DANS le panneau Filtres (panelTop). */}
        {!isMobile && (
          <LeadsKpiStrip
            leads={kpiPool}
            filters={filters}
            setFilters={setFilters}
            myUsername={currentUser?.username}
          />
        )}
        {!isMobile && (
          <SavedViewsBar
            inline
            savedViews={savedViews}
            onApply={applySavedView}
            onDelete={deleteSavedView}
            onMove={moveSavedView}
            buildShareUrl={buildShareUrl}
          />
        )}
        <div className="page-header-actions lp-header-actions">
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
              <DropdownMenuItem onSelect={() => setShowExpressModal(true)}>
                <Zap aria-hidden="true" /> Express
              </DropdownMenuItem>
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
              <DropdownMenuItem onSelect={saveCurrentView}>
                ⭐ Enregistrer cette vue
              </DropdownMenuItem>
              {/* LB47 — au téléphone, ⋯ porte AUSSI le changement de vue
                  (items depuis la MÊME liste VIEWS que le sélecteur desktop)
                  et l'application des vues enregistrées du compte. */}
              {isMobile && (
                <>
                  <DropdownMenuSeparator />
                  {VIEWS.map((vw) => {
                    // Classe lint maison #23b : le rename de déstructuration
                    // (`icon: Icon`) n'est pas crédité par no-unused-vars.
                    const Icon = vw.icon
                    return (
                      <DropdownMenuItem
                        key={vw.value}
                        onSelect={() => setView(vw.value)}
                        aria-current={view === vw.value ? 'true' : undefined}
                      >
                        <Icon aria-hidden="true" /> {vw.label}{view === vw.value ? ' ✓' : ''}
                      </DropdownMenuItem>
                    )
                  })}
                  {savedViews.length > 0 && <DropdownMenuSeparator />}
                  {savedViews.map((v) => (
                    <DropdownMenuItem key={v.name} onSelect={() => applySavedView(v)}>
                      ⭐ {v.name}
                    </DropdownMenuItem>
                  ))}
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
          {/* LB47 — au téléphone la création vit dans le FAB (déjà à portée
              de pouce) : le bouton d'en-tête ne rend qu'au desktop. */}
          {!isMobile && <Button onClick={openNew}>+ Nouveau lead</Button>}
          {!isMobile && (
            <div className="lp-header-sep" role="separator" aria-orientation="vertical" />
          )}
          {!isMobile && <ViewSwitcher view={view} setView={setView} />}
        </div>
      </div>

      {/* LB25 — barre bulk FLOTTANTE (blueprint D5) : l'ancienne barre inline
          poussait le layout à chaque sélection (le board sautait de
          hauteur) ; MÊME composant BulkActionBar (toutes les actions +
          BulkDestructiveConfirm conservées), seul le conteneur change. */}
      {visibleSelected.size > 0 && (
        <div className="lp-bulk-float">
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
        </div>
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
        {/* LB27 — trois paliers, jamais deux affichés ensemble (blueprint
            I9) : 0-300ms rien (le contenu réel, encore vide, ne flashe pas
            à cette échelle) ; 300-500ms un spinner discret ; ≥500ms le
            squelette EN FORME de la vue active, avec un crossfade FadeSwap
            (même pattern que LeadWorkspace.jsx, LW25) vers le contenu réel
            une fois les leads arrivés. */}
        {showSpinner && (
          <div className="lp-view-loading"><Spinner /> Chargement des leads…</div>
        )}
        {!showSpinner && (
        <FadeSwap
          loading={showSkeleton}
          className="lp-view-skeleton-swap"
          skeleton={<LeadsViewSkeleton view={view} />}
        >
        {/* LB9-wire — KanbanView (lane LB1, board) accepte désormais 4 props
            OPTIONNELLES pour ses empty states à deux paliers (0 lead du tout
            vs 0 résultat filtré), dégradant proprement quand absentes : même
            trio que ChartsView ci-dessous (totalLeads/onClearFilters) + les
            deux actions de coach « + Nouveau lead »/« Importer » déjà
            câblées ailleurs sur la page (openNew, l'item ⋯ Importer). */}
        {view === 'kanban' && (
          <KanbanView
            {...viewProps}
            totalLeads={leads.length}
            onClearFilters={() => setFilters(EMPTY_FILTERS)}
            onNewLead={openNew}
            onImportLeads={() => setShowImport(true)}
          />
        )}
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
        </FadeSwap>
        )}
      </div>

      {(showForm || deepLead) && (
        <LeadWorkspace
          lead={showForm ? editLead : deepLead}
          onClose={closeForm}
          onSaved={onSaved}
          onOpenDuplicate={onOpenDuplicate}
          initialDevis={showForm ? formDevisIntent : null}
          focusSection={showForm ? formFocusSection : null}
          // VX224 — session de qualification en rafale : `filtered` est déjà
          // la liste EN MÉMOIRE (même liste que ListView/KanbanView) —
          // aucune re-requête. `onOpenLead` fait déjà exactement ce qu'une
          // navigation ◀▶/J-K demande (basculer `editLead` SANS fermer la
          // fiche), réutilisé tel quel plutôt que dupliqué.
          leadsQueue={showForm ? filtered : null}
          onNavigateLead={showForm ? onOpenLead : null}
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
      {/* LB47 — le FAB devient LE bouton de création au téléphone (l'en-tête
          n'en rend plus) : il porte le nom accessible « + Nouveau lead »
          attendu par gotoLeads/MB6 (aria-label passé en prop, spread après
          le aria-label={label} interne → il gagne). */}
      <FloatingActionButton
        label="Nouveau lead"
        aria-label="+ Nouveau lead"
        icon={<Plus className="size-5" aria-hidden="true" />}
        onClick={openNew} />
    </div>
  )
}
