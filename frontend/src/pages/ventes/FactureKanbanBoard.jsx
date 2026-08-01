import { formatMAD } from '../../lib/format'
import { kanbanSummary } from './factureKanban'

/* ZFAC9 — Vue kanban des factures par statut (pipeline visuel). Wiring/
   données ONLY : réutilise `filtered` déjà chargé par FactureList.jsx et la
   MÊME dérivation de colonne que les onglets (`factureKanban.js`, miroir de
   `isOverdue`/`isPartiallyPaid`/`statutKey`) — aucun nouveau champ backend.
   `onOpenFacture` réutilise la MÊME action que la ligne de la vue liste
   (`openEdit(f)` → dialogue d'édition existant) — pas de route de détail
   séparée, cette vue n'invente aucune nouvelle navigation.

   APX15(c) — cette vue était une grille STATIQUE en classes utilitaires sans
   AUCUNE parenté avec le langage `kb-*` du board des leads : deux « kanban »
   du même produit qui ne se ressemblaient pas. Elle parle désormais ce
   langage (mêmes colonnes, mêmes cartes), avec le MONTANT en héros comme le
   board devis — c'est l'app de l'argent. Les `data-testid` `fkb-*` sont
   CONSERVÉS : ils sont le contrat de ses tests. Toujours AUCUN glisser-
   déposer (`kb-board-static`) : encaisser/annuler restent des actions
   explicites, jamais un drag. */
export default function FactureKanbanBoard({ factures, today, onOpenFacture }) {
  const columns = kanbanSummary(factures, today)

  return (
    <div className="kb-board kb-board-static mt-4" data-testid="facture-kanban-board">
      {columns.map((col) => (
        <section
          key={col.key}
          className="kb-col"
          aria-label={`Statut ${col.label} — ${col.count} facture${col.count === 1 ? '' : 's'}`}
          data-testid={`fkb-column-${col.key}`}
        >
          <header className="kb-col-header">
            <div className="kb-col-title-row">
              <span className="kb-col-title">{col.label}</span>
              <span className="kb-col-count" data-testid={`fkb-count-${col.key}`}>
                {col.count}
              </span>
            </div>
            <span className="kb-col-money" data-testid={`fkb-total-${col.key}`}>
              Total {formatMAD(col.total)}
            </span>
          </header>
          <div className="kb-col-body">
            {col.factures.length === 0 ? (
              <div className="kb-col-empty">Aucune facture</div>
            ) : (
              col.factures.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className="kb-card-open"
                  onClick={() => onOpenFacture?.(f)}
                >
                  <article className="kb-card">
                    <div className="fkb-card-top">
                      <span className="fkb-card-ref">{f.reference}</span>
                      {/* VX142(d) — la colonne EST déjà le statut : le StatusPill
                          répété sur chaque carte n'apporte rien. Remplacé par une
                          info utile (échéance si due, sinon montant dû). */}
                      {f.date_echeance ? (
                        <span className="fkb-card-meta" title="Échéance">
                          {new Date(f.date_echeance).toLocaleDateString('fr-FR')}
                        </span>
                      ) : f.montant_du != null && Number(f.montant_du) > 0 ? (
                        <span className="fkb-card-meta" title="Montant dû">
                          Dû {formatMAD(f.montant_du)}
                        </span>
                      ) : null}
                    </div>
                    <div className="num fkb-card-amount">
                      {f.total_ttc != null ? formatMAD(f.total_ttc) : '—'}
                    </div>
                    <span className="fkb-card-client">{f.client_nom}</span>
                  </article>
                </button>
              ))
            )}
          </div>
        </section>
      ))}
    </div>
  )
}
