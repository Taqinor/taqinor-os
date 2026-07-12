import { useEffect, useRef } from 'react'
import TaqinorMark from './TaqinorMark'
import { celebrateDealSigned } from './celebrate'
import { voice } from '../lib/voice'
import { formatMAD } from '../lib/format'

/* VX155 — la carte de victoire du moment le plus important de l'ERP (un
   devis SIGNÉ). Enrichit le Done= de VX40 (qui posait déjà un toast + un
   burst CSS-only) : montant TTC + kWc RÉELS (calculés par l'appelant,
   `SigneDialog.optionsDetail`), « ≈ X t CO₂ évitées/an » dérivée, TaqinorMark
   qui s'illumine. Sous `prefers-reduced-motion` : LA MÊME carte, seulement
   SANS mouvement (ni burst, ni pulse) — jamais moins d'information, jamais
   une gamification de la routine (règle VX40 : ce burst reste réservé à CE
   seul moment). */

// Hypothèses marocaines par défaut, identiques à celles du rapport de
// production estimée (`installations/energy_report.py` :
// DEFAULT_RENDEMENT_KWH_PAR_KWC_AN=1600 × DEFAULT_CO2_KG_PAR_KWH=0.81) — un
// ordre de grandeur cohérent avec le reste de l'app, jamais un chiffre inventé.
const CO2_TONNES_PAR_KWC_AN = 1.3

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export default function DealSignedCelebration({
  open, reference, montantTtc, kwc, onClose,
}) {
  // Le burst (celebrate.js) ne se pose qu'UNE fois par ouverture, jamais à
  // chaque re-render pendant que la carte reste affichée.
  const fired = useRef(false)
  useEffect(() => {
    if (open && !fired.current) {
      fired.current = true
      celebrateDealSigned()
    }
    if (!open) fired.current = false
  }, [open])

  if (!open) return null

  const reduced = prefersReducedMotion()
  const co2 = kwc != null ? Math.round(kwc * CO2_TONNES_PAR_KWC_AN * 10) / 10 : null

  return (
    <div
      className="fixed inset-0 z-[var(--z-overlay)] flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="deal-signed-title"
      data-testid="deal-signed-celebration"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-2xl border border-border bg-card p-8 text-center shadow-ui-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex justify-center">
          <TaqinorMark size={56} animate={!reduced} />
        </div>
        <h2
          id="deal-signed-title"
          className="font-display text-lg font-bold tracking-tight text-foreground"
        >
          Affaire signée{reference ? ` — ${reference}` : ''}
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">{voice.dealSigned}</p>
        <p className="mt-4 text-2xl font-bold tabular-nums text-foreground">
          {formatMAD(montantTtc)}
        </p>
        {kwc != null && (
          <p className="mt-1 text-sm tabular-nums text-muted-foreground">
            ≈ {kwc} kWc{co2 != null ? ` · ≈ ${co2} t CO₂ évitées/an` : ''}
          </p>
        )}
        <button
          type="button"
          onClick={onClose}
          className="btn mt-6 inline-flex items-center justify-center rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          Continuer
        </button>
      </div>
    </div>
  )
}
