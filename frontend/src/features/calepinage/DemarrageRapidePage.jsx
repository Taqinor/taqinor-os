import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import { useHasPermission } from '../../hooks/useHasPermission'
import DemarrageRapide from './reglages/DemarrageRapide'

/* Coque — la page « Démarrage rapide » des réglages (`/calepinage/reglages/demarrage-rapide`,
   maquette DemarrageRapide) : le fil d'Ariane des réglages et le composant EXISTANT
   `reglages/DemarrageRapide` (lane L6), nourri par la MÊME lecture que la page des réglages
   (`GET parametres/` → sections `simulation` / `electrique_societe`). */
export default function DemarrageRapidePage() {
  const peutApprouver = useHasPermission('calepinage_approuver')
  const [servis, setServis] = useState(null)
  const [relecture, setRelecture] = useState(0)
  useEffect(() => {
    let annule = false
    Promise.resolve(calepinageApi.parametres.get())
      .then((res) => {
        const data = res?.data ?? {}
        if (!annule) setServis({ simulation: data.simulation, electrique_societe: data.electrique_societe })
      })
      .catch(() => { if (!annule) setServis(null) })
    return () => { annule = true }
  }, [relecture])
  return (
    <div className="page">
      <nav aria-label="Fil d’Ariane" className="text-sm text-muted-foreground">
        <Link to="/calepinage/reglages" className="underline underline-offset-2">Réglages simulation</Link>
        {' › '}
        <span className="text-foreground">Démarrage rapide</span>
      </nav>
      <DemarrageRapide reglages={servis} peutApprouver={peutApprouver}
        onChange={() => setRelecture((n) => n + 1)} />
    </div>
  )
}
