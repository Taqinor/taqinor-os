/* ============================================================================
   AOF181 — Règles pures de conformité du CPS (verdicts, blocage, valeurs).
   ----------------------------------------------------------------------------
   Séparé de `ConformiteTable.jsx` pour que le composant n'exporte QUE des
   composants (react-refresh/only-export-components) — comportement inchangé,
   déplacement structurel uniquement. **Aucun chiffre de conformité n'est
   calculé ici** (garde AOF94) : ces fonctions ne font que LIRE et METTRE EN
   FORME ce que le serveur a déjà tranché.
   ========================================================================== */

export const CONFORME = 'conforme'
export const NON_CONFORME = 'non_conforme'
export const NON_EVALUE = 'non_evalue'

/** Statut de conformité TEL QUE LE SERVEUR le donne (`conformite.statut` ou
    `statut_conformite`), `non_evalue` à défaut. Jamais déduit d'une
    comparaison de valeurs. */
export function statutConformite(exigence) {
  return exigence?.conformite?.statut || exigence?.statut_conformite || NON_EVALUE
}

/** Sévérité d'AFFICHAGE (clé de `STATUT_CONTROLE`), ou `null` quand le serveur
    n'a pas évalué la clause — un « non évalué » n'est ni vert ni rouge. */
export function severiteAffichee(exigence) {
  const statut = statutConformite(exigence)
  if (statut === CONFORME) return 'ok'
  if (statut === NON_CONFORME) return exigence?.bloquant ? 'bloquant' : 'avertissement'
  return null
}

/** Les clauses BLOQUANTES que le serveur déclare non satisfaites. */
export function exigencesBloquantes(exigences) {
  return (exigences || []).filter(
    (e) => e.bloquant && statutConformite(e) === NON_CONFORME,
  )
}

/** Motif AFFICHABLE du blocage de `pret_a_deposer`, `null` si rien ne bloque. */
export function motifBlocageDepot(exigences) {
  const premiere = exigencesBloquantes(exigences)[0]
  if (!premiere) return null
  return premiere.conformite?.message
    || premiere.libelle
    || premiere.code
    || 'exigence bloquante non satisfaite'
}

/** Valeur EXIGÉE, assemblée en texte à partir de ce que porte la clause.
    Assemblage de chaînes uniquement — aucune arithmétique, aucun arrondi. */
export function valeurExigee(exigence) {
  if (!exigence) return '—'
  if (exigence.valeur_texte) return exigence.valeur_texte
  const unite = exigence.unite ? ` ${exigence.unite}` : ''
  const min = exigence.valeur_min
  const max = exigence.valeur_max
  if (min != null && min !== '' && max != null && max !== '') {
    return `${min} – ${max}${unite}`
  }
  const seule = [exigence.valeur, min, max].find((v) => v != null && v !== '')
  if (seule == null) return '—'
  const prefixe = exigence.type === 'plafond' ? '≤ ' : exigence.type === 'plancher' ? '≥ ' : ''
  return `${prefixe}${seule}${unite}`
}
