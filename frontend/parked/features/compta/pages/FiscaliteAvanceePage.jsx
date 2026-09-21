import { useState } from 'react'
import { CheckCircle2, Plus } from 'lucide-react'
import { useTabParam } from '../components/useTabParam'
import { ListShell } from '../../../ui/module'
import { Button, Segmented, toast } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT28 — Fiscalité avancée : acomptes IS, conventions fiscales, TVA non
   déductible.
   ----------------------------------------------------------------------------
   Trois référentiels/registres fiscaux jusqu'ici sans écran : les 4 acomptes
   provisionnels d'IS (NTMAR12, matérialisés ailleurs — cet écran les liste et
   les marque payés), les conventions fiscales de non-double-imposition
   (NTMAR18, taux RAS réduit par pays) et les familles à TVA non déductible
   (XACC11, référentiel CGNC). Endpoints /compta/acomptes-is/,
   /compta/conventions-fiscales/, /compta/familles-tva-non-deductibles/.
   ========================================================================== */

// ── NTMAR12 — Acomptes provisionnels d'IS ──
function AcomptesISPanel() {
  const list = useComptaList(comptaApi.acomptesIS.list, undefined)

  const marquerPaye = async (row) => {
    try {
      await comptaApi.acomptesIS.marquerPaye(row.id)
      toast.success('Acompte marqué payé.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Action impossible.'))
    }
  }

  const columns = [
    { id: 'exercice', header: 'Exercice', accessor: (r) => r.exercice,
      cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'rang', header: 'Rang', accessor: (r) => r.rang, width: 80 },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'echeance', header: 'Échéance', accessor: (r) => r.date_echeance, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut || '—' },
  ]

  const rowActions = (row) => (row.statut !== 'paye'
    ? [{ id: 'payer', label: 'Marquer payé', icon: CheckCircle2, onClick: () => marquerPaye(row) }]
    : [])

  return (
    <ListShell
      hideHeader
      title="Acomptes provisionnels d'IS"
      columns={columns}
      rows={list.rows}
      loading={list.loading}
      error={list.error}
      rowActions={rowActions}
      exportName="acomptes-is"
      emptyTitle="Aucun acompte"
      emptyDescription="Aucun acompte d'IS matérialisé pour le moment (généré depuis « Aide IS »)."
    />
  )
}

// ── NTMAR18 — Conventions fiscales de non-double-imposition ──
function ConventionsFiscalesPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.conventionsFiscales.list, undefined)

  const toggleActif = async (row) => {
    try {
      await comptaApi.conventionsFiscales.update(row.id, { actif: !row.actif })
      toast.success(row.actif ? 'Convention désactivée.' : 'Convention activée.')
      list.reload()
    } catch {
      toast.error('Action impossible.')
    }
  }

  const columns = [
    { id: 'pays', header: 'Pays', accessor: (r) => r.pays },
    { id: 'code_pays', header: 'Code', accessor: (r) => r.code_pays || '—', width: 90 },
    { id: 'taux', header: 'Taux conventionnel', accessor: (r) => Number(r.taux_conventionnel) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => `${v} %` },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || '—' },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non') },
  ]

  const rowActions = (row) => [
    { id: 'edit', label: 'Éditer', onClick: () => setDialog({ row }) },
    { id: 'toggle', label: row.actif ? 'Désactiver' : 'Activer', onClick: () => toggleActif(row) },
  ]

  const fields = [
    { name: 'pays', label: 'Pays bénéficiaire', required: true },
    { name: 'code_pays', label: 'Code pays (ISO)' },
    { name: 'taux_conventionnel', label: 'Taux conventionnel (%)', type: 'number', required: true },
    { name: 'libelle', label: 'Libellé' },
  ]

  const submit = (payload) => (dialog?.row
    ? comptaApi.conventionsFiscales.update(dialog.row.id, payload)
    : comptaApi.conventionsFiscales.create(payload))

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvelle convention</Button>
      </div>
      <ListShell
        hideHeader
        title="Conventions fiscales"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="conventions-fiscales"
        emptyTitle="Aucune convention"
        emptyDescription="Aucune convention fiscale de non-double-imposition enregistrée."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? 'Modifier la convention' : 'Nouvelle convention fiscale'}
          fields={fields}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── XACC11 — Familles à TVA non déductible ──
function FamillesTvaPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.famillesTvaNonDeductibles.list, undefined)

  const toggleActif = async (row) => {
    try {
      await comptaApi.famillesTvaNonDeductibles.update(row.id, { actif: !row.actif })
      toast.success(row.actif ? 'Famille désactivée.' : 'Famille activée.')
      list.reload()
    } catch {
      toast.error('Action impossible.')
    }
  }

  const columns = [
    { id: 'famille', header: 'Famille (clef DC22)', accessor: (r) => r.famille,
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || '—' },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non') },
  ]

  const rowActions = (row) => [
    { id: 'edit', label: 'Éditer', onClick: () => setDialog({ row }) },
    { id: 'toggle', label: row.actif ? 'Désactiver' : 'Activer', onClick: () => toggleActif(row) },
  ]

  const fields = [
    { name: 'famille', label: 'Famille (clef DC22)', required: true },
    { name: 'libelle', label: 'Libellé' },
  ]

  const submit = (payload) => (dialog?.row
    ? comptaApi.famillesTvaNonDeductibles.update(dialog.row.id, payload)
    : comptaApi.famillesTvaNonDeductibles.create(payload))

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvelle famille</Button>
      </div>
      <ListShell
        hideHeader
        title="Familles TVA non déductible"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="familles-tva-non-deductibles"
        emptyTitle="Aucune famille"
        emptyDescription="Aucune famille à TVA non déductible référencée (véhicules de tourisme, missions/réceptions…)."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? 'Modifier la famille' : 'Nouvelle famille TVA non déductible'}
          fields={fields}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

const TABS = [
  { value: 'acomptesIS', label: 'Acomptes IS' },
  { value: 'conventionsFiscales', label: 'Conventions fiscales' },
  { value: 'famillesTva', label: 'TVA non déductible' },
]

export default function FiscaliteAvanceePage() {
  const [tab, setTab] = useTabParam('acomptesIS')

  return (
    <div className="page">
      <div className="page-header">
        <h2>Fiscalité avancée</h2>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet fiscalité avancée" />
      </div>

      {tab === 'acomptesIS' && <AcomptesISPanel />}
      {tab === 'conventionsFiscales' && <ConventionsFiscalesPanel />}
      {tab === 'famillesTva' && <FamillesTvaPanel />}
    </div>
  )
}
