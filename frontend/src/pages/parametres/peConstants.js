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
  { key: 'societe',    label: 'Société & identité' },
  { key: 'leads',      label: 'Leads' },
  { key: 'clients',    label: 'Clients' },
  { key: 'devis',      label: 'Devis & Factures' },
  { key: 'stock',      label: 'Stock' },
  { key: 'statuts',    label: 'Statuts' },
  { key: 'checklists', label: 'Checklists' },
  { key: 'kits',       label: "Kits d'outillage" },
  { key: 'equipe',     label: 'Équipe & rôles' },
  { key: 'messages',   label: 'Messages & relances' },
  { key: 'avance',     label: 'Avancé' },
]

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
