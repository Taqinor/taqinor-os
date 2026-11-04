import { useEffect, useRef, useState } from 'react'
import { useSelector } from 'react-redux'
import api from '../api/axios'
import { isPortalUser } from '../features/portail/portalScope'

/* BPQ6 — Dead-man's switch du tri quotidien des problèmes. Le endpoint santé
   expose `dernier_tri_problemes` (ISO 8601, battement de cœur posé par la passe
   `tri=1` de la routine, BPQ4/BPQ8). Un superuser voit un bandeau si le tri n'a
   pas tourné depuis plus de 48 h : sans lui, une routine morte ne se remarque
   jamais.

   UN SEUL appel par chargement (ref), jamais périodique ; réservé aux
   superusers internes (jamais un compte portail : ShellGlobal.portail.test
   interdit tout endpoint interne). Échec réseau, `null` (le tri n'a jamais
   tourné : la routine n'est pas encore armée) ou date illisible : AUCUN
   bandeau, jamais un toast. */

const SEUIL_HEURES = 48

function heuresDepuis(iso, maintenant = Date.now()) {
  const t = Date.parse(iso)
  if (!iso || Number.isNaN(t)) return null
  return Math.floor((maintenant - t) / 3600000)
}

export default function TriProblemesBanner() {
  const isAuthenticated = useSelector((s) => s.auth?.isAuthenticated)
  const superuser = useSelector((s) => (
    s.auth?.user?.is_superuser === true && !isPortalUser(s.auth?.user)
  ))
  const [heures, setHeures] = useState(null)
  const fetchedRef = useRef(false)

  useEffect(() => {
    if (!isAuthenticated || !superuser || fetchedRef.current) return
    fetchedRef.current = true
    api.get('/core/health/ready/', { suppressErrorToast: true })
      .then((res) => {
        const h = heuresDepuis(res.data?.dernier_tri_problemes)
        if (h !== null && h > SEUIL_HEURES) setHeures(h)
      })
      .catch(() => { /* silencieux — jamais bloquer l'ouverture de l'ERP */ })
  }, [isAuthenticated, superuser])

  if (!superuser || heures === null) return null
  return (
    <div
      role="status"
      data-testid="bandeau-tri-problemes"
      className="fixed inset-x-0 top-0 z-50 bg-amber-100 px-4 py-2 text-center text-sm text-amber-900"
    >
      {`Le tri quotidien des problèmes n'a pas tourné depuis ${heures} h.`}
    </div>
  )
}
