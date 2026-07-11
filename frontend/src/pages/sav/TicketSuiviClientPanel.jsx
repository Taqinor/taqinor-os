import { useState } from 'react'
import { Timer, Link2, Copy, Check } from 'lucide-react'
import savApi from '../../api/savApi'
import { Badge, Button, Input, toast } from '../../ui'
import { formatDateTime } from '../../lib/format'

// WR11 — suivi SLA & transparence client d'un ticket SAV :
//  - FG81 : enregistrement de la première réponse (horloge SLA, idempotent
//    côté serveur — un second clic renvoie la date existante) ;
//  - FG86 : lien de suivi public tokenisé, copiable (aucun prix ni chatter
//    n'y est exposé — garanti côté serveur).

const fmtDateTime = (iso) => formatDateTime(iso)

export default function TicketSuiviClientPanel({ ticket, onUpdated }) {
  const [busy, setBusy] = useState(false)
  const [lien, setLien] = useState(null)
  const [lienBusy, setLienBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  const premiereReponse = async () => {
    setBusy(true)
    try {
      const r = await savApi.premierReponseTicket(ticket.id)
      toast.success('Première réponse enregistrée')
      onUpdated?.(r.data)
    } catch (err) {
      toast.error(err?.response?.data?.detail
        ?? "Impossible d'enregistrer la première réponse.")
    } finally {
      setBusy(false)
    }
  }

  const genererLien = async () => {
    setLienBusy(true)
    try {
      const r = await savApi.lienClientTicket(ticket.id)
      setLien(r.data?.url ?? null)
    } catch (err) {
      toast.error(err?.response?.data?.detail
        ?? 'Lien de suivi indisponible — réessayez.')
    } finally {
      setLienBusy(false)
    }
  }

  const copier = async () => {
    if (!lien) return
    try {
      await navigator.clipboard.writeText(lien)
      setCopied(true)
      toast.success('Lien copié')
      setTimeout(() => setCopied(false), 2500)
    } catch {
      toast.error('Copie impossible — sélectionnez le lien manuellement.')
    }
  }

  return (
    <div className="flex flex-col gap-3" data-testid="ticket-suivi-client">
      {/* FG81 — première réponse (SLA) */}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Timer className="size-4 text-muted-foreground" aria-hidden="true" />
        <span className="font-medium">Première réponse :</span>
        {ticket.date_premiere_reponse ? (
          <Badge tone="success">
            {fmtDateTime(ticket.date_premiere_reponse)}
          </Badge>
        ) : (
          <Button type="button" size="sm" variant="outline"
                  loading={busy} onClick={premiereReponse}>
            Enregistrer la première réponse
          </Button>
        )}
      </div>

      {/* FG86 — lien de suivi client (public, sans prix) */}
      <div className="flex flex-col gap-1.5">
        <span className="flex items-center gap-2 text-sm font-medium">
          <Link2 className="size-4 text-muted-foreground" aria-hidden="true" />
          Lien de suivi client
        </span>
        <p className="text-xs text-muted-foreground">
          Lien public à partager avec le client — statut du ticket uniquement,
          jamais de prix ni de notes internes.
        </p>
        {lien ? (
          <div className="flex items-center gap-2">
            <Input readOnly value={lien} onFocus={(e) => e.target.select()}
                   aria-label="Lien de suivi client" />
            <Button type="button" size="sm" variant="outline" onClick={copier}>
              {copied ? <Check /> : <Copy />} {copied ? 'Copié' : 'Copier'}
            </Button>
          </div>
        ) : (
          <div>
            <Button type="button" size="sm" variant="outline"
                    loading={lienBusy} onClick={genererLien}>
              <Link2 /> Générer le lien de suivi
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
