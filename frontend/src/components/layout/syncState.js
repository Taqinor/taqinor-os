// NTMOB3 — état affiché du badge de synchro, dérivé PUREMENT des compteurs.
//
// Vit dans son propre module (et non dans `SyncStatusBadge.jsx`) parce que la
// règle eslint `react-refresh/only-export-components` interdit à un fichier de
// composant d'exporter autre chose qu'un composant : un export mixte casse le
// Fast Refresh en dev. Séparé, il reste testable sans React.
import { CloudOff, RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react'

export function syncState({ online, pending, pendingPhotos, failedCount }) {
  const enAttente = (pending || 0) + (pendingPhotos || 0)
  if (failedCount > 0) {
    return {
      key: 'erreur',
      label: 'Erreur de synchro',
      icon: AlertTriangle,
      tone: 'text-destructive',
      count: failedCount,
    }
  }
  if (enAttente > 0) {
    return {
      key: 'attente',
      label: `${enAttente} opération${enAttente > 1 ? 's' : ''} en attente`,
      icon: online ? RefreshCw : CloudOff,
      tone: 'text-warning',
      count: enAttente,
    }
  }
  return {
    key: 'ok',
    label: 'Synchronisé',
    icon: CheckCircle2,
    tone: 'text-success',
    count: 0,
  }
}
