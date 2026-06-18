import { Compass } from 'lucide-react'
import { EmptyState } from './EmptyState'
import { Button } from './Button'

/* G30 — Écran 404 réutilisable. `onHome` optionnel (sinon lien « / »). */
export function NotFound({ onHome }) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <EmptyState
        icon={Compass}
        title="Page introuvable (404)"
        description="La page demandée n'existe pas ou a été déplacée."
        action={
          onHome ? (
            <Button onClick={onHome}>Retour à l'accueil</Button>
          ) : (
            <Button asChild>
              <a href="/">Retour à l'accueil</a>
            </Button>
          )
        }
        className="max-w-md border-solid"
      />
    </div>
  )
}

export default NotFound
