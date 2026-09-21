import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { MapPin, PackageCheck, ClipboardList, Boxes, Archive } from 'lucide-react'
import { ModuleDashboard, ModuleHero } from '../../ui/module'
import { Button } from '../../ui'
import installationsApi from '../../api/installationsApi'
import useMagasinResource from './useMagasinResource'
// APX22 — accent unique de la famille inventaire (Stock/Magasin/Logistique).
import { INVENTAIRE_ACCENT } from '../stock/inventaireAccent'

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

  // APX22 — les tuiles deviennent des FILES D'ACTION (« N à traiter » façon
  // Odoo Inventory) et mènent chacune à la liste DÉJÀ filtrée sur le statut
  // qui a servi à les compter. Aucun endpoint nouveau : ce sont les quatre
  // appels déjà faits ci-dessus. Les casiers passent en dernier — c'est un
  // référentiel, pas une file d'action.
  const stats = useMemo(() => [
    {
      label: 'Rangements à traiter',
      value: putaways.data.length,
      hint: 'Put-away en attente',
      icon: PackageCheck,
      to: '/magasin/rangement',
    },
    {
      label: 'Prélèvements à traiter',
      value: pickLists.data.length,
      hint: 'Listes de prélèvement en cours',
      icon: ClipboardList,
      to: '/magasin/prelevements',
    },
    {
      label: 'Colis à traiter',
      value: colisList.data.length,
      hint: 'Colis en préparation',
      icon: Boxes,
      to: '/magasin/colisage',
    },
    {
      label: 'Casiers actifs',
      value: bins.data.length,
      hint: 'Référentiel d’emplacements',
      icon: MapPin,
      to: '/magasin/casiers',
    },
  ], [bins.data, putaways.data, pickLists.data, colisList.data])

  return (
    // APX22 — même conteneur que les autres écrans de la famille inventaire
    // (`ui-root` + padding de StockList) : Magasin était en `page`, Stock en
    // `ui-root` — deux gouttières différentes pour deux écrans voisins.
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      {/* ODY17 — ModuleHero VX15 : identité de cockpit + actions rapides vers
          les 4 écrans Magasin (Casiers/Rangement/Prélèvements/Colisage).
          APX22 — `accent` : token VX8 de la FAMILLE INVENTAIRE (source unique
          `features/stock/inventaireAccent.js`, la clé que Stock portait déjà),
          posé identiquement sur `ModuleDashboard` ci-dessous. */}
      <ModuleHero
        title="Magasin"
        subtitle="Casiers, rangement, prélèvements et colisage d'entrepôt."
        accent={INVENTAIRE_ACCENT}
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
      <ModuleDashboard stats={stats} loading={loading} error={error} accent={INVENTAIRE_ACCENT} />
    </div>
  )
}
