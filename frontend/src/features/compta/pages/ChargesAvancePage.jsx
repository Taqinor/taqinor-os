import { useCallback, useState } from 'react'
import { Plus, CalendarClock } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, toast,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT163 / XACC15 — Charges constatées d'avance (étalement).
   ----------------------------------------------------------------------------
   Une charge payée d'un coup (assurance annuelle, loyer payé d'avance…) est
   portée au compte 3491 puis étalée mois par mois sur le compte de charge
   d'origine (services.etaler_charge_avance, ici via /compta/charges-avance/).
   L'échéancier de dotations mensuelles est généré par le serveur, jamais
   saisi à la main — cet écran l'affiche en lecture seule (détail au clic).
   ========================================================================== */

const compteAsync = () => comptaApi.comptes.list({ page_size: 500 }).then((res) => {
  const list = Array.isArray(res.data) ? res.data : (res.data?.results || [])
  return list
    .filter((c) => String(c.numero || '').startsWith('6'))
    .map((c) => ({ value: c.id, label: `${c.numero} — ${c.intitule || c.libelle || ''}` }))
})

const FIELDS = [
  { name: 'libelle', label: 'Libellé', required: true },
  { name: 'montant_total', label: 'Montant total à étaler', type: 'number', required: true },
  { name: 'date_debut', label: "Début de l'étalement", type: 'date', required: true },
  { name: 'nb_mois', label: "Nombre de mois d'étalement", type: 'number', required: true },
  { name: 'compte_charge', label: 'Compte de charge (classe 6)', async: compteAsync },
]

function DotationsDialog({ charge, onClose }) {
  const dotations = charge.dotations || []
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Échéancier — {charge.reference || charge.libelle}</DialogTitle>
        </DialogHeader>
        {dotations.length === 0 ? (
          <EmptyState
            icon={CalendarClock}
            title="Aucune dotation"
            description="Cette charge n'a pas encore d'échéancier généré."
          />
        ) : (
          <ComptaTable
            aria-label="Échéancier de dotations"
            exportName="dotations-etalement"
            rows={dotations}
            getRowKey={(d) => d.id ?? d.numero}
            columns={[
              { key: 'numero', label: 'Rang', sortValue: (d) => Number(d.numero) || 0,
                cell: (d) => d.numero },
              { key: 'date_dotation', label: 'Date', cell: (d) => formatDate(d.date_dotation) },
              { key: 'montant', label: 'Dotation', align: 'right', numeric: true,
                sortValue: (d) => Number(d.montant) || 0, cell: (d) => formatMAD(d.montant) },
              { key: 'posted', label: 'Postée', cell: (d) => (d.posted ? 'Oui' : 'Non') },
            ]}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

export default function ChargesAvancePage() {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [detail, setDetail] = useState(null)
  const list = useComptaList(comptaApi.chargesAvance.list, undefined)

  const submit = useCallback(
    (payload) => comptaApi.chargesAvance.create(payload), [])

  const onSaved = () => {
    toast.success('Charge à étaler enregistrée.')
    list.reload()
  }

  const columns = [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference || '—' },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'montant_total', header: 'Montant total', accessor: (r) => Number(r.montant_total) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'date_debut', header: 'Début', accessor: (r) => r.date_debut, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'nb_mois', header: 'Mois', accessor: (r) => r.nb_mois, searchable: false },
    { id: 'dotations', header: 'Dotations postées', searchable: false,
      accessor: (r) => {
        const dotations = r.dotations || []
        const postees = dotations.filter((d) => d.posted).length
        return `${postees}/${dotations.length}`
      } },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h2>Charges constatées d'avance</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialogOpen(true)}>
            <Plus /> Nouvelle charge à étaler
          </Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Charges constatées d'avance"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        onRowClick={(row) => setDetail(row)}
        exportName="charges-avance"
        emptyTitle="Aucune charge à étaler"
        emptyDescription="Une charge prépayée (assurance, loyer…) étalée sur plusieurs mois."
      />

      {dialogOpen && (
        <CrudDialog
          open
          onClose={() => setDialogOpen(false)}
          title="Nouvelle charge à étaler"
          fields={FIELDS}
          onSubmit={submit}
          onSaved={onSaved}
        />
      )}

      {detail && (
        <DotationsDialog charge={detail} onClose={() => setDetail(null)} />
      )}
    </div>
  )
}
