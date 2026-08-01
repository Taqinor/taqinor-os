import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { MapPin, PackageCheck, ClipboardList, Boxes, Archive } from 'lucide-react'
import { ModuleDashboard, ModuleHero } from '../../ui/module'
import { Button } from '../../ui'
import installationsApi from '../../api/installationsApi'
import useMagasinResource from './useMagasinResource'

/* ============================================================================
   XSTK1 — Cockpit Magasin (`/magasin`).
   ----------------------------------------------------------------------------
   Bandeau de KPI de synthèse (casiers, put-away à faire, prélèvements en
   cours, colis en préparation) avec liens vers chaque écran. Purement
   informatif : aucune action ici, aucun coût/prix d'achat.
   ODY17 — identité de cockpit VX15 (ModuleHero) + raccourcis vers les écrans
   Magasin, en plus du bandeau KPI déjà existant (kpiSlot, inchangé).
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
      {/* ODY17 — ModuleHero VX15 : identité de cockpit + actions rapides vers
          les 4 écrans Magasin (Casiers/Rangement/Prélèvements/Colisage).
          `accent` : token VX8 du module (`nav.accent: 'success'` du
          module.config — terrain/logistique), plus le même token que
          `ModuleDashboard` ci-dessous (jamais une couleur inventée). */}
      <ModuleHero
        title="Magasin"
        subtitle="Casiers, rangement, prélèvements et colisage d'entrepôt."
        accent="var(--module-accent-success)"
        actions={(
          <>
            <Button asChild variant="outline" size="sm">
              <Link to="/magasin/casiers"><MapPin /> Casiers</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to="/magasin/rangement"><PackageCheck /> Rangement</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to="/magasin/prelevements"><ClipboardList /> Prélèvements</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to="/magasin/entrepot"><Archive /> Entrepôt</Link>
            </Button>
          </>
        )}
      />
      <ModuleDashboard stats={stats} loading={loading} error={error} accent="var(--module-accent-success)" />
    </div>
  )
}
