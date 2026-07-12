import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Pencil, FileText, Trash2, Upload, Plus, FilePlus } from 'lucide-react'
import { useIsAdmin } from '../../hooks/useHasPermission'
import { fetchClients, deleteClient, updateClient } from '../../features/crm/store/crmSlice'
import ventesApi from '../../api/ventesApi'
import crmApi from '../../api/crmApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import ClientForm from './ClientForm'
import ClientDetailPanel from './ClientDetailPanel'
import ExcelImport from '../../components/ExcelImport'
import SavedViewsBar, { SaveViewButton } from '../../components/SavedViewsBar'
import {
  DataTable, Badge, Button, Segmented,
  Skeleton, SkeletonTableRow, EmptyState,
} from '../../ui'
import { StateBlock } from '../../components/StateBlock'
import { useConfirmDialog, toast } from '../../ui/confirm'
import { useDelayedLoading } from '../../hooks/useDelayedLoading'
import ClientTypeToggle from './ClientTypeToggle'
import { useSavedViews } from '../../hooks/useSavedViews'
import { formatMAD } from '../../lib/format'

const CL_SAVED_VIEWS_KEY = 'taqinor.crm.clients.savedViews'

const formatDateFR = (iso) => new Date(iso).toLocaleDateString('fr-FR')

// Un client est « entreprise » s'il porte ce type ou un identifiant légal B2B.
const isEntreprise = (c) => c.type_client === 'entreprise'
  || !!(c.ice || c.if_fiscal || c.rc)

const TYPE_FILTERS = [
  { value: 'tous', label: 'Tous' },
  { value: 'particulier', label: 'Particuliers' },
  { value: 'entreprise', label: 'Entreprises' },
]

export default function ClientList() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { clients, loading, error } = useSelector(s => s.crm)
  const isAdmin = useIsAdmin()
  const { confirmDelete } = useConfirmDialog()
  // Squelette différé : on n'affiche le chargement que s'il dure (anti-flash).
  const { showSkeleton } = useDelayedLoading(loading)

  const [showForm, setShowForm]     = useState(false)
  const [editClient, setEditClient] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [showImport, setShowImport] = useState(false)
  const [typeFilter, setTypeFilter] = useState('tous')
  // Vues enregistrées (FG11).
  const { savedViews, saveView, deleteView } = useSavedViews(CL_SAVED_VIEWS_KEY)
  const saveCurrentView = () => {
    const name = window.prompt('Nom de la vue enregistrée :')
    saveView(name, { typeFilter })
  }
  const applyView = (v) => {
    if (v.state?.typeFilter) setTypeFilter(v.state.typeFilter)
  }
  // Panneau détail (lecture) : devis / factures / chantiers du client cliqué.
  const [detailClient, setDetailClient] = useState(null)
  // VX220 — lien profond ?id=<pk> (patron VX79 déjà lu par InstallationsPage.jsx/
  // TicketsPage.jsx) : la palette de commandes (⌘K) ouvre désormais le CLIENT
  // exact plutôt que la liste. État DÉRIVÉ (aucun effet) — un id absent des
  // clients chargés reste simplement sans panneau (jamais une page blanche).
  const wantedId = searchParams.get('id')
  const deepClient = useMemo(() => {
    if (!wantedId) return null
    return (clients ?? []).find(c => String(c.id) === String(wantedId)) ?? null
  }, [wantedId, clients])
  const clearDeepLink = () => {
    if (searchParams.has('id')) {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev)
        next.delete('id')
        return next
      }, { replace: true })
    }
  }
  // Panneau ouvert : sélection manuelle OU client ciblé par le lien profond.
  const detailItem = detailClient ?? deepClient

  // VX55 — annule la requête en vol au démontage : sans ça, une réponse tardive
  // (3G qui cale) peut écraser l'état d'un AUTRE écran après navigation.
  useEffect(() => {
    const thunk = dispatch(fetchClients())
    return () => thunk?.abort?.()
  }, [dispatch])

  // Filtre segmenté par type (Particulier / Entreprise), appliqué avant le
  // DataTable (qui garde sa propre recherche/tri/export sur le sous-ensemble).
  const visibleClients = useMemo(() => {
    if (typeFilter === 'tous') return clients
    if (typeFilter === 'entreprise') return clients.filter(isEntreprise)
    return clients.filter(c => !isEntreprise(c))
  }, [clients, typeFilter])

  const openNew   = () => { setEditClient(null); setShowForm(true) }
  const openEdit  = c  => { setEditClient(c);    setShowForm(true) }
  const closeForm = () => { setShowForm(false);  setEditClient(null) }

  // VX220(b) — raccourci clavier « c c » (shortcuts.js/CommandPalette) navigue
  // vers /crm?new=1 : câblage MINIMAL du paramètre — ouvre directement le
  // formulaire de création (périmètre réduit, @coord NTUX9/10 — cf. LeadsPage.jsx
  // même patron). Le paramètre est retiré une fois lu.
  useEffect(() => {
    if (searchParams.get('new') !== '1') return
    openNew()
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('new')
      return next
    }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const openReleve = async (c) => {
    try {
      const res = await ventesApi.getClientRelevePdf(c.id)
      openPdfBlob(res.data, `Releve_${c.nom}.pdf`)
    } catch { toast.error('Relevé indisponible.') }
  }

  const handleDelete = async (c) => {
    const fullName = [c.nom, c.prenom].filter(Boolean).join(' ')
    const ok = await confirmDelete({
      title: `Supprimer le client « ${fullName} » ?`,
      description: 'Cette action est irréversible.',
    })
    if (!ok) return
    setDeletingId(c.id)
    try {
      await dispatch(deleteClient(c.id)).unwrap()
      toast.success('Client supprimé.')
    } catch (err) {
      // Message serveur en clair (ex. client protégé par ses devis) —
      // jamais de JSON brut ni d'échec silencieux.
      toast.error(err?.detail
        ?? 'Suppression impossible — réessayez ou contactez l\'administrateur.')
    } finally {
      setDeletingId(null)
    }
  }

  // Suppression EN MASSE (admin) : ne supprime QUE les clients sans devis lié
  // (devis_count===0). Les clients protégés par un devis sont ignorés avec un
  // message FR clair — jamais d'orphelinage de pièces financières.
  const bulkDelete = async (rows, _keys, clear) => {
    const supprimables = rows.filter((c) => (c.devis_count ?? 0) === 0)
    const proteges = rows.length - supprimables.length
    if (!supprimables.length) {
      toast.error('Aucun client supprimable : tous les clients sélectionnés ont '
        + 'des devis liés (protégés).')
      return
    }
    const description = proteges > 0
      ? `${proteges} client(s) avec devis seront ignorés (protégés).`
      : 'Cette action est irréversible.'
    const ok = await confirmDelete({
      title: `Supprimer ${supprimables.length} client(s) sans devis ?`,
      description,
    })
    if (!ok) return
    let done = 0
    for (const c of supprimables) {
      try { await dispatch(deleteClient(c.id)).unwrap(); done += 1 } catch { /* ignoré */ }
    }
    toast.success(`${done} client(s) supprimé(s).`)
    clear?.()
  }

  // Export Excel : DataTable nous passe le jeu courant (filtré par sa recherche).
  const exportRows = async (rows) => {
    const ids = rows.map(c => c.id)
    if (!ids.length) return
    try {
      const res = await crmApi.exportClientsXlsx(ids)
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url; a.download = 'clients.xlsx'
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch { toast.error('Export indisponible — réessayez.') }
  }

  // L151 — bascule optimiste du type de client (Particulier ↔ Entreprise),
  // seul « statut » persisté du client. Passe par le thunk updateClient
  // existant ; rollback automatique si le PATCH échoue.
  const saveType = (c, next) =>
    dispatch(updateClient({ id: c.id, data: { type_client: next } })).unwrap()

  const columns = useMemo(() => [
    {
      id: 'nom',
      header: 'Client',
      width: 200,
      hideable: false,
      accessor: (c) => [c.nom, c.prenom].filter(Boolean).join(' '),
      // VX144(c) — empilement 2 lignes déterministe à 200px : nom+pastille
      // toujours ensemble sur la 1re ligne, badge ICE toujours en dessous
      // (jamais avant le nom, quel que soit l'ordre de wrap du flex).
      cell: (value, c) => (
        <span className="flex flex-col gap-0.5">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="font-medium">{value || '—'}</span>
            {/* L151 — type éditable en place avec enregistrement optimiste. */}
            <ClientTypeToggle client={c} onSave={(next) => saveType(c, next)} />
          </span>
          {isEntreprise(c) && !c.ice && (
            <Badge tone="warning" title="Identifiant ICE manquant sur un client B2B">
              ICE manquant
            </Badge>
          )}
        </span>
      ),
      exportValue: (c) => [c.nom, c.prenom].filter(Boolean).join(' '),
    },
    {
      id: 'ice',
      header: 'ICE',
      width: 160,
      // Affiche l'ICE mais rend recherchables tous les identifiants légaux
      // (ICE/IF/RC/CIN) : l'accesseur les concatène pour la recherche globale,
      // la cellule n'affiche que l'ICE depuis la ligne.
      accessor: (c) => [c.ice, c.if_fiscal, c.rc, c.cin].filter(Boolean).join(' '),
      exportValue: (c) => c.ice || '',
      cell: (_value, c) => (c.ice
        ? <span className="font-mono text-xs">{c.ice}</span>
        : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'email',
      header: 'Email',
      width: 220,
      cell: (value) => (
        <a className="link-blue" href={`mailto:${value}`} onClick={(e) => e.stopPropagation()}>{value}</a>
      ),
    },
    {
      id: 'telephone',
      header: 'Téléphone',
      width: 150,
      cell: (value) => value || '—',
    },
    {
      id: 'adresse',
      header: 'Adresse',
      width: 220,
      searchable: false,
      accessor: (c) => (c.adresse ? c.adresse.split('\n')[0] : ''),
      cell: (value) => (
        <span className="text-truncate" title={value}>{value || '—'}</span>
      ),
    },
    {
      id: 'valeur',
      header: 'Valeur client',
      align: 'right',
      numeric: true,
      width: 150,
      searchable: false,
      // Total facturé (TTC) cumulé, avec l'encaissé en sous-ligne. Montants
      // client-facing uniquement (aucun prix d'achat ni marge).
      accessor: (c) => Number(c.total_facture_ttc ?? 0),
      cell: (_value, c) => {
        const facture = Number(c.total_facture_ttc ?? 0)
        const paye = Number(c.total_paye ?? 0)
        if (!facture && !paye) return <span className="text-muted-foreground">—</span>
        return (
          <span className="flex flex-col items-end leading-tight">
            <span className="font-medium">{formatMAD(facture)}</span>
            <span className="text-xs text-muted-foreground">
              Payé : {formatMAD(paye)}
            </span>
          </span>
        )
      },
      exportValue: (c) => Number(c.total_facture_ttc ?? 0),
    },
    {
      id: 'devis_count',
      header: 'Devis',
      align: 'right',
      numeric: true,
      width: 90,
      searchable: false,
      accessor: (c) => c.devis_count ?? 0,
      // La pastille devient un lien vers la liste des devis pré-filtrée sur ce
      // client (uniquement si le client a au moins un devis).
      cell: (value, c) => (value ? (
        <button
          type="button"
          className="appearance-none border-0 bg-transparent p-0"
          title="Voir les devis de ce client"
          onClick={(e) => {
            e.stopPropagation()
            navigate(`/ventes/devis?client=${c.id}`)
          }}
        >
          <Badge tone="info">{value}</Badge>
        </button>
      ) : <Badge tone="neutral">{value}</Badge>),
    },
    {
      id: 'date_creation',
      header: 'Depuis',
      align: 'right',
      width: 120,
      searchable: false,
      cell: (value) => (
        <span className="text-muted-foreground">{value ? formatDateFR(value) : '—'}</span>
      ),
      exportValue: (c) => (c.date_creation ? formatDateFR(c.date_creation) : ''),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [])

  const rowActions = (c) => {
    const actions = [
      { id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => openEdit(c) },
      {
        id: 'devis',
        label: 'Nouveau devis',
        icon: FilePlus,
        onClick: () => navigate(`/ventes/devis/nouveau?client=${c.id}`),
      },
      { id: 'releve', label: 'Relevé', icon: FileText, onClick: () => openReleve(c) },
    ]
    if (isAdmin) {
      actions.push({
        id: 'delete',
        label: deletingId === c.id ? 'Suppression…' : 'Supprimer',
        icon: Trash2,
        destructive: true,
        separatorBefore: true,
        disabled: deletingId === c.id,
        onClick: () => handleDelete(c),
      })
    }
    return actions
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Clients
          {clients.length > 0 && (
            <span className="count-badge">{clients.length}</span>
          )}
        </h2>
        <div className="page-header-actions">
          <Button variant="outline" onClick={() => setShowImport(true)}>
            <Upload /> Importer
          </Button>
          <Button onClick={openNew}>
            <Plus /> Nouveau client
          </Button>
        </div>
      </div>

      {showForm && (
        <ClientForm client={editClient} onClose={closeForm} />
      )}

      {showImport && (
        <ExcelImport target="clients" onClose={() => setShowImport(false)}
                     onDone={() => dispatch(fetchClients())} />
      )}

      {error ? (
        // VX67 — StateBlock unifie l'état d'erreur avec un bouton « Réessayer »
        // câblé sur le même thunk que le montage initial (jamais d'objet brut
        // ni de page blanche).
        <StateBlock
          error="Impossible de charger les clients. Vérifiez votre connexion puis réessayez."
          onRetry={() => dispatch(fetchClients())}
        />
      ) : loading && clients.length === 0 ? (
        // Chargement : squelette de table différé (anti-flash via useDelayedLoading).
        showSkeleton ? (
          <div className="mt-3 space-y-2" aria-busy="true" aria-label="Chargement des clients">
            <Skeleton className="h-9 w-full" />
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonTableRow key={i} columns={7} />
            ))}
          </div>
        ) : null
      ) : clients.length === 0 ? (
        // État vide actionnable : un bouton principal câblé à la création.
        <EmptyState
          icon={Plus}
          title="Aucun client pour le moment"
          description="Créez votre premier client pour démarrer."
          action={(
            <Button onClick={openNew}>
              <Plus /> Nouveau client
            </Button>
          )}
        />
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Segmented
              options={TYPE_FILTERS}
              value={typeFilter}
              onChange={setTypeFilter}
              aria-label="Filtrer par type de client"
            />
            <SaveViewButton onSave={saveCurrentView} />
            <SavedViewsBar
              savedViews={savedViews}
              onApply={applyView}
              onDelete={deleteView}
            />
          </div>

          <DataTable
            data={visibleClients}
            columns={columns}
            getRowId={(c) => c.id}
            searchable
            searchPlaceholder="Rechercher nom, email, tél, ICE, IF, RC, CIN…"
            rowActions={rowActions}
            selectable={isAdmin}
            bulkActions={isAdmin ? (rows, _keys, clear) => [{
              id: 'bulk-delete',
              label: 'Supprimer (sans devis)',
              icon: Trash2,
              destructive: true,
              onClick: () => bulkDelete(rows, _keys, clear),
            }] : undefined}
            onExport={exportRows}
            exportName="clients"
            onRowClick={(c) => setDetailClient(c)}
            emptyTitle="Aucun résultat"
            emptyDescription="Aucun client ne correspond à ces filtres."
            aria-label="Liste des clients"
          />
        </>
      )}

      {detailItem && (
        <ClientDetailPanel
          client={detailItem}
          onClose={() => { setDetailClient(null); clearDeepLink() }}
          onNewDevis={(c) => navigate(`/ventes/devis/nouveau?client=${c.id}`)}
          onChanged={() => dispatch(fetchClients())}
        />
      )}
    </div>
  )
}
