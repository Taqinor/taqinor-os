// Étapes canoniques du pipeline CRM — MIROIR STRICT de STAGES.py (racine du
// repo). La CI (scripts/check_stages.py) échoue à la moindre divergence.
// Ne JAMAIS déclarer une autre liste d'étapes ailleurs : tout importe d'ici.
// Testable avec node --test (import limité au formateur monnaie partagé).
import { formatMAD as sharedFormatMAD } from '../../lib/format.js'

export const PIPELINE_STAGES = [
  'NEW',
  'CONTACTED',
  'QUOTE_SENT',
  'FOLLOW_UP',
  'SIGNED',
  'COLD',
]

// Étape de conversion (miroir de STAGES.py CONVERSION_STAGE) : ENTRER dans
// cette étape correspond à un devis accepté. Constante scalaire — pas une
// nouvelle liste d'étapes (check_stages.py ne contrôle que les listes).
export const CONVERSION_STAGE = 'SIGNED'

export const STAGE_LABELS = {
  NEW: 'Nouveau',
  CONTACTED: 'Contacté',
  QUOTE_SENT: 'Devis envoyé',
  FOLLOW_UP: 'Relance',
  SIGNED: 'Signé',
  COLD: 'Froid',
}

// Accent visuel par étape (entonnoir froid → chaud → signé, froid en gris).
// VX26 — couleurs dérivées des tokens de marque (frontend/src/design/tokens.css)
// plutôt que du hex local : les 6 CLÉS restent le miroir strict de STAGES.py,
// seule la source de couleur a changé.
export const STAGE_COLORS = {
  NEW: 'var(--stage-new)',
  CONTACTED: 'var(--stage-contacted)',
  QUOTE_SENT: 'var(--stage-quote-sent)',
  FOLLOW_UP: 'var(--stage-follow-up)',
  SIGNED: 'var(--stage-signed)',
  COLD: 'var(--stage-cold)',
}

// Libellés des choix du modèle Lead (apps/crm/models.py) — affichage seulement.
export const CANAL_LABELS = {
  meta_ads: 'Publicité Meta',
  whatsapp_ctwa: 'WhatsApp/CTWA',
  site_web: 'Site web',
  reference: 'Référence',
  telephone: 'Téléphone',
  walk_in: 'Visite/Walk-in',
  autre: 'Autre',
}

export const PRIORITE_LABELS = {
  basse: 'Basse',
  normale: 'Normale',
  haute: 'Haute',
}

// Libellés du marché / type d'installation (miroir Lead.TypeInstallation).
export const TYPE_INSTALLATION_LABELS = {
  residentiel: 'Résidentiel',
  commercial: 'Commercial',
  industriel: 'Industriel',
  agricole: 'Agricole',
}

// Nombre d'étoiles pleines affichées sur la carte (sur 2).
export const PRIORITE_STARS = { basse: 0, normale: 1, haute: 2 }

// « Perdu » est un DRAPEAU booléen (champ `perdu`), jamais une colonne ni le
// texte du motif : un lead est perdu SSI perdu === true, à n'importe quelle
// étape. Le motif_perte n'est que l'explication, plus jamais le signal.
// Le lead reste dans son étape avec le style perdu.
export const isPerdu = (lead) => Boolean(lead && lead.perdu)

// Tags libres, séparés par des virgules → liste propre.
export const tagList = (lead) =>
  String(lead?.tags ?? '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)

// Couleur stable d'une pastille de tag (palette fixe, déterministe).
const TAG_PALETTE = [
  '#e0f2fe', '#fef3c7', '#dcfce7', '#fae8ff', '#fee2e2',
  '#e2e8f0', '#fdf3e0', '#dbeafe', '#fce7f3', '#ecfccb',
]
const TAG_TEXT = [
  '#0369a1', '#a16207', '#15803d', '#a21caf', '#b91c1c',
  '#475569', '#92600a', '#1d4ed8', '#be185d', '#4d7c0f',
]
export const tagColor = (tag) => {
  let h = 0
  for (const c of String(tag)) h = (h * 31 + c.charCodeAt(0)) % 997
  const i = h % TAG_PALETTE.length
  return { bg: TAG_PALETTE[i], color: TAG_TEXT[i] }
}

// Initiales du responsable (ex. « meryem » → ME, « Reda Kasri » → RK).
export const initials = (name) => {
  const parts = String(name ?? '').trim().split(/[\s._-]+/).filter(Boolean)
  if (!parts.length) return ''
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

// LB4 — rang d'avancement dans l'entonnoir, MIROIR STRICT de
// apps/crm/services.py `_rang_funnel` : COLD est un état de PARKING, pas
// « plus avancé » — classé SOUS toute étape active (rang -1) pour qu'un lead
// froid soit RÉACTIVÉ par un déplacement vers n'importe quelle étape active.
// Bug recon2-03 #7 : `PIPELINE_STAGES.indexOf('COLD')` valait 5 (le plus haut
// rang) → tout drag COLD→actif était refusé comme un « recul ».
export function funnelRank(stage) {
  if (stage === 'COLD') return -1
  return PIPELINE_STAGES.indexOf(stage)
}

// LB4 — miroir BYTE-À-BYTE de apps/crm/services.py `_bulk_stage_allowed` :
//   - même étape → non (rien à faire) ;
//   - Froid → n'importe quelle étape active → oui (réactivation) ;
//   - vers Froid → oui (mise au parking, autorisée depuis n'importe où) ;
//   - sinon → uniquement vers une étape PLUS avancée (jamais de recul).
// Utilisé par le garde de drag (KanbanView), les options du StageMover et
// l'InlineEdit stage de la liste — un SEUL garde, tous les chemins (souris,
// clavier, select) obtiennent la même réponse (bug #8 meurt avec ça).
export function isStageMoveAllowed(current, target) {
  if (current === target) return false
  if (current === 'COLD' || target === 'COLD') return true
  return funnelRank(target) > funnelRank(current)
}

// Total TTC du devis le plus récent du lead (le serializer trie déjà du plus
// récent au plus ancien) — 0 si aucun devis.
export const latestDevisTotal = (lead) => {
  const d = lead?.devis?.[0]
  const n = d ? parseFloat(d.total_ttc) : NaN
  return Number.isFinite(n) ? n : 0
}

export const formatMAD = (n) => sharedFormatMAD(n, { decimals: 0 })

// Tri dans une colonne : priorité haute d'abord, puis le plus récent.
const PRIO_ORDER = { haute: 0, normale: 1, basse: 2 }
const sortColumn = (leads) =>
  [...leads].sort(
    (a, b) =>
      (PRIO_ORDER[a.priorite] ?? 1) - (PRIO_ORDER[b.priorite] ?? 1) ||
      new Date(b.date_creation ?? 0) - new Date(a.date_creation ?? 0),
  )

// Regroupe les leads par étape — TOUJOURS les 6 colonnes, dans l'ordre de
// l'entonnoir, même vides. Ajoute le compteur et le total devis par colonne.
export function groupLeadsByStage(leads) {
  return PIPELINE_STAGES.map((key) => {
    const inStage = sortColumn((leads ?? []).filter((l) => l.stage === key))
    return {
      key,
      label: STAGE_LABELS[key],
      color: STAGE_COLORS[key],
      leads: inStage,
      count: inStage.length,
      totalDevis: inStage.reduce((s, l) => s + latestDevisTotal(l), 0),
    }
  })
}

export const EMPTY_FILTERS = {
  q: '',
  canal: '',
  owner: '',
  priorite: '',
  tag: '',
  stage: '', // étape du funnel ('' = toutes)
  type_installation: '', // résidentiel/commercial/industriel/agricole ('' = tous)
  relance: '', // '' | 'retard' (en retard) | 'semaine' (cette semaine)
  perdus: 'avec', // 'avec' | 'sans' | 'seuls'
  archived: 'actifs', // 'actifs' | 'tous' | 'seuls' — dimension serveur (refetch)
  // QW3 — préférence de contact explicite ('' = toutes | 'phone_ok' | 'whatsapp_only')
  contact_preference: '',
  // VX224 — toggle « Mes leads » (chip FilterBar.jsx) : distinct de `owner`
  // (qui filtre par N'IMPORTE QUEL responsable, usage manager) — celui-ci
  // épingle spécifiquement l'utilisateur COURANT, résolu par l'appelant
  // (LeadsPage.jsx passe `myUsername`, jamais codé en dur ici).
  mesLeads: false,
}

// 'YYYY-MM-DD' du jour, en heure LOCALE (jamais via toISOString → pas d'UTC).
function todayLocalISO() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const j = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${j}`
}

// Fin de la semaine courante (dimanche) en 'YYYY-MM-DD', heure locale.
function endOfWeekLocalISO() {
  const d = new Date()
  const dow = (d.getDay() + 6) % 7 // lundi = 0
  d.setDate(d.getDate() + (6 - dow))
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const j = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${j}`
}

// Paramètre serveur ?archived=… déduit du filtre (vide = actifs uniquement).
export const archivedParam = (value) =>
  value === 'tous' ? { archived: 'all' }
    : value === 'seuls' ? { archived: 'only' }
      : {}

// Filtre partagé par les quatre vues (kanban, liste, calendrier, graphique).
// VX224 — `myUsername` (3e argument, optionnel) résout le toggle « Mes
// leads » (`filters.mesLeads`) sur `owner_nom` — le même champ déjà comparé
// par `filters.owner`, jamais un second champ dupliqué. Sans `myUsername`
// (repli), `mesLeads` n'a simplement aucun effet (jamais un filtre qui
// viderait la liste par accident).
export function filterLeads(leads, filters, { myUsername } = {}) {
  const f = { ...EMPTY_FILTERS, ...(filters ?? {}) }
  const q = f.q.trim().toLowerCase()
  const today = todayLocalISO()
  const weekEnd = endOfWeekLocalISO()
  return (leads ?? []).filter((l) => {
    if (f.canal && l.canal !== f.canal) return false
    if (f.owner && (l.owner_nom ?? '') !== f.owner) return false
    if (f.mesLeads && myUsername && (l.owner_nom ?? '') !== myUsername) return false
    if (f.priorite && (l.priorite ?? 'normale') !== f.priorite) return false
    if (f.tag && !tagList(l).includes(f.tag)) return false
    if (f.stage && l.stage !== f.stage) return false
    if (f.type_installation && (l.type_installation ?? '') !== f.type_installation) {
      return false
    }
    if (f.relance === 'retard') {
      if (!l.relance_date || l.relance_date >= today) return false
    }
    if (f.relance === 'semaine') {
      if (!l.relance_date || l.relance_date < today || l.relance_date > weekEnd) {
        return false
      }
    }
    if (f.perdus === 'sans' && isPerdu(l)) return false
    if (f.perdus === 'seuls' && !isPerdu(l)) return false
    if (f.contact_preference && l.contact_preference !== f.contact_preference) {
      return false
    }
    if (!q) return true
    return (
      (l.nom ?? '').toLowerCase().includes(q) ||
      (l.prenom ?? '').toLowerCase().includes(q) ||
      (l.societe ?? '').toLowerCase().includes(q) ||
      (l.email ?? '').toLowerCase().includes(q) ||
      (l.telephone ?? '').includes(f.q.trim()) ||
      (l.whatsapp ?? '').includes(f.q.trim()) ||
      (l.ville ?? '').toLowerCase().includes(q)
    )
  })
}
