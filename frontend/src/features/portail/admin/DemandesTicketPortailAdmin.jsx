// PACT101 — Demandes de ticket (portail). `apps.portail.DemandeTicketPortail`
// capture une demande du client ; l'action serveur `prendre_en_charge` fait
// passer la demande à « Prise en charge » et LIE le ticket SAV dont le n°
// est fourni dans la requête (`ticket_id`, optionnel côté serveur — il n'en
// crée jamais un lui-même). Le formulaire d'ouverture côté client reste hors
// périmètre : cet écran construit uniquement la prise en charge ERP. Le lien
// affiché après coup vient du `ticket_id` renvoyé par la RÉPONSE serveur —
// jamais un ticket fictif construit côté client.
import { useEffect, useState } from 'react'
import { Check, X, Ticket as TicketIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import portailApi from '../../../api/portailApi'
import {
  Button, Card, EmptyState, Skeleton, StatusPill, NumberInput, DataTable, toast,
} from '../../../ui'

const formatDateHeure = (iso) => (iso ? new Date(iso).toLocaleString('fr-FR') : '—')

// Libellés FR — copiés tels quels du TextChoices serveur (DemandeTicketPortail.Statut).
const STATUT_LABELS = {
  soumise: 'Soumise', prise_en_charge: 'Prise en charge', resolue: 'Résolue', refusee: 'Refusée',
}
const STATUT_TONES = {
  soumise: 'warning', prise_en_charge: 'info', resolue: 'success', refusee: 'danger',
}

export default function DemandesTicketPortailAdmin() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [edit, setEdit] = useState(null) // { id, ticketId }
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    setLoading(true)
    setLoadError(false)
    return portailApi.admin.demandesTicket.liste()
      .then((r) => setRows(r.data?.results ?? r.data ?? []))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const confirmerPriseEnCharge = async (row) => {
    const ticketId = Number(edit?.ticketId)
    if (!ticketId) return
    setBusyId(row.id)
    try {
      await portailApi.admin.demandesTicket.prendreEnCharge(row.id, { ticket_id: ticketId })
      setEdit(null)
      toast.success('Demande prise en charge')
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Prise en charge impossible.')
    } finally {
      setBusyId(null)
    }
  }

  const columns = [
    { id: 'client', header: 'Client', width: 100, accessor: (r) => (r.client_id ? `#${r.client_id}` : '—') },
    { id: 'chantier', header: 'Chantier', width: 100, accessor: (r) => (r.chantier_id ? `#${r.chantier_id}` : '—') },
    { id: 'sujet', header: 'Sujet', width: 200, accessor: (r) => r.sujet },
    {
      id: 'statut', header: 'Statut', width: 130, sortable: false,
      cell: (_v, row) => (
        <StatusPill tone={STATUT_TONES[row.statut] ?? 'neutral'}
                    label={STATUT_LABELS[row.statut] ?? row.statut} />
      ),
      exportValue: (row) => STATUT_LABELS[row.statut] ?? row.statut,
    },
    { id: 'date_creation', header: 'Créée le', width: 170, accessor: (r) => formatDateHeure(r.date_creation) },
    {
      id: 'actions', header: 'Ticket SAV', width: 260, sortable: false, searchable: false, hideable: false,
      cell: (_v, row) => {
        if (row.ticket_id) {
          return (
            <Link to={`/sav?id=${row.ticket_id}`} className="text-primary underline">
              Voir le ticket SAV #{row.ticket_id}
            </Link>
          )
        }
        if (row.statut !== 'soumise') return null
        if (edit?.id === row.id) {
          return (
            <span className="flex items-center gap-1.5">
              <NumberInput aria-label={`N° de ticket SAV existant — ${row.sujet}`}
                           className="h-8 w-24" placeholder="N° ticket"
                           value={edit.ticketId}
                           onChange={(e) => setEdit((s) => ({ ...s, ticketId: e.target.value }))} />
              <Button size="sm" variant="outline" disabled={busyId === row.id || !Number(edit.ticketId)}
                      onClick={() => confirmerPriseEnCharge(row)}>
                <Check /> Confirmer
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEdit(null)}><X /></Button>
            </span>
          )
        }
        return (
          <Button variant="outline" size="sm" onClick={() => setEdit({ id: row.id, ticketId: '' })}>
            Prendre en charge
          </Button>
        )
      },
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Demandes de ticket SAV ouvertes depuis le portail client. « Prendre en
        charge » lie la demande au n° d'un ticket SAV déjà existant (créé
        depuis Après-vente → Tickets SAV) — le serveur ne crée jamais de
        ticket lui-même ; le lien affiché vient de la réponse du serveur,
        jamais d'un ticket fictif côté client.
      </p>

      {loading ? (
        <Card className="space-y-2 p-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </Card>
      ) : loadError ? (
        <EmptyState title="Chargement impossible"
                    description="Les demandes de ticket n'ont pas pu être chargées. Réessayez."
                    action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>} />
      ) : rows.length === 0 ? (
        <EmptyState icon={TicketIcon} title="Aucune demande"
                    description="Aucune demande de ticket n'a encore été soumise depuis le portail client." />
      ) : (
        <DataTable data={rows} columns={columns} getRowId={(r) => r.id}
                   searchable={false} exportName="demandes-ticket-portail"
                   emptyTitle="Aucune demande" />
      )}
    </div>
  )
}
