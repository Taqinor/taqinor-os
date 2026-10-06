import { useEffect, useState } from 'react'
import { Users } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, EmptyState, Input, Spinner,
} from '../../../ui'
import { formatDate } from '../../../lib/format'

/* ============================================================================
   ADOC138 (D-ADOC-1) — « Mon équipe » du portail client.
   ----------------------------------------------------------------------------
   Contrat `mon_equipe.json` : `{results, peut_gerer}`. Les boutons « Inviter »
   et « Révoquer » n'apparaissent que si `peut_gerer` est vrai (le serveur reste
   l'autorité : 403 sinon, message affiché tel quel). Le jeton d'invitation
   n'est jamais servi.
   ========================================================================== */

const TON_STATUT = {
  en_attente: 'neutral',
  acceptee: 'success',
  revoquee: 'neutral',
}

function messageErreur(err) {
  const d = err?.response?.data
  return d?.detail
    || (d && typeof d === 'object' && Object.values(d).flat().join(' '))
    || "L'opération n'a pas abouti."
}

export default function PortailClientEquipe() {
  const [rows, setRows] = useState([])
  const [peutGerer, setPeutGerer] = useState(false)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('lecture')
  const [envoi, setEnvoi] = useState(false)
  const [messageErr, setMessageErr] = useState(null)
  const [messageOk, setMessageOk] = useState(null)

  const charger = () => {
    portailApi.equipe.liste()
      .then((r) => {
        setRows(r.data?.results ?? [])
        setPeutGerer(r.data?.peut_gerer === true)
        setErreur(false)
      })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    Promise.resolve().then(charger)
  }, [])

  const inviter = async (e) => {
    e.preventDefault()
    if (!email.trim()) return
    setMessageErr(null)
    setMessageOk(null)
    setEnvoi(true)
    try {
      await portailApi.equipe.inviter({ email: email.trim(), role })
      setMessageOk('Invitation envoyée.')
      setEmail('')
      charger()
    } catch (err) {
      setMessageErr(messageErreur(err))
    } finally {
      setEnvoi(false)
    }
  }

  const revoquer = async (membre) => {
    setMessageErr(null)
    setMessageOk(null)
    try {
      await portailApi.equipe.revoquer(membre.id)
      setMessageOk('Accès révoqué.')
      charger()
    } catch (err) {
      setMessageErr(messageErreur(err))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de votre équipe…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Équipe indisponible"
        description="Votre équipe n’a pas pu être chargée. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <Users className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mon équipe
        </h1>
      </div>

      {peutGerer && (
        <Card className="p-4">
          <form onSubmit={inviter} className="flex flex-col gap-3">
            <h2 className="font-medium">Inviter un collègue</h2>
            <label className="flex flex-col gap-1.5 text-sm">
              E-mail
              <Input type="email" value={email}
                     onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5 text-sm">
              Rôle
              <select value={role} onChange={(e) => setRole(e.target.value)}
                      className="h-9 rounded-md border border-border bg-background px-2">
                <option value="lecture">Lecture seule</option>
                <option value="ecriture">Lecture et écriture</option>
              </select>
            </label>
            <Button type="submit" disabled={envoi || !email.trim()}>
              {envoi ? 'Envoi…' : 'Inviter'}
            </Button>
          </form>
        </Card>
      )}

      {messageOk ? (
        <p className="text-sm text-emerald-600" role="status">{messageOk}</p>
      ) : null}
      {messageErr ? (
        <p className="text-sm text-destructive" role="alert">{messageErr}</p>
      ) : null}

      {rows.length === 0 ? (
        <EmptyState
          title="Aucun membre"
          description="Aucun collègue n’a encore été invité."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((m) => (
            <Card key={m.id} className="flex flex-wrap items-start justify-between gap-3 p-4">
              <div>
                <p className="font-medium">{m.email}</p>
                <p className="text-xs text-muted-foreground">
                  {m.role_display} — invité le {formatDate(m.date_creation)}
                  {m.date_acceptation
                    ? ` — accepté le ${formatDate(m.date_acceptation)}`
                    : ''}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={TON_STATUT[m.statut] || 'neutral'}>
                  {m.statut_display}
                </Badge>
                {peutGerer && m.statut !== 'revoquee' && (
                  <Button variant="outline" size="sm"
                          onClick={() => revoquer(m)}>
                    Révoquer
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </ul>
      )}
    </>
  )
}
