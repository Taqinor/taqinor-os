import { cn } from '../../lib/cn'
import PageHeader from '../../components/layout/PageHeader'
import { Card } from '../Card'
import { DataTable } from '../datatable'

/* ============================================================================
   UX1 — Coquille de liste (en-tête + tableau).
   ----------------------------------------------------------------------------
   Passe-plat FIN autour du moteur DataTable : PageHeader (titre/actions/filtres/
   fil d'Ariane), un éventuel bandeau de KPI (`children`), puis la grille dans
   une Card. Aucune logique de tri/filtre/pagination ici — DataTable la gère à
   partir de `rows`. Toutes les props de liste sont transmises telles quelles au
   moteur pour ne pas dupliquer son contrat.
   ========================================================================== */

export function ListShell({
  title,
  subtitle,
  actions,
  filters,
  breadcrumbs,
  // APX32 — la page porte parfois DÉJÀ son titre (et un Segmented qui nomme
  // l'onglet juste au-dessus) : la coquille en ajoutait un SECOND. `hideHeader`
  // supprime l'en-tête de la coquille sans rien changer au reste ; les actions
  // et filtres éventuels restent rendus (ils n'ont pas de titre à eux).
  hideHeader = false,
  columns,
  rows = [],
  loading,
  error,
  onRowClick,
  rowActions,
  bulkActions,
  selectable,
  searchable = true,
  searchPlaceholder,
  exportName,
  savedViews,
  persistToUrl,
  urlKey,
  emptyTitle,
  emptyDescription,
  emptyAction,
  summary,
  pageSize,
  children,
  className,
}) {
  return (
    <div className={cn('flex flex-col gap-4', className)}>
      {(!hideHeader || actions || filters || breadcrumbs) && (
        <PageHeader
          title={hideHeader ? undefined : title}
          subtitle={hideHeader ? undefined : subtitle}
          actions={actions}
          filters={filters}
          breadcrumbs={breadcrumbs}
        />
      )}
      {children}
      <Card className="p-4 sm:p-5">
        <DataTable
          data={rows}
          columns={columns}
          loading={loading}
          error={error}
          onRowClick={onRowClick}
          rowActions={rowActions}
          bulkActions={bulkActions}
          selectable={selectable}
          searchable={searchable}
          searchPlaceholder={searchPlaceholder}
          exportName={exportName}
          savedViews={savedViews}
          persistToUrl={persistToUrl}
          urlKey={urlKey}
          emptyTitle={emptyTitle}
          emptyDescription={emptyDescription}
          emptyAction={emptyAction}
          summary={summary}
          pageSize={pageSize}
        />
      </Card>
    </div>
  )
}

export default ListShell
