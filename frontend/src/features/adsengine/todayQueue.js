/* ============================================================================
   PUB42 — File « Aujourd'hui » unifiée (logique PURE, sans JSX).
   ----------------------------------------------------------------------------
   Normalise ``GET /adsengine/aujourd-hui/`` (déjà classée par priorité côté
   backend — garde-fous > alertes > approbations > commentaires > digest,
   ``metrics.today_queue``) : on ne fait que LIRE/FORMATER, jamais retrier
   (le tri de priorité est une décision métier, elle vit au backend — la même
   doctrine que ``normalizeFunnel``/``normalizeCohorts`` dans adsengine.js).
   ========================================================================== */

// Tons FR par catégorie (cohérents avec les badges déjà utilisés ailleurs
// dans la console — rouge = bloquant, orange = attention, bleu = neutre).
const CATEGORY_TONES = {
  garde_fou: { bg: '#fee2e2', color: '#991b1b' },
  alerte: { bg: '#ffedd5', color: '#9a3412' },
  approbation: { bg: '#eef2ff', color: '#3730a3' },
  commentaire: { bg: '#e0f2fe', color: '#075985' },
  digest: { bg: '#f1f5f9', color: '#475569' },
}

export function categoryTone(categorie) {
  return CATEGORY_TONES[categorie] || { bg: '#f1f5f9', color: '#475569' }
}

// Normalise la réponse en ``{items, total}`` — repli sûr sur une réponse
// absente/malformée (jamais une erreur, jamais un item fabriqué).
export function normalizeTodayQueue(raw) {
  const d = raw && typeof raw === 'object' ? raw : {}
  const list = Array.isArray(d.items) ? d.items : (Array.isArray(d) ? d : [])
  const items = list.filter(Boolean).map((it, i) => ({
    id: it.id ?? String(i),
    categorie: it.categorie || it.category || 'digest',
    categorie_label: it.categorie_label || it.category_label || it.categorie || '—',
    titre: it.titre || it.title || '—',
    detail: it.detail || '',
    lien: it.lien || it.link || '',
    quand: it.quand || it.when || null,
  }))
  return { items, total: Number.isFinite(d.total) ? d.total : items.length }
}
