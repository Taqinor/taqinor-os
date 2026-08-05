import { useEffect, useState } from 'react'

/* ============================================================================
   NTADM26 — Entité ACTIVE (bascule de l'en-tête).

   Filtre de CONFORT, jamais une frontière de sécurité : choisir une entité
   n'ouvre ni ne ferme aucun droit. Il pose simplement le paramètre `?entite=`
   de NTADM2 sur les listes affichées ; le serveur reste seul juge de ce que
   l'utilisateur peut voir (périmètre de rôle NTADM3).

   Persisté dans `localStorage` pour survivre à un rafraîchissement. Le
   changement est diffusé par un événement window : la bascule n'a donc aucune
   dépendance au store Redux, et un autre onglet suit via `storage`.
   ========================================================================== */

export const CLE_ENTITE_ACTIVE = 'taqinor.entite_active'
export const EVENEMENT_ENTITE_ACTIVE = 'taqinor:entite-active'

export function lireEntiteActive() {
  try {
    const brut = window.localStorage.getItem(CLE_ENTITE_ACTIVE)
    if (!brut) return null
    const id = Number(brut)
    return Number.isFinite(id) && id > 0 ? id : null
  } catch {
    // Stockage indisponible (navigation privée stricte) : « toutes entités ».
    return null
  }
}

export function poserEntiteActive(id) {
  const valeur = Number(id)
  const retenu = Number.isFinite(valeur) && valeur > 0 ? valeur : null
  try {
    if (retenu) window.localStorage.setItem(CLE_ENTITE_ACTIVE, String(retenu))
    else window.localStorage.removeItem(CLE_ENTITE_ACTIVE)
  } catch {
    // Ignoré volontairement : la bascule reste effective pour cette vue.
  }
  window.dispatchEvent(
    new CustomEvent(EVENEMENT_ENTITE_ACTIVE, { detail: { id: retenu } }))
  return retenu
}

export function useEntiteActive() {
  const [id, setId] = useState(lireEntiteActive)
  useEffect(() => {
    const relire = () => setId(lireEntiteActive())
    window.addEventListener(EVENEMENT_ENTITE_ACTIVE, relire)
    // Un autre onglet a basculé : on suit.
    window.addEventListener('storage', relire)
    return () => {
      window.removeEventListener(EVENEMENT_ENTITE_ACTIVE, relire)
      window.removeEventListener('storage', relire)
    }
  }, [])
  return id
}
