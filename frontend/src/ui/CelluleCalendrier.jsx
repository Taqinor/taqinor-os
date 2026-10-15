/* Cellule d'un jour dans une grille calendrier mensuelle : numéro du jour,
   pastilles (au plus `max`, le reste derrière « +N autres » / « Réduire »).
   `rendrePastille(élément)` dessine une pastille ; `classes` ajoute des classes
   à la cellule ; le reste des props (onDragOver, onDrop…) va sur le `div`.
   Un seul endroit pour le calendrier des leads et celui des installations. */
export default function CelluleCalendrier({
  cell, aujourdhui, items, deplie, onBasculer, rendrePastille, max = 3, classes = [], ...divProps
}) {
  const visibles = deplie || items.length <= max ? items : items.slice(0, max)
  const caches = items.length - visibles.length
  return (
    <div
      className={[
        'cal-cell',
        cell.inMonth ? '' : 'cal-cell-out',
        aujourdhui ? 'cal-cell-today' : '',
        ...classes,
      ].filter(Boolean).join(' ')}
      {...divProps}
    >
      <span className="cal-day-number">{cell.dayNumber}</span>
      <div className="cal-chips">
        {visibles.map(rendrePastille)}
        {caches > 0 && (
          <button type="button" className="cal-more" onClick={() => onBasculer(cell.key)}>
            +{caches} autres
          </button>
        )}
        {deplie && items.length > max && (
          <button type="button" className="cal-more" onClick={() => onBasculer(cell.key)}>
            Réduire
          </button>
        )}
      </div>
    </div>
  )
}
