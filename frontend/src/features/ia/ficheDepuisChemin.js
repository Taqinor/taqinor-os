// NTAI10 — Correspondance URL -> fiche, pour le Copilote CONTEXTUEL
// (CopilotContext.jsx). Module PUR (aucun accès React) — c'est ce qui le
// rend testable seul, et ce qui évite de faire de CopilotContext.jsx un
// fichier qui exporte autre chose qu'un composant (react-refresh).

/** Correspondance URL → fiche. Étendre ici quand un écran détail apparaît. */
const ROUTES_FICHE = [
  { motif: /^\/crm\/leads\/(\d+)/, contentType: 'crm.lead' },
  { motif: /^\/contrats\/(\d+)/, contentType: 'contrats.contrat' },
]

/**
 * Déduit `{ contentType, objectId }` d'un chemin, ou `null`.
 * Pure (aucun accès React) — c'est ce qui la rend testable seule.
 */
export function ficheDepuisChemin(pathname) {
  for (const { motif, contentType } of ROUTES_FICHE) {
    const trouve = motif.exec(pathname || '')
    if (trouve) return { contentType, objectId: Number(trouve[1]) }
  }
  return null
}
