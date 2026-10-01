/* APX15(b) — Le regroupement du board VENTES, en logique PURE (testable sans
   DOM, comme `factureKanban.js` l'est déjà pour les factures).

   RÈGLE #4 — les colonnes sont les statuts DOCUMENT du devis
   (brouillon / envoyé / accepté / refusé / expiré). JAMAIS les clés du funnel
   STAGES.py (règle #2) : aucune n'est importée ici, les deux couches ne se
   mélangent jamais. */

import { DEVIS_STATUTS, STATUT_DEVIS_LABELS } from './devisStatuts.js'

// QJR654 — ordre et libellés : la table unique (devisStatuts.js) ; seule la
// couleur d'accent est propre au board.
const ACCENT = {
  brouillon: 'var(--muted-foreground)',
  envoye: 'var(--info)',
  accepte: 'var(--success)',
  refuse: 'var(--destructive)',
  expire: 'var(--warning)',
}

export const DEVIS_BOARD_COLUMNS = DEVIS_STATUTS.map(key => ({
  key, label: STATUT_DEVIS_LABELS[key], accent: ACCENT[key],
}))

/* Un devis en attente dont la validité est dépassée s'affiche « Expiré » SANS
   que son statut stocké change — exactement la règle T7 de la vue liste. */
export function effectiveStatut(d) {
  return d?.is_expired ? 'expire' : d?.statut
}

/* Colonnes ordonnées, avec compteur et TOTAL AFFICHÉ. Un statut inconnu
   n'invente aucune colonne (et n'est compté nulle part).
   QJR205 — le total de colonne lit le MÊME champ que la vue liste
   (`total_affiche ?? total_ttc`, `DevisList.jsx`) : sur un devis à deux
   options, `total_affiche` porte le total de l'option 1 (jamais la somme des
   deux) tandis que `total_ttc` peut différer — additionner `total_ttc` seul
   ferait afficher un montant de colonne incohérent avec la carte. */
export function devisBoardColumns(devis = []) {
  const buckets = new Map(DEVIS_BOARD_COLUMNS.map(c => [c.key, []]))
  for (const d of devis ?? []) {
    const key = effectiveStatut(d)
    if (buckets.has(key)) buckets.get(key).push(d)
  }
  return DEVIS_BOARD_COLUMNS.map(c => {
    const items = buckets.get(c.key)
    return {
      ...c,
      devis: items,
      count: items.length,
      total: items.reduce((s, d) => s + (Number(d.total_affiche ?? d.total_ttc) || 0), 0),
    }
  })
}
