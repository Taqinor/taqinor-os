// ENF22 — helpers extraits de BandeauProvenanceProduction.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/* ============================================================================
   ACAL52 — LA BORNE HAUTE ET LES RÉGLAGES UTILISÉS, DITS SUR L'ÉCRAN.
   ----------------------------------------------------------------------------
   `production.total.complete === false` (ACAL49) veut dire que des postes de
   perte du socle n'ont pas été renseignés : le P50 servi est une BORNE HAUTE.
   Le bandeau reprend la mention SERVIE, la liste `socle_manquant` et le lien
   vers les réglages ; PR / P75 / P90 / P95 s'affichent « — non publié » (motif
   en infobulle), jamais un nombre. Rien n'est recalculé ici : la complétude est
   celle du serveur. `complete === true` : ni bandeau ni masquage.
   ========================================================================== */

/** T4-X2-002 — LA phrase d'une simulation périmée (le document enregistré a changé depuis le calcul : le serveur ne
    publie plus sa production, `simulation_perimee`). Le chiffre simulé n'est plus montré : c'est DIT, jamais remplacé
    en silence par l'estimation de l'atelier. */
export const SIMULATION_A_REFAIRE = 'Simulation à refaire : le toit ou un réglage de votre société a changé depuis le dernier calcul.'

/** Une simulation existe mais elle est périmée. */
export const simulationARefaire = (resultat) => resultat?.simule === true && resultat?.simulation_perimee === true

/** Résultat simulé mais incomplet : le P50 existe, le socle de pertes non. */
export function estIncomplet(total) {
  return Boolean(total) && total.complete === false
    && total.p50_kwh !== null && total.p50_kwh !== undefined
}
