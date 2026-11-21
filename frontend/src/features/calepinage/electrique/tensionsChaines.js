import { formatNumber } from '../../../lib/format'

/* ACAL619 — la mise en forme française des tensions de chaîne servies par `evaluer-electrique`
   (`chaines[]`, contrat `calepinage_evaluation_electrique.json`). L'écran ne calcule ni ne compare
   rien : les nombres et les drapeaux `voc_froid_conforme` / `vmp_chaud_conforme` sont ceux du serveur. */

export const volts = (v) => (v === null || v === undefined ? 'non calculable' : `${formatNumber(v, { decimals: 0 })} V`)

/** Une chaîne dont une tension manque n'est jamais affichée avec un nombre inventé. */
export const estIndeterminee = (c) => c.voc_froid_v == null || c.vmp_chaud_v == null

/** « Chaîne 3 : 12 modules — Voc à froid 594 V / 1 000 V, Vmp à chaud 410 V ≥ démarrage 200 V ». */
export function phraseChaine(c) {
  if (estIndeterminee(c)) {
    return `Chaîne ${c.chaine} : tension non calculable : ${(c.indetermine ?? []).join(' ')}`.trim()
  }
  const limite = c.voc_froid_conforme === false ? ' (au-dessus de la limite)' : ''
  const signe = c.vmp_chaud_conforme === true ? '≥' : c.vmp_chaud_conforme === false ? '<' : null
  const demarrage = c.demarrage_v == null || signe === null
    ? ', démarrage non renseigné'
    : ` ${signe} démarrage ${volts(c.demarrage_v)}`
  return `Chaîne ${c.chaine} : ${c.nombre_modules} modules — Voc à froid ${volts(c.voc_froid_v)} / ${volts(c.voc_froid_limite_v)}${limite}, Vmp à chaud ${volts(c.vmp_chaud_v)}${demarrage}`
}

/** Les phrases des seules chaînes `numeros` (affectées dans la session), dans l'ordre du serveur. */
export const phrasesChaines = (chaines, numeros) => (Array.isArray(chaines) ? chaines : [])
  .filter((c) => numeros.has(c.chaine)).map(phraseChaine)
