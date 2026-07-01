import { useMemo, useState } from 'react'
import { Plus, Pencil, Download } from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, Segmented, Card, Input, Label, toast } from '../../../ui'
import { formatMAD } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   UX7 — Fiscalité & déclarations.
   ----------------------------------------------------------------------------
   CRUD des déclarations TVA / retenues à la source / timbres fiscaux, plus un
   bloc d'exports fichiers (téléchargement de blob) : FEC, liasse fiscale, export
   fiduciaire (Sage/CEGID), relevé des déductions TVA, déclaration des honoraires
   et aide au calcul de l'IS. Ces exports exigent « ?export=... » côté backend
   (jamais « ?format= ») — géré dans comptaApi.
   ========================================================================== */

const TABS = [
  { value: 'declarationsTva', label: 'Déclarations TVA' },
  { value: 'retenuesSource', label: 'Retenues à la source' },
  { value: 'timbresFiscaux', label: 'Timbres fiscaux' },
]

const RESOURCE = {
  declarationsTva: comptaApi.declarationsTva,
  retenuesSource: comptaApi.retenuesSource,
  timbresFiscaux: comptaApi.timbresFiscaux,
}

const StatutFiscal = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  prepare: { label: 'Préparée', tone: 'info' },
  preparee: { label: 'Préparée', tone: 'info' },
  declaree: { label: 'Déclarée', tone: 'success' },
  verse: { label: 'Versé', tone: 'success' },
  versee: { label: 'Versée', tone: 'success' },
  du: { label: 'Dû', tone: 'warning' },
})

const money = (v) => formatMAD(v)

const COLUMNS = {
  declarationsTva: [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'regime', header: 'Régime', accessor: (r) => r.regime_display || r.regime || '—' },
    { id: 'periode', header: 'Période', accessor: (r) => `${r.date_debut || ''} → ${r.date_fin || ''}`,
      searchable: false },
    { id: 'a_declarer', header: 'TVA à déclarer', accessor: (r) => Number(r.tva_a_declarer) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutFiscal status={v} /> },
  ],
  retenuesSource: [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'tiers', header: 'Tiers', accessor: (r) => r.tiers_nom || '—' },
    { id: 'type', header: 'Prestation', accessor: (r) => r.type_prestation_display || r.type_prestation || '—' },
    { id: 'base', header: 'Base', accessor: (r) => Number(r.base) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'montant', header: 'Retenue', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutFiscal status={v} /> },
  ],
  timbresFiscaux: [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'facture', header: 'Facture', accessor: (r) => r.facture_ref || '—' },
    { id: 'tiers', header: 'Tiers', accessor: (r) => r.tiers_nom || '—' },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutFiscal status={v} /> },
  ],
}

const FIELDS = {
  declarationsTva: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'date_debut', label: 'Début', type: 'date', required: true },
    { name: 'date_fin', label: 'Fin', type: 'date', required: true },
    { name: 'regime', label: 'Régime', options: [
      { value: 'encaissement', label: 'Encaissement' },
      { value: 'debit', label: 'Débit' },
    ] },
    { name: 'tva_collectee', label: 'TVA collectée', type: 'number' },
    { name: 'tva_deductible', label: 'TVA déductible', type: 'number' },
  ],
  retenuesSource: [
    { name: 'piece', label: 'Pièce', required: true },
    { name: 'date_piece', label: 'Date pièce', type: 'date', required: true },
    { name: 'tiers_nom', label: 'Tiers', required: true },
    { name: 'identifiant_fiscal', label: 'Identifiant fiscal' },
    { name: 'base', label: 'Base', type: 'number', required: true },
    { name: 'taux', label: 'Taux (%)', type: 'number' },
  ],
  timbresFiscaux: [
    { name: 'facture_ref', label: 'Réf. facture', required: true },
    { name: 'tiers_nom', label: 'Tiers' },
    { name: 'base', label: 'Base', type: 'number', required: true },
    { name: 'taux', label: 'Taux (%)', type: 'number' },
  ],
}

// Exports fichiers (blob). Ceux exigeant un exercice sont marqués `needsExercice`.
const EXPORTS = [
  { key: 'exportFec', label: 'FEC (DGI)', fn: comptaApi.etats.exportFec, file: 'FEC.txt', needsExercice: true },
  { key: 'liasseFiscale', label: 'Liasse fiscale', fn: comptaApi.etats.liasseFiscale, file: 'liasse-fiscale.csv', needsExercice: true },
  { key: 'exportFiduciaire', label: 'Export fiduciaire', fn: comptaApi.etats.exportFiduciaire, file: 'export-fiduciaire.csv', needsExercice: true },
  { key: 'releveDeductionsTva', label: 'Relevé déductions TVA', fn: comptaApi.etats.releveDeductionsTva, file: 'releve-deductions-tva.csv' },
  { key: 'declarationHonoraires', label: 'Déclaration honoraires', fn: comptaApi.etats.declarationHonoraires, file: 'declaration-honoraires.csv' },
  { key: 'aideIs', label: 'Aide au calcul IS', fn: comptaApi.etats.aideIs, file: 'aide-is.csv', needsExercice: true },
]

export default function FiscalitePage() {
  const [tab, setTab] = useState('declarationsTva')
  const [dialog, setDialog] = useState(null)
  const [exercice, setExercice] = useState('')

  const list = useComptaList(RESOURCE[tab].list, undefined)

  const rowActions = (row) => [{
    id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }),
  }]

  const submit = (payload) => {
    const api = RESOURCE[tab]
    return dialog?.row ? api.update(dialog.row.id, payload) : api.create(payload)
  }

  const runExport = async (exp) => {
    if (exp.needsExercice && !exercice) {
      toast.error('Renseignez l’exercice avant cet export.')
      return
    }
    try {
      const params = exp.needsExercice ? { exercice } : {}
      const res = await exp.fn(params)
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      comptaApi.downloadBlob(blob, exp.file)
      toast.success('Export téléchargé.')
    } catch {
      toast.error('Export indisponible — vérifiez les paramètres.')
    }
  }

  const singular = useMemo(() => ({
    declarationsTva: 'déclaration TVA',
    retenuesSource: 'retenue',
    timbresFiscaux: 'timbre',
  }[tab]), [tab])

  return (
    <div className="page">
      <div className="page-header">
        <h2>Fiscalité & déclarations</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialog({ row: null })}>
            <Plus /> Nouvelle {singular}
          </Button>
        </div>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet fiscalité" />
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

      {/* Bloc exports fichiers / télédéclarations (blob download). */}
      <Card className="mt-4 p-4 sm:p-5">
        <h3 className="mb-3 font-display text-base font-semibold">Exports & télédéclarations</h3>
        <div className="mb-3 flex flex-col gap-1 sm:max-w-xs">
          <Label htmlFor="fx-exercice">Exercice (ID) — requis pour FEC / liasse / IS</Label>
          <Input id="fx-exercice" value={exercice} onChange={(e) => setExercice(e.target.value)}
                 placeholder="ex. 3" inputMode="numeric" />
        </div>
        <div className="flex flex-wrap gap-2">
          {EXPORTS.map((exp) => (
            <Button key={exp.key} variant="outline" size="sm" onClick={() => runExport(exp)}>
              <Download className="size-4" /> {exp.label}
            </Button>
          ))}
        </div>
      </Card>

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? `Modifier la ${singular}` : `Nouvelle ${singular}`}
          fields={FIELDS[tab]}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}
