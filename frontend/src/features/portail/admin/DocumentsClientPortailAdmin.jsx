// PACT99 — Documents clients (portail). `apps.portail.DocumentClientPortail`
// stocke le fichier téléversé par le client dans MinIO (`fichier_key`) ; le
// champ `traite` est en lecture seule côté serializer — seule l'action
// serveur `marquer_traite` peut le poser. SOLMVP16 — le miroir GED
// automatique (WIR94) a été retiré (ged est un module sorti du produit) :
// cet écran affiche désormais seulement si un fichier est présent, sans lien
// de consultation directe. À noter honnêtement, contrairement à la règle
// générale du portail : ni le client ni l'équipe n'ont d'écran de DÉPÔT ;
// cet écran construit UNIQUEMENT le côté ERP (consultation + marquage
// traité), le dépôt côté client reste hors périmètre.
import { useEffect, useState } from 'react'
import { formatDateTime } from '../../../lib/format'
import { Check, FileText } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import { Button, Card, EmptyState, Skeleton, StatusPill, DataTable, toast } from '../../../ui'

const formatDateHeure = (iso) => formatDateTime(iso)

// Libellés FR — copiés tels quels du TextChoices serveur (DocumentClientPortail.TypeDoc).
const TYPE_LABELS = { facture_onee: 'Facture ONEE', plan: 'Plan / schéma', autre: 'Autre' }

export default function DocumentsClientPortailAdmin() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const fetchDocumentsClient = () => portailApi.admin.documentsClient.liste()
    .then((r) => setRows(r.data?.results ?? r.data ?? []))
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  const load = () => {
    setLoading(true)
    setLoadError(false)
    return fetchDocumentsClient()
  }

  useEffect(() => { fetchDocumentsClient() }, [])

  const marquerTraite = async (row) => {
    setBusyId(row.id)
    try {
      await portailApi.admin.documentsClient.marquerTraite(row.id)
      toast.success('Document marqué traité')
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Marquage impossible.')
    } finally {
      setBusyId(null)
    }
  }

  const columns = [
    { id: 'client', header: 'Client', width: 110, accessor: (r) => (r.client_id ? `#${r.client_id}` : '—') },
    { id: 'lead', header: 'Lead', width: 100, accessor: (r) => (r.lead_id ? `#${r.lead_id}` : '—') },
    { id: 'type_document', header: 'Type', width: 140, accessor: (r) => TYPE_LABELS[r.type_document] ?? r.type_document },
    { id: 'libelle', header: 'Libellé', width: 180, accessor: (r) => r.libelle || '—' },
    {
      // AUD148 (b) — le lien pointait sur l'URL BRUTE du `FileField`
      // (`/media/compta/portail_docs/…`), morte par construction : le backend
      // ne définit ni `MEDIA_URL` ni `MEDIA_ROOT`, aucune route ne sert
      // `/media/` et `frontend/nginx.conf` n'a aucune `location /media/`.
      // SOLMVP16 — le lien de consultation GED authentifié a été retiré avec
      // le miroir GED (module sorti du produit) : la colonne affiche
      // seulement si un binaire a été déposé, sans exposer d'URL brute.
      id: 'fichier', header: 'Fichier', width: 110, sortable: false,
      cell: (_v, row) => (row.fichier_present ? 'Déposé' : '—'),
    },
    {
      id: 'traite', header: 'Statut', width: 110, sortable: false,
      cell: (_v, row) => (
        <StatusPill tone={row.traite ? 'success' : 'warning'}
                    label={row.traite ? 'Traité' : 'À traiter'} />
      ),
      exportValue: (row) => (row.traite ? 'Traité' : 'À traiter'),
    },
    { id: 'date_depot', header: 'Déposé le', width: 170, accessor: (r) => formatDateHeure(r.date_depot) },
    {
      id: 'actions', header: '', width: 150, sortable: false, searchable: false, hideable: false,
      cell: (_v, row) => (row.traite ? null : (
        <Button variant="outline" size="sm" disabled={busyId === row.id}
                onClick={() => marquerTraite(row)}>
          <Check /> Marquer traité
        </Button>
      )),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Documents déposés par le client depuis le portail (factures ONEE,
        plans…). « Marquer traité » signale qu'un document a été intégré à
        l'étude — le dépôt lui-même reste hors périmètre de cet écran (aucun
        formulaire de dépôt côté ERP).
      </p>

      {loading ? (
        <Card className="space-y-2 p-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </Card>
      ) : loadError ? (
        <EmptyState title="Chargement impossible"
                    description="Les documents client n'ont pas pu être chargés. Réessayez."
                    action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>} />
      ) : rows.length === 0 ? (
        <EmptyState icon={FileText} title="Aucun document"
                    description="Aucun document n'a encore été déposé depuis le portail client." />
      ) : (
        <DataTable data={rows} columns={columns} getRowId={(r) => r.id}
                   searchable={false} exportName="documents-client-portail"
                   emptyTitle="Aucun document" />
      )}
    </div>
  )
}
