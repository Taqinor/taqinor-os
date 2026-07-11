import { cn } from '../lib/cn'

/* ============================================================================
   VX152 — KeyValueTable : primitif partagé « libellé → valeur » (deux colonnes).
   ----------------------------------------------------------------------------
   Remplace les <table> clé/valeur écrites à la main (ex. les champs OCR extraits
   dans OcrUpload, qui en dupliquaient deux). L'appelant fournit `items`
   [{ key, label, value? }] ; `renderValue(item)` permet une cellule éditable
   (ex. <Input>) — sinon `item.value` est rendu tel quel. Toujours enveloppé dans
   un conteneur défilable (invariant PWA 375px). Style unifié, tokens seulement.

   Props :
     items       : [{ key, label, value? }]
     renderValue : (item) => node  (optionnel — cellule de droite personnalisée)
     dense       : plus compact (text-xs, libellé sans fond) pour les vues denses
     className / 'aria-label'
   ========================================================================== */
export function KeyValueTable({
  items = [],
  renderValue,
  dense = false,
  className,
  'aria-label': ariaLabel,
}) {
  return (
    <div className="overflow-x-auto">
      <table
        className={cn('w-full', dense ? 'text-xs' : 'text-sm', className)}
        aria-label={ariaLabel}
      >
        <tbody>
          {items.map((it) => (
            <tr key={it.key} className="border-b border-border last:border-0">
              <th
                scope="row"
                className={cn(
                  'text-left align-middle font-medium text-muted-foreground',
                  dense ? 'w-36 py-1 pr-3' : 'w-40 bg-muted/50 px-4 py-2',
                )}
              >
                {it.label}
              </th>
              <td className={cn('align-middle text-foreground', dense ? 'py-1' : 'px-3 py-1.5')}>
                {renderValue ? renderValue(it) : it.value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default KeyValueTable
