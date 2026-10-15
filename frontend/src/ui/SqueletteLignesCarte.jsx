import { Card, CardContent } from './Card'
import { Skeleton } from './Skeleton'

/* Squelette de liste en carte : `lignes` barres pleine largeur pendant le
   chargement (Balance âgée, Paiements, Listes de prix…). Un seul endroit. */
export default function SqueletteLignesCarte({ lignes = 5 }) {
  return (
    <Card>
      <CardContent className="space-y-2 pt-5">
        {Array.from({ length: lignes }).map((unused, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </CardContent>
    </Card>
  )
}
