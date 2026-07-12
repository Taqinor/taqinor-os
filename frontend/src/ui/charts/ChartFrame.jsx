import { useId, useState } from 'react'
import { Table as TableIcon } from 'lucide-react'

/* N161 — Accessibilité des graphiques.
   Enveloppe un graphique du kit avec :
     • `role="img"` + `aria-label` (résumé lisible par lecteur d'écran),
     • un repli « Voir le tableau » : une table de données équivalente, masquée
       par défaut (mais TOUJOURS dans le DOM pour les lecteurs d'écran via
       `.sr-only` quand repliée), dépliable pour tous (utile mobile/impression).

   Le graphe lui-même reste décoratif pour l'AT (la donnée chiffrée vit dans la
   table) : on passe `aria-hidden` au conteneur visuel, et l'`aria-label` porte
   le résumé.

   Props :
     label      : aria-label / résumé du graphe (obligatoire pour l'a11y)
     columns    : [{ key, header, align?, format?(value,row) }]
     rows       : données tabulaires équivalentes au graphe
     getRowKey  : (row, i) => key  (défaut i)
     caption    : légende de la table (défaut = label)
     tableToggleLabel : libellé du bouton (défaut « Voir le tableau »)
     children   : le graphique (AreaSansAxe / BarArrondie / …)
*/
export function ChartFrame({
  label,
  columns = [],
  rows = [],
  getRowKey = (row, i) => i,
  caption,
  tableToggleLabel = 'Voir le tableau',
  children,
}) {
  const [open, setOpen] = useState(false)
  const tableId = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const hasTable = columns.length > 0 && rows.length > 0

  return (
    <div className="chart-frame">
      {/* Visuel : décoratif pour l'AT, l'info chiffrée est dans la table. */}
      <div role="img" aria-label={label}>
        <div aria-hidden="true">{children}</div>
      </div>

      {hasTable && (
        <>
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground focus-ring"
              aria-expanded={open}
              aria-controls={`chart-table-${tableId}`}
              onClick={() => setOpen((v) => !v)}
            >
              <TableIcon className="size-3.5" aria-hidden="true" />
              {open ? 'Masquer le tableau' : tableToggleLabel}
            </button>
          </div>

          {/* La table reste dans le DOM même repliée : `sr-only` la garde
              accessible aux lecteurs d'écran et au mobile. */}
          <div
            id={`chart-table-${tableId}`}
            className={open ? 'mt-2 overflow-x-auto' : 'sr-only'}
          >
            <table className="data-table">
              <caption className="sr-only">{caption ?? label}</caption>
              <thead>
                <tr>
                  {columns.map((c) => (
                    <th key={c.key} scope="col" className={c.align === 'right' ? 'ta-right' : undefined}>
                      {c.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={getRowKey(row, i)}>
                    {columns.map((c) => (
                      <td
                        key={c.key}
                        data-label={c.header}
                        className={c.align === 'right' ? 'ta-right tabular-nums' : undefined}
                      >
                        {c.format ? c.format(row[c.key], row) : row[c.key]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

export default ChartFrame
