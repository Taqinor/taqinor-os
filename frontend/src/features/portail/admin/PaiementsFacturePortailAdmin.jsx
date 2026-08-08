// PACT98 — Paiements de facture (portail) : le rapprochement impossible
// jusqu'ici. `apps.portail.PaiementFacturePortail` est créé quand un client
// initie un virement depuis son portail (statut `initie`) ; le SEUL workflow
// serveur est `rapprocher` (marque PAYÉ, idempotent depuis `initie`
// uniquement) — sans écran, un virement reçu ne pouvait jamais être confirmé
// dans l'ERP. Trou (c) à respecter : le statut `echoue` existe dans le
// modèle mais n'est posé par AUCUN code serveur — cet écran ne propose donc
// QUE « Rapprocher », jamais un bouton « Rejeter » sans service derrière.
import { useCallback, useEffect, useState } from 'react'
import { Check, Banknote } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import { formatMAD } from '../../../lib/format'
import {
  Button, Card, EmptyState, Skeleton, StatusPill,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem, DataTable, toast,
} from '../../../ui'

const formatDateHeure = (iso) => (iso ? new Date(iso).toLocaleString('fr-FR') : '—')

// Libellés FR — copiés tels quels des TextChoices serveur (PaiementFacturePortail.Statut/Methode).
const STATUT_LABELS = { initie: 'Initié', paye: 'Payé', echoue: 'Échoué' }
const METHODE_LABELS = { carte: 'Carte (CMI)', virement: 'Virement' }
const STATUT_TONES = { initie: 'warning', paye: 'success', echoue: 'danger' }

export default function PaiementsFacturePortailAdmin() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [statutFiltre, setStatutFiltre] = useState('initie')
  const [busyId, setBusyId] = useState(null)

  const fetchPaiements = useCallback(() => portailApi.admin.paiementsFacture.liste(statutFiltre ? { statut: statutFiltre } : {})
    .then((r) => setRows(r.data?.results ?? r.data ?? []))
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false)), [statutFiltre])

  const load = () => {
    setLoading(true)
    setLoadError(false)
    return fetchPaiements()
  }

  useEffect(() => { fetchPaiements() }, [fetchPaiements])

  const rapprocher = async (row) => {
    setBusyId(row.id)
    try {
      await portailApi.admin.paiementsFacture.rapprocher(row.id)
      toast.success('Paiement rapproché')
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Rapprochement impossible.')
    } finally {
      setBusyId(null)
    }
  }

  const columns = [
    { id: 'facture', header: 'Facture', width: 110, accessor: (r) => `Facture #${r.facture_id}` },
    { id: 'montant', header: 'Montant', width: 130, accessor: (r) => formatMAD(r.montant) },
    { id: 'methode', header: 'Méthode', width: 130, accessor: (r) => METHODE_LABELS[r.methode] ?? r.methode },
    {
      id: 'statut', header: 'Statut', width: 110, sortable: false,
      cell: (_v, row) => (
        <StatusPill tone={STATUT_TONES[row.statut] ?? 'neutral'}
                    label={STATUT_LABELS[row.statut] ?? row.statut} />
      ),
      exportValue: (row) => STATUT_LABELS[row.statut] ?? row.statut,
    },
    { id: 'reference', header: 'Référence', width: 150, accessor: (r) => r.reference || '—' },
    { id: 'paye_le', header: 'Payé le', width: 170, accessor: (r) => formatDateHeure(r.paye_le) },
    { id: 'date_creation', header: 'Créé le', width: 170, accessor: (r) => formatDateHeure(r.date_creation) },
    {
      id: 'actions', header: '', width: 140, sortable: false, searchable: false, hideable: false,
      cell: (_v, row) => (row.statut === 'initie' ? (
        <Button variant="outline" size="sm" disabled={busyId === row.id}
                onClick={() => rapprocher(row)}>
          <Check /> Rapprocher
        </Button>
      ) : null),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Intentions de paiement en ligne (virement ou carte CMI) initiées
        depuis le portail client. « Rapprocher » confirme la réception d'un
        virement et marque le paiement Payé — la seule action que le serveur
        propose.
      </p>

      <div className="flex items-center gap-2">
        <Select value={statutFiltre || '__all'}
                onValueChange={(v) => {
                  setLoading(true)
                  setLoadError(false)
                  setStatutFiltre(v === '__all' ? '' : v)
                }}>
          <SelectTrigger aria-label="Statut" className="w-56"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__all">Tous les statuts</SelectItem>
            <SelectItem value="initie">À rapprocher (Initié)</SelectItem>
            <SelectItem value="paye">Payé</SelectItem>
            <SelectItem value="echoue">Échoué</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <Card className="space-y-2 p-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </Card>
      ) : loadError ? (
        <EmptyState title="Chargement impossible"
                    description="Les paiements n'ont pas pu être chargés. Réessayez."
                    action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>} />
      ) : rows.length === 0 ? (
        <EmptyState icon={Banknote} title="Aucun paiement"
                    description="Aucune intention de paiement pour ce filtre." />
      ) : (
        <DataTable data={rows} columns={columns} getRowId={(r) => r.id}
                   searchable={false} exportName="paiements-facture-portail"
                   emptyTitle="Aucun paiement" />
      )}
    </div>
  )
}
