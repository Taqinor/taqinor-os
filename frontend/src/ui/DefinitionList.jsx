import { cn } from '../lib/cn'

/* G29 — Liste de définitions (clé → valeur), pour fiches/récapitulatifs.
   `items` = [{ term, description }] ; `description` peut être un nœud React. */
export function DefinitionList({ items = [], className, ...props }) {
  return (
    <dl className={cn('grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-4 gap-y-2 text-sm', className)} {...props}>
      {items.map((it, i) => (
        <div key={i} className="contents">
          <dt className="text-muted-foreground">{it.term}</dt>
          <dd className="font-medium text-foreground">{it.description ?? '—'}</dd>
        </div>
      ))}
    </dl>
  )
}

export default DefinitionList
