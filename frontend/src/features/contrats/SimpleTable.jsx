import { EmptyState } from '../../ui'

/* ============================================================================
   Table légère (lecture seule) pour les onglets de détail — pas de moteur
   DataTable ici : quelques colonnes, quelques lignes. `columns` = [{ header,
   cell:(row)=>node, align? }]. Affiche un état vide si aucune ligne.
   ========================================================================== */

export default function SimpleTable({ columns = [], rows = [], emptyText = 'Aucun élément.' }) {
  if (!rows.length) {
    return <EmptyState title="Rien à afficher" description={emptyText} />
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40 text-left">
            {columns.map((c, i) => (
              <th
                key={i}
                className={`px-3 py-2 font-medium text-muted-foreground ${c.align === 'right' ? 'text-right' : ''}`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={row.id ?? ri} className="border-b border-border/60 last:border-0">
              {columns.map((c, ci) => (
                <td
                  key={ci}
                  className={`px-3 py-2 align-top ${c.align === 'right' ? 'text-right tabular-nums' : ''}`}
                >
                  {c.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
