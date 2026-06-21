import { cn } from '../../lib/cn'

/* J146 — Primitif de tableau partagé du reporting (remplace les anciennes
   <table className="data-table"> écrites à la main). Table sémantique stylée
   par les tokens (pas de couleurs en dur), TOUJOURS enveloppée d'un conteneur
   scrollable (`overflow-x-auto`) pour l'invariant PWA 375px (L878).

   Props :
     columns : [{ key, header, align?: 'right', cell?(row, index), headerClassName?, cellClassName? }]
     rows    : objet[] (lignes de données)
     getRowKey : (row, i) => key  (défaut i)
     footer  : noeud <tr>… optionnel (ligne de total)
     empty   : noeud affiché à la place du corps quand rows est vide
     caption : légende (sr-only) pour l'accessibilité
     'aria-label' : libellé de la table
*/
export function Table({
  columns = [],
  rows = [],
  getRowKey = (row, i) => i,
  footer = null,
  empty = null,
  caption,
  className,
  'aria-label': ariaLabel,
}) {
  const isEmpty = rows.length === 0
  return (
    <div className="overflow-x-auto">
      <table className={cn('report-table w-full border-collapse text-sm', className)} aria-label={ariaLabel}>
        {caption && <caption className="sr-only">{caption}</caption>}
        {columns.some((c) => c.header != null) && (
          <thead>
            <tr className="border-b border-border">
              {columns.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  className={cn(
                    'px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground',
                    c.align === 'right' && 'text-right',
                    c.headerClassName,
                  )}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {isEmpty ? (
            <tr>
              <td colSpan={columns.length || 1} className="px-3 py-2">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr key={getRowKey(row, i)} className="border-b border-border/60 last:border-b-0">
                {columns.map((c) => (
                  <td
                    key={c.key}
                    data-label={typeof c.header === 'string' ? c.header : undefined}
                    className={cn(
                      'px-3 py-2 text-foreground',
                      c.align === 'right' && 'text-right tabular-nums',
                      c.cellClassName,
                    )}
                  >
                    {c.cell ? c.cell(row, i) : row[c.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
        {footer && !isEmpty && <tfoot>{footer}</tfoot>}
      </table>
    </div>
  )
}

export default Table
