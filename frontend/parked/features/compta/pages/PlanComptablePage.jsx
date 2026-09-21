import { useMemo, useState } from 'react'
import { Plus, Pencil } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import { Button, Segmented, Badge } from '../../../ui'
import { formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   UX3 — Plan comptable CGNC (comptes par classe) + journaux.
   ----------------------------------------------------------------------------
   Deux vues commutées (Segmented) : les comptes (filtrables par classe 1–8,
   CRUD) et les journaux (VTE/ACH/BNK/CSH/OD/AN). Endpoints :
   /compta/comptes/?classe= , /compta/journaux/ , /compta/plans/.
   ========================================================================== */

const CLASSES = [
  { value: '', label: 'Toutes' },
  { value: '1', label: '1' }, { value: '2', label: '2' }, { value: '3', label: '3' },
  { value: '4', label: '4' }, { value: '5', label: '5' }, { value: '6', label: '6' },
  { value: '7', label: '7' }, { value: '8', label: '8' },
]

const SENS_OPTS = [
  { value: 'debit', label: 'Débiteur' },
  { value: 'credit', label: 'Créditeur' },
]

const TYPE_JOURNAL_OPTS = [
  { value: 'VTE', label: 'Ventes' }, { value: 'ACH', label: 'Achats' },
  { value: 'BNK', label: 'Banque' }, { value: 'CSH', label: 'Caisse' },
  { value: 'OD', label: 'Opérations diverses' }, { value: 'AN', label: 'À-nouveaux' },
]

const COMPTE_FIELDS = [
  { name: 'numero', label: 'Numéro', required: true },
  { name: 'intitule', label: 'Intitulé', required: true },
  { name: 'classe', label: 'Classe', type: 'number', required: true },
  { name: 'sens', label: 'Sens', options: SENS_OPTS },
]

const JOURNAL_FIELDS = [
  { name: 'code', label: 'Code', required: true },
  { name: 'libelle', label: 'Libellé', required: true },
  { name: 'type_journal', label: 'Type', options: TYPE_JOURNAL_OPTS },
]

export default function PlanComptablePage() {
  const [view, setView] = useState('comptes')
  const [classe, setClasse] = useState('')
  const [dialog, setDialog] = useState(null) // { kind, row } | null

  const comptesParams = useMemo(
    () => (classe ? { classe } : undefined), [classe])
  const comptes = useComptaList(comptaApi.comptes.list, comptesParams)
  const journaux = useComptaList(comptaApi.journaux.list, undefined)

  const compteCols = useMemo(() => [
    { id: 'numero', header: 'N°', accessor: (r) => r.numero, width: 120,
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'intitule', header: 'Intitulé', accessor: (r) => r.intitule },
    { id: 'classe', header: 'Classe', accessor: (r) => r.classe_display || r.classe,
      width: 160, searchable: false },
    { id: 'sens', header: 'Sens', accessor: (r) => r.sens, width: 110, searchable: false,
      cell: (v) => v || '—' },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non'),
      width: 90, searchable: false,
      cell: (_v, r) => <Badge tone={r.actif ? 'success' : 'neutral'}>{r.actif ? 'Actif' : 'Inactif'}</Badge> },
    { id: 'date_creation', header: 'Créé le', accessor: (r) => r.date_creation, width: 120,
      searchable: false, align: 'right', cell: (v) => formatDate(v) },
  ], [])

  const journalCols = useMemo(() => [
    { id: 'code', header: 'Code', accessor: (r) => r.code, width: 110,
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'type', header: 'Type', accessor: (r) => r.type_journal_display || r.type_journal,
      width: 180, searchable: false },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non'),
      width: 90, searchable: false,
      cell: (_v, r) => <Badge tone={r.actif ? 'success' : 'neutral'}>{r.actif ? 'Actif' : 'Inactif'}</Badge> },
  ], [])

  const isComptes = view === 'comptes'
  const active = isComptes ? comptes : journaux

  const rowActions = (row) => [{
    id: 'edit', label: 'Éditer', icon: Pencil,
    onClick: () => setDialog({ kind: view, row }),
  }]

  const submit = (payload) => {
    const api = isComptes ? comptaApi.comptes : comptaApi.journaux
    const row = dialog?.row
    return row ? api.update(row.id, payload) : api.create(payload)
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Plan comptable & journaux</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialog({ kind: view, row: null })}>
            <Plus /> {isComptes ? 'Nouveau compte' : 'Nouveau journal'}
          </Button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Segmented
          options={[
            { value: 'comptes', label: 'Comptes CGNC' },
            { value: 'journaux', label: 'Journaux' },
          ]}
          value={view}
          onChange={setView}
        />
        {isComptes && (
          <Segmented
            options={CLASSES}
            value={classe}
            onChange={setClasse}
            aria-label="Filtrer par classe"
          />
        )}
      </div>

      <ListShell
        title={isComptes ? 'Comptes' : 'Journaux'}
        columns={isComptes ? compteCols : journalCols}
        rows={active.rows}
        loading={active.loading}
        error={active.error}
        rowActions={rowActions}
        exportName={isComptes ? 'comptes' : 'journaux'}
        emptyTitle="Aucun élément"
        emptyDescription={isComptes
          ? 'Aucun compte pour cette classe.'
          : 'Aucun journal défini.'}
      />

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={isComptes
            ? (dialog.row ? 'Modifier le compte' : 'Nouveau compte')
            : (dialog.row ? 'Modifier le journal' : 'Nouveau journal')}
          fields={isComptes ? COMPTE_FIELDS : JOURNAL_FIELDS}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={active.reload}
        />
      )}
    </div>
  )
}
