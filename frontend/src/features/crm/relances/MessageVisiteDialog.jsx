// VISCAD2 — Aperçu du message « proposer la visite » (patron
// `ToucheMessageDialog.jsx` : aperçu AVANT ouverture de WhatsApp, jamais un
// envoi automatique — décision D5). Distinct de `ToucheMessageDialog` :
// `crmApi.getMessageVisite` renvoie LES DEUX corps rendus côté serveur pour
// CE lead (pas un seul, contrairement au message d'une touche) — donc un vrai
// bascule FR/Darija ici.
//
// CAD111 — deux défauts corrigés :
//   * le lien wa.me était construit CÔTÉ ÉCRAN, en chiffres bruts (« 06… »
//     partait tel quel, sans indicatif) : il vient désormais du SERVEUR
//     (`wa_url_fr` / `wa_url_darija`, numéro normalisé E.164 — contrat
//     `lead_message_visite.json`), comme pour les touches normales ;
//   * l'ouverture ne laissait AUCUNE trace : un POST jumeau
//     (`journaliserMessageVisiteOuvert`) est appelé en best-effort APRÈS
//     `window.open` — journalisé « ouvert », jamais « fait » — et, ouvert
//     depuis une touche (`etapeId`), il est rattaché à CETTE touche (son
//     panneau « Fait » sait alors que le message a été ouvert).
import { useEffect, useState } from 'react'
import { Send, Copy } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import { toastSuccess } from '../../../lib/toast'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Spinner,
} from '../../../ui'

export default function MessageVisiteDialog({
  leadId, cle = 'visite_proposition', open, onOpenChange,
  // CAD111 — la touche depuis laquelle le message est ouvert (facultatif).
  etapeId = null,
}) {
  const [loading, setLoading] = useState(false)
  const [erreur, setErreur] = useState(false)
  const [rendu, setRendu] = useState(null)
  const [langue, setLangue] = useState('fr')

  // Même patron que `ToucheMessageDialog.jsx` — `queueMicrotask` plutôt qu'un
  // `setState` synchrone direct dans l'effet (règle react-hooks v7).
  useEffect(() => {
    let active = true
    if (!open || !leadId) {
      queueMicrotask(() => { if (active) setRendu(null) })
      return () => { active = false }
    }
    queueMicrotask(() => {
      if (!active) return
      setLangue('fr'); setLoading(true); setErreur(false)
    })
    crmApi.getMessageVisite(leadId, cle)
      .then((r) => { if (active) setRendu(r.data) })
      .catch(() => { if (active) setErreur(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [open, leadId, cle])

  const message = langue === 'darija' ? rendu?.corps_darija : rendu?.corps_fr
  // CAD111 — le lien du SERVEUR (E.164), jamais reconstruit ici.
  const wa = (langue === 'darija' ? rendu?.wa_url_darija : rendu?.wa_url_fr) || null

  const copier = async () => {
    if (!message) return
    try {
      await navigator.clipboard.writeText(message)
      toastSuccess('Message copié.')
    } catch {
      // best-effort — le presse-papier peut être indisponible (contexte non
      // sécurisé, permission refusée) : aucune action bloquante à proposer.
    }
  }

  const ouvrirWhatsApp = () => {
    if (!wa) return
    // Le clic humain d'abord (le message est déjà écrit) ; la trace suit, en
    // best-effort : elle ne bloque jamais l'ouverture déjà faite.
    window.open(wa, '_blank', 'noopener')
    if (typeof crmApi.journaliserMessageVisiteOuvert === 'function') {
      const payload = { cle, langue }
      if (etapeId != null) payload.etape = etapeId
      Promise.resolve()
        .then(() => crmApi.journaliserMessageVisiteOuvert(leadId, payload))
        .catch(() => {
          // best-effort — WhatsApp est déjà ouvert ; une trace manquée ne
          // doit jamais gêner la commerciale (la touche reste à faire).
        })
    }
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Message — proposer la visite</DialogTitle>
        </DialogHeader>
        {loading ? (
          <Spinner />
        ) : erreur ? (
          <p className="text-sm text-muted-foreground">Message indisponible pour le moment.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {rendu?.corps_darija && (
              <div className="flex gap-1.5" role="group" aria-label="Langue du message">
                <Button
                  type="button" size="sm" variant={langue === 'fr' ? 'default' : 'outline'}
                  onClick={() => setLangue('fr')}
                >
                  Français
                </Button>
                <Button
                  type="button" size="sm" variant={langue === 'darija' ? 'default' : 'outline'}
                  onClick={() => setLangue('darija')}
                >
                  Darija
                </Button>
              </div>
            )}
            {/* Darija = écriture arabe, de droite à gauche — même garde que
                `ToucheMessageDialog.jsx` (incident du 07/09). */}
            <div
              className={`whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-3 text-sm${langue === 'darija' ? ' text-right' : ''}`}
              dir={langue === 'darija' ? 'rtl' : 'auto'}
              lang={langue === 'darija' ? 'ar' : 'fr'}
            >
              {message || '…'}
            </div>
            {rendu && !wa && (
              <p className="text-sm text-destructive">
                Aucun numéro WhatsApp exploitable : le message ne peut pas être ouvert dans WhatsApp.
              </p>
            )}
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Fermer</Button>
          <Button variant="outline" onClick={copier} disabled={!message}>
            <Copy className="mr-1 size-4" aria-hidden="true" />
            Copier
          </Button>
          <Button onClick={ouvrirWhatsApp} disabled={!wa}>
            <Send className="mr-1 size-4" aria-hidden="true" />
            Ouvrir WhatsApp
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
