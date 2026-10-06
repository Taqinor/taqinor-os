import { useEffect, useState } from 'react'
import { LifeBuoy } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, EmptyState, Input, Spinner, Textarea,
} from '../../../ui'
import { formatDate, formatDateTime } from '../../../lib/format'

/* ============================================================================
   ADOC136 (D-ADOC-1) — « Mes demandes SAV » du portail client.
   ----------------------------------------------------------------------------
   Contrats `mes_demandes_sav_liste.json` (liste + création) et
   `mes_tickets_fil.json` (fil client-visible du ticket lié). La demande part en
   POST `/mes-demandes-sav/` `{sujet, description, chantier_id}` : société et
   client viennent du compte connecté, jamais du corps ; un compte lecture seule
   reçoit un 403 dont le message est affiché tel quel. Le fil n'existe qu'une
   fois la demande prise en charge (`ticket_id` non nul).
   ========================================================================== */

const TON_STATUT = {
  soumise: 'neutral',
  prise_en_charge: 'info',
  resolue: 'success',
  refusee: 'neutral',
}

function messageErreur(err) {
  const d = err?.response?.data
  return d?.detail
    || (d && typeof d === 'object' && Object.values(d).flat().join(' '))
    || "La demande n'a pas abouti."
}

export default function PortailClientSav() {
  const [rows, setRows] = useState([])
  const [chantiers, setChantiers] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [sujet, setSujet] = useState('')
  const [description, setDescription] = useState('')
  const [chantierId, setChantierId] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [messageCreation, setMessageCreation] = useState(null)
  const [erreurCreation, setErreurCreation] = useState(null)
  const [fils, setFils] = useState({})

  const charger = () => {
    portailApi.demandesSav.liste()
      .then((r) => { setRows(r.data?.results ?? []); setErreur(false) })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    Promise.resolve().then(charger)
    portailApi.chantiers.liste()
      .then((r) => setChantiers(r.data?.results ?? []))
      .catch(() => setChantiers([]))
  }, [])

  const creer = async (e) => {
    e.preventDefault()
    if (!sujet.trim()) return
    setMessageCreation(null)
    setErreurCreation(null)
    setEnvoi(true)
    try {
      const corps = { sujet: sujet.trim(), description: description.trim() }
      if (chantierId) corps.chantier_id = Number(chantierId)
      await portailApi.demandesSav.creer(corps)
      setMessageCreation('Demande envoyée. Nous revenons vers vous rapidement.')
      setSujet('')
      setDescription('')
      setChantierId('')
      charger()
    } catch (err) {
      setErreurCreation(messageErreur(err))
    } finally {
      setEnvoi(false)
    }
  }

  const voirFil = async (demande) => {
    setFils((f) => ({ ...f, [demande.id]: { chargement: true } }))
    try {
      const r = await portailApi.demandesSav.fil(demande.id)
      setFils((f) => ({ ...f, [demande.id]: { entrees: r.data?.results ?? [] } }))
    } catch (err) {
      setFils((f) => ({ ...f, [demande.id]: { erreur: messageErreur(err) } }))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos demandes…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Demandes indisponibles"
        description="Vos demandes n’ont pas pu être chargées. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <LifeBuoy className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes demandes SAV
        </h1>
      </div>

      <Card className="p-4">
        <form onSubmit={creer} className="flex flex-col gap-3">
          <h2 className="font-medium">Nouvelle demande</h2>
          <label className="flex flex-col gap-1.5 text-sm">
            Sujet
            <Input value={sujet} maxLength={200}
                   onChange={(e) => setSujet(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            Description
            <Textarea aria-label="Description" value={description} maxLength={4000}
                      onChange={(e) => setDescription(e.target.value)} />
          </label>
          {chantiers.length > 0 && (
            <label className="flex flex-col gap-1.5 text-sm">
              Chantier concerné
              <select value={chantierId}
                      onChange={(e) => setChantierId(e.target.value)}
                      className="h-9 rounded-md border border-border bg-background px-2">
                <option value="">Aucun chantier précis</option>
                {chantiers.map((c) => (
                  <option key={c.id} value={c.id}>{c.reference}</option>
                ))}
              </select>
            </label>
          )}
          {messageCreation ? (
            <p className="text-sm text-emerald-600" role="status">{messageCreation}</p>
          ) : null}
          {erreurCreation ? (
            <p className="text-sm text-destructive" role="alert">{erreurCreation}</p>
          ) : null}
          <Button type="submit" disabled={envoi || !sujet.trim()}>
            {envoi ? 'Envoi…' : 'Envoyer la demande'}
          </Button>
        </form>
      </Card>

      {rows.length === 0 ? (
        <EmptyState
          title="Aucune demande"
          description="Vous n’avez encore ouvert aucune demande SAV."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((d) => {
            const fil = fils[d.id]
            return (
              <Card key={d.id} className="flex flex-col gap-2 p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{d.sujet}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(d.date_creation)}
                    </p>
                  </div>
                  <Badge tone={TON_STATUT[d.statut] || 'neutral'}>
                    {d.statut_display}
                  </Badge>
                </div>
                {d.description ? (
                  <p className="text-sm text-muted-foreground">{d.description}</p>
                ) : null}
                {d.ticket_id ? (
                  <div className="flex flex-col gap-2">
                    <Button variant="outline" size="sm" className="self-start"
                            onClick={() => voirFil(d)}>
                      Voir le suivi
                    </Button>
                    {fil?.erreur ? (
                      <p className="text-sm text-destructive" role="alert">{fil.erreur}</p>
                    ) : null}
                    {fil?.entrees && fil.entrees.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        Aucun message pour le moment.
                      </p>
                    ) : null}
                    {fil?.entrees && fil.entrees.length > 0 ? (
                      <ul className="flex flex-col gap-2 rounded-md border border-border bg-muted/30 p-3">
                        {fil.entrees.map((m) => (
                          <li key={m.id} className="text-sm">
                            <p>{m.body}</p>
                            <p className="text-xs text-muted-foreground">
                              {m.auteur} — {formatDateTime(m.created_at)}
                            </p>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
              </Card>
            )
          })}
        </ul>
      )}
    </>
  )
}
