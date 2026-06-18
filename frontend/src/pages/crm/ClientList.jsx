import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { Pencil, FileText, Trash2, Upload, Plus, FilePlus } from 'lucide-react'
import { fetchClients, deleteClient } from '../../features/crm/store/crmSlice'
import ventesApi from '../../api/ventesApi'
import crmApi from '../../api/crmApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import ClientForm from './ClientForm'
import ExcelImport from '../../components/ExcelImport'
import { DataTable, Badge, Button, Spinner, Segmented } from '../../ui'

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
  const { clients, loading, error } = useSelector(s => s.crm)
  const role = useSelector(s => s.auth.role)

  const [showForm, setShowForm]     = useState(false)
  const [editClient, setEditClient] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [showImport, setShowImport] = useState(false)
  const [typeFilter, setTypeFilter] = useState('tous')

  useEffect(() => { dispatch(fetchClients()) }, [dispatch])

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

  const openReleve = async (c) => {
    try {
      const res = await ventesApi.getClientRelevePdf(c.id)
      openPdfBlob(res.data, `Releve_${c.nom}.pdf`)
    } catch { alert('Relevé indisponible.') }
  }

  const handleDelete = async (c) => {
    const fullName = [c.nom, c.prenom].filter(Boolean).join(' ')
    if (!window.confirm(`Supprimer le client « ${fullName} » ?`)) return
    setDeletingId(c.id)
    try {
      await dispatch(deleteClient(c.id)).unwrap()
    } catch (err) {
      // Message serveur en clair (ex. client protégé par ses devis) —
      // jamais de JSON brut ni d'échec silencieux.
      alert(err?.detail
        ?? 'Suppression impossible — réessayez ou contactez l\'administrateur.')
    } finally {
      setDeletingId(null)
    }
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
    } catch { /* ignore */ }
  }

  const columns = useMemo(() => [
    {
      id: 'nom',
      header: 'Client',
      width: 200,
      hideable: false,
      accessor: (c) => [c.nom, c.prenom].filter(Boolean).join(' '),
      cell: (value, c) => (
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="font-medium">{value || '—'}</span>
          {isEntreprise(c)
            ? <Badge tone="info">Entreprise</Badge>
            : <Badge tone="neutral">Particulier</Badge>}
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
      accessor: (c) => c.ice || '',
      cell: (value) => (value
        ? <span className="font-mono text-xs">{value}</span>
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
      id: 'devis_count',
      header: 'Devis',
      align: 'right',
      numeric: true,
      width: 90,
      searchable: false,
      accessor: (c) => c.devis_count ?? 0,
      cell: (value) => <Badge tone={value ? 'info' : 'neutral'}>{value}</Badge>,
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
    if (role === 'admin') {
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

  if (loading) {
    return <p className="page-loading"><Spinner /> Chargement des clients…</p>
  }
  if (error) {
    return (
      <p className="page-error">
        Impossible de charger les clients. Vérifiez votre connexion puis réessayez.
      </p>
    )
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

      <div className="mb-3">
        <Segmented
          options={TYPE_FILTERS}
          value={typeFilter}
          onChange={setTypeFilter}
          aria-label="Filtrer par type de client"
        />
      </div>

      <DataTable
        data={visibleClients}
        columns={columns}
        getRowId={(c) => c.id}
        searchable
        searchPlaceholder="Rechercher nom, email, tél, ICE…"
        rowActions={rowActions}
        onExport={exportRows}
        exportName="clients"
        emptyTitle="Aucun client"
        emptyDescription="Créez votre premier client pour démarrer."
        aria-label="Liste des clients"
      />
    </div>
  )
}
