import { cn } from '../lib/cn'

/* VX28 — En-tête de page UNIQUE de l'app. Trois idiomes divergeaient
   (Dashboard en font-display, `<h2>` nu monitoring, `.page-title` reporting) —
   ce composant unifie titre + sous-titre + actions sur les tokens sémantiques
   (donc clair/sombre cohérent), avec une rangée de filtres optionnelle.

   Props :
     - title       : chaîne ou noeud (rendu <h2>, ancre e2e getByRole('heading')).
     - subtitle    : texte secondaire optionnel.
     - actions     : noeud aligné à droite du titre (boutons, etc.).
     - filters     : rangée sous le titre (segmented, recherche…).
     - icon        : icône lucide optionnelle devant le titre.
     - headingClassName / className : échappatoires.
     - headingId   : id du <h2> (aria-labelledby éventuel). */
export function PageHeader({
  title,
  subtitle,
  actions,
  filters,
  icon: Icon,
  className,
  headingClassName,
  headingId,
  children,
  ...props
}) {
  return (
    <header className={cn('mb-6', className)} {...props}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h2
            id={headingId}
            className={cn(
              'flex items-center gap-2 font-display text-xl font-semibold leading-tight tracking-tight text-foreground',
              headingClassName,
            )}
          >
            {Icon && <Icon className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />}
            {title}
          </h2>
          {subtitle && (
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          )}
        </div>
        {actions && (
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        )}
      </div>
      {filters && (
        <div className="mt-4 flex flex-wrap items-center gap-3">{filters}</div>
      )}
      {children}
    </header>
  )
}

export default PageHeader
