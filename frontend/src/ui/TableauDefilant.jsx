/* Tableau dans son enveloppe défilante : `<div enveloppe><table …>` …
   `</table></div>` d'un seul tenant. `enveloppe` / `enveloppeStyle` vont sur
   le `div`, `avant` est rendu dans le `div` juste avant le tableau
   (pagination…), tout le reste (className, aria-*, style…) va sur le `table`.
   Un seul endroit — le balisage de fermeture n'est plus recopié écran par
   écran. */
export default function TableauDefilant({
  enveloppe, enveloppeStyle, avant, children, ...table
}) {
  return (
    <div className={enveloppe} style={enveloppeStyle}>
      {avant}
      <table {...table}>{children}</table>
    </div>
  )
}

/* Idem, avec `tete` (l'élément `<thead>`) et les enfants = lignes du
   `<tbody>` : ni `<tbody>` ni `</tbody>` à recopier. */
export function TableauLignes({
  enveloppe, enveloppeStyle, avant, tete, children, ...table
}) {
  return (
    <TableauDefilant enveloppe={enveloppe} enveloppeStyle={enveloppeStyle}
                     avant={avant} {...table}>
      {tete}
      <tbody>{children}</tbody>
    </TableauDefilant>
  )
}
