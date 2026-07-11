import { Card } from '../../ui'
import { formatMAD } from '../../lib/format'
import { kanbanSummary } from './factureKanban'

/* ZFAC9 — Vue kanban des factures par statut (pipeline visuel). Wiring/
   données ONLY : réutilise `filtered` déjà chargé par FactureList.jsx et la
   MÊME dérivation de colonne que les onglets (`factureKanban.js`, miroir de
   `isOverdue`/`isPartiallyPaid`/`statutKey`) — aucun nouveau champ backend,
   aucune refonte visuelle (mêmes StatusPill/formatMAD que la vue liste).
   `onOpenFacture` réutilise la MÊME action que la ligne de la vue liste
   (`openEdit(f)` → dialogue d'édition existant) — pas de route de détail
   séparée, cette vue n'invente aucune nouvelle navigation. */
export default function FactureKanbanBoard({ factures, today, onOpenFacture }) {
  const columns = kanbanSummary(factures, today)

  return (
    <div
      className="mt-4 grid gap-3 overflow-x-auto pb-2"
      style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(220px, 1fr))` }}
      data-testid="facture-kanban-board"
    >
      {columns.map((col) => (
        <div key={col.key} className="flex min-w-[220px] flex-col gap-2" data-testid={`fkb-column-${col.key}`}>
          <div className="flex items-center justify-between gap-2 px-1">
            <span className="text-sm font-medium text-foreground">{col.label}</span>
            <span className="rounded bg-muted px-1.5 text-xs text-muted-foreground" data-testid={`fkb-count-${col.key}`}>
              {col.count}
            </span>
          </div>
          <div className="px-1 text-xs text-muted-foreground" data-testid={`fkb-total-${col.key}`}>
            Total {formatMAD(col.total)}
          </div>
          <div className="flex flex-col gap-2">
            {col.factures.length === 0 ? (
              <Card className="p-3 text-center text-xs text-muted-foreground">Aucune facture</Card>
            ) : (
              col.factures.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className="block w-full text-left"
                  onClick={() => onOpenFacture?.(f)}
                >
                  <Card className="flex flex-col gap-1 p-3 text-sm transition-colors hover:bg-muted/40">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{f.reference}</span>
                      {/* VX142(d) — la colonne EST déjà le statut : le StatusPill
                          répété sur chaque carte n'apporte rien. Remplacé par une
                          info utile (échéance si due, sinon montant dû). */}
                      {f.date_echeance ? (
                        <span className="text-xs text-muted-foreground" title="Échéance">
                          {new Date(f.date_echeance).toLocaleDateString('fr-FR')}
                        </span>
                      ) : f.montant_du != null && Number(f.montant_du) > 0 ? (
                        <span className="text-xs text-muted-foreground" title="Montant dû">
                          Dû {formatMAD(f.montant_du)}
                        </span>
                      ) : null}
                    </div>
                    <span className="text-xs text-muted-foreground">{f.client_nom}</span>
                    <span className="tabular-nums font-medium">
                      {f.total_ttc != null ? formatMAD(f.total_ttc) : '—'}
                    </span>
                  </Card>
                </button>
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
