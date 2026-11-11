import { useContext, useSyncExternalStore } from 'react'
import { ReactReduxContext } from 'react-redux'
import { useHasPermission, useIsAdminOrResponsable } from '../../hooks/useHasPermission'

const sansAbonnement = () => () => {}

// ACSV62 / D-ACSV-3 — droit métier d'un geste SAV : le code fin quand le compte
// en porte (rôle fin), sinon le palier responsable (comptes hérités) — la même
// règle que `HasPermissionOrLegacy(code)` côté serveur. ADRG39 : extrait de
// TicketsPage pour être partagé par Tickets, Équipements, Contrats et Supervision.
// Le store est lu par son contexte (et non `useSelector`) : un rendu sans
// <Provider> dont les hooks de droits sont simulés retombe sur ces hooks.
export default function useDroitMetier(code) {
  const store = useContext(ReactReduxContext)?.store
  const fins = useSyncExternalStore(store?.subscribe ?? sansAbonnement,
    () => (store?.getState().auth?.permissions || []).length > 0)
  const parCode = useHasPermission(code)
  const parPalier = useIsAdminOrResponsable()
  return fins ? parCode : parPalier
}
