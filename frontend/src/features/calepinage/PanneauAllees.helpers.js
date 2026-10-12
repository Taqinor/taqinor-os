// ENF22 — helpers extraits de PanneauAllees.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/**
 * CAL70 — la suggestion `ALLEE_GRATUITE` d'une réponse du moteur, ou `null`.
 * Fonction PURE : elle ne calcule rien, elle LIT ce que le moteur a déjà
 * publié dans `suggestions[]` (contrat `moteur_calculer.json`).
 */
export function suggestionAlleeGratuite(resultat) {
  const suggestions = resultat?.suggestions
  if (!Array.isArray(suggestions)) return null
  const trouvee = suggestions.find((s) => s?.code === 'ALLEE_GRATUITE'
    && Number.isFinite(s?.action?.patch?.allee_m))
  if (!trouvee) return null
  return {
    alleeM: trouvee.action.patch.allee_m,
    titre: trouvee.titre ?? null,
    gainModules: trouvee.gain_modules ?? null,
    gainKwc: trouvee.gain_kwc ?? null,
    confiance: trouvee.confiance ?? null,
  }
}

/* ============================================================================
   CIQ138 — CONTRAINTES DE SITE DU PROJET (assureur, dégagements, îlots).
   ----------------------------------------------------------------------------
   Champ serveur `Calepinage.contraintes_site` (CIQ136, contrat
   `calepinage_detail.json`) : VIDE par défaut ; le préréglage FM Global
   DS 1-15 (avril 2026) ne se charge QUE sur clic, QUE pour l'assureur FM ;
   une valeur sans SOURCE est refusée (comme le serveur). Les règles affichées
   à côté des obstacles sont celles que le serveur publie (`regles`), jamais
   recomposées ici. Saisie libre : `step="any"`, aucun nombre n'est arrondi.
   ========================================================================== */

/** Le préréglage FM Global DS 1-15 — MÊMES valeurs que
 *  `services/degagements.py PRESET_FM_DS_1_15` (verrouillé par un test sur le
 *  contrat committé `calepinage_detail.json`). */
export const PRESET_FM_DS_1_15 = {
  assureur: 'fm_global',
  degagements_m: { lanterneau: 1.8, joint_dilatation: 1.2 },
  ilot_max_m: { longueur: 46.0, largeur: 46.0 },
  allee_ilot_m: 1.2,
  source: {
    document: 'FM Global Data Sheet 1-15 « Roof-Mounted Solar Photovoltaic Panels » (avril 2026)',
    date: '2026-04',
    reference: '§2.1.1.4 B-E',
  },
  regles: {
    lanterneau: 'DS 1-15 §2.1.1.4 — 1,8 m des lanterneaux',
    joint_dilatation: 'DS 1-15 §2.1.1.4 — 1,2 m des joints de dilatation',
    ilot_max_m: 'DS 1-15 §2.1.1.4 — champs ≤ 46 × 46 m',
    allee_ilot_m: 'DS 1-15 §2.1.1.4 — allées de 1,2 m entre champs',
  },
}
