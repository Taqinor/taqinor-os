import { useState } from 'react'
import PortailValiderMotDePasse from './PortailValiderMotDePasse'
import { Link, useSearchParams } from 'react-router-dom'
import portailApi from '../../api/portailApi'
import { Button, Card, Form, FormField, Input } from '../../ui'

/* ============================================================================
   ADOC117 — Page PUBLIQUE d'acceptation d'une invitation portail
   (`/portail/invitation/accepter?token=…`, lien de l'e-mail ADOC116).
   ----------------------------------------------------------------------------
   Hors layout et sans session : l'invité n'a pas encore de compte. Il choisit
   son mot de passe ; le serveur (contrat `invitation_accepter.json`) répond
     - 200 {detail}                 → compte créé, renvoi vers /login ;
     - 400 {mot_de_passe:[…]}       → refus de la politique, affiché SOUS le
                                      champ (rien n'est créé) ;
     - 400 {detail}                 → jeton inconnu/expiré/utilisé/révoqué.
   Le jeton part dans le corps, jamais l'e-mail ni le rôle (lus côté serveur).
   ========================================================================== */

export default function PortailInvitationAccepter() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [mdp, setMdp] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [refus, setRefus] = useState([])
  const [erreur, setErreur] = useState(null)
  const [succes, setSucces] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setRefus([])
    setErreur(null)
    if (mdp !== confirmation) {
      setErreur('Les deux mots de passe ne correspondent pas.')
      return
    }
    setBusy(true)
    try {
      const r = await portailApi.invitation.accepter({
        token, mot_de_passe: mdp,
      })
      setSucces(r?.data?.detail
        || 'Compte créé — vous pouvez maintenant vous connecter.')
    } catch (err) {
      const data = err?.response?.data
      const messages = data?.mot_de_passe
      if (messages) {
        setRefus(Array.isArray(messages) ? messages : [String(messages)])
      } else {
        setErreur(data?.detail || "L'invitation n'a pas pu être acceptée.")
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center gap-4 p-4">
      <h1 className="font-display text-xl font-semibold tracking-tight">
        Rejoindre l’espace client
      </h1>

      {!token ? (
        <p className="text-sm text-destructive" role="alert">
          Ce lien d’invitation est incomplet. Ouvrez-le depuis l’e-mail reçu.
        </p>
      ) : succes ? (
        <Card className="flex flex-col gap-3 p-4">
          <p className="text-sm" role="status">{succes}</p>
          <Button asChild>
            <Link to="/login">Se connecter</Link>
          </Button>
        </Card>
      ) : (
        <Card className="p-4">
          <Form onSubmit={submit} className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">
              Choisissez le mot de passe de votre compte.
            </p>
            <FormField label="Mot de passe">
              <Input type="password" aria-label="Mot de passe" value={mdp} autoComplete="new-password"
                     onChange={(e) => setMdp(e.target.value)} required />
            </FormField>
            {refus.length > 0 ? (
              <ul className="text-sm text-destructive" role="alert">
                {refus.map((m) => <li key={m}>{m}</li>)}
              </ul>
            ) : null}
            <FormField label="Confirmez le mot de passe">
              <Input type="password" aria-label="Confirmez le mot de passe" value={confirmation}
                     autoComplete="new-password"
                     onChange={(e) => setConfirmation(e.target.value)} required />
            </FormField>
            <PortailValiderMotDePasse erreur={erreur} busy={busy}>Créer mon compte</PortailValiderMotDePasse>
          </Form>
        </Card>
      )}
    </div>
  )
}
