import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import calepinageApi from '../../api/calepinageApi'
import { useHasPermission } from '../../hooks/useHasPermission'
import DemarrageRapide from './reglages/DemarrageRapide'

/* Coque — la page « Démarrage rapide » des réglages (`/calepinage/reglages/demarrage-rapide`,
   maquette DemarrageRapide) : le fil d'Ariane des réglages et le composant EXISTANT
   `reglages/DemarrageRapide` (lane L6), nourri par la MÊME lecture que la page des réglages
   (`GET parametres/` → sections `simulation` / `electrique_societe`).
   ACAL1826 — maquette v2 : PLEIN ÉCRAN (route `plein`), papier, fil d'Ariane dans un bandeau flottant
   (16,16 · 56 px · rayon 16) ; le défilant (`main`) garde 16 px de marge pour que les ombres des pièces se lisent. */
const LIEN = 'flex h-11 items-center rounded-[10px] px-1.5 text-[color:var(--cal-texte-2)] no-underline'

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
    <div className="cal-reglages fixed inset-0 flex flex-col gap-4 bg-[var(--cal-papier)] pt-4 text-[color:var(--cal-texte-1)]"
      data-testid="cal-demarrage-rapide">
      <nav aria-label="Fil d’Ariane"
        className="mx-4 flex h-14 flex-none items-center gap-2.5 rounded-[var(--cal-rayon-piece)] bg-[var(--cal-surface)] pl-2 pr-4 text-sm shadow-[var(--cal-ombre-posee)]">
        <Link to="/calepinage/reglages" className={`${LIEN} gap-1.5 pl-1.5 pr-2.5`}>
          <ChevronLeft size={18} aria-hidden="true" />Réglages
        </Link>
        <span aria-hidden="true" className="text-[color:var(--cal-texte-3)]">/</span>
        <Link to="/calepinage" className={LIEN}>Calepinage</Link>
        <span aria-hidden="true" className="text-[color:var(--cal-texte-3)]">/</span>
        <span className="px-1.5 font-semibold" aria-current="page">Démarrage rapide</span>
      </nav>
      <main className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
        <DemarrageRapide reglages={servis} peutApprouver={peutApprouver}
          onChange={() => setRelecture((n) => n + 1)} />
      </main>
    </div>
  )
}
