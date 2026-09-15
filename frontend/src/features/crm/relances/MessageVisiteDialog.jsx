// VISCAD2 — Aperçu du message « proposer la visite » (patron
// `ToucheMessageDialog.jsx` : aperçu AVANT ouverture de WhatsApp, jamais un
// envoi automatique — décision D5). Distinct de `ToucheMessageDialog` :
// `crmApi.getMessageVisite` renvoie {corps_fr, corps_darija} — LES DEUX
// corps rendus côté serveur pour CE lead (pas un seul, contrairement au
// message d'une touche) — donc un vrai bascule FR/Darija ici, et le lien
// wa.me se construit CÔTÉ ÉCRAN depuis le téléphone déjà porté par la touche
// (`etape.lead_whatsapp`, contrat `relance_etape_v2.json`) puisque l'endpoint
// ne renvoie pas de `wa_url` (contrat fixé — jamais une forme inventée).
import { useEffect, useState } from 'react'
import { Send, Copy } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import { toastSuccess } from '../../../lib/toast'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Spinner,
} from '../../../ui'

// Lien wa.me AVEC message pré-rempli — même nettoyage que `lib/contactLinks.js
// waHref` (chiffres seuls) + `?text=`, motif déjà utilisé localement par
// `DevisActionBoardPage.jsx` (brouillon `wa_drafts`) faute d'un `wa_url`
// serveur ici.
function waHrefAvecTexte(raw, texte) {
  const digits = String(raw ?? '').replace(/\D/g, '')
  if (!digits) return null
  return `https://wa.me/${digits}?text=${encodeURIComponent(texte || '')}`
}

export default function MessageVisiteDialog({
  leadId, telephone, cle = 'visite_proposition', open, onOpenChange,
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
  const wa = waHrefAvecTexte(telephone, message)

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
    window.open(wa, '_blank', 'noopener')
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
            {!wa && (
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
