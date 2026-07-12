import { ConfirmDialog } from './ConfirmDialog'

// VX244 — confirmation typée pour une suppression EN MASSE (bulk ≥5 éléments,
// ex. leads archivés/supprimés en lot depuis le Kanban), extraite du patron
// `ForceDeleteModal` (StockList.jsx:507-560) — on tape le NOMBRE d'éléments
// (générique quel que soit le type d'enregistrement) au lieu d'un nom/SKU.
// Toujours `severity="high"` (ConfirmDialog) : le bouton reste désactivé tant
// que la saisie ne correspond pas exactement au compte.
export function BulkDestructiveConfirm({
  open,
  onOpenChange,
  count,
  itemLabel = 'éléments',
  title,
  description,
  confirmLabel = 'Supprimer définitivement',
  loading = false,
  onConfirm,
}) {
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      severity="high"
      title={title || `Supprimer ${count} ${itemLabel} ?`}
      description={description || `Cette action est irréversible. ${count} ${itemLabel} seront définitivement supprimés.`}
      confirmText={String(count)}
      confirmLabel={confirmLabel}
      loading={loading}
      onConfirm={onConfirm}
    />
  )
}

export default BulkDestructiveConfirm
