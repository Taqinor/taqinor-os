/* ============================================================================
   PUB22 — Schéma DÉCLARATIF des composeurs d'action manuels.
   ----------------------------------------------------------------------------
   Un descripteur PAR kind RÉEL d'EngineAction (models.EngineAction.Kind +
   constantes services set_schedule/duplicate/pause_for_month/create_ad_study/
   enable_cbo). `edit_copy` est EXCLU : il a déjà son composeur dédié
   (EditCopyComposer). Le composeur générique (ManualActionComposer) rend le
   formulaire à partir de ce schéma ; CHAQUE soumission part en proposition
   (propose_action côté backend) — jamais un write Meta direct, naissance PAUSED
   intacte pour les créations.

   Deux modes de soumission :
   - `raw`     → adsengineApi.actions.create({ kind, reason_fr, payload }) sur le
                 viewset générique (payload validé par kind côté serveur pour
                 create_ad / set_spend_cap / rename).
   - `curated` → adsengineApi.actions.proposeCurated(kind, { ...params, reason_fr })
                 vers le producteur backend (résolution DB / validation) pour
                 duplicate / set_schedule / create_ad_study.

   `scope` (campaign|adset|ad|global) décide sur quelle ligne le kind est offert
   et d'où vient l'id cible (`target.metaId`, injecté par buildPayload — le
   formulaire ne demande QUE les valeurs nouvelles, jamais de re-saisir l'id).
   ========================================================================== */

// Note : dans buildPayload(v, t), `v` (valeurs saisies) peut être inutilisé quand
// le kind n'a pas de champ (pause/enable_cbo) — `t` (cible) le suit toujours, donc
// eslint (args: after-used) ne le signale pas.
export const MANUAL_ACTIONS = [
  // ── Campagne ──────────────────────────────────────────────────────────────
  {
    kind: 'pause', scope: 'campaign', mode: 'raw', label: 'Mettre en pause',
    fields: [],
    buildPayload: (v, t) => ({ target_meta_id: t.metaId, target_type: 'campaign' }),
    reasonPlaceholder: 'ex. Dépense sans lead — mise en pause de sécurité.',
  },
  {
    kind: 'pause_for_month', scope: 'campaign', mode: 'raw', label: 'Pause pour le mois',
    fields: [],
    buildPayload: (v, t) => ({ target_meta_id: t.metaId, target_type: 'campaign' }),
    reasonPlaceholder: 'ex. Plafond mensuel bientôt atteint — pause pour le mois.',
  },
  {
    kind: 'set_spend_cap', scope: 'campaign', mode: 'raw', label: 'Poser un plafond de dépense',
    fields: [{ name: 'spend_cap', label: 'Plafond (centimes)', type: 'number', required: true, placeholder: 'ex. 500000' }],
    buildPayload: (v, t) => ({ campaign_id: t.metaId, spend_cap: Number(v.spend_cap) }),
    reasonPlaceholder: 'ex. Limiter la dépense totale de la campagne.',
  },
  {
    kind: 'rename', scope: 'campaign', mode: 'raw', label: 'Renommer',
    fields: [{ name: 'name', label: 'Nouveau nom', type: 'text', required: true, placeholder: 'Nouveau nom' }],
    buildPayload: (v, t) => ({ object_id: t.metaId, name: v.name }),
    reasonPlaceholder: 'ex. Normaliser la nomenclature.',
  },
  {
    kind: 'enable_cbo', scope: 'campaign', mode: 'raw', label: 'Activer le budget de campagne (CBO)',
    fields: [],
    buildPayload: (v, t) => ({ campaign_id: t.metaId }),
    reasonPlaceholder: 'ex. Consolider les budgets des ad sets (Advantage+).',
  },
  {
    kind: 'create_adset', scope: 'campaign', mode: 'raw', label: 'Créer un ad set',
    fields: [{ name: 'name', label: "Nom de l'ad set", type: 'text', required: true, placeholder: 'Nom' }],
    buildPayload: (v, t) => ({ name: v.name, campaign_id: t.metaId }),
    reasonPlaceholder: "ex. Nouveau segment d'audience à tester.",
  },
  {
    kind: 'create_ad_study', scope: 'campaign', mode: 'curated', label: 'Lancer une étude A/B native',
    fields: [
      { name: 'name', label: "Nom de l'étude", type: 'text', required: true, placeholder: 'Nom' },
      {
        name: 'cells', label: 'Cellules (JSON — 2 à 5, somme treatment_percentage = 100)',
        type: 'json', required: true,
        placeholder: '[{"name":"A","treatment_percentage":50},{"name":"B","treatment_percentage":50}]',
      },
    ],
    buildPayload: (v) => ({ name: v.name, cells: v.cells }),
    reasonPlaceholder: "ex. Comparer deux structures d'ad set en A/B natif.",
  },
  // ── Ad set ──────────────────────────────────────────────────────────────
  {
    kind: 'rebalance_budget', scope: 'adset', mode: 'raw', label: 'Rééquilibrer le budget',
    fields: [{ name: 'daily_budget', label: 'Budget/jour (centimes)', type: 'number', required: true, placeholder: 'ex. 20000' }],
    buildPayload: (v, t) => ({ adset_id: t.metaId, daily_budget: Number(v.daily_budget) }),
    reasonPlaceholder: "ex. Réallouer vers l'ad set gagnant (dans la bande ±15 %).",
  },
  {
    kind: 'duplicate', scope: 'adset', mode: 'curated', label: 'Dupliquer',
    fields: [{ name: 'name_suffix', label: 'Suffixe de nom', type: 'text', required: false, placeholder: ' (copie)' }],
    buildPayload: (v, t) => ({ adset_id: t.metaId, name_suffix: v.name_suffix || ' (copie)' }),
    reasonPlaceholder: 'ex. Dupliquer le gagnant pour une nouvelle audience.',
  },
  {
    kind: 'set_schedule', scope: 'adset', mode: 'curated', label: 'Poser un horaire (dayparting natif)',
    fields: [{ name: 'grid', label: 'Grille horaire (JSON)', type: 'json', required: true, placeholder: '{"mon":[9,10,11]}' }],
    buildPayload: (v, t) => ({ adset_id: t.metaId, grid: v.grid }),
    reasonPlaceholder: 'ex. Diffuser seulement aux heures ouvrables.',
  },
  {
    kind: 'create_ad', scope: 'adset', mode: 'raw', label: 'Créer une ad',
    fields: [{ name: 'name', label: "Nom de l'ad", type: 'text', required: true, placeholder: 'Nom' }],
    buildPayload: (v, t) => ({ name: v.name, adset_id: t.metaId }),
    reasonPlaceholder: 'ex. Nouvelle variante créative à tester.',
  },
  {
    kind: 'rotate_creative', scope: 'adset', mode: 'raw', label: 'Roter le créatif',
    fields: [{ name: 'name', label: 'Nom de la nouvelle ad', type: 'text', required: true, placeholder: 'Nom' }],
    buildPayload: (v, t) => ({ name: v.name, adset_id: t.metaId }),
    reasonPlaceholder: 'ex. Créatif fatigué — rotation (nouvelle ad, née PAUSED).',
  },
  {
    kind: 'pause', scope: 'adset', mode: 'raw', label: 'Mettre en pause',
    fields: [],
    buildPayload: (v, t) => ({ target_meta_id: t.metaId, target_type: 'adset' }),
    reasonPlaceholder: 'ex. Ad set non performant — mise en pause.',
  },
  {
    kind: 'rename', scope: 'adset', mode: 'raw', label: 'Renommer',
    fields: [{ name: 'name', label: 'Nouveau nom', type: 'text', required: true, placeholder: 'Nouveau nom' }],
    buildPayload: (v, t) => ({ object_id: t.metaId, name: v.name }),
    reasonPlaceholder: 'ex. Normaliser la nomenclature.',
  },
  // ── Ad ──────────────────────────────────────────────────────────────────
  {
    kind: 'pause', scope: 'ad', mode: 'raw', label: 'Mettre en pause',
    fields: [],
    buildPayload: (v, t) => ({ target_meta_id: t.metaId, target_type: 'ad' }),
    reasonPlaceholder: 'ex. Ad perdante — mise en pause.',
  },
  {
    kind: 'rename', scope: 'ad', mode: 'raw', label: 'Renommer',
    fields: [{ name: 'name', label: 'Nouveau nom', type: 'text', required: true, placeholder: 'Nouveau nom' }],
    buildPayload: (v, t) => ({ object_id: t.metaId, name: v.name }),
    reasonPlaceholder: 'ex. Normaliser la nomenclature.',
  },
  // ── Global ───────────────────────────────────────────────────────────────
  {
    kind: 'create_campaign', scope: 'global', mode: 'raw', label: 'Créer une campagne',
    fields: [
      { name: 'name', label: 'Nom de la campagne', type: 'text', required: true, placeholder: 'Nom' },
      { name: 'objective', label: 'Objectif (optionnel)', type: 'text', required: false, placeholder: 'ex. OUTCOME_LEADS' },
    ],
    buildPayload: (v) => ({ name: v.name, ...(v.objective ? { objective: v.objective } : {}) }),
    reasonPlaceholder: 'ex. Nouvelle campagne de génération de leads (née PAUSED).',
  },
]

/** Descripteurs offerts pour un `scope` de ligne donné (dans l'ordre du schéma). */
export function actionsForScope(scope) {
  return MANUAL_ACTIONS.filter(a => a.scope === scope)
}

/** Le descripteur d'un couple (kind, scope) — les kinds pause/rename existent sur
 *  plusieurs scopes (target_type/id différents), la clé est donc bien (kind, scope). */
export function findAction(kind, scope) {
  return MANUAL_ACTIONS.find(a => a.kind === kind && a.scope === scope) || null
}
