/* ============================================================================
   NTMKT3 — Panneau comparatif A/B : logique PURE (testable au node).
   ----------------------------------------------------------------------------
   Regroupe la trace `EnvoiCampagne` (XMKT2, champ `variante_ab` ∈
   {'a','b',''}) en 3 lots — variante A, variante B, reste (hors test ou
   envoyé après décision du gagnant) — avec les taux d'ouverture/clic par lot.
   ========================================================================== */

function statLot(envois) {
  const total = envois.length
  const ouverts = envois.filter(e => e.statut === 'ouvert' || e.statut === 'clique'
    || e.ouvert_le).length
  const cliques = envois.filter(e => e.statut === 'clique' || e.clique_le).length
  const pct = (n) => (total ? Math.round((n / total) * 1000) / 10 : 0)
  return {
    total, ouverts, cliques,
    taux_ouverture_pct: pct(ouverts), taux_clic_pct: pct(cliques),
  }
}

export function computeAbComparatif(envois) {
  const list = envois || []
  const a = list.filter(e => e.variante_ab === 'a')
  const b = list.filter(e => e.variante_ab === 'b')
  const reste = list.filter(e => e.variante_ab !== 'a' && e.variante_ab !== 'b')
  return { a: statLot(a), b: statLot(b), reste: statLot(reste) }
}
