/* H31/H32/H33 — Point d'entrée du moteur DataTable. */
export { DataTable } from './DataTable.jsx'
export { useDataTable } from './useDataTable.js'
export { EditableCell } from './EditableCell.jsx'
export { BulkActionBar } from './BulkActionBar.jsx'
export { ColumnManager } from './ColumnManager.jsx'

// Logique pure (réutilisable/testable hors React).
export * from './logic.js'
export * from './urlState.js'
export * from './csv.js'
