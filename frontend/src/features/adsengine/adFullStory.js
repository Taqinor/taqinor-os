/* ============================================================================
   PUB44 — Fiche « histoire complète » d'une ad (logique PURE, sans JSX).
   ----------------------------------------------------------------------------
   Normalise ``GET /adsengine/ads/<meta_id>/histoire/`` — repli défensif sur
   une réponse absente/malformée (jamais une erreur, jamais une section
   fabriquée). Aucune valeur n'est recalculée : chaque section est déjà
   produite côté backend par les sélecteurs existants (ads_cockpit_rows,
   BreakdownsView, CommentListView…) — ce fichier ne fait que LIRE.
   ========================================================================== */

export function normalizeAdFullStory(raw) {
  const d = raw && typeof raw === 'object' ? raw : {}
  const adRaw = d.ad && typeof d.ad === 'object' ? d.ad : {}
  return {
    ad: {
      id: adRaw.id ?? null,
      meta_id: adRaw.meta_id || '',
      nom: adRaw.nom || adRaw.name || '—',
      statut: adRaw.statut || '',
      statut_display: adRaw.statut_display || adRaw.statut || '—',
    },
    creatif: (d.creatif && typeof d.creatif === 'object') ? d.creatif : null,
    metriques: (d.metriques && typeof d.metriques === 'object') ? d.metriques : null,
    actions: Array.isArray(d.actions) ? d.actions.filter(Boolean) : [],
    commentaires: Array.isArray(d.commentaires) ? d.commentaires.filter(Boolean) : [],
    regles: Array.isArray(d.regles) ? d.regles.filter(Boolean) : [],
    experiences: Array.isArray(d.experiences) ? d.experiences.filter(Boolean) : [],
    breakdowns: Array.isArray(d.breakdowns) ? d.breakdowns.filter(Boolean) : [],
  }
}
