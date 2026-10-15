/* Doublure PARTAGÉE du placement `@roofpro/scene3d` des écrans Mode terrain et
   Ombrière (ENF19). Même transformation géométrique pure que le builder —
   x0/x1/y0/y1 moteur -> centre + emprise, pas inter-rangées MESURÉ,
   `nonMesure` — appliquée aux VRAIES tables/rangées de l'exemple de contrat
   `pose.json` : les assertions des écrans n'ont rien à changer. Le VRAI module
   reste exercé par ses propres tests (`apps/web/src/scripts/roofPro11/*.test.ts`). */

/**
 * @param plan  tables/rangées/modules renvoyés par le moteur.
 * @param opts  `aireTerrainM2`, `penteTerrainDeg`, `hauteurLibreM`…
 * @param cfg   `altitude` (z de chaque table), `pente` : 'siAbsente' (message
 *              seulement si la pente manque) ou 'toujours', `manqueFin` : message
 *              ajouté en dernier (ou null).
 */
export function champPoseMock(plan, opts, { altitude, pente, manqueFin = null }) {
  const tables = []
  let empriseTablesM2Calc = 0
  for (const t of plan?.tables ?? []) {
    const largeurM = Math.abs(t.x1 - t.x0)
    const profondeurM = Math.abs(t.y1 - t.y0)
    empriseTablesM2Calc += largeurM * profondeurM
    tables.push({
      cx: (t.x0 + t.x1) / 2,
      cy: (t.y0 + t.y1) / 2,
      largeurM,
      profondeurM,
      z: altitude,
      inclinaisonRad: 0,
      kit: typeof t.kit === 'string' ? t.kit : null,
    })
  }
  const nonMesure = []
  if (!tables.length) nonMesure.push('aucune table rendue par le moteur')
  if (pente === 'toujours' || !Number.isFinite(opts?.penteTerrainDeg)) {
    nonMesure.push('pente du terrain non renseignée : terrain rendu horizontal')
  }

  const y = Array.from(new Set((plan?.rangees ?? [])
    .map((r) => Number(r?.y0)).filter((v) => Number.isFinite(v)))).sort((a, b) => a - b)
  let pasInterRangeeM = null
  if (y.length >= 2) {
    let min = Infinity
    for (let i = 1; i < y.length; i += 1) min = Math.min(min, y[i] - y[i - 1])
    pasInterRangeeM = Number.isFinite(min) && min > 0 ? min : null
  }
  if (pasInterRangeeM === null) {
    nonMesure.push('pas inter-rangées non mesurable (moins de deux rangées posées)')
  }

  const aire = Number.isFinite(opts?.aireTerrainM2) ? opts.aireTerrainM2 : null
  let tauxOccupationCalc = null
  if (aire !== null && aire > 0 && tables.length) tauxOccupationCalc = empriseTablesM2Calc / aire
  else nonMesure.push('taux d’occupation non calculable (surface du terrain manquante)')
  if (manqueFin) nonMesure.push(manqueFin)

  return {
    tables,
    modules: Number.isFinite(plan?.modules) ? plan.modules : null,
    pasInterRangeeM,
    empriseTablesM2: empriseTablesM2Calc,
    tauxOccupation: tauxOccupationCalc,
    nonMesure,
  }
}
