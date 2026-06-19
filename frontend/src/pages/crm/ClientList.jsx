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

  // Suppression EN MASSE (admin) : ne supprime QUE les clients sans devis lié
  // (devis_count===0). Les clients protégés par un devis sont ignorés avec un
  // message FR clair — jamais d'orphelinage de pièces financières.
  const bulkDelete = async (rows, _keys, clear) => {
    const supprimables = rows.filter((c) => (c.devis_count ?? 0) === 0)
    const proteges = rows.length - supprimables.length
    if (!supprimables.length) {
      alert('Aucun client supprimable : tous les clients sélectionnés ont des '
        + 'devis liés (protégés).')
      return
    }
    const msg = proteges > 0
      ? `Supprimer ${supprimables.length} client(s) sans devis ? `
        + `${proteges} client(s) avec devis seront ignorés (protégés).`
      : `Supprimer ${supprimables.length} client(s) sélectionné(s) ?`
    if (!window.confirm(msg)) return
    for (const c of supprimables) {
      try { await dispatch(deleteClient(c.id)).unwrap() } catch { /* ignoré */ }
    }
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
            <span className="font-medium">{facture.toLocaleString('fr-MA')} MAD</span>
            <span className="text-xs text-muted-foreground">
              Payé : {paye.toLocaleString('fr-MA')} MAD
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

      {clients.length === 0 ? (
        // État vide actionnable : un bouton principal câblé à la création.
        <div className="empty-state-block" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
          <p style={{ marginBottom: '1rem' }}>
            Aucun client pour le moment. Créez votre premier client pour démarrer.
          </p>
          <Button onClick={openNew}>
            <Plus /> Nouveau client
          </Button>
        </div>
      ) : (
        <>
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
            searchPlaceholder="Rechercher nom, email, tél, ICE, IF, RC, CIN…"
            rowActions={rowActions}
            selectable={role === 'admin'}
            bulkActions={role === 'admin' ? (rows, _keys, clear) => [{
              id: 'bulk-delete',
              label: 'Supprimer (sans devis)',
              icon: Trash2,
              destructive: true,
              onClick: () => bulkDelete(rows, _keys, clear),
            }] : undefined}
            onExport={exportRows}
            exportName="clients"
            emptyTitle="Aucun résultat"
            emptyDescription="Aucun client ne correspond à ces filtres."
            aria-label="Liste des clients"
          />
        </>
      )}
    </div>
  )
}
