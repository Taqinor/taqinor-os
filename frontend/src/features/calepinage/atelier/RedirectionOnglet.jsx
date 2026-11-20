import { Navigate, useLocation, useParams } from 'react-router-dom'
import { ongletParChemin } from './onglets'

/* ACAL407 — UNE adresse par panneau : `/calepinage/:id/<cle>` (lien envoyé
   hier) devient `/calepinage/:id?onglet=<cle>` par REMPLACEMENT (aucune entrée
   d'historique en trop). La clé est le dernier segment de l'URL, lue par le
   registre `onglets.js` ; une clé inconnue ouvre l'atelier nu. Monté SANS props
   par `buildModuleRoutes`, d'où la lecture de l'URL. */
export default function RedirectionOnglet() {
  const { id } = useParams()
  const { pathname } = useLocation()
  const onglet = ongletParChemin(pathname)
  const cible = onglet ? `/calepinage/${id}?onglet=${onglet.cle}` : `/calepinage/${id}`
  return <Navigate to={cible} replace />
}
