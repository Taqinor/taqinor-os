/* ============================================================================
   NTAGR8 — Alerte DAR (délai avant récolte) EN DIRECT pour les traitements
   phyto, miroir client de `apps.agriculture.models.check_dar_guard` — même
   patron que `AffectationDialog.controlePermis` : retour immédiat côté
   client, re-vérifié côté serveur à l'enregistrement.
   ========================================================================== */

// Miroir de `apps.agriculture.models.check_dar_guard` : retourne
// `{ ok: true }` ou `{ ok: false, message }`. Ne bloque jamais si le type
// n'est pas « traitement », si l'intrant n'a pas de DAR défini, ou si la
// campagne n'a aucune date de récolte connue.
export function checkDarAlert({ typeEtape, date, intrant, campagne }) {
  if (typeEtape !== 'traitement') return { ok: true }
  if (!intrant || intrant.delai_avant_recolte_jours == null) return { ok: true }
  if (!date) return { ok: true }
  const candidates = [campagne?.date_recolte_prevue, campagne?.date_recolte_reelle]
    .filter(Boolean)
  if (candidates.length === 0) return { ok: true }
  const dateRecolteContraignante = candidates.sort()[0]
  // Arithmétique en UTC pur à partir des composants "YYYY-MM-DD" — évite
  // tout décalage de fuseau horaire local (Date.UTC gère nativement le
  // débordement de mois/année quand on ajoute les jours de DAR).
  const [y, m, d] = date.split('-').map(Number)
  const limiteIso = new Date(
    Date.UTC(y, m - 1, d + Number(intrant.delai_avant_recolte_jours)),
  ).toISOString().slice(0, 10)
  if (limiteIso > dateRecolteContraignante) {
    const produit = intrant.matiere_active || intrant.produit_nom || `intrant #${intrant.id}`
    return {
      ok: false,
      message: (
        `Délai avant récolte (DAR) de ${intrant.delai_avant_recolte_jours} jour(s) `
        + `pour « ${produit} » appliqué le ${date} : dépasse la date de récolte `
        + `du ${dateRecolteContraignante}.`
      ),
    }
  }
  return { ok: true }
}
