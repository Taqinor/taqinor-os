import { useEffect, useState } from 'react'
import api from '../../api/axios'

/* ============================================================================
   PUB10 — Permissions effectives de l'utilisateur courant (module Publicité).
   ----------------------------------------------------------------------------
   La console montrait Approuver/Rejeter à tout `responsable` alors que le
   back exige `adsengine_approve` — DISTINCTE de `adsengine_manage`/`adsengine_
   view` (règle ENG19) — pour ces actions ; découverte en 403 seulement. Cet
   endpoint léger existe DÉJÀ (`GET /auth/me/`, consommé partout par
   `authSlice.fetchMe` → `state.auth.permissions`) — on le RÉUTILISE ici en
   appel direct plutôt que de dépendre de Redux (le module adsengine n'a
   AUCUNE autre dépendance store ; ses écrans sont 100 % testés par mock API
   local, jamais un <Provider> Redux — dépendre du store casserait tous les
   tests existants pour un gain nul, l'API donne déjà tout ce qu'il faut).

   FAIL-CLOSED tant que le chargement n'est pas terminé (et en cas d'échec
   réseau) : `has()` renvoie `false` — un contrôle protégé reste désactivé/
   masqué plutôt que brièvement actif puis grisé.
   ========================================================================== */
export function useAdsPermissions() {
  const [permissions, setPermissions] = useState(null) // null = chargement

  useEffect(() => {
    let alive = true
    api.get('/auth/me/')
      .then(r => {
        if (!alive) return
        setPermissions(Array.isArray(r.data?.permissions) ? r.data.permissions : [])
      })
      .catch(() => { if (alive) setPermissions([]) })
    return () => { alive = false }
  }, [])

  return {
    loading: permissions === null,
    has: (code) => Array.isArray(permissions) && permissions.includes(code),
  }
}

export default useAdsPermissions
