// MRY14/MRY13 — Aperçu du message d'une touche de relance AVANT ouverture de
// WhatsApp (décision D5 : aucun envoi automatique, le clic humain reste seul
// maître). Patron `DevisList.jsx openWhatsApp` (:2049) : `window.open(wa_url)`
// PUIS l'appel serveur qui marque la touche faite — jamais l'inverse (le clic
// humain a déjà eu lieu quoi qu'il arrive côté serveur).
import { useEffect, useState } from 'react'
import { Send, TriangleAlert } from 'lucide-react'
import crmApi from '../../api/crmApi'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Spinner,
} from '../../ui'

export default function ToucheMessageDialog({ etape, open, onOpenChange, onSent }) {
  const [loading, setLoading] = useState(false)
  const [erreur, setErreur] = useState(false)
  const [rendu, setRendu] = useState(null)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    let active = true
    if (!open || !etape) {
      queueMicrotask(() => { if (active) setRendu(null) })
      return () => { active = false }
    }
    queueMicrotask(() => { if (active) { setLoading(true); setErreur(false) } })
    crmApi.getRelanceEtapeMessage(etape.id)
      .then((r) => { if (active) setRendu(r.data) })
      .catch(() => { if (active) setErreur(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [open, etape])

  const ouvrirWhatsApp = async () => {
    if (!rendu?.wa_url) return
    // Le clic humain d'abord (le message est déjà écrit) — le marquage
    // serveur qui suit ne doit jamais bloquer l'ouverture déjà faite.
    window.open(rendu.wa_url, '_blank', 'noopener')
    setSending(true)
    try {
      const r = await crmApi.whatsappRelanceEtape(etape.id)
      onSent?.(etape.id, r?.data)
      onOpenChange(false)
    } catch {
      // best-effort — WhatsApp est déjà ouvert ; un échec du marquage reste
      // silencieux ici, la file se resynchronisera au prochain chargement.
    } finally {
      setSending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>WhatsApp — {etape?.lead_nom || 'Lead'}</DialogTitle>
        </DialogHeader>
        {loading ? (
          <Spinner />
        ) : erreur ? (
          <p className="text-sm text-muted-foreground">Message indisponible pour le moment.</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-3 text-sm">
              {rendu?.message || '…'}
            </div>
            {/* Règle « aucun chiffre inventé » — un placeholder sans valeur
                réelle a fait OMETTRE la phrase côté serveur, jamais un blanc
                à sa place : l'écran nomme juste ce qui manquait. */}
            {rendu?.placeholders_manquants?.length > 0 && (
              <p className="flex items-start gap-1.5 text-xs text-warning">
                <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                Informations manquantes ({rendu.placeholders_manquants.join(', ')}) — la
                phrase correspondante a été omise du message.
              </p>
            )}
            {!rendu?.wa_url && (
              <p className="text-sm text-destructive">
                Aucun numéro exploitable : le message ne peut pas être ouvert dans WhatsApp.
              </p>
            )}
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={sending}>
            Fermer
          </Button>
          <Button onClick={ouvrirWhatsApp} disabled={!rendu?.wa_url || sending} loading={sending}>
            <Send className="mr-1 size-4" aria-hidden="true" />
            Ouvrir WhatsApp
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
