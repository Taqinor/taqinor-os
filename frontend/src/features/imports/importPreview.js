// Logique pure de présentation de l'aperçu d'import (dry-run).
// Testée en isolation (importPreview.test.mjs) — aucun appel réseau ici.

export const IMPORT_TARGETS = [
  { target: 'lead', label: 'Leads' },
  { target: 'client', label: 'Clients' },
  { target: 'produit', label: 'Produits' },
]

// Libellés FR des statuts de ligne renvoyés par le serveur.
export const STATUS_LABELS = {
  create: 'À créer',
  duplicate: 'Doublon (ignoré)',
  error: 'Erreur',
}

export function statusLabel(status) {
  return STATUS_LABELS[status] || status
}

// Résumé court d'un aperçu : combien créés / ignorés / colonnes non mappées.
export function summarize(preview) {
  if (!preview) return ''
  const parts = [
    `${preview.total_rows} ligne(s)`,
    `${preview.will_create} à créer`,
  ]
  if (preview.will_skip) parts.push(`${preview.will_skip} ignorée(s)`)
  if (preview.unmapped_columns && preview.unmapped_columns.length) {
    parts.push(`${preview.unmapped_columns.length} colonne(s) non reconnue(s)`)
  }
  return parts.join(' · ')
}

// L'import peut-il être confirmé ? Au moins une ligne créable.
export function canConfirm(preview) {
  return !!preview && preview.will_create > 0
}
