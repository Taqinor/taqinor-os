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

/* T4-X8-015/016 — un DROIT MANQUANT n'est pas une panne réseau. Vrai pour une
   réponse 403, qu'on tienne l'erreur axios (`response.status`) ou le corps
   rangé par un slice (`rejectWithValue(err.response.data)` : l'enveloppe du
   serveur porte `error.code = 'permission_denied'`, core/exceptions.py). */
export function estRefusDeDroit(erreur) {
  return erreur?.response?.status === 403
    || erreur?.error?.code === 'permission_denied'
    || erreur?.response?.data?.error?.code === 'permission_denied'
}

/* L'état d'un écran dont la lecture est refusée (403) : la phrase du droit,
   jamais « vérifiez votre connexion », sans « Réessayer » (réessayer ne
   donnera pas le droit) ni bouton de création. `objet` : « ce lead », « les
   factures »… */
export function RefusDeDroit({ objet, className = '' }) {
  return (
    <EmptyState
      icon={ShieldAlert}
      tone="warning"
      title="Accès refusé"
      description={`Vous n'avez pas le droit d'ouvrir ${objet}. Contactez un administrateur si vous pensez que c'est une erreur.`}
      className={className}
    />
  )
}

export default Forbidden
