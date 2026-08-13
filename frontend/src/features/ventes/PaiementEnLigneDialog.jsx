import { useState } from 'react'
import { CreditCard, ExternalLink, RefreshCw } from 'lucide-react'
import api from '../../api/axios'
import { formatMAD } from '../../lib/format'
import {
  Badge, Button, Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, Input, Label,
} from '../../ui'

/* ============================================================================
   PACT121 — Paiement EN LIGNE d'une facture (core.PaymentTransaction, FG370).
   ----------------------------------------------------------------------------
   À NE PAS CONFONDRE avec « Encaisser » : celui-ci enregistre un paiement DÉJÀ
   REÇU (ventes.Paiement) ; ici on DEMANDE un paiement carte au client via un
   prestataire (CMI / Payzone). `core.PaymentTransaction` savait initier une
   transaction et rafraîchir son statut — aucun écran ne l'appelait.

   Sans compte marchand configuré, la création reste PROPRE et sans effet : le
   connecteur n'émet AUCUN appel réseau, la transaction reste « initiée » et le
   serveur renvoie son motif dans `detail`. L'écran affiche alors « prestataire
   non configuré » — JAMAIS une erreur brute.

   LIMITE CONNUE, à lever AVANT d'activer un prestataire (liée à QXG2) — ce
   commentaire disait l'inverse et c'était FAUX. Le lien générique
   (content_type/object_id) n'est posé par PERSONNE sur ce chemin : le
   navigateur ne peut pas le deviner (aucune API n'expose les ContentType), et
   `PaymentTransactionViewSet.perform_create` (core/views.py) fait
   `serializer.save(company=...)` sans jamais appeler `core.payment.creer_transaction`,
   la seule fonction qui pose ce lien. Conséquence : `ventes/receivers.py`
   `_materialize_paiement_on_payment_captured` teste `isinstance(target, Facture)`
   et sort toujours — un paiement RÉELLEMENT capturé ne matérialiserait aucun
   `Paiement` et ne bougerait pas le `montant_du` de la facture. Aujourd'hui sans
   effet (aucun prestataire configuré, l'écran répond « non configuré »).
   La corriger demande un ARBITRAGE : `core` est une couche de fondation sous
   contrat import-linter et ne peut pas résoudre une `Facture` ; il faut soit
   exposer le ContentType, soit passer par un point d'entrée côté `ventes`.
   `company` est toujours imposée par le serveur, jamais lue du corps.

   Endpoints (core/views.py PaymentTransactionViewSet) :
     POST /core/paiements-en-ligne/                  initie la transaction
     POST /core/paiements-en-ligne/{id}/rafraichir/  synchronise le statut
   ========================================================================== */

const LIBELLE_STATUT = {
  initie: 'Initiée',
  en_attente: 'En attente de paiement',
  paye: 'Payée',
  echec: 'Échec',
  annule: 'Annulée',
  rembourse: 'Remboursée',
}
const TONE_STATUT = {
  paye: 'success', en_attente: 'info', echec: 'danger', annule: 'danger',
}

// Motif LISIBLE d'une transaction sans lien de paiement. Le serveur range son
// explication dans `detail.detail` ; on ne montre jamais un objet brut.
function motifIndisponible(transaction) {
  const brut = transaction?.detail?.detail
  if (typeof brut === 'string' && brut.trim()) return brut
  return 'Prestataire de paiement non configuré : aucun lien n\'a été généré.'
}

export default function PaiementEnLigneDialog({ facture, open, onOpenChange }) {
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [transaction, setTransaction] = useState(null)
  const [message, setMessage] = useState(null)

  // Repart de zéro à chaque ouverture (ajustement pendant le rendu, pas dans
  // un effet — même motif que NoteDebitDialog).
  const [wasOpen, setWasOpen] = useState(open)
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) { setTransaction(null); setMessage(null); setEmail('') }
  }

  const creer = async () => {
    if (!facture) return
    setBusy(true)
    setMessage(null)
    try {
      const res = await api.post('/core/paiements-en-ligne/', {
        montant: String(facture.montant_du ?? facture.total_ttc ?? ''),
        devise: 'MAD',
        payeur_email: email,
      })
      const t = res.data
      setTransaction(t)
      if (!t?.redirect_url) setMessage(motifIndisponible(t))
    } catch {
      // Jamais l'erreur brute du serveur : un motif compréhensible.
      setMessage('Le paiement en ligne n\'a pas pu être initié. '
        + 'Vérifiez la configuration du prestataire de paiement.')
    } finally { setBusy(false) }
  }

  const rafraichir = async () => {
    if (!transaction?.id) return
    setBusy(true)
    try {
      const res = await api.post(
        `/core/paiements-en-ligne/${transaction.id}/rafraichir/`)
      const t = res.data
      setTransaction(t)
      setMessage(t?.redirect_url ? null : motifIndisponible(t))
    } catch {
      setMessage('Le statut du paiement n\'a pas pu être actualisé.')
    } finally { setBusy(false) }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Payer en ligne — {facture?.reference}
          </DialogTitle>
          <DialogDescription>
            Demande de paiement carte au client (CMI / Payzone). Différent
            d&apos;« Encaisser », qui enregistre un règlement déjà reçu.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <p className="m-0 text-sm">
            <span className="text-muted-foreground">Montant à payer : </span>
            <strong className="tabular-nums">
              {formatMAD(facture?.montant_du ?? facture?.total_ttc)}
            </strong>
          </p>
          <div className="grid gap-1.5">
            <Label htmlFor="paiement-email">Email du payeur (optionnel)</Label>
            <Input id="paiement-email" type="email" value={email}
                   onChange={(e) => setEmail(e.target.value)} />
          </div>

          {transaction && (
            <div className="grid gap-1.5 rounded-lg border border-border p-3 text-sm">
              <span>
                <span className="text-muted-foreground">Transaction : </span>
                <Badge tone={TONE_STATUT[transaction.statut] || 'neutral'}>
                  {LIBELLE_STATUT[transaction.statut] || transaction.statut}
                </Badge>
              </span>
              {transaction.redirect_url && (
                <a className="inline-flex items-center gap-1 break-all underline"
                   href={transaction.redirect_url}
                   target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="size-3.5" aria-hidden="true" />
                  Lien de paiement
                </a>
              )}
            </div>
          )}

          {message && (
            <p className="m-0 text-sm text-muted-foreground" role="status">
              {message}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange?.(false)}>
            Fermer
          </Button>
          {transaction && (
            <Button variant="outline" loading={busy} onClick={rafraichir}>
              <RefreshCw /> Actualiser le statut
            </Button>
          )}
          {!transaction && (
            <Button loading={busy} onClick={creer}>
              <CreditCard /> Créer la demande de paiement
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
