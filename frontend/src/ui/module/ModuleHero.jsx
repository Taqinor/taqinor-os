import { cn } from '../../lib/cn'

/* VX15 — Identité de cockpit : ModuleHero.
   ----------------------------------------------------------------------------
   En-tête de tableau de bord de module : titre (heading, niveau paramétrable
   pour préserver un contrat e2e existant), sous-titre, actions, slot KPI, et
   un liseré gradient brass→transparent (≤8 % d'opacité) — le SEUL gradient de
   marque autorisé À L'INTÉRIEUR de l'app (« lumière à travers le verre »).
   Coupé sous `prefers-reduced-motion` (statique, aucun shimmer).

   Casse la monotonie « 4 boîtes grises copiées-collées » : un cockpit de
   module s'ouvre sur une identité visible, pas un `<h2>` nu.

   Props :
     title      : string (obligatoire)
     subtitle   : string?
     actions    : ReactNode? (boutons alignés à droite du titre)
     kpiSlot    : ReactNode? (bandeau KPI rendu sous le hero)
     accent     : string? — VX8 pastille d'accent de module (teinte dérivée de
                  la marque) ; no-op tant que VX8 (registre d'accents) n'est
                  pas livré — jamais fabriqué, simplement absent si non fourni.
     headingAs  : 'h1' | 'h2' (défaut 'h1') — Dashboard.jsx doit garder un
                  <h2> pour préserver le contrat e2e existant (auth.setup.js).
*/
export function ModuleHero({
  title,
  subtitle,
  actions,
  kpiSlot,
  accent,
  headingAs = 'h1',
  className,
}) {
  const Heading = headingAs === 'h2' ? 'h2' : 'h1'

  return (
    <div className={cn('module-hero relative overflow-hidden rounded-xl', className)}>
      {/* Liseré gradient brass→transparent, décoratif uniquement. */}
      <div className="module-hero-sheen pointer-events-none absolute inset-x-0 top-0 h-px" aria-hidden="true" />
      <div className="flex flex-col gap-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            {accent && (
              <span
                className="size-2 shrink-0 rounded-full"
                style={{ background: accent }}
                aria-hidden="true"
              />
            )}
            <div>
              <Heading className={cn(
                'font-display font-bold tracking-tight text-foreground',
                headingAs === 'h2' ? 'text-xl' : 'text-2xl',
              )}
              >
                {title}
              </Heading>
              {subtitle && (
                <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
              )}
            </div>
          </div>
          {actions && (
            <div className="flex flex-wrap items-center gap-2">{actions}</div>
          )}
        </div>
        {kpiSlot}
      </div>
    </div>
  )
}

export default ModuleHero
