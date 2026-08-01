/* APX15(b) — Le regroupement du board VENTES, en logique PURE (testable sans
   DOM, comme `factureKanban.js` l'est déjà pour les factures).

   RÈGLE #4 — les colonnes sont les statuts DOCUMENT du devis
   (brouillon / envoyé / accepté / refusé / expiré). JAMAIS les clés du funnel
   STAGES.py (règle #2) : aucune n'est importée ici, les deux couches ne se
   mélangent jamais. */

export const DEVIS_BOARD_COLUMNS = [
  { key: 'brouillon', label: 'Brouillon', accent: 'var(--muted-foreground)' },
  { key: 'envoye', label: 'Envoyé', accent: 'var(--info)' },
  { key: 'accepte', label: 'Accepté', accent: 'var(--success)' },
  { key: 'refuse', label: 'Refusé', accent: 'var(--destructive)' },
  { key: 'expire', label: 'Expiré', accent: 'var(--warning)' },
]

/* Un devis en attente dont la validité est dépassée s'affiche « Expiré » SANS
   que son statut stocké change — exactement la règle T7 de la vue liste. */
export function effectiveStatut(d) {
  return d?.is_expired ? 'expire' : d?.statut
}

/* Colonnes ordonnées, avec compteur et TOTAL TTC. Un statut inconnu n'invente
   aucune colonne (et n'est compté nulle part). */
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
      total: items.reduce((s, d) => s + (Number(d.total_ttc) || 0), 0),
    }
  })
}
