/* AOF176 — helpers partagés du panneau « Contrôles avant dépôt ».
   Extraits de ControlesAvantDepot.jsx (react-refresh/only-export-components :
   un fichier de composant ne doit exporter QUE des composants). Aucun verdict
   n'est calculé ici (AOF94) : sévérité, message et code de règle viennent du
   serveur ; ces fonctions ne font que TRIER ce que le serveur a déjà décidé. */

export const BLOQUANT = 'bloquant'

// Sévérité normalisée : le serveur peut la porter sur `severite` (AOF146) ou
// sur `statut` — les deux valent la même chose, on n'en invente pas une 3e.
export function severiteDe(controle) {
  return controle?.severite || controle?.statut || 'ok'
}

/** Motif AFFICHABLE du blocage : le message du premier contrôle bloquant
    (ou son code de règle à défaut). `null` quand rien ne bloque. */
export function motifBlocage(controles) {
  const bloquant = (controles || []).find((c) => severiteDe(c) === BLOQUANT)
  if (!bloquant) return null
  return bloquant.message || bloquant.libelle || bloquant.code || 'contrôle bloquant'
}
