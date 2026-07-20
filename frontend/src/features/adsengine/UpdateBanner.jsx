import { RefreshCw } from 'lucide-react'
import { useRegisterSW } from 'virtual:pwa-register/react'

/* ============================================================================
   FIXPUB4 — Bandeau « version périmée » des écrans-données de la console
   (Dashboard/Cockpit/Campagnes/Journal).
   ----------------------------------------------------------------------------
   RÉUTILISE le mécanisme SW existant (`useRegisterSW`, `virtual:pwa-register/
   react`) — le MÊME hook que `features/pwa/PwaPrompts.jsx` (lecture seule
   pour cette lane, jamais dupliqué en poll de build-id) : dès qu'une nouvelle
   version est PRÊTE (`needRefresh`), affiche un bandeau explicite avec un
   bouton « Recharger » plutôt que de forcer un rechargement silencieux au
   milieu d'une saisie (composition d'action, filtre en cours…).
   ========================================================================== */
export default function UpdateBanner() {
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW()

  if (!needRefresh) return null

  return (
    <p className="card" data-testid="ae-update-banner" role="alert"
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: '0.75rem', padding: '0.6rem 0.9rem', marginBottom: '1rem',
        background: '#fef9c3', color: '#713f12', border: '1px solid #fde68a' }}>
      <span>Nouvelle version disponible.</span>
      <button type="button" className="btn btn-primary" data-testid="ae-update-banner-reload"
        onClick={() => updateServiceWorker(true)}
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
        <RefreshCw size={14} aria-hidden="true" /> Recharger
      </button>
    </p>
  )
}
