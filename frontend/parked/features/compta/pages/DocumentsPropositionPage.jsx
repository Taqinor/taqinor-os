import { useState } from 'react'
import { Plus } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import { Button, toast } from '../../../ui'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT40 — Bibliothèque d'annexes de proposition.
   ----------------------------------------------------------------------------
   FG215 : documents réutilisables (lettre de couverture, références,
   garanties…) attachables au PDF de proposition commerciale. Purement
   additif — ne touche NI le générateur de devis NI le moteur PDF (règle #4
   du dépôt) : c'est la bibliothèque de contenu que le commercial choisit,
   le rendu reste `apps/ventes/quote_engine/`. Endpoint
   /compta/documents-proposition/.
   ========================================================================== */

const TYPE_LABELS = {
  lettre: 'Lettre de couverture',
  references: 'Références / réalisations',
  garanties: 'Garanties',
  autre: 'Autre annexe',
}

export default function DocumentsPropositionPage() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.documentsProposition.list, undefined)

  const toggleActif = async (row) => {
    try {
      await comptaApi.documentsProposition.update(row.id, { actif: !row.actif })
      toast.success(row.actif ? 'Document désactivé.' : 'Document activé.')
      list.reload()
    } catch {
      toast.error('Action impossible.')
    }
  }

  const columns = [
    { id: 'titre', header: 'Titre', accessor: (r) => r.titre },
    { id: 'type', header: 'Type', accessor: (r) => r.type_document_display || TYPE_LABELS[r.type_document] || r.type_document },
    { id: 'ordre', header: 'Ordre', accessor: (r) => r.ordre, width: 80 },
    { id: 'fichier', header: 'Pièce jointe', accessor: (r) => (r.fichier ? 'Oui' : 'Non'), width: 100 },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non') },
  ]

  const rowActions = (row) => [
    { id: 'edit', label: 'Éditer', onClick: () => setDialog({ row }) },
    { id: 'toggle', label: row.actif ? 'Désactiver' : 'Activer', onClick: () => toggleActif(row) },
  ]

  const fields = [
    { name: 'titre', label: 'Titre', required: true },
    { name: 'type_document', label: 'Type de document', options: Object.entries(TYPE_LABELS).map(
      ([value, label]) => ({ value, label })) },
    { name: 'contenu', label: 'Contenu (texte)' },
    { name: 'ordre', label: 'Ordre', type: 'number' },
  ]

  const submit = (payload) => (dialog?.row
    ? comptaApi.documentsProposition.update(dialog.row.id, payload)
    : comptaApi.documentsProposition.create(payload))

  return (
    <div className="page">
      <div className="page-header">
        <h2>Annexes de proposition</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialog({ row: null })}><Plus /> Nouvelle annexe</Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Bibliothèque d'annexes"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="documents-proposition"
        emptyTitle="Aucune annexe"
        emptyDescription="Aucun document réutilisable pour l'instant (lettre, références, garanties…)."
      />

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? 'Modifier l’annexe' : 'Nouvelle annexe de proposition'}
          fields={fields}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}
