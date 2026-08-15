import { cn } from '../lib/cn'

/* NTP2P8 — badge coloré du score de risque fournisseur (0-100, 100 = risque
   nul). Le badge n'ASSÈNE jamais un score : il porte le détail des facteurs
   pénalisants en infobulle et en liste dépliée, pour qu'un acheteur sache
   POURQUOI un fournisseur est mal noté (documents expirés, retards, litiges…).

   Aucune donnée client-facing ici : ce sont des indicateurs achats INTERNES.

   Props : { data, className } — `data` est la réponse de
   `GET /stock/fournisseurs/{id}/score-risque/`. `null` → rien n'est rendu
   (jamais un « 0 » trompeur quand la donnée n'a pas pu être chargée). */

const TONES = {
  faible: {
    label: 'Risque faible',
    cls: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  },
  modere: {
    label: 'Risque modéré',
    cls: 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400',
  },
  eleve: {
    label: 'Risque élevé',
    cls: 'border-destructive/40 bg-destructive/10 text-destructive',
  },
}

export default function ScoreRisqueFournisseurBadge({ data, className }) {
  if (!data || typeof data.score !== 'number') return null
  const tone = TONES[data.niveau] ?? TONES.modere
  const penalisants = (data.facteurs ?? []).filter((f) => f.penalite > 0)

  return (
    <div className={cn('mt-2 flex flex-col gap-1', className)}>
      <span
        data-testid="score-risque-badge"
        data-niveau={data.niveau}
        title={
          penalisants.length
            ? penalisants.map((f) => `${f.libelle} : −${f.penalite}`).join(' · ')
            : 'Aucun facteur pénalisant'
        }
        className={cn(
          'inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
          tone.cls,
        )}
      >
        {tone.label} — {data.score}/100
      </span>
      {penalisants.length > 0 && (
        <ul className="text-xs text-muted-foreground">
          {penalisants.map((f) => (
            <li key={f.code}>
              {f.libelle} : −{f.penalite} / {f.plafond}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
