import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { KeyRound } from 'lucide-react'
import api from '../../../api/axios'
import { fetchMe } from '../../auth/store/authSlice'
import {
  Button, Card, Form, FormField, Input, toast,
} from '../../../ui'

/* ============================================================================
   AUD139 — Changement OBLIGATOIRE du mot de passe temporaire (portail client).
   ----------------------------------------------------------------------------
   `provisionner_compte_portail_client` crée le compte avec
   `must_change_password=True` et envoie un mot de passe temporaire EN CLAIR
   par email. Le drapeau était inerte des deux côtés : aucune garde serveur, et
   aucun écran de changement forcé côté portail — le mot de passe temporaire
   restait donc valide indéfiniment.

   Le serveur refuse désormais toute route portail avec le code
   `mot_de_passe_a_changer` (403) tant que le mot de passe n'est pas changé ;
   `portalLoader` amène le client ICI, et cet écran est le SEUL de l'espace
   client joignable dans cet état. Il n'y a volontairement aucune sortie
   (« plus tard », « passer ») : ce serait rouvrir le trou côté écran.

   L'endpoint est celui de l'ERP (`/auth/change-password/`, N96) : jamais un
   second chemin d'authentification pour le portail.
   ========================================================================== */

export default function PortailClientMotDePasse() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const doitChanger = useSelector((s) => !!s.auth.user?.must_change_password)
  const [actuel, setActuel] = useState('')
  const [nouveau, setNouveau] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setErreur(null)
    if (nouveau !== confirmation) {
      setErreur('Les deux nouveaux mots de passe ne correspondent pas.')
      return
    }
    setBusy(true)
    try {
      await api.post('/auth/change-password/', {
        current_password: actuel,
        new_password: nouveau,
      })
      // Le drapeau `must_change_password` vient du serveur : on le relit au
      // lieu de le supposer tombé, sinon le loader nous renverrait ici.
      await dispatch(fetchMe())
      toast.success('Mot de passe mis à jour')
      navigate('/portail/client', { replace: true })
    } catch (err) {
      setErreur(
        err?.response?.data?.detail
        || 'Impossible de changer le mot de passe.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-4">
      <h1 className="font-display text-xl font-semibold tracking-tight">
        Choisissez votre mot de passe
      </h1>
      <p className="text-sm text-muted-foreground">
        {doitChanger
          ? 'Votre mot de passe a été transmis par email : il est temporaire. '
            + 'Définissez le vôtre pour accéder à votre espace.'
          : 'Vous pouvez changer votre mot de passe à tout moment.'}
      </p>

      <Card className="p-4">
        <Form onSubmit={submit} className="flex flex-col gap-3">
          <FormField label="Mot de passe temporaire">
            <Input type="password" value={actuel} autoComplete="current-password"
                   onChange={(e) => setActuel(e.target.value)} required />
          </FormField>
          <FormField label="Nouveau mot de passe">
            <Input type="password" value={nouveau} autoComplete="new-password"
                   onChange={(e) => setNouveau(e.target.value)} required />
          </FormField>
          <FormField label="Confirmez le nouveau mot de passe">
            <Input type="password" value={confirmation} autoComplete="new-password"
                   onChange={(e) => setConfirmation(e.target.value)} required />
          </FormField>
          {erreur ? (
            <p className="text-sm text-destructive" role="alert">{erreur}</p>
          ) : null}
          <Button type="submit" disabled={busy}>
            <KeyRound /> Valider mon mot de passe
          </Button>
        </Form>
      </Card>
    </div>
  )
}
