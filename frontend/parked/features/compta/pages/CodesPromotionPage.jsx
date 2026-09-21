import { useState } from 'react'
import { Plus } from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, toast } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT37 — Codes promotionnels datés sur devis.
   ----------------------------------------------------------------------------
   FG209 : codes de remise à dates de validité, traçables au retour sur
   investissement (nb_utilisations, ca_genere calculés côté serveur). Un code
   expiré reste VISIBLE dans la liste avec son état affiché — jamais filtré
   silencieusement, pour que le retour sur investissement passé reste
   consultable. Endpoint /compta/codes-promotion/.
   ========================================================================== */

const EtatTag = statusPill({
  actif: { label: 'Actif', tone: 'success' },
  expire: { label: 'Expiré', tone: 'danger' },
  a_venir: { label: 'À venir', tone: 'info' },
  inactif: { label: 'Désactivé', tone: 'neutral' },
})

function etatDe(row) {
  if (!row.actif) return 'inactif'
  const today = new Date().toISOString().slice(0, 10)
  if (row.date_fin && row.date_fin < today) return 'expire'
  if (row.date_debut && row.date_debut > today) return 'a_venir'
  return 'actif'
}

export default function CodesPromotionPage() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.codesPromotion.list, undefined)

  const toggleActif = async (row) => {
    try {
      await comptaApi.codesPromotion.update(row.id, { actif: !row.actif })
      toast.success(row.actif ? 'Code désactivé.' : 'Code activé.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Action impossible.'))
    }
  }

  const columns = [
    { id: 'code', header: 'Code', accessor: (r) => r.code, cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || '—' },
    { id: 'taux', header: 'Remise', accessor: (r) => Number(r.taux_remise) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => `${v} %` },
    { id: 'validite', header: 'Validité', accessor: (r) => r.date_debut, searchable: false,
      cell: (_v, r) => `${formatDate(r.date_debut)} → ${formatDate(r.date_fin)}` },
    { id: 'etat', header: 'État', accessor: (r) => etatDe(r), searchable: false,
      cell: (_v, r) => <EtatTag status={etatDe(r)} /> },
    { id: 'utilisations', header: 'Utilisations', accessor: (r) => r.nb_utilisations || 0, width: 100 },
    { id: 'ca', header: 'CA généré', accessor: (r) => Number(r.ca_genere) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
  ]

  const rowActions = (row) => [
    { id: 'edit', label: 'Éditer', onClick: () => setDialog({ row }) },
    { id: 'toggle', label: row.actif ? 'Désactiver' : 'Activer', onClick: () => toggleActif(row) },
  ]

  const fields = [
    { name: 'code', label: 'Code', required: true },
    { name: 'libelle', label: 'Libellé' },
    { name: 'taux_remise', label: 'Taux de remise (%)', type: 'number', required: true },
    { name: 'date_debut', label: 'Date de début', type: 'date', required: true },
    { name: 'date_fin', label: 'Date de fin', type: 'date', required: true },
  ]

  const submit = (payload) => (dialog?.row
    ? comptaApi.codesPromotion.update(dialog.row.id, payload)
    : comptaApi.codesPromotion.create(payload))

  return (
    <div className="page">
      <div className="page-header">
        <h2>Codes promotionnels</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialog({ row: null })}><Plus /> Nouveau code</Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Codes promotionnels"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="codes-promotion"
        emptyTitle="Aucun code"
        emptyDescription="Aucun code promotionnel créé pour l'instant."
      />

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? 'Modifier le code' : 'Nouveau code promotionnel'}
          fields={fields}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}
