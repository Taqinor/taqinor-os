import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Pencil, FileText, Trash2, Upload, Plus } from 'lucide-react'
import { fetchClients, deleteClient } from '../../features/crm/store/crmSlice'
import ventesApi from '../../api/ventesApi'
import crmApi from '../../api/crmApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import ClientForm from './ClientForm'
import ExcelImport from '../../components/ExcelImport'
import { DataTable, Badge, Button, Spinner } from '../../ui'

const formatDateFR = (iso) => new Date(iso).toLocaleDateString('fr-FR')

export default function ClientList() {
  const dispatch = useDispatch()
  const { clients, loading, error } = useSelector(s => s.crm)
  const role = useSelector(s => s.auth.role)

  const [showForm, setShowForm]     = useState(false)
  const [editClient, setEditClient] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [showImport, setShowImport] = useState(false)

  useEffect(() => { dispatch(fetchClients()) }, [dispatch])

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
      cell: (value) => <span className="font-medium">{value || '—'}</span>,
      exportValue: (c) => [c.nom, c.prenom].filter(Boolean).join(' '),
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
  if (error) return <p className="page-error">Erreur : {JSON.stringify(error)}</p>

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

      <DataTable
        data={clients}
        columns={columns}
        getRowId={(c) => c.id}
        searchable
        searchPlaceholder="Rechercher nom, email, tél…"
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
