// ENF22 — helpers extraits de RemplissageProuve.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/**
 * CAL79 — le RÉGIME de preuve d'un résultat du moteur.
 * Rend `{ prouve, total, borne, phrase, methode }`, ou `null` si le moteur
 * n'a publié aucun bloc `preuve` (on n'affirme alors rien du tout).
 */
export function regimeDePreuve(resultat) {
  const preuve = resultat?.preuve
  if (!preuve || typeof preuve !== 'object') return null

  const total = preuve.total_retenu ?? resultat?.total_modules ?? null
  const prouve = Boolean(preuve.optimal) && Boolean(preuve.methode_exacte)
  const borne = preuve.borne_superieure ?? null

  if (prouve) {
    return {
      prouve: true,
      total,
      borne,
      methode: preuve.methode ?? null,
      phrase: `Optimum prouvé (${total ?? '—'})`,
    }
  }
  return {
    prouve: false,
    total,
    borne,
    methode: preuve.methode ?? null,
    phrase: borne === null || borne === undefined
      // Aucune borne publiée : on ne la fabrique pas.
      ? `Meilleur plan trouvé (${total ?? '—'}) — aucune borne supérieure publiée`
      : `Meilleur plan trouvé (${total ?? '—'}) — borne supérieure ${borne}`,
  }
}
