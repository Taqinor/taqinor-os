import { useMemo } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Card } from '../Card'
import { Badge } from '../Badge'
import { EmptyState } from '../EmptyState'
import { Skeleton } from '../Skeleton'
import { Button } from '../Button'

/* Éléments PARTAGÉS des tableaux « Action requise » (tickets SAV, relances de
   devis) : état chargement / erreur, en-tête, carte de panier. Un seul endroit —
   jamais recopiés écran par écran. */

/** Somme des comptes de `board.buckets`. */
export function useTotalBuckets(board) {
  return useMemo(() => {
    if (!board) return 0
    return Object.values(board.buckets ?? {}).reduce((sum, b) => sum + b.count, 0)
  }, [board])
}

/** Squelette pendant le chargement, sinon carte d'erreur avec « Réessayer ». */
export function EtatActionBoard({ loading, squelettes, onRetry }) {
  if (loading) {
    return (
      <div className="ui-root mx-auto flex max-w-6xl flex-col gap-4 p-1">
        {Array.from({ length: squelettes }).map((unused, i) => <Skeleton key={i} className="h-40 w-full" />)}
      </div>
    )
  }
  return (
    <div className="ui-root mx-auto max-w-6xl p-1">
      <EmptyState icon={AlertTriangle} title="Chargement impossible"
                  description="Le tableau d'action n'a pas pu être chargé. Réessayez."
                  action={<Button size="sm" variant="outline" onClick={onRetry}>Réessayer</Button>} />
    </div>
  )
}

/** Titre de page + sous-titre (compte). */
export function EnTeteActionBoard({ titre, sousTitre }) {
  return (
    <header>
      <h1 className="font-display text-2xl font-bold tracking-tight">{titre}</h1>
      <p className="text-sm text-muted-foreground">
        {sousTitre}
      </p>
    </header>
  )
}

/** Carte d'un panier : icône + libellé + compte, puis ses lignes (20 max). */
export function CartePanier({ Icon, label, tone, count, ids, vide, espacement = 'gap-1', renderId }) {
  return (
    <Card className="flex flex-col gap-2 p-3">
      <div className="flex items-center gap-2">
        {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden="true" />}
        <span className="flex-1 font-display text-sm font-semibold">{label}</span>
        <Badge tone={tone}>{count}</Badge>
      </div>
      {ids.length === 0 ? (
        <p className="text-xs text-muted-foreground">{vide}</p>
      ) : (
        <ul className={`flex flex-col ${espacement}`}>
          {ids.slice(0, 20).map(renderId)}
          {ids.length > 20 && (
            <li className="text-xs text-muted-foreground">
              + {ids.length - 20} autre(s)
            </li>
          )}
        </ul>
      )}
    </Card>
  )
}
