/* SOL5 — « ce module est-il actif pour la société ? », en UN seul endroit.
   ----------------------------------------------------------------------------
   Le gating par module existait déjà pour les SECTIONS de nav et les ROUTES
   (`router/moduleGating.js` + `moduleLoader`), mais pas pour les surfaces
   INCRUSTÉES dans un écran d'une autre app : une carte KPI posée sur le
   Dashboard générique, un bouton d'une autre app dans le générateur de devis.
   Ces surfaces-là restaient visibles quand le module était désactivé — et
   échouaient à l'appel (404 du `DisabledModuleMiddleware`) ou, module parqué
   par l'édition, sur une route qui n'existe plus du tout.

   Ce hook réutilise la source de vérité EXISTANTE (`modules_desactives` servi
   par `/auth/me/`, ODX6) — aucune règle dupliquée ici. Défaut : actif (liste
   vide ⇒ comportement identique à aujourd'hui). */
import { useSelector } from 'react-redux'

import { isModuleDisabled, selectModulesDesactives } from '../router/moduleGating'

/**
 * Vrai si le module `key` est actif pour la société courante.
 * `key` absente/nulle → true (surface globale, jamais togglable).
 */
export function useModuleActif(key) {
  const desactives = useSelector(selectModulesDesactives)
  return !isModuleDisabled(desactives, key)
}

export default useModuleActif
