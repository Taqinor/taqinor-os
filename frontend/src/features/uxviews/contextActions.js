// NTUX9 — Palette de commandes : actions CONTEXTUELLES par écran.
//
// Étend `providers/commandActions.js` (navigation pure) au-delà de la
// navigation : un registre RÉSOLU DYNAMIQUEMENT selon la route active
// (pathname + query string, cf. `useLocation()` de react-router-dom) et
// l'objet actuellement affiché (id porté par la query string du deep-link —
// même convention que `lib/search/entityRoutes.js` : `?lead=<id>`,
// `?devis=<id>`).
//
// Module PUR (aucun import React/API) — comme `commandActions.js`, testable
// en `node --test`. Les actions concrètes (appel réseau, téléchargement,
// navigation) sont fournies par l'APPELANT via `helpers` : ce module ne fait
// QUE décider QUELLES actions proposer pour une route donnée, jamais
// comment les exécuter — la palette (providers/CommandPalette.jsx) réutilise
// les MÊMES endpoints que le reste de l'app (ex. `ventesApi.getProposalPdf`,
// le même chemin `/proposal` que le catalogue d'actions agent
// `apps/agent/registry.py` — `ventes.devis.proposal_pdf` — aucune logique
// métier dupliquée).
//
// Frontières : ce registre ne remplace PAS le mécanisme `taqinor:lead-workspace-actions`
// (LW26) qui reste spécifique à la fiche LeadWorkspace montée. « Nouveau
// lead »/« Créer un devis » (les deux autres exemples cités par NTUX9) NE
// SONT PAS reposés ici : `providers/shortcuts.js` (VX220(b), commentaire
// « NTUX possède la palette de quick-create générique (NTUX9/10) ») les
// expose déjà GLOBALEMENT dans la section « Créer » de la palette (quick-create
// modal pour Lead, raccourci nav pour Devis) — les redéclarer ici les
// dupliquerait sous un second libellé identique. Ce registre n'ajoute donc
// que les actions VRAIMENT dépendantes d'un OBJET ouvert (id porté par la
// query string), qui n'existent nulle part ailleurs.

/**
 * contextActionsForRoute — actions contextuelles pour la route courante.
 *
 * @param {{pathname: string, searchParams: URLSearchParams}} location
 * @param {{
 *   downloadDevisProposal?: (devisId: string) => void,
 *   changeLeadStage?: (leadId: string) => void,
 * }} helpers — callbacks fournis par l'appelant ; une action dont le helper
 *   requis est absent n'est simplement pas proposée (jamais une action
 *   cassée dans la palette).
 * @returns {{id: string, label: string, run: () => void}[]}
 */
export function contextActionsForRoute(location, helpers = {}) {
  const pathname = location?.pathname || ''
  const searchParams = location?.searchParams
  const getParam = (key) => (searchParams && typeof searchParams.get === 'function'
    ? searchParams.get(key)
    : null)
  const { downloadDevisProposal, changeLeadStage } = helpers
  const actions = []

  if (pathname.startsWith('/crm/leads')) {
    const leadId = getParam('lead')
    if (leadId && typeof changeLeadStage === 'function') {
      actions.push({
        id: 'ctx-lead-stage',
        label: 'Changer le stage du lead sélectionné',
        run: () => changeLeadStage(leadId),
      })
    }
  }

  if (pathname.startsWith('/ventes/devis')) {
    const devisId = getParam('devis')
    if (devisId && typeof downloadDevisProposal === 'function') {
      actions.push({
        id: 'ctx-devis-pdf',
        label: 'Générer le PDF du devis ouvert',
        run: () => downloadDevisProposal(devisId),
      })
    }
  }

  return actions
}

// Étape SUIVANTE du funnel après `currentStage`, ou `null` si déjà à la
// dernière étape ACTIVE (SIGNED) ou étape inconnue/COLD. COLD est un
// parking : on ne « avance » jamais automatiquement vers ni depuis lui ici
// (règle identique à `features/crm/stages.js isStageMoveAllowed` — un
// mouvement impliquant COLD est un choix explicite, jamais une avance
// automatique). Dupliqué en PUR ici (pas d'import de `features/crm/stages.js`,
// qui tire du JSX via `lib/format.js` transitivement pour d'autres exports)
// pour rester un module isomorphe testable en `node --test` sans bundler —
// la LISTE d'étapes elle-même reste `PIPELINE_STAGES` (miroir STAGES.py,
// passée en paramètre par l'appelant, jamais recopiée en dur ici).
export function nextStageFor(currentStage, pipelineStages) {
  const stages = Array.isArray(pipelineStages) ? pipelineStages : []
  const idx = stages.indexOf(currentStage)
  if (idx === -1 || currentStage === 'COLD') return null
  const next = stages[idx + 1]
  if (!next || next === 'COLD') return null
  return next
}
