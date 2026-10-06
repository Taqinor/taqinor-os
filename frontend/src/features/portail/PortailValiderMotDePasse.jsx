import { KeyRound } from 'lucide-react'
import { Button } from '../../ui'

/* ADOC117 / ADOC119 — pied commun des formulaires de mot de passe portail
   (acceptation d'invitation, changement du mot de passe temporaire) :
   l'erreur du serveur puis le bouton de validation. Un seul endroit. */
export default function PortailValiderMotDePasse({ erreur, busy, children }) {
  return (
    <>
      {erreur ? (
        <p className="text-sm text-destructive" role="alert">{erreur}</p>
      ) : null}
      <Button type="submit" disabled={busy}>
        <KeyRound /> {children}
      </Button>
    </>
  )
}
