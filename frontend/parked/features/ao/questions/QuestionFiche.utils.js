/* ============================================================================
   AOF107 (1/3) — logique PURE de `QuestionFiche.jsx`, extraite dans ce fichier
   voisin : `react-refresh/only-export-components` (HMR de dev) exige qu'un
   fichier de COMPOSANT n'exporte que des composants. `deltaReel` n'en est pas
   un — `QuestionFiche.jsx` l'importe pour son propre usage. Comportement
   inchangé (déplacement mécanique, correction structurelle ESLint).
   ========================================================================== */

/** Delta RÉEL = soustraction d'affichage entre deux comptes serveur. */
export function deltaReel(question) {
  const { compte_avant_modules: avant, compte_apres_modules: apres } = question || {}
  if (!Number.isFinite(avant) || !Number.isFinite(apres)) return null
  return apres - avant
}
