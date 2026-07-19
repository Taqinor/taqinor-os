import { useEffect, useState } from 'react'
import { Sunrise } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { normalizeTodayQueue } from './todayQueue'

/* ============================================================================
   PUB42 — Icône de nav « Aujourd'hui » + badge de comptage.
   ----------------------------------------------------------------------------
   ``module.config.jsx`` ne prend qu'un ÉLÉMENT JSX comme icône de nav item
   (rendu tel quel par `Sidebar.jsx`, un fichier PARTAGÉ hors du périmètre de
   cette lane) — ce composant s'auto-charge pour porter SON PROPRE badge sans
   toucher au moindre fichier hors ``features/adsengine/`` (contrainte de
   disjonction de lane, comme ``adsengineApi.js``). Masqué à 0/erreur/
   chargement (jamais un « 0 » affiché avant que le compte réel arrive — même
   doctrine que le badge Approbations de la Sidebar, VX86).
   ========================================================================== */

export default function TodayNavIcon() {
  const [count, setCount] = useState(null)

  useEffect(() => {
    let alive = true
    adsengineApi.today.get()
      .then(r => { if (alive) setCount(normalizeTodayQueue(r.data).total) })
      .catch(() => { if (alive) setCount(null) })
    return () => { alive = false }
  }, [])

  return (
    <span style={{ position: 'relative', display: 'inline-flex' }}>
      <Sunrise size={17} strokeWidth={1.75} aria-hidden="true" />
      {count != null && count > 0 && (
        <span
          data-testid="ae-nav-today-badge"
          aria-label={`${count} élément${count > 1 ? 's' : ''} à traiter aujourd'hui`}
          style={{
            position: 'absolute', top: -6, right: -8,
            background: '#dc2626', color: '#fff', borderRadius: 999,
            fontSize: '0.6rem', fontWeight: 700, minWidth: 14, height: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '0 3px', lineHeight: 1,
          }}
        >
          {count > 9 ? '9+' : count}
        </span>
      )}
    </span>
  )
}
