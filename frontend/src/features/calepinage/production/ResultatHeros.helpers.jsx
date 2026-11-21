import { formatNumber, formatPercent } from '../../../lib/format'

/* ACAL443 — formats « non calculée » / « non publié » partagés (jamais 0). */

/** Une grandeur absente du serveur s'écrit « non calculée », jamais « — » nu ni 0. */
export function nonCalculee(valeur, rendu) {
  return valeur === null || valeur === undefined ? 'non calculée' : rendu(valeur)
}

/** ACAL52 — grandeur d'un résultat INCOMPLET : « — non publié », motif en infobulle. */
export function nonPublie(motif) {
  return <span title={motif || undefined} data-testid="acal52-non-publie">— non publié</span>
}

export const kwh = (v) => nonCalculee(v, (x) => `${formatNumber(x, { decimals: 0 })} kWh`)
export const pourcentagePerf = (v) => nonCalculee(v, (x) => formatPercent(x * 100, { decimals: 1 }))
export const kwhParKwc = (v) => nonCalculee(v, (x) => `${formatNumber(x, { decimals: 1 })} kWh/kWc`)
