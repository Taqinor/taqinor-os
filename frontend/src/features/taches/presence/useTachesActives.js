import { useHasPermission } from '../../../hooks/useHasPermission'
import { useModuleActif } from '../../../hooks/useModuleActif'

/* ============================================================================
   F4 revue #15 — « Tâches est-il à ma disposition ? », en UN seul endroit pour les cinq montages posés chez les autres
   écrans (hôte de saisie du Layout, ✓+ du Header, carte du cockpit du Dashboard et de l'accueil iPhone, « + À faire »
   de `/activites`). Deux conditions, jamais une seule : la PERMISSION `taches_voir` ET le MODULE actif pour la société
   (`modules_desactives` de `/auth/me/`, le hook existant `useModuleActif`). Module éteint ou droit absent : l'écran se
   comporte exactement comme avant la fusion 4 — aucun appel `taches/*` (404 du middleware de module), aucune
   interception de « + À faire ».
   ========================================================================== */
export function useTachesActives() {
  const peutVoir = useHasPermission('taches_voir')
  const moduleActif = useModuleActif('taches')
  return peutVoir && moduleActif
}

export default useTachesActives
