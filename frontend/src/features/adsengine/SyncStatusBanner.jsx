import { useEffect, useState, useCallback } from 'react'
import { WifiOff } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { normalizeSyncStatus, formatAge, formatSyncDateTime } from './syncStatus'

/* ============================================================================
   PUB41 — Bandeau global « Meta ne répond plus… » (fraîcheur + panne).
   ----------------------------------------------------------------------------
   Auto-chargé (léger, GET /adsengine/sync-status/) au montage de chaque écran
   qui le monte. N'affiche RIEN tant que rien n'est stale (jamais un bandeau
   d'alarme sur un tenant simplement JAMAIS connecté — la distinction
   « vide » vs « panne » vit déjà côté backend, ``metrics.sync_status`` :
   un type sans historique n'est jamais marqué `stale`). Dès qu'UN type de
   synchro dépasse son seuil, montre le PIRE (``worst``) : type concerné +
   âge lisible + horodatage du dernier succès.
   ========================================================================== */

export default function SyncStatusBanner() {
  const [status, setStatus] = useState(null)

  const load = useCallback(() => {
    // Endpoint optionnel côté test : les écrans qui mockent une API réduite
    // (sans `syncStatus`) ne doivent jamais planter — garde `?.` (même
    // patron que `dashboardV2Fn` dans DashboardScreen).
    const fn = adsengineApi.syncStatus?.get
    if (!fn) return
    fn()
      .then(r => setStatus(normalizeSyncStatus(r.data)))
      .catch(() => setStatus(null))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  if (!status || !status.stale || !status.worst) return null

  const { worst } = status
  const age = formatAge(worst.age_minutes)
  const when = formatSyncDateTime(worst.last_ok_at)

  return (
    <div className="ae-sync-banner" data-testid="ae-sync-banner" role="alert"
      style={{ display: 'flex', alignItems: 'center', gap: '0.5rem',
        background: '#fef2f2', color: '#991b1b', padding: '0.55rem 0.85rem',
        borderRadius: 8, marginBottom: '1rem' }}>
      <WifiOff size={16} aria-hidden="true" />
      <span>
        Meta ne répond plus ({worst.label}) depuis {age || 'un moment'}
        {when && `, données du ${when}`}.
      </span>
    </div>
  )
}
