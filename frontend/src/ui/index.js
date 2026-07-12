/* Bibliothèque de primitifs UI (refonte, Groupe G). Point d'entrée unique :
   `import { Button, Input, Dialog } from '@/ui'`. */

export * from './Button'
export * from './IconButton'
// VX249(a) — micro-accusé de sauvegarde au grain du champ (pulse vert).
export * from './FieldSavedPulse'
export * from './Spinner'
export * from './Badge'
export * from './StatusPill'
export * from './Card'
export * from './Stat'
export * from './StatusAccentCard'
export * from './Separator'
export * from './Skeleton'
export * from './EmptyState'
export * from './ErrorBoundary'
export * from './NotFound'
export * from './OfflineState'

// Formulaire / contrôles
export * from './Label'
export * from './Input'
export * from './Textarea'
export * from './NumberInputs'
export * from './Checkbox'
export * from './Switch'
export * from './RadioGroup'
export * from './Slider'
export * from './Segmented'
export * from './Select'
export * from './Combobox'
export * from './MultiSelect'
export * from './DatePicker'
export * from './TimePicker'
export * from './FileUpload'
export * from './Form'
export * from './useDirtyGuard'

// Overlays
export * from './Dialog'
export * from './Sheet'
export * from './AlertDialog'
export * from './Popover'
export * from './Tooltip'
export * from './DropdownMenu'
export * from './HoverCard'
export * from './ContextMenu'
export * from './HelpTip'

// Affichage / feedback
export * from './Toaster'
export * from './Tag'
export * from './Avatar'
export * from './DefinitionList'
export * from './Tabs'
export * from './Accordion'
export * from './Progress'
export * from './FloatingActionButton'

// Données / listes (Groupe H — moteur DataTable réutilisable)
export { DataTable, useDataTable, EditableCell, BulkActionBar, ColumnManager } from './datatable'
// VX152 — primitif « libellé → valeur » partagé (fin des tables clé/valeur maison).
export * from './KeyValueTable'
