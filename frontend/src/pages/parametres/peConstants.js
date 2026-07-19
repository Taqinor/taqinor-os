// Constantes & styles partagés de la page Paramètres (D1).
// Extraits tels quels de ParametresEntreprise.jsx lors de l'éclatement par
// onglet : aucune valeur, aucun libellé, aucun style ne change.
import { originFrom } from '../../api/origin'

// Défauts métier — miroir des valeurs codées en dur côté serveur. Affichés
// quand le profil n'a encore rien d'enregistré ; sauver = valeurs identiques.
export const DEFAULT_PAYMENT_TERMS = {
  residentiel: { acompte: 30, materiel: 60, solde: 10 },
  agricole: { acompte: 30, materiel: 60, solde: 10 },
  industriel: { acompte: 50, materiel: 40, solde: 10 },
}
export const DEFAULT_PREFIXES = { devis: 'DEV', facture: 'FAC', avoir: 'AVO', bon_commande: 'BC' }
// Numérotation par type (D3) : largeur de remplissage + période de
// réinitialisation. Défauts = comportement historique (4 chiffres, mensuel).
export const DEFAULT_NUMBERING = {
  devis: { padding: 4, reset: 'monthly' },
  facture: { padding: 4, reset: 'monthly' },
  avoir: { padding: 4, reset: 'monthly' },
  bon_commande: { padding: 4, reset: 'monthly' },
}
export const DOC_TYPES = [['devis', 'Devis'], ['facture', 'Facture'], ['avoir', 'Avoir'], ['bon_commande', 'Bon de commande']]
export const MODE_LABELS = { residentiel: 'Résidentiel', agricole: 'Agricole', industriel: 'Industriel / Commercial' }

// ── Familles d'onglets (VX35) ──────────────────────────────────────────────────
// Architecture d'information ≤ 2 niveaux (façon Stripe/Linear) : la sidebar
// verticale regroupe les onglets par domaine via le champ `group` ci-dessous.
// L'ORDRE de cette liste = l'ordre des sections dans la sidebar. Aucun réglage
// courant n'est caché derrière un mode avancé (erreur Odoo n°3) : « Avancé » ne
// contient que des réglages réellement techniques/rares.
export const SETTINGS_GROUPS = [
  { key: 'general',        label: 'Général' },
  { key: 'ventes',         label: 'Ventes & Devis' },
  { key: 'terrain',        label: 'Terrain & Stock' },
  { key: 'equipe',         label: 'Équipe & Sécurité' },
  { key: 'automatisation', label: 'Automatisation' },
  { key: 'avance',         label: 'Avancé' },
]

// ── Onglets de la page Paramètres (D1) ─────────────────────────────────────────
// Chaque réglage existant reste présent, simplement regroupé par domaine. Les
// clés (`key`) sont INCHANGÉES (VX35 : aucune renommée) ; seul le champ `group`
// est ajouté pour ranger chaque onglet dans une famille de `SETTINGS_GROUPS`.
export const TABS = [
  { key: 'onboarding', label: 'Prise en main',            group: 'general' },
  { key: 'societe',    label: 'Société & identité',       group: 'general' },
  { key: 'leads',      label: 'Leads',                    group: 'ventes' },
  { key: 'clients',    label: 'Clients',                  group: 'ventes' },
  { key: 'devis',      label: 'Devis & Factures',         group: 'ventes' },
  { key: 'documents',  label: 'Modèles de documents',     group: 'ventes' },
  { key: 'tarification', label: 'Tarification & ROI',     group: 'ventes' },
  { key: 'stock',      label: 'Stock',                    group: 'terrain' },
  { key: 'donnees',    label: 'Données',                  group: 'avance' },
  { key: 'statuts',    label: 'Statuts',                  group: 'automatisation' },
  { key: 'monitoring', label: 'Supervision',              group: 'terrain' },
  { key: 'checklists', label: 'Checklists',               group: 'terrain' },
  { key: 'etapes_chantier', label: 'Étapes chantier',     group: 'terrain' },
  { key: 'kits',       label: "Kits d'outillage",         group: 'terrain' },
  { key: 'shotlist',   label: 'Documentation terrain',    group: 'terrain' },
  { key: 'automatisations', label: 'Automatisations',     group: 'automatisation' },
  { key: 'notifications', label: 'Notifications',         group: 'automatisation' },
  { key: 'securite',   label: 'Sécurité & terrain',       group: 'equipe' },
  { key: 'equipe',     label: 'Équipe & rôles',           group: 'equipe' },
  { key: 'messages',   label: 'Messages & relances',      group: 'ventes' },
  { key: 'email',      label: 'Email',                    group: 'automatisation' },
  { key: 'api',        label: 'API & Webhooks',           group: 'avance' },
  { key: 'avance',     label: 'Avancé',                   group: 'avance' },
]

// ── Modèle de sauvegarde par onglet (VX151) ────────────────────────────────────
// Le bouton « Enregistrer » partagé n'existe que sur 4/24 onglets (ceux qui
// portent des champs du profil) ; les autres onglets sont des sections
// autonomes qui gèrent leur propre persistance. Sans repère préalable,
// l'utilisateur cherche un bouton de sauvegarde qui n'est pas là. Ce map
// annonce, AVANT toute édition, la convention de chaque onglet.
//   'form'    → bouton « Enregistrer » partagé, en bas de page.
//   'section' → la section porte ses propres boutons d'enregistrement.
//   'guide'   → onglet d'assistance, rien à enregistrer.
// Un onglet absent de ce map est traité comme 'section' (défaut sûr : on
// n'affirme jamais un bouton partagé qui n'existe pas).
export const SAVE_MODEL_BY_TAB = {
  onboarding: 'guide',
  societe: 'form',
  leads: 'form',
  devis: 'form',
  avance: 'form',
}
export const SAVE_MODEL_HINTS = {
  form:    'Cet onglet s’enregistre avec le bouton « Enregistrer » en bas de page.',
  section: 'Cet onglet dispose de ses propres boutons d’enregistrement dans la section.',
  guide:   'Onglet d’assistance — aucun réglage à enregistrer ici.',
}
export function saveModelForTab(tab) {
  return SAVE_MODEL_BY_TAB[tab] || 'section'
}

// L790 — index de recherche : { tab, libellés/mots-clés }. Une saisie qui
// correspond à un mot-clé propose de sauter à l'onglet concerné. Liste
// volontairement large mais simple à maintenir (un onglet par entrée).
export const SETTINGS_SEARCH_INDEX = [
  { tab: 'onboarding', terms: ['prise en main', 'onboarding', 'guide', 'démarrage', 'checklist de configuration', 'coachmarks', 'visite guidée'] },
  { tab: 'societe', terms: ['nom', 'entreprise', 'adresse', 'email', 'téléphone', 'logo', 'signature', 'couleur', 'ice', 'if', 'identifiant fiscal', 'rc', 'registre de commerce', 'patente', 'cnss', 'rib', 'iban', 'banque', 'siret', 'tva intracommunautaire', 'instructions de paiement', 'conditions générales'] },
  { tab: 'leads', terms: ['responsable par défaut', 'installateur par défaut', 'parrainage', 'récompense', 'étiquettes', 'tags', 'motifs de perte', 'canaux', 'sources', 'couleur étiquette'] },
  { tab: 'clients', terms: ['clients', 'champs personnalisés client'] },
  { tab: 'devis', terms: ['échéancier', 'acompte', 'matériel', 'solde', 'validité du devis', 'pompage', 'numérotation', 'préfixe', 'prochain numéro', 'commission', 'tva', 'taux standard', 'taux panneaux', 'taxes'] },
  { tab: 'documents', terms: ['modèles de documents', 'textes du devis'] },
  { tab: 'tarification', terms: ['barème onee', 'paliers', 'force motrice', 'agricole', 'surplus injecté', 'autoconsommation', 'pertes système', 'productible', 'pvgis', 'irradiation', 'roi', 'rentabilité'] },
  { tab: 'stock', terms: ['stock', 'catégories', 'fournisseurs', 'marques', 'seuil'] },
  { tab: 'statuts', terms: ['statuts', 'libellé', 'ordre'] },
  { tab: 'monitoring', terms: ['supervision', 'sous-performance', 'auto-ticket', 'sav'] },
  { tab: 'checklists', terms: ['checklist', 'modèles de checklist', 'étapes', 'capture série'] },
  { tab: 'kits', terms: ["kits d'outillage", 'outils'] },
  { tab: 'shotlist', terms: ['documentation terrain', 'shot list', 'photos', 'créneaux'] },
  { tab: 'automatisations', terms: ['automatisations', 'approbations'] },
  { tab: 'securite', terms: ['sécurité', 'consignes', 'dépassement', 'services swappables', 'ocr', 'transcription'] },
  { tab: 'equipe', terms: ['équipe', 'rôles', 'utilisateurs'] },
  { tab: 'messages', terms: ['niveaux de relance', 'relance', 'message', 'whatsapp', 'darija', 'rappel'] },
  { tab: 'email', terms: ['email', "compte d'envoi", 'capture entrante'] },
  { tab: 'api', terms: ['api', 'webhooks', "clés d'api"] },
  { tab: 'avance', terms: ['avancé', 'hypothèses roi', 'tarif onee', 'rendement', 'logique de devis', 'prix cible', 'remise', "types d'intervention", "checklist d'exécution", 'champs personnalisés', "journal des modifications", "journal d'audit", 'seuil régime', '82-21'] },
]

// VX35 — regroupe une liste d'onglets par famille, dans l'ordre de
// SETTINGS_GROUPS. Un onglet sans `group` (ou avec un group inconnu) tombe dans
// « Avancé » — ainsi aucun onglet ne disparaît jamais de la sidebar. Renvoie
// uniquement les familles non vides, chacune avec ses onglets.
export function groupTabs(tabs) {
  const fallback = 'avance'
  const known = new Set(SETTINGS_GROUPS.map(g => g.key))
  return SETTINGS_GROUPS
    .map(g => ({
      ...g,
      tabs: tabs.filter(t => (known.has(t.group) ? t.group : fallback) === g.key),
    }))
    .filter(g => g.tabs.length > 0)
}

// Cherche les onglets dont au moins un mot-clé contient la requête (≥ 2 car).
export function searchSettings(query) {
  const q = (query || '').trim().toLowerCase()
  if (q.length < 2) return []
  return SETTINGS_SEARCH_INDEX
    .map(({ tab, terms }) => {
      const hits = terms.filter(t => t.toLowerCase().includes(q))
      return hits.length ? { tab, hits } : null
    })
    .filter(Boolean)
}

export const ACCEPTED   = ['image/png', 'image/jpeg', 'image/webp']
export const MAX_MB     = 2
// Var d'env VIDE = même origine (prod derrière nginx) — surtout ne jamais
// construire new URL('') : c'est ce qui tuait toute la page en production.
export const MEDIA_BASE = originFrom(import.meta.env.VITE_API_URL)
export const mediaUrl   = (url) => {
  if (!url) return null
  if (MEDIA_BASE) {
    // Dev local : les URLs présignées MinIO utilisent l'hôte Docker interne
    return url
      .replace(/^https?:\/\/minio(:\d+)?/, `${MEDIA_BASE.replace(/:\d+$/, '')}:9000`)
      .replace(/^\//, `${MEDIA_BASE}/`)
  }
  // Prod (même origine) : on garde les chemins relatifs tels quels ; les URLs
  // minio internes ne sont pas joignables du navigateur — pas de réécriture
  // hasardeuse, l'aperçu dégrade proprement (la page, elle, vit).
  return url
}
