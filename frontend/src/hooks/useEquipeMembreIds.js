import { useEffect, useState } from 'react'
import crmApi from '../api/crmApi'

/* VX236 — résout `?equipe=<id>` (posé par `MesEquipesCard`) en l'ensemble des
   IDs de ses membres, pour un filtre CLIENT-SIDE sur une liste déjà chargée
   en mémoire (leads/devis) — AUCUNE agrégation cross-app nouvelle, aucun
   endpoint nouveau : `crmApi.getEquipes()` expose déjà `membres` par équipe
   (`EquipeCommercialeSerializer`). Les équipes actives d'une société sont peu
   nombreuses : charger la liste complète et filtrer côté client reste léger.

   Retour : `null` tant que non résolu (pas de filtre = ne rien exclure) ; un
   `Set` (éventuellement vide si l'équipe n'existe plus) une fois résolu. */
export function useEquipeMembreIds(equipeId) {
  const [membreIds, setMembreIds] = useState(null)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialise le filtre quand `equipeId` est vidé
    if (!equipeId) { setMembreIds(null); return undefined }
    let alive = true
    crmApi.getEquipes()
      .then((r) => {
        if (!alive) return
        const list = r.data?.results ?? r.data ?? []
        const eq = list.find((e) => String(e.id) === String(equipeId))
        setMembreIds(new Set(eq?.membres ?? []))
      })
      .catch(() => { if (alive) setMembreIds(new Set()) })
    return () => { alive = false }
  }, [equipeId])

  return membreIds
}

export default useEquipeMembreIds
