/* ============================================================================
   PUB41 — Fraîcheur + panne visibles (logique PURE, sans JSX).
   ----------------------------------------------------------------------------
   Normalise la réponse de ``GET /adsengine/sync-status/`` (dernier sync OK
   par type + âge + « stale ») et formate l'âge/l'horodatage pour l'affichage
   FR — rien n'est inventé, ces fonctions ne font que LIRE/FORMATER ce que
   l'API renvoie (même doctrine que ``dateRange.js``/``adsengine.js``).
   Consommé par `SyncStatusBanner.jsx` (bandeau global) ET par les tuiles du
   Dashboard (horodatage discret par tuile).
   ========================================================================== */

function numOrNull(v) {
  const n = typeof v === 'string' ? Number(v) : v
  return Number.isFinite(n) ? n : null
}

// Normalise ``{types, stale, worst}`` — repli défensif à `{types: [], stale:
// false, worst: null}` sur une réponse absente/malformée (jamais une erreur).
export function normalizeSyncStatus(raw) {
  const s = raw && typeof raw === 'object' ? raw : {}
  const types = (Array.isArray(s.types) ? s.types : []).filter(Boolean).map(t => ({
    type: t.type,
    label: t.label || t.type,
    last_ok_at: t.last_ok_at || null,
    age_minutes: numOrNull(t.age_minutes),
    stale: !!t.stale,
  }))
  const worstRaw = s.worst && typeof s.worst === 'object' ? s.worst : null
  const worst = worstRaw ? {
    type: worstRaw.type,
    label: worstRaw.label || worstRaw.type,
    last_ok_at: worstRaw.last_ok_at || null,
    age_minutes: numOrNull(worstRaw.age_minutes),
  } : null
  return { types, stale: !!s.stale, worst }
}

// Trouve le statut d'UN type par clé (ex. 'insights' pour les tuiles
// spend/CPL/fréquence) — ``null`` si absent (jamais fabriqué).
export function syncStatusFor(status, type) {
  const types = status && Array.isArray(status.types) ? status.types : []
  return types.find(t => t.type === type) || null
}

// Âge en minutes -> libellé FR lisible (« 12 min » / « 3 h » / « 2 j »).
// ``null``/non-fini -> chaîne vide (jamais un « NaN min » à l'écran).
export function formatAge(minutes) {
  if (minutes === null || minutes === undefined || !Number.isFinite(minutes)) return ''
  if (minutes < 60) return `${Math.round(minutes)} min`
  const hours = minutes / 60
  if (hours < 48) return `${Math.round(hours)} h`
  return `${Math.round(hours / 24)} j`
}

// Horodatage ISO -> « JJ/MM HH:MM » (heure LOCALE du navigateur — cohérent
// avec le reste de la console, jamais l'UTC brut). Chaîne vide si absent.
export function formatSyncDateTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${dd}/${mm} ${hh}:${mi}`
}
