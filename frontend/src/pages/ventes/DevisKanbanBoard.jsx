/* APX15(b) — LE VRAI BOARD VENTES : les devis par statut DOCUMENT.
   ---------------------------------------------------------------------------
   Il n'existait AUCUN board côté ventes : le fichier qui portait le nom
   « VentesKanban » rendait en réalité la liste des bons de commande (renommé
   `BonCommandeList` par APX15(a)), et `FactureKanbanBoard` était une grille
   statique sans aucune parenté avec le langage `kb-*` du board leads.

   Ce board parle le MÊME langage visuel que le board des leads (classes
   `kb-*` existantes — aucune nouvelle grammaire), avec le montant en HÉROS
   (c'est l'app de l'argent). Le regroupement vit dans
   `features/ventes/devisBoard.js` (logique pure, testable sans DOM).

   DEUX INVARIANTS NON NÉGOCIABLES :
   1. RÈGLE #4 — les colonnes sont les statuts DOCUMENT du devis. JAMAIS les
      clés du funnel STAGES.py (règle #2).
   2. AUCUNE action d'état par glisser-déposer. Un devis ne se signe pas en le
      faisant glisser : accepter/refuser restent des actions EXPLICITES de la
      vue liste. Les cartes sont des boutons (ouvrir), pas des draggables —
      d'où `kb-board-static`, qui neutralise l'affordance de glissé. */
import { formatMAD } from '../../lib/format'
import { devisBoardColumns } from '../../features/ventes/devisBoard'

export default function DevisKanbanBoard({ devis, onOpenDevis }) {
  const columns = devisBoardColumns(devis)

  return (
    <div className="kb-board kb-board-static" data-testid="devis-kanban-board">
      {columns.map(col => (
        <section
          key={col.key}
          className="kb-col"
          style={{ '--kb-accent': col.accent }}
          aria-label={`Statut ${col.label} — ${col.count} devis`}
          data-testid={`dkb-column-${col.key}`}
        >
          <header className="kb-col-header">
            <div className="kb-col-title-row">
              <span className="kb-col-title">{col.label}</span>
              <span className="kb-col-count" data-testid={`dkb-count-${col.key}`}>{col.count}</span>
            </div>
            {col.total > 0 && (
              <span className="kb-col-money" data-testid={`dkb-total-${col.key}`}>
                {formatMAD(col.total)}
              </span>
            )}
          </header>
          <div className="kb-col-body">
            {col.count === 0 ? (
              <div className="kb-col-empty">Aucun devis</div>
            ) : col.devis.map(d => (
              <button
                key={d.id}
                type="button"
                className="kb-card-open"
                onClick={() => onOpenDevis?.(d)}
              >
                <article className="kb-card">
                  {/* Le MONTANT est le héros : c'est l'app de l'argent. */}
                  <div className="num dkb-card-amount">
                    {d.total_ttc != null ? formatMAD(d.total_ttc) : '—'}
                  </div>
                  <div className="dkb-card-ref">{d.reference}</div>
                  <div className="dkb-card-client">{d.client_nom ?? '—'}</div>
                </article>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
