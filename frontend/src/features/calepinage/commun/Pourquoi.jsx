import { BookOpen, HelpCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '../../../lib/cn'
import { Popover, PopoverContent, PopoverTrigger } from '../../../ui/Popover'
import useExplications, { remplirPhrase } from './useExplications'

/* ============================================================================
   ACAL872 — LE « ? » UNIQUE D'UN CHIFFRE DU MODULE (« Pourquoi ce chiffre ? »).
   ----------------------------------------------------------------------------
   La phrase vient du REGISTRE servi (`GET calepinages/explications/`, ACAL871),
   jamais écrite ici : ses trous sont remplis par les valeurs SERVIES de
   l'écran (`valeurs` = la réponse que l'écran a déjà en main) ; un trou sans
   valeur s'écrit « valeur non publiée », jamais 0. Une `cle` absente du
   registre ne rend RIEN (et la garde `explications.garde.test.js` échoue).
   Zone tactile 44 × 44 px (marges négatives : la ligne ne bouge pas) ; ouvert
   au clic, à Entrée / Espace et à l'appui long (le relâcher est un clic).
   Distinct de `HelpTip` (bulle d'onglet du rail) : jamais imbriqués.
   ========================================================================== */
export default function Pourquoi({ cle, valeurs = null, className }) {
  const entrees = useExplications()
  const entree = entrees?.find((e) => e.cle === cle) ?? null
  if (entrees && !entree) return null
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Pourquoi ce chiffre ?"
          title="Pourquoi ce chiffre ?"
          data-grandeur={cle}
          className={cn(
            'inline-flex size-11 shrink-0 items-center justify-center -my-3 rounded-full',
            'text-muted-foreground transition-colors hover:text-foreground focus-ring',
            className,
          )}
        >
          <HelpCircle className="size-4" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 text-sm leading-relaxed text-foreground normal-case tracking-normal">
        {entree ? (
          <div className="flex flex-col gap-2">
            <p>{remplirPhrase(entree, valeurs)}</p>
            {entree.geste && <p className="text-muted-foreground">{entree.geste}</p>}
          </div>
        ) : (
          <p className="text-muted-foreground">Explication en cours de chargement.</p>
        )}
        <Link
          to="/aide/lexique"
          className="mt-2 inline-flex min-h-11 items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          <BookOpen className="size-4" aria-hidden="true" /> Voir le lexique complet
        </Link>
      </PopoverContent>
    </Popover>
  )
}
