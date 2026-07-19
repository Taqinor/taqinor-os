import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import adminopsApi from '../../features/adminops/adminopsApi'

// WIR69 — suivi d'adoption (NTADM16) : enregistre un `EvenementUsage` à chaque
// changement de route pour que `AdoptionPage` affiche des chiffres réels (sans
// cet appel, le tableau de bord d'adoption reste à zéro).
//   - module = 1er segment du chemin (ex. « reporting »), ecran = chemin complet.
//   - débounce simple : une seule trace par pathname (garde `last`), donc les
//     re-rendus sans navigation ne spamment pas l'endpoint.
//   - best-effort : un échec (403, hors-ligne) est silencieux et ne casse
//     jamais le rendu du shell.
// Composant sans rendu (retourne null) : monté une fois dans le Layout.
export default function UsageTracker() {
  const { pathname } = useLocation()
  const last = useRef(null)

  useEffect(() => {
    if (!pathname || pathname === last.current) return
    // Écrans techniques / non authentifiés : rien à tracer.
    if (pathname === '/' || pathname.startsWith('/login')) return
    last.current = pathname
    const seg = pathname.split('/').filter(Boolean)
    const module = seg[0] || 'accueil'
    adminopsApi.trackerUsage(module, pathname).catch(() => {})
  }, [pathname])

  return null
}
