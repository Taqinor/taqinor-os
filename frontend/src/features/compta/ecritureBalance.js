/* ============================================================================
   UX4 — Aide pure au contrôle d'équilibre d'une écriture comptable.
   ----------------------------------------------------------------------------
   Une écriture est enregistrable UNIQUEMENT si la somme des débits égale la
   somme des crédits (à un cent près) et qu'elle porte au moins deux lignes non
   nulles. Logique pure (aucune dépendance React) → testable en isolation et
   réutilisable pour bloquer le bouton « Enregistrer » tant que c'est déséquilibré.
   ========================================================================== */

// Coerce une saisie (nombre | chaîne fr/en | vide) en nombre fini, sinon 0.
function num(v) {
  if (v === null || v === undefined || v === '') return 0
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0
  const n = Number(String(v).replace(/\s/g, '').replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

/** Somme des débits d'un tableau de lignes { debit, credit }. */
export function totalDebit(lignes = []) {
  return lignes.reduce((s, l) => s + num(l.debit), 0)
}

/** Somme des crédits d'un tableau de lignes { debit, credit }. */
export function totalCredit(lignes = []) {
  return lignes.reduce((s, l) => s + num(l.credit), 0)
}

/** Écart débit − crédit (positif = trop de débit, négatif = trop de crédit). */
export function ecart(lignes = []) {
  return Math.round((totalDebit(lignes) - totalCredit(lignes)) * 100) / 100
}

/**
 * Une écriture est équilibrée si débits == crédits (tolérance 1 cent), qu'il y
 * a au moins deux lignes portant un compte, et que le total mouvementé n'est
 * pas nul (une écriture toute à zéro n'est pas « équilibrée » au sens métier).
 */
export function estEquilibree(lignes = []) {
  const withCompte = lignes.filter((l) => l && l.compte)
  if (withCompte.length < 2) return false
  const total = totalDebit(lignes) + totalCredit(lignes)
  if (total === 0) return false
  return Math.abs(ecart(lignes)) < 0.01
}

export default estEquilibree
