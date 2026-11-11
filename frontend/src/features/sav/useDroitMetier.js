import { useContext, useSyncExternalStore } from 'react'
import { ReactReduxContext } from 'react-redux'

const sansAbonnement = () => () => {}
const PALIERS_ECRITURE = ['responsable', 'admin']

// ACSV62 / D-ACSV-3 — droit métier d'un geste : le code fin quand le compte en
// porte (rôle fin), sinon le palier responsable/admin (comptes hérités) — la
// règle exacte de `HasPermissionOrLegacy(code)` côté serveur (même lecture de
// `state.auth` que `useHasPermission` / `useHasRole`). ADRG39 : extrait de
// TicketsPage, partagé par Tickets, Équipements, Contrats, Supervision, Problèmes
// et la fiche/liste des leads (ADRG20).
// Le store est lu par son CONTEXTE (jamais `useSelector`, qui lève hors
// <Provider>) : un rendu isolé sans store (tests de composant) garde les gestes
// visibles, comme avant ce crochet — le serveur reste le seul juge.
export default function useDroitMetier(code) {
  const store = useContext(ReactReduxContext)?.store
  const auth = useSyncExternalStore(store?.subscribe ?? sansAbonnement,
    () => (store ? store.getState().auth ?? null : undefined))
  if (auth === undefined) return true
  const permissions = auth?.permissions || []
  return permissions.length > 0
    ? permissions.includes(code)
    : PALIERS_ECRITURE.includes(auth?.role)
}
