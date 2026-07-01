import { ListShell } from '../../ui/module'
import { useQhseList } from './useQhseList'

/* ============================================================================
   UX31–UX33 — Liste générique d'une ressource QHSE dans un onglet.
   Charge via `fetcher` (fonction → promesse axios) et rend une ListShell.
   Sert les nombreux registres « lecture/CRUD simple » regroupés sous onglets.
   Props : { title, subtitle, fetcher, columns, exportName, actions?,
             rowActions?, onRowClick?, deps? }.
   ========================================================================== */

export function QhseResourceList({
  title, subtitle, fetcher, columns, exportName, actions, rowActions,
  onRowClick, deps = [],
}) {
  const { rows, loading, error } = useQhseList(fetcher, deps)
  return (
    <ListShell
      title={title}
      subtitle={subtitle}
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      searchable
      exportName={exportName}
      actions={actions}
      rowActions={rowActions}
      onRowClick={onRowClick}
    />
  )
}

export default QhseResourceList
