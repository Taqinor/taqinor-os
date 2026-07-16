/* ============================================================================
   ENG29 — Contrat de hooks DOM `ae-*` du module Publicité (moteur ads).
   ----------------------------------------------------------------------------
   Comme les préfixes `ap-` / `att-` / `pp-*` que ciblent les specs Playwright,
   les hooks `ae-*` (« ads engine ») sont un CONTRAT STABLE entre l'UI et les
   tests e2e/a11y : ils sont posés en `data-testid` (RTL/axe) ET en `className`
   (sélecteurs Playwright) sur les éléments-clés des deux écrans à fort enjeu —
   la boîte d'approbation (écran-vaisseau-amiral) et le dashboard « un chiffre ».
   NE JAMAIS renommer un hook sans mettre à jour les specs qui en dépendent.
   Ce fichier EST la documentation (source unique, testée par a11y.test.jsx).
   Certains hooks d'item sont suffixés par l'id de l'action (ex. `ae-approve-11`,
   `ae-batch-toggle-11`, `ae-reject-11`).
   ========================================================================== */

export const AE_HOOKS = {
  // Dashboard « un chiffre » (ENG23) — chaque chiffre est cliquable → leads réels.
  dashboard: {
    root: 'ae-dashboard',
    hero: 'ae-hero', // coût par signature (le seul chiffre qui compte)
    tiles: ['ae-tile-spend', 'ae-tile-cpl', 'ae-tile-frequency'],
    alertBanner: 'ae-alert-banner', // bandeau ENG13
    drillPanel: 'ae-drill-panel', // liste des leads derrière un chiffre
    drillClose: 'ae-drill-close',
  },
  // Boîte d'approbation (ENG25) — approuver/rejeter structurés, batch partiel.
  approvals: {
    root: 'ae-approvals',
    card: 'ae-action-card',
    reason: 'ae-action-reason', // reason_fr (le « pourquoi »)
    artifactBudget: 'ae-artifact-budget', // diff avant→après
    artifactCreative: 'ae-artifact-creative', // préview du créatif réel
    approvePrefix: 'ae-approve-', // + id
    rejectPrefix: 'ae-reject-', // + id
    rejectReasonPrefix: 'ae-reject-reason-', // select structuré, jamais du chat
    rejectConfirmPrefix: 'ae-reject-confirm-', // + id
    batchTogglePrefix: 'ae-batch-toggle-', // + id
    batchBar: 'ae-batch-bar',
    batchApprove: 'ae-batch-approve',
  },
}

export default AE_HOOKS
