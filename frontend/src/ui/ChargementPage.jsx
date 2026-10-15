import { Spinner } from './Spinner'
import { EmptyState } from './EmptyState'

/* Éléments d'état PARTAGÉS des écrans de rapport / supervision / IA : ligne
   « Chargement… » et carte d'échec de chargement. Un seul endroit — jamais
   recopiés écran par écran. */
export function ChargementPage() {
  return (
    <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
  )
}

/** Carte « Impossible de charger … » (icône, titre et description propres à l'écran). */
export function ErreurChargement({ icon, title, description }) {
  return <EmptyState icon={icon} title={title} description={description} className="my-6" />
}

/** Écran de paramétrage / registre en cours de chargement : ligne
 *  « Chargement… » dans la colonne centrée (1100 px) de la page. */
export function ChargementPageCentree() {
  return (
    <div className="mx-auto max-w-[1100px] p-6">
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner className="size-4 text-primary" /> Chargement…
      </p>
    </div>
  )
}
