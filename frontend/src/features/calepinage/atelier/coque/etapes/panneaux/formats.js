// Étape « Panneaux » — les formats de la ligne d'un modèle et de la date du soleil (fr-FR).

import { formatNumber } from '../../../../../../lib/format'

const fr = (n, max = 2) => formatNumber(n, { maxDecimals: max })

/** La ligne sous le nom d'un modèle : puissance et cotes de la fiche servie, jamais une valeur supposée. */
export function ligneModule(module) {
  if (!module) return ''
  const parts = []
  if (module.pmaxWc > 0) parts.push(`${fr(module.pmaxWc, 0)} Wc`)
  if (module.longueurMm > 0 && module.largeurMm > 0) {
    parts.push(`${fr(module.longueurMm / 1000)} × ${fr(module.largeurMm / 1000)} m`)
  }
  return parts.join(' · ')
}

const NOMBRE_ET_UNITE = /^(≈\s*)?(\d(?:[\d\s,.]*\d)?)\s+(\S.*)$/

/** ACAL1829 — `{ valeur, unite }` d'un texte « nombre unité » (« 6,96 kWc », « ≈ 82 % ») ; `unite` vaut `''` quand le
    texte n'a pas cette forme (la valeur est alors le texte entier). */
export function scinderUnite(texte) {
  const m = NOMBRE_ET_UNITE.exec(String(texte ?? ''))
  return m ? { valeur: `${m[1] ?? ''}${m[2]}`, unite: m[3] } : { valeur: String(texte ?? ''), unite: '' }
}

/** « Jour mois » d'une date `AAAA-MM-JJ` du champ date du constructeur (« 21 décembre »). */
export function jourMois(date) {
  const m = /^\d{4}-(\d{2})-(\d{2})$/.exec(date ?? '')
  if (!m) return ''
  return new Date(Date.UTC(2028, Number(m[1]) - 1, Number(m[2])))
    .toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', timeZone: 'UTC' })
}
