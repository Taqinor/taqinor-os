import { Skeleton } from '../ui/Skeleton'
// VX154 — chaque transition de route est signée : un petit soleil Taqinor animé
// coiffe la silhouette de page (figé sous prefers-reduced-motion).
import SolarLoader from '../ui/SolarLoader'

/* O65 — Repli de chargement « skeleton-first » pour le lazy-loading des routes.
   ----------------------------------------------------------------------------
   Pendant qu'un bundle de page est récupéré (code splitting via React.lazy +
   <Suspense>), on n'affiche plus un simple texte « Chargement… » : on rend une
   silhouette de page (en-tête + lignes de contenu) qui rappelle la structure
   réelle d'un écran. Ça réduit le décalage de mise en page (CLS) et donne une
   impression de chargement immédiat.

   Réutilise le primitif <Skeleton> (anim respectueuse de prefers-reduced-motion).
   `aria-busy` + libellé FR pour l'accessibilité (lecteurs d'écran). */
export default function RouteFallback() {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Chargement de la page"
      className="flex flex-col gap-6 p-6"
    >
      {/* VX154 — petit soleil animé qui signe l'attente (au-dessus de la
          silhouette skeleton conservée pour la stabilité de mise en page). */}
      <SolarLoader size={22} label="Chargement de la page…" />

      {/* En-tête : titre + sous-titre + action */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-7 w-56" />
          <Skeleton className="h-4 w-72" />
        </div>
        <Skeleton className="h-9 w-28" />
      </div>

      {/* Bandeau d'indicateurs (cartes) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((unused, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>

      {/* Corps : grand bloc de contenu (liste / tableau / formulaire) */}
      <Skeleton className="h-80 w-full" />
    </div>
  )
}
