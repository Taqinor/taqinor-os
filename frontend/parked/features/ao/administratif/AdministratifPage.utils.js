/* ============================================================================
   AOF182 — Règles pures du volet administratif (dates, cautions, blocage).
   ----------------------------------------------------------------------------
   Séparé de `AdministratifPage.jsx` pour que le composant n'exporte QUE des
   composants (react-refresh/only-export-components) — comportement inchangé,
   déplacement structurel uniquement.
   ========================================================================== */

// Libellés de repli des vérifications téléphoniques réellement faites avant un
// dépôt — jamais une liste FERMÉE : un code inconnu s'affiche tel quel.
export const VERIFICATIONS_LABELS = {
  prorogation_ecrite: 'Prorogation écrite obtenue',
  attestation_visite: 'Attestation de visite de site',
  plis_separes: 'Plis séparés ou pli unique — confirmé par téléphone',
}

export const TYPES_CAUTION = [
  ['provisoire', 'Caution provisoire (soumission)'],
  ['definitive', 'Caution définitive'],
]

/** `true` si `dateValidite` s'achève AVANT `dateReference` (ouverture des
    plis). Comparaison de JOURS calendaires, jamais d'heures. `false` dès
    qu'une des deux dates manque : on ne signale pas ce qu'on ne sait pas. */
export function expireAvant(dateValidite, dateReference) {
  if (!dateValidite || !dateReference) return false
  const a = new Date(dateValidite)
  const b = new Date(dateReference)
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return false
  const jour = (d) => Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())
  return jour(a) < jour(b)
}

/** Les vérifications OBLIGATOIRES encore ouvertes. */
export function verificationsOuvertes(verifications) {
  return (verifications || []).filter((v) => v.obligatoire && !v.fait)
}

/** Motif AFFICHABLE du blocage du dépôt, `null` si rien ne bloque. */
export function motifBlocageDepot(verifications) {
  const premiere = verificationsOuvertes(verifications)[0]
  if (!premiere) return null
  return premiere.libelle || VERIFICATIONS_LABELS[premiere.code] || premiere.code || 'vérification obligatoire'
}

/** Cautions ET pièces dont la validité s'achève avant l'ouverture des plis. */
export function elementsExpires({ cautions = [], pieces = [], dateOuverture }) {
  return [
    ...cautions
      .filter((c) => expireAvant(c.date_validite, dateOuverture))
      .map((c) => ({
        cle: `caution-${c.id}`,
        libelle: c.libelle || TYPES_CAUTION.find(([t]) => t === c.type)?.[1] || c.type,
        date: c.date_validite,
      })),
    ...pieces
      .filter((p) => expireAvant(p.valide_jusqu_au, dateOuverture))
      .map((p) => ({
        cle: `piece-${p.id}`,
        libelle: p.libelle || p.code,
        date: p.valide_jusqu_au,
      })),
  ]
}
