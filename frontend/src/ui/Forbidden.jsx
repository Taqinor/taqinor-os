import { ShieldAlert } from 'lucide-react'
import { EmptyState } from './EmptyState'
import { Button } from './Button'

/* VX131(c) — Écran 403 réutilisable, jumeau de `NotFound.jsx` : un refus de
   rôle/permission retombait sur un toast technique ou une redirection
   silencieuse vers /dashboard — jamais un écran dédié expliquant POURQUOI.
   `onHome` optionnel (sinon lien « / »), même contrat que `NotFound`. */
export function Forbidden({ onHome }) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <EmptyState
        icon={ShieldAlert}
        tone="warning"
        title="Accès refusé (403)"
        description="Votre rôle ne permet pas d'accéder à cette page. Contactez un administrateur si vous pensez que c'est une erreur."
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

export default Forbidden
