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

// ── Onglets de la page Paramètres (D1) ─────────────────────────────────────────
// Chaque réglage existant reste présent, simplement regroupé par domaine.
export const TABS = [
  { key: 'onboarding', label: 'Prise en main' },
  { key: 'societe',    label: 'Société & identité' },
  { key: 'leads',      label: 'Leads' },
  { key: 'clients',    label: 'Clients' },
  { key: 'devis',      label: 'Devis & Factures' },
  { key: 'documents',  label: 'Modèles de documents' },
  { key: 'tarification', label: 'Tarification & ROI' },
  { key: 'stock',      label: 'Stock' },
  { key: 'donnees',    label: 'Données' },
  { key: 'statuts',    label: 'Statuts' },
  { key: 'monitoring', label: 'Supervision' },
  { key: 'checklists', label: 'Checklists' },
  { key: 'etapes_chantier', label: 'Étapes chantier' },
  { key: 'kits',       label: "Kits d'outillage" },
  { key: 'shotlist',   label: 'Documentation terrain' },
  { key: 'automatisations', label: 'Automatisations' },
  { key: 'securite',   label: 'Sécurité & terrain' },
  { key: 'equipe',     label: 'Équipe & rôles' },
  { key: 'messages',   label: 'Messages & relances' },
  { key: 'email',      label: 'Email' },
  { key: 'api',        label: 'API & Webhooks' },
  { key: 'avance',     label: 'Avancé' },
]

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
