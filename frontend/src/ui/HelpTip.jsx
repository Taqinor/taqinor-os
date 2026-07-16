import { HelpCircle, BookOpen } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '../lib/cn'
import { Popover, PopoverTrigger, PopoverContent } from './Popover'

/* VX47 — Aide contextuelle intégrée : popovers « ? » sur les écrans difficiles.
   L'overlay `?` global (I138) n'explique que les raccourcis clavier et `/ui`
   est développeur-facing ; aucun écran métier n'expliquait ses concepts à un
   nouvel employé. `HelpTip` = petit bouton « ? » discret (jamais un gros
   bouton — il ne doit JAMAIS provoquer de re-layout) qui ouvre un `Popover`
   du kit avec un contenu FR concis (2-4 phrases, jamais de lien vers une doc
   externe — tout tient dans la bulle).

   VX247(d) — un lien interne discret vers le lexique (`/aide/lexique`, une
   page de l'app, PAS une doc externe) POINTE vers le glossaire complet au
   lieu de dupliquer une définition détaillée dans chaque bulle.

   Usage :
     <span className="inline-flex items-center gap-1.5">
       Score de lead <HelpTip label="Score de lead">Texte FR 2-4 phrases…</HelpTip>
     </span> */
export function HelpTip({ label = 'Aide', children, side = 'top', align = 'center', className }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={label}
          title={label}
          className={cn(
            // Discret : cercle 18px, contour ténu, jamais de fond plein tant
            // qu'on ne survole pas — ne doit jamais peser plus qu'un mot.
            'inline-flex size-[18px] shrink-0 items-center justify-center rounded-full',
            'text-muted-foreground/70 transition-colors hover:bg-muted hover:text-foreground',
            'focus-ring',
            className,
          )}
        >
          <HelpCircle className="size-[15px]" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent side={side} align={align} className="w-72 text-sm leading-relaxed text-foreground">
        {children}
        <Link
          to="/aide/lexique"
          className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          <BookOpen className="size-3.5" aria-hidden="true" /> Voir le lexique complet
        </Link>
      </PopoverContent>
    </Popover>
  )
}

export default HelpTip
