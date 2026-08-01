/* ============================================================================
   AOF181 — Types de clause et corps de création, hors composant.
   ----------------------------------------------------------------------------
   Séparé de `ExigencesPage.jsx` pour que le composant n'exporte QUE des
   composants (react-refresh/only-export-components) — comportement inchangé,
   déplacement structurel uniquement.
   ========================================================================== */

export const TYPES_CLAUSE = [
  { value: 'intervalle', label: 'Intervalle (min – max)', intervalle: true },
  { value: 'plafond', label: 'Plafond (maximum)' },
  { value: 'plancher', label: 'Plancher (minimum)' },
  { value: 'montant', label: 'Montant absolu' },
  { value: 'duree', label: 'Durée (jours)' },
  { value: 'texte', label: 'Exigence rédactionnelle' },
]

export function estIntervalle(type) {
  return TYPES_CLAUSE.find((t) => t.value === type)?.intervalle === true
}

/** Corps de création d'une clause. Les valeurs partent TELLES QUE TAPÉES
    (aucun `parseFloat`, aucune virgule convertie) : le serveur seul décide. */
export function payloadClause(form, affaireId) {
  const corps = {
    affaire: affaireId,
    libelle: form.libelle.trim(),
    type: form.type,
    bloquant: Boolean(form.bloquant),
    source_piece: form.sourcePiece.trim(),
    source_page: form.sourcePage.trim() || null,
    unite: form.unite.trim() || null,
  }
  if (estIntervalle(form.type)) {
    corps.valeur_min = form.valeur.trim()
    corps.valeur_max = form.valeurMax.trim()
  } else {
    corps.valeur = form.valeur.trim()
  }
  return corps
}
