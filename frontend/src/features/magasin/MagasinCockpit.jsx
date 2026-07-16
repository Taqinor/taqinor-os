import { useMemo } from 'react'
import { MapPin, PackageCheck, ClipboardList, Boxes } from 'lucide-react'
import { ModuleDashboard } from '../../ui/module'
import installationsApi from '../../api/installationsApi'
import useMagasinResource from './useMagasinResource'

/* ============================================================================
   XSTK1 — Cockpit Magasin (`/magasin`).
   ----------------------------------------------------------------------------
   Bandeau de KPI de synthèse (casiers, put-away à faire, prélèvements en
   cours, colis en préparation) avec liens vers chaque écran. Purement
   informatif : aucune action ici, aucun coût/prix d'achat.
   ========================================================================== */

export default function MagasinCockpit() {
  const bins = useMagasinResource(installationsApi.getBinLocations, { archived: '0' })
  const putaways = useMagasinResource(installationsApi.getPutAways, { statut: 'a_ranger' })
  const pickLists = useMagasinResource(installationsApi.getPickLists, { statut: 'en_cours' })
  const colisList = useMagasinResource(installationsApi.getColisList, { statut: 'preparation' })

  const loading = bins.loading || putaways.loading || pickLists.loading || colisList.loading
  const error = bins.error || putaways.error || pickLists.error || colisList.error

  const stats = useMemo(() => [
    {
      label: 'Casiers actifs',
      value: bins.data.length,
      icon: MapPin,
      to: '/magasin/casiers',
    },
    {
      label: 'À ranger',
      value: putaways.data.length,
      hint: 'Put-away en attente',
      icon: PackageCheck,
      to: '/magasin/rangement',
    },
    {
      label: 'Prélèvements en cours',
      value: pickLists.data.length,
      icon: ClipboardList,
      to: '/magasin/prelevements',
    },
    {
      label: 'Colis en préparation',
      value: colisList.data.length,
      icon: Boxes,
      to: '/magasin/colisage',
    },
  ], [bins.data, putaways.data, pickLists.data, colisList.data])

  return (
    <div className="page flex flex-col gap-4">
      <h2 className="font-display text-xl font-semibold tracking-tight">Magasin</h2>
      {/* VX15 — `accent` : pastille de couleur de module (token sémantique
          existant en attendant le registre VX8 ; jamais une couleur inventée). */}
      <ModuleDashboard stats={stats} loading={loading} error={error} accent="var(--info)" />
    </div>
  )
}
