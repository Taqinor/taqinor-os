import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { FileSignature } from 'lucide-react'
import { contratsPortailApi } from '../../api/contratsApi'
import {
  Card, Badge, Button, Textarea, Label, EmptyState, Spinner, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../ui'
import { formatMAD, formatDate } from '../../lib/format'
import { StatutContrat } from './status'

/* ============================================================================
   XCTR14 — Portail client PUBLIC « Mes contrats & abonnements ».
   ----------------------------------------------------------------------------
   Sans login : le client est identifié par le token du portail self-service
   (compta.ComptePortailClient). Lecture seule + deux demandes 1-clic
   (renouvellement / résiliation) qui NE changent JAMAIS le statut du contrat
   (elles créent une activité côté ERP). Aucune donnée interne exposée.
   ========================================================================== */

export default function PortailContratsPage() {
  const { token } = useParams()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [invalid, setInvalid] = useState(false)
  const [demande, setDemande] = useState(null) // { contrat, type }

  const load = () => {
    setLoading(true)
    contratsPortailApi.mesContrats(token)
      .then((r) => { setRows(r.data?.results ?? []); setInvalid(false) })
      .catch(() => setInvalid(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refetch only when token changes
  }, [token])

  if (loading) {
    return (
      <div className="mx-auto flex max-w-3xl items-center gap-2 p-8 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos contrats…
      </div>
    )
  }

  if (invalid) {
    return (
      <div className="mx-auto max-w-3xl p-8">
        <EmptyState
          title="Lien invalide"
          description="Ce lien de portail est invalide ou a expiré."
        />
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <div className="flex items-center gap-2">
        <FileSignature className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">Mes contrats &amp; abonnements</h1>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="Aucun contrat" description="Vous n’avez aucun contrat actif pour le moment." />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((c) => (
            <Card key={c.id} className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{c.objet || c.reference}</p>
                  <p className="text-xs text-muted-foreground">{c.reference}</p>
                </div>
                <StatutContrat status={c.statut} label={c.statut_display} />
              </div>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
                <div><dt className="text-xs text-muted-foreground">Début</dt><dd>{c.date_debut ? formatDate(c.date_debut) : '—'}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Fin</dt><dd>{c.date_fin ? formatDate(c.date_fin) : '—'}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Montant</dt><dd>{c.montant != null ? formatMAD(c.montant) : '—'}</dd></div>
                <div>
                  <dt className="text-xs text-muted-foreground">Prochaine échéance</dt>
                  <dd>{c.prochaine_echeance ? formatDate(c.prochaine_echeance) : '—'}</dd>
                </div>
              </dl>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => setDemande({ contrat: c, type: 'renouvellement' })}>
                  Demander le renouvellement
                </Button>
                <Button size="sm" variant="outline" onClick={() => setDemande({ contrat: c, type: 'resiliation' })}>
                  Demander la résiliation
                </Button>
              </div>
            </Card>
          ))}
        </ul>
      )}

      {demande && (
        <DemandeDialog
          token={token}
          contrat={demande.contrat}
          type={demande.type}
          onClose={() => setDemande(null)}
        />
      )}
    </div>
  )
}

function DemandeDialog({ token, contrat, type, onClose }) {
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)
  const titre = type === 'renouvellement' ? 'Demande de renouvellement' : 'Demande de résiliation'

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErr(null)
    try {
      await contratsPortailApi.demander(token, contrat.id, { type, message: message.trim() })
      toast.success('Votre demande a bien été transmise.')
      onClose()
    } catch (e2) {
      setErr(e2?.response?.data?.detail || 'Envoi impossible.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>{titre}</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <p className="text-sm text-muted-foreground">
            Contrat : <Badge tone="neutral">{contrat.reference}</Badge>. Notre équipe vous recontactera.
          </p>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dem-msg">Message (optionnel)</Label>
            <Textarea id="dem-msg" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Envoi…' : 'Envoyer la demande'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
