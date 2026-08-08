// PACT97 — Acceptations de devis (portail) : la preuve légale côté ERP.
// `apps.portail.AcceptationDevisPortail` enregistre la signature client
// (option choisie, nom du signataire, IP, date) créée en coulisse quand le
// client accepte depuis son portail — jusqu'ici l'ERP n'avait aucun écran
// pour CONSULTER cette preuve liée au devis. Écran de lecture seule :
// l'IP et la date affichées viennent telles quelles du serveur, jamais
// recalculées côté client (pas de formulaire de création ici — la preuve
// naît de l'action `signer` du portail, jamais d'une saisie ERP).
import { useEffect, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import { Button, Card, EmptyState, Skeleton, StatusPill, DataTable } from '../../../ui'

const formatDateHeure = (iso) => (iso ? new Date(iso).toLocaleString('fr-FR') : '—')

export default function AcceptationsDevisPortailAdmin() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  const load = () => {
    setLoading(true)
    setLoadError(false)
    return portailApi.admin.acceptationsDevis.liste()
      .then((r) => setRows(r.data?.results ?? r.data ?? []))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const columns = [
    { id: 'devis', header: 'Devis', width: 110, accessor: (r) => `Devis #${r.devis_id}` },
    { id: 'option_choisie', header: 'Option choisie', width: 160, accessor: (r) => r.option_choisie || '—' },
    { id: 'nom_signataire', header: 'Signataire', width: 180, accessor: (r) => r.nom_signataire || '—' },
    {
      id: 'signature_ip', header: 'IP de signature', width: 150,
      cell: (_v, row) => <code className="text-xs">{row.signature_ip || '—'}</code>,
      exportValue: (row) => row.signature_ip || '',
    },
    {
      id: 'accepte', header: 'Statut', width: 130, sortable: false,
      cell: (_v, row) => (
        <StatusPill tone={row.accepte ? 'success' : 'neutral'}
                    label={row.accepte ? 'Accepté' : 'Non accepté'} />
      ),
      exportValue: (row) => (row.accepte ? 'Accepté' : 'Non accepté'),
    },
    { id: 'signe_le', header: 'Signé le', width: 170, accessor: (r) => formatDateHeure(r.signe_le) },
    { id: 'date_creation', header: 'Créée le', width: 170, accessor: (r) => formatDateHeure(r.date_creation) },
  ]

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Preuve d'acceptation électronique d'un devis depuis le portail client
        (loi 53-05) : option, signataire, IP et horodatage, tels que capturés
        par le serveur au moment de la signature. Lecture seule — la preuve
        naît de l'action « signer » du portail, jamais d'une saisie ERP.
      </p>

      {loading ? (
        <Card className="space-y-2 p-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </Card>
      ) : loadError ? (
        <EmptyState title="Chargement impossible"
                    description="Les acceptations de devis n'ont pas pu être chargées. Réessayez."
                    action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>} />
      ) : rows.length === 0 ? (
        <EmptyState icon={ShieldCheck} title="Aucune acceptation de devis"
                    description="Aucun devis n'a encore été signé depuis le portail client." />
      ) : (
        <DataTable data={rows} columns={columns} getRowId={(r) => r.id}
                   searchable={false} exportName="acceptations-devis-portail"
                   emptyTitle="Aucune acceptation de devis" />
      )}
    </div>
  )
}
