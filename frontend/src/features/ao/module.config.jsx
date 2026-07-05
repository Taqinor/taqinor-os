/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */

/* ============================================================================
   APPELS D'OFFRES (ODX11) — configuration du module « Appels d'offres ».
   ----------------------------------------------------------------------------
   Enregistre la clé de module `ao` (corrélée au manifest backend `apps/ao`) et
   sa section de navigation. Aucun écran AO n'existe encore dans la SPA (FG222–
   227 backend-only) : la config est volontairement SANS route/écran — le
   câblage UI est hors ODX11. Elle sert d'ancrage stable pour
   `scripts/check_modules.py` (corrélation clé frontend ↔ manifest backend).
   ========================================================================== */

const config = {
  key: 'ao',
  order: 56,
  // Pas de section `nav` ni de `routes` tant qu'aucun écran AO n'est construit
  // (hors périmètre ODX11) — la clé seule corrèle le module backend `ao`.
  sectionLabels: { ao: "Appels d'offres" },
}

export default config
