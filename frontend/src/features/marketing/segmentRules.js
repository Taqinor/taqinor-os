/* ============================================================================
   NTMKT4 — SegmentBuilder : logique métier PURE (testable au node).
   ----------------------------------------------------------------------------
   Marshalling formulaire ↔ `regles` JSON du backend (`apps.crm.selectors.
   LEAD_SEGMENT_FIELDS` = ville/type_installation/tags/canal/score/
   facture_energie, + clés d'activité marketing `activite`/`evenement_present`/
   `evenement_absent` — whitelist stricte, `apps.compta.services.
   valider_regles_segment`). Le formulaire garde des champs bornes séparés
   (`score_gte`/`score_lte`) plus faciles à saisir ; `buildRegles` les
   recompose en `{gte, lte}` et OMET toute clé vide (jamais de règle
   fantôme envoyée au serveur).
   ========================================================================== */

export function emptyRuleForm() {
  return {
    ville: '', type_installation: '', tags: '', canal: '',
    score_gte: '', score_lte: '', facture_gte: '', facture_lte: '',
    activite: '', evenement_present: '', evenement_absent: '',
  }
}

export function ruleFormFromRegles(regles) {
  const r = regles || {}
  return {
    ville: r.ville || '',
    type_installation: r.type_installation || '',
    tags: r.tags || '',
    canal: r.canal || '',
    score_gte: r.score?.gte ?? '',
    score_lte: r.score?.lte ?? '',
    facture_gte: r.facture_energie?.gte ?? '',
    facture_lte: r.facture_energie?.lte ?? '',
    activite: r.activite || '',
    evenement_present: r.evenement_present ?? '',
    evenement_absent: r.evenement_absent ?? '',
  }
}

export function buildRegles(form) {
  const regles = {}
  if (form.ville) regles.ville = form.ville
  if (form.type_installation) regles.type_installation = form.type_installation
  if (form.tags) regles.tags = form.tags
  if (form.canal) regles.canal = form.canal
  const score = {}
  if (form.score_gte !== '' && form.score_gte != null) score.gte = Number(form.score_gte)
  if (form.score_lte !== '' && form.score_lte != null) score.lte = Number(form.score_lte)
  if (Object.keys(score).length) regles.score = score
  const facture = {}
  if (form.facture_gte !== '' && form.facture_gte != null) facture.gte = Number(form.facture_gte)
  if (form.facture_lte !== '' && form.facture_lte != null) facture.lte = Number(form.facture_lte)
  if (Object.keys(facture).length) regles.facture_energie = facture
  if (form.activite) regles.activite = form.activite
  if (form.evenement_present !== '' && form.evenement_present != null) {
    regles.evenement_present = Number(form.evenement_present)
  }
  if (form.evenement_absent !== '' && form.evenement_absent != null) {
    regles.evenement_absent = Number(form.evenement_absent)
  }
  return regles
}

// Clé stable pour déclencher un re-preview seulement quand les règles
// changent réellement (évite un appel réseau par frappe non significative).
export function reglesKey(form) {
  return JSON.stringify(buildRegles(form))
}
