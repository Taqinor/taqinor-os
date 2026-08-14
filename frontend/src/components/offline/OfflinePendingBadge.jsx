// NTMOB24 — badge hors-ligne PAR ENREGISTREMENT (« Modifications non
// synchronisées : n »), posé directement sur la ligne concernée d'une liste.
//
// Le bandeau global (NTMOB3) dit COMBIEN d'opérations attendent ; ce badge dit
// LESQUELLES. Composant « bête » : il ne lit aucune file lui-même — l'écran
// calcule la carte des compteurs UNE fois avec `useOfflinePending` et passe
// simplement `n`. Aucun nouveau modèle, aucune nouvelle file, aucun 2ᵉ
// compteur (décision VX105).
import { CloudOff } from 'lucide-react'

export default function OfflinePendingBadge({ n = 0, className = '' }) {
  if (!n) return null
  const libelle = `Modifications non synchronisées : ${n}`
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[11px] font-semibold text-amber-700 dark:text-amber-400 ${className}`}
      title={libelle}
      aria-label={libelle}
      data-testid="offline-pending-badge"
      data-offline-pending={n}
    >
      <CloudOff size={12} aria-hidden="true" />
      <span className="tabular-nums">{n}</span>
    </span>
  )
}
