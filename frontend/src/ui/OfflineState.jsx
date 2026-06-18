import { useEffect, useState } from 'react'
import { WifiOff } from 'lucide-react'
import { cn } from '../lib/cn'

/** Hook : statut en ligne / hors ligne du navigateur. */
export function useOnlineStatus() {
  const [online, setOnline] = useState(
    typeof navigator === 'undefined' ? true : navigator.onLine,
  )
  useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
    }
  }, [])
  return online
}

/* G30 — Bannière hors-ligne discrète (au lieu d'une page d'erreur navigateur).
   Ne s'affiche que lorsque la connexion est perdue. */
export function OfflineBanner({ className }) {
  const online = useOnlineStatus()
  if (online) return null
  return (
    <div
      role="status"
      className={cn(
        'flex items-center justify-center gap-2 bg-warning px-3 py-1.5 text-sm font-medium text-warning-foreground',
        className,
      )}
    >
      <WifiOff className="size-4" aria-hidden="true" />
      Hors ligne — les changements seront synchronisés au retour de la connexion.
    </div>
  )
}

export default OfflineBanner
