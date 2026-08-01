// APX26 — « Prochaine action » : UN seul composant pour les deux surfaces qui
// le rendaient chacune à leur façon (le bandeau de `ChantierGateTimeline`
// CH6/`ch6-next-action` et celui de « Ma journée » VX42/`mj-next-action` — la
// duplication était auto-documentée dans le code de MaJourneePage).
//
// Contrat conservé des deux côtés : ton info, libellé « Prochaine action : »
// en gras, une action facultative à droite, et le `data-testid` d'origine passé
// par l'appelant (les specs existantes continuent de le cibler).
import { cn } from '../lib/cn'

export function NextActionBanner({
  children,
  action = null,
  className,
  compact = false,
  ...props
}) {
  return (
    <div
      role="status"
      className={cn(
        // Aucun `text-*` sur le conteneur : l'encre reste `foreground` (le
        // token `--info-foreground` est fait pour un fond info PLEIN, il serait
        // blanc sur blanc ici) — seul le libellé en gras porte la couleur info.
        'flex flex-wrap items-center gap-2 border-info/30 bg-info/10',
        compact
          ? 'justify-between border-b px-4 py-2 text-[13px]'
          : 'flex-col items-stretch gap-2 rounded-lg border p-3',
        className,
      )}
      {...props}
    >
      <span className="text-sm">
        <strong className="text-info">Prochaine action&nbsp;:</strong> {children}
      </span>
      {action}
    </div>
  )
}

export default NextActionBanner
