import { Check, X, ShieldQuestion, CheckCircle2 } from 'lucide-react'
import { Button } from '../../ui'

/* XKB31 — Carte de confirmation d'une commande / dans le composer, MÊME
   principe que la carte proposition du Copilote (S8/S19,
   `frontend/src/features/ia/CopilotPanel.jsx`) : l'exécution passe TOUJOURS
   par confirm_token, jamais d'exécution automatique. Rendue au-dessus du
   composer tant que la commande est en attente de confirmation/résultat. */
export default function SlashProposalCard({ proposal, confirming, error, onConfirm, onCancel }) {
  if (!proposal) return null

  if (proposal.kind === 'result') {
    return (
      <div
        data-testid="slash-result-card"
        className="chat-slash-card chat-slash-card-result"
        role="status"
      >
        <p className="chat-slash-card-title">
          <CheckCircle2 size={14} aria-hidden="true" /> Action effectuée
        </p>
        {proposal.text && <p className="chat-slash-card-body">{proposal.text}</p>}
      </div>
    )
  }

  return (
    <div data-testid="slash-proposal-card" className="chat-slash-card" role="alert">
      <p className="chat-slash-card-title">
        <ShieldQuestion size={14} aria-hidden="true" /> Confirmation requise
      </p>
      {proposal.human_preview && (
        <p className="chat-slash-card-body">{proposal.human_preview}</p>
      )}
      {!proposal.confirm_token && (
        <p className="chat-slash-card-body chat-slash-card-muted">
          Confirmation indisponible pour le moment.
        </p>
      )}
      <div className="chat-slash-card-actions">
        <Button
          size="sm"
          disabled={!proposal.confirm_token || confirming}
          loading={confirming}
          onClick={onConfirm}
        >
          <Check size={14} aria-hidden="true" /> Confirmer
        </Button>
        <Button size="sm" variant="outline" disabled={confirming} onClick={onCancel}>
          <X size={14} aria-hidden="true" /> Annuler
        </Button>
      </div>
      {error && <p className="chat-slash-card-error">{error}</p>}
    </div>
  )
}
