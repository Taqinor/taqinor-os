import { ArrowDown, ArrowUp } from 'lucide-react'
import { cn } from '../lib/cn'
import { Card } from './Card'

/* G29 — Carte de KPI / statistique. `value` déjà formatée (via lib/format).
   `delta` optionnel : { value, direction: 'up'|'down', tone? }. Chiffres
   tabulaires pour alignement.
   VX157 — `tone="impact"` : variante à accent brass pour les grandeurs
   d'impact POSITIF (production, CO₂ évité, économies…), qui la distingue
   visuellement d'une carte KPI neutre sans être criarde.
   VX124 — `.stat-value-solidify` (voir tokens.css) : le chiffre KPI « se
   solidifie » au montage — la police variable (100–900, brand.css) passe de
   wght 500 à 600 sur --motion-slow, un saut direct sous reduced-motion.
   VX129 — le delta rendait `▲/▼` en glyphe TEXTE (seul endroit hors lucide de
   tout le reste de l'app) : icônes lucide `ArrowUp`/`ArrowDown`, cohérentes
   avec EmptyState/ErrorBoundary/toasts. */
export function Stat({ label, value, hint, delta, icon, tone, className, children, ...props }) {
  const Icon = icon
  const deltaTone =
    delta?.tone ??
    (delta?.direction === 'up' ? 'success' : delta?.direction === 'down' ? 'danger' : 'muted')
  const deltaClass = {
    success: 'text-success',
    danger: 'text-destructive',
    muted: 'text-muted-foreground',
  }[deltaTone]
  const isImpact = tone === 'impact'

  return (
    <Card
      className={cn(
        'p-4 sm:p-5',
        isImpact && 'border-primary/40 bg-primary/[0.06]',
        className,
      )}
      {...props}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        {Icon && (
          <Icon
            className={cn('size-4', isImpact ? 'text-primary' : 'text-muted-foreground')}
            aria-hidden="true"
          />
        )}
      </div>
      {/* VX5 — `.num` (data typography) : chiffres tabulaires à zéro barré +
          tracking resserré, la valeur héros d'un KPI aligne ses colonnes. */}
      <div className="num mt-2 text-2xl font-semibold leading-none stat-value-solidify">
        {value}
      </div>
      {(hint || delta) && (
        <div className="mt-1.5 flex items-center gap-2 text-xs">
          {delta && (
            <span className={cn('inline-flex items-center gap-0.5 font-medium tabular-nums', deltaClass)}>
              {delta.direction === 'up' && <ArrowUp className="size-3" aria-hidden="true" />}
              {delta.direction === 'down' && <ArrowDown className="size-3" aria-hidden="true" />}
              {delta.value}
            </span>
          )}
          {hint && <span className="text-muted-foreground">{hint}</span>}
        </div>
      )}
      {children}
    </Card>
  )
}

export default Stat
