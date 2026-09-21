import { cn } from '../../lib/cn'
import { CONTRAT_STATUS, CONTRAT_STATUS_ORDER, StatutContrat } from './status'

/* ============================================================================
   UX34 — Machine d'états LISIBLE du contrat (CONTRAT12).
   ----------------------------------------------------------------------------
   Rend le graphe d'états sous forme de rail horizontal : l'état courant est mis
   en avant, les états déjà franchis sont atténués. Purement présentatif — les
   transitions gardées passent par l'action `changer-statut` (backend).
   ========================================================================== */

export default function StateMachine({ statut }) {
  const currentIndex = CONTRAT_STATUS_ORDER.indexOf(statut)
  return (
    <div className="flex flex-wrap items-center gap-1.5" aria-label="Cycle de vie du contrat">
      {CONTRAT_STATUS_ORDER.map((key, i) => {
        const isCurrent = key === statut
        const isPast = currentIndex >= 0 && i < currentIndex
        return (
          <div key={key} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-muted-foreground/50" aria-hidden="true">→</span>}
            <span
              className={cn(
                'rounded-full border px-2 py-0.5 text-xs transition-opacity',
                isCurrent
                  ? 'border-ring font-semibold'
                  : isPast
                    ? 'border-border opacity-50'
                    : 'border-dashed border-border opacity-60',
              )}
              title={CONTRAT_STATUS[key]?.label}
            >
              {isCurrent
                ? <StatutContrat status={key} />
                : (CONTRAT_STATUS[key]?.label ?? key)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
