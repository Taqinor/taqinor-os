// ODY3 — L'atterrissage : ouvrir l'ERP, c'est voir SES apps.
// ----------------------------------------------------------------------------
// Point d'entrée UNIQUE partagé par les deux endroits qui décident où l'on
// atterrit — `pages/Login.jsx` (après une connexion réussie) et la garde `/`
// du routeur — pour qu'ils ne puissent jamais diverger.
//
// La règle de résolution vit dans `pages/preferences/prefs.js`
// (`resolveLandingPath`, module PUR) ; ce fichier ne fait que lui fournir les
// deux entrées qu'elle ne peut pas aller chercher elle-même : le registre de
// modules (UX1) et la liste « mes apps » (ODY1, registre ∩ modules actifs
// société ∩ rôle/permission).
//
// Ordre appliqué (cf. resolveLandingPath) :
//   1. préférence « module d'atterrissage » VX46 → droit dans l'app ;
//   2. dernier module visité (VX11) ;
//   3. mono-app (une seule app visible) → on entre directement dedans ;
//   4. repli : `/apps`, le Menu d'accueil.
// Un `?next=` (VX65) reste PRIORITAIRE sur tout ceci — il est traité par
// l'appelant, avant même de demander un atterrissage.
import { moduleConfigs } from '../../router/moduleRoutes'
import { buildInstalledApps } from './useInstalledApps'
import { resolveLandingPath, getLastModuleSegment } from '../../pages/preferences/prefs'

/**
 * resolveLandingFromAuth — chemin d'atterrissage pour l'état d'auth donné
 * (`store.getState().auth`). Lu à l'INSTANT de la décision (jamais une valeur
 * capturée au rendu précédent), donc juste après un `setCredentials`.
 *
 * @param {{role?:string, permissions?:string[], modulesDesactives?:string[]}} auth
 * @returns {string} chemin interne
 */
export function resolveLandingFromAuth(auth) {
  const apps = buildInstalledApps(moduleConfigs, {
    disabledModules: auth?.modulesDesactives || [],
    role: auth?.role || 'normal',
    permissions: auth?.permissions || [],
  })
  return resolveLandingPath(moduleConfigs, getLastModuleSegment(), { apps })
}

/**
 * ODY34 — landingApresBasculeSociete : où atterrir APRÈS un changement de
 * société active. On ne peut pas encore connaître les apps de la nouvelle
 * société (ses `modules_desactives` n'arriveront qu'au prochain `/auth/me/`),
 * donc pas d'exception mono-app ici ; et le « dernier module visité » (VX11)
 * est DÉLIBÉRÉMENT ignoré — il appartient à la société qu'on vient de quitter.
 * Reste : la préférence d'atterrissage VX46 si elle est renseignée, sinon le
 * Menu d'accueil.
 */
export function landingApresBasculeSociete() {
  return resolveLandingPath(moduleConfigs, '')
}

/**
 * rechargerVers — navigation par CHARGEMENT COMPLET du document (pas une
 * navigation react-router) : après une bascule de société il faut re-amorcer
 * toute l'application pour que plus AUCUNE donnée de l'ancienne entité ne
 * subsiste à l'écran. Isolé ici pour rester testable (jsdom interdit de
 * remplacer `window.location`).
 */
export function rechargerVers(path) {
  try {
    window.location.assign(path)
  } catch { /* environnement sans navigation (tests, SSR) : sans effet */ }
}

export default resolveLandingFromAuth
