import { useMemo, useState } from 'react'
import { Plus, Pencil } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import { Button, Segmented } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   UX6 — Trésorerie & prévisionnel.
   ----------------------------------------------------------------------------
   Onglets : comptes de trésorerie (banques), caisses, virements internes et
   lignes prévisionnelles. CRUD par onglet. Endpoints /compta/tresorerie/,
   /caisses/, /virements/, /previsionnel/.
   ========================================================================== */

const TABS = [
  { value: 'tresorerie', label: 'Comptes' },
  { value: 'caisses', label: 'Caisses' },
  { value: 'virements', label: 'Virements' },
  { value: 'previsionnel', label: 'Prévisionnel' },
]

const RESOURCE = {
  tresorerie: comptaApi.tresorerie,
  caisses: comptaApi.caisses,
  virements: comptaApi.virements,
  previsionnel: comptaApi.previsionnel,
}

const FIELDS = {
  tresorerie: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'banque', label: 'Banque' },
    { name: 'rib', label: 'RIB' },
    { name: 'iban', label: 'IBAN' },
    { name: 'solde_initial', label: 'Solde initial', type: 'number' },
  ],
  caisses: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'responsable', label: 'Responsable' },
    { name: 'solde_initial', label: 'Solde initial', type: 'number' },
  ],
  virements: [
    { name: 'date_virement', label: 'Date', type: 'date', required: true },
    { name: 'montant', label: 'Montant', type: 'number', required: true },
    { name: 'libelle', label: 'Libellé' },
    { name: 'reference', label: 'Référence' },
  ],
  previsionnel: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'date_prevue', label: 'Date prévue', type: 'date', required: true },
    { name: 'montant', label: 'Montant', type: 'number', required: true },
    { name: 'commentaire', label: 'Commentaire' },
  ],
}

const money = (v) => formatMAD(v)

const COLUMNS = {
  tresorerie: [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'banque', header: 'Banque', accessor: (r) => r.banque || '—' },
    { id: 'rib', header: 'RIB', accessor: (r) => r.rib || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'solde', header: 'Solde initial', accessor: (r) => Number(r.solde_initial) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
  caisses: [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'responsable', header: 'Responsable', accessor: (r) => r.responsable || '—' },
    { id: 'solde', header: 'Solde courant', accessor: (r) => Number(r.solde_courant ?? r.solde_initial) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
  virements: [
    { id: 'date', header: 'Date', accessor: (r) => r.date_virement, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'source', header: 'Source', accessor: (r) => r.source_libelle || '—' },
    { id: 'dest', header: 'Destination', accessor: (r) => r.destination_libelle || '—' },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
  previsionnel: [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'categorie', header: 'Catégorie', accessor: (r) => r.categorie_display || r.categorie || '—' },
    { id: 'date', header: 'Date prévue', accessor: (r) => r.date_prevue, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
}

export default function TresoreriePage() {
  const [tab, setTab] = useState('tresorerie')
  const [dialog, setDialog] = useState(null)

  const list = useComptaList(RESOURCE[tab].list, undefined)

  const rowActions = (row) => [{
    id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }),
  }]

  const submit = (payload) => {
    const api = RESOURCE[tab]
    return dialog?.row ? api.update(dialog.row.id, payload) : api.create(payload)
  }

  const singular = useMemo(() => ({
    tresorerie: 'compte', caisses: 'caisse',
    virements: 'virement', previsionnel: 'ligne',
  }[tab]), [tab])

  return (
    <div className="page">
      <div className="page-header">
        <h2>Trésorerie & prévisionnel</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialog({ row: null })}>
            <Plus /> Nouveau {singular}
          </Button>
        </div>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet trésorerie" />
      </div>

      <ListShell
        title={TABS.find((t) => t.value === tab).label}
        columns={COLUMNS[tab]}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName={tab}
        emptyTitle="Aucun élément"
        emptyDescription="Rien à afficher pour cet onglet."
      />

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? `Modifier le ${singular}` : `Nouveau ${singular}`}
          fields={FIELDS[tab]}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}
