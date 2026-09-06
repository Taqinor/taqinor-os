import { useState } from 'react'
import { Plus, Coins, Play } from 'lucide-react'
import { useTabParam } from '../components/useTabParam'
import { ListShell } from '../../../ui/module'
import {
  Button, Segmented, Input, Label, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   AUDV06 / XACC17-XACC18 — Devises : taux, postes ouverts, réévaluation.
   ----------------------------------------------------------------------------
   Quatre services complets vivaient sans AUCUN ViewSet ni écran : la table de
   taux de change était inatteignable hors admin Django, donc tout document en
   devise retombait EN SILENCE sur le repli 1:1 ; aucun écran ne pouvait
   déclarer un poste ouvert, constater son écart de change au règlement
   (gain 733 / perte 633), ni lancer la réévaluation de clôture (écart LATENT
   1701/2701 + son extourne au lendemain).

   Rien n'est recalculé ici : les contre-valeurs, l'écart réalisé et l'écart
   latent viennent tous du serveur. L'écran SAISIT et AFFICHE.
   ========================================================================== */

const TABS = [
  { value: 'taux', label: 'Taux de change' },
  { value: 'postes', label: 'Postes ouverts' },
  { value: 'reevaluations', label: 'Réévaluations de clôture' },
]

const CHAMPS_TAUX = [
  { name: 'devise', label: 'Devise (ISO 4217, ex. EUR)', required: true },
  { name: 'date_taux', label: 'Date du taux', type: 'date', required: true },
  { name: 'taux_vers_mad', label: '1 unité = ? MAD', type: 'number', required: true },
]

const CHAMPS_POSTE = [
  { name: 'type_document', label: 'Type de document', options: [
    { value: 'facture_client', label: 'Facture client' },
    { value: 'facture_fournisseur', label: 'Facture fournisseur' },
  ] },
  { name: 'document_id', label: 'ID du document', type: 'number', required: true },
  { name: 'document_reference', label: 'Référence du document' },
  { name: 'devise', label: 'Devise (ISO 4217)', required: true },
  { name: 'montant_devise', label: 'Montant en devise', type: 'number', required: true },
  { name: 'taux_origine', label: "Taux d'origine (vers MAD)", type: 'number', required: true },
  { name: 'date_origine', label: "Date d'origine", type: 'date', required: true },
]

function messageErreur(err, repli) {
  const d = err?.response?.data
  return typeof d === 'string' ? d : (d?.detail || repli)
}

// XACC18 — constat de l'écart de change RÉALISÉ au règlement d'un poste.
function ConstatEcartDialog({ poste, onClose, onConstate }) {
  const [date, setDate] = useState('')
  const [taux, setTaux] = useState('')
  const [busy, setBusy] = useState(false)

  const constater = async () => {
    setBusy(true)
    try {
      await comptaApi.itemsOuvertsDevise.constaterEcart(poste.id, {
        date_reglement: date,
        taux_reglement: taux || undefined,
      })
      toast.success('Écart de change constaté.')
      onConstate?.()
      onClose()
    } catch (err) {
      toast.error(messageErreur(err, 'Constat impossible.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Écart de change — {poste.document_reference || `#${poste.document_id}`}
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          L’écart réalisé est la différence entre la contre-valeur au taux du
          règlement et celle au taux d’origine. Un gain est porté au 733, une
          perte au 633. Sans taux saisi, celui de la table au jour du règlement
          est utilisé.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <Label htmlFor="ecart-date" required>Date de règlement</Label>
            <Input
              id="ecart-date" type="date" value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="ecart-taux">Taux de règlement (facultatif)</Label>
            <Input
              id="ecart-taux" type="number" step="any" value={taux}
              onChange={(e) => setTaux(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={constater} disabled={busy || !date}>
            {busy ? 'Constat…' : "Constater l'écart"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TauxPanel() {
  const [dialog, setDialog] = useState(false)
  const list = useComptaList(comptaApi.tauxDevise.list, undefined)

  const columns = [
    { id: 'devise', header: 'Devise', accessor: (r) => r.devise },
    { id: 'date_taux', header: 'Date', accessor: (r) => r.date_taux,
      searchable: false, cell: (v) => formatDate(v) },
    { id: 'taux_vers_mad', header: '1 unité = ? MAD', accessor: (r) => r.taux_vers_mad,
      align: 'right', numeric: true, searchable: false },
    { id: 'source', header: 'Source', accessor: (r) => r.source_display || r.source },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div>
        <Button onClick={() => setDialog(true)}><Plus /> Nouveau taux</Button>
      </div>
      <ListShell
        hideHeader
        title="Taux de change"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="taux-devise"
        emptyTitle="Aucun taux enregistré"
        emptyDescription="Sans table de taux, un document en devise retombe sur un change 1:1."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(false)}
          title="Nouveau taux de change"
          fields={CHAMPS_TAUX}
          onSubmit={(payload) => comptaApi.tauxDevise.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

function PostesPanel() {
  const [dialog, setDialog] = useState(false)
  const [constat, setConstat] = useState(null)
  const list = useComptaList(comptaApi.itemsOuvertsDevise.list, undefined)

  const columns = [
    { id: 'document', header: 'Document',
      accessor: (r) => r.document_reference || `#${r.document_id}` },
    { id: 'type', header: 'Type', accessor: (r) => r.type_document_display || r.type_document },
    { id: 'devise', header: 'Devise', accessor: (r) => r.devise },
    { id: 'montant_devise', header: 'Montant (devise)', accessor: (r) => r.montant_devise,
      align: 'right', numeric: true, searchable: false },
    { id: 'contre_valeur', header: 'Contre-valeur d’origine',
      accessor: (r) => Number(r.contre_valeur_origine) || 0,
      align: 'right', numeric: true, searchable: false,
      cell: (v) => formatMAD(v) },
    { id: 'ecart', header: 'Écart réalisé', searchable: false,
      align: 'right', numeric: true,
      accessor: (r) => (r.ecart_change ? Number(r.ecart_change.difference) : null),
      cell: (v) => (v === null ? '—' : formatMAD(v)) },
    { id: 'solde', header: 'Soldé', accessor: (r) => (r.solde ? 'Oui' : 'Non'),
      searchable: false },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div>
        <Button onClick={() => setDialog(true)}><Plus /> Nouveau poste ouvert</Button>
      </div>
      <ListShell
        hideHeader
        title="Postes ouverts en devise"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={(row) => (row.solde ? [] : [{
          id: 'ecart', label: "Constater l'écart de change", icon: Coins,
          onClick: () => setConstat(row),
        }])}
        exportName="postes-ouverts-devise"
        emptyTitle="Aucun poste ouvert"
        emptyDescription="Un document en MAD n’a pas besoin de suivi de change."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(false)}
          title="Nouveau poste ouvert en devise"
          fields={CHAMPS_POSTE}
          onSubmit={(payload) => comptaApi.itemsOuvertsDevise.create(payload)}
          onSaved={list.reload}
        />
      )}
      {constat && (
        <ConstatEcartDialog
          poste={constat}
          onClose={() => setConstat(null)}
          onConstate={list.reload}
        />
      )}
    </div>
  )
}

function ReevaluationsPanel() {
  const [date, setDate] = useState('')
  const [busy, setBusy] = useState(false)
  const [detail, setDetail] = useState(null)
  const list = useComptaList(comptaApi.reevaluationsCloture.list, undefined)

  const lancer = async () => {
    setBusy(true)
    try {
      const res = await comptaApi.reevaluationsCloture.lancer({
        date_cloture: date,
      })
      setDetail(res.data)
      toast.success('Réévaluation de clôture lancée.')
      list.reload()
    } catch (err) {
      toast.error(messageErreur(err, 'Réévaluation impossible.'))
    } finally {
      setBusy(false)
    }
  }

  const columns = [
    { id: 'date_cloture', header: 'Date de clôture', accessor: (r) => r.date_cloture,
      searchable: false, cell: (v) => formatDate(v) },
    { id: 'total_ecart', header: 'Écart latent total',
      accessor: (r) => Number(r.total_ecart) || 0, align: 'right', numeric: true,
      searchable: false, cell: (v) => formatMAD(v) },
    { id: 'ecriture', header: 'Écriture', searchable: false,
      accessor: (r) => (r.ecriture ? `#${r.ecriture}` : '—') },
    { id: 'extourne', header: 'Extourne', searchable: false,
      accessor: (r) => (r.date_extourne ? formatDate(r.date_extourne) : '—') },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-2 rounded-lg border p-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="reev-date" required>Date de clôture</Label>
          <Input
            id="reev-date" type="date" value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <Button onClick={lancer} disabled={busy || !date}>
          <Play className="size-4" /> {busy ? 'Réévaluation…' : 'Lancer'}
        </Button>
        <span className="text-xs text-muted-foreground">
          Idempotent : relancer la même date ne double jamais l’écriture.
        </span>
      </div>

      <ListShell
        hideHeader
        title="Réévaluations de clôture"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        onRowClick={(row) => setDetail(row)}
        exportName="reevaluations-cloture"
        emptyTitle="Aucune réévaluation"
        emptyDescription="L’écart latent de change se constate à la clôture, puis s’extourne au lendemain."
      />

      {detail && (detail.lignes || []).length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">
            Détail — clôture du {formatDate(detail.date_cloture)}
          </h3>
          <ComptaTable
            aria-label="Détail de la réévaluation"
            exportName="reevaluation-detail"
            rows={detail.lignes}
            getRowKey={(l) => l.id}
            columns={[
              { key: 'document', label: 'Document',
                cell: (l) => l.document_reference || `#${l.item}` },
              { key: 'devise', label: 'Devise', cell: (l) => l.devise },
              { key: 'taux_cloture', label: 'Taux de clôture', align: 'right',
                numeric: true, cell: (l) => l.taux_cloture },
              { key: 'ecart', label: 'Écart latent', align: 'right',
                numeric: true, sortValue: (l) => Number(l.ecart) || 0,
                cell: (l) => formatMAD(l.ecart) },
            ]}
          />
        </div>
      )}
    </div>
  )
}

export default function DevisesPage() {
  const [tab, setTab] = useTabParam('taux')

  return (
    <div className="page">
      <div className="page-header">
        <h2>Devises & change</h2>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet devises" />
      </div>

      {tab === 'taux' && <TauxPanel />}
      {tab === 'postes' && <PostesPanel />}
      {tab === 'reevaluations' && <ReevaluationsPanel />}
    </div>
  )
}
