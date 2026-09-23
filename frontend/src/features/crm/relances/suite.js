// CAD17 — la SUITE annoncée d'une réponse, DÉRIVÉE du moteur.
//
// Cause commune de CAD1, CAD3, CAD16 et CAD97 : les phrases « suite » du
// panneau « Fait » étaient écrites PAR CADENCE dans un objet littéral d'écran,
// alors que ce que fait le serveur dépend aussi du LIBELLÉ de la touche
// (barreau, étape de filet, geste de visite), de son RANG (la dernière ne fait
// naître aucune suivante) et de l'état du devis. L'écran promettait donc des
// suites qui n'existaient pas.
//
// Désormais la promesse vient du SERVEUR : chaque touche porte `suites`
// (contrat `relance_etape_v2`, `apps/crm/suite_touche.py`) — pour chaque
// réponse proposée, la liste des CODES D'EFFET que le moteur produira. Ce
// module ne fait que traduire chaque code en UNE phrase (`suite_phrases.json`).
// La garde `apps/crm/tests_cad17_parite_promesse_effet.py` rejoue chaque
// réponse de chaque cadence et vérifie l'effet réel de chaque code.
//
// Sans `suites` (touche déjà traitée, ancienne réponse serveur), AUCUNE phrase
// n'est inventée : mieux vaut se taire que promettre une suite fausse.
import PHRASES from './suite_phrases.json'

/** Clé de la réponse « Fait — passer à la suite » (aucune issue). */
export const CLE_SANS_ISSUE = 'sans_issue'

/** La phrase d'UN code d'effet, ou '' s'il est inconnu de l'écran. */
export function phraseEffet(code) {
  return PHRASES.effets[code] ?? ''
}

/** Les codes connus de l'écran (la garde back les compare au serveur). */
export function codesConnus() {
  return Object.keys(PHRASES.effets)
}

/** La clé sous laquelle le serveur range la suite d'une réponse du panneau :
 *  la CLÉ de réponse du client (`reponse`, CAD-A) quand il y en a une, sinon
 *  l'ISSUE (`outcome`) — « aucune issue » devenant `sans_issue`. */
export function cleSuite(reponse) {
  if (!reponse) return null
  if (reponse.reponse) return reponse.reponse
  const issue = reponse.outcome ?? ''
  if (issue === '') return CLE_SANS_ISSUE
  // « intéressé » et « joint » ont le MÊME effet moteur (même table d'arrêt
  // `CADENCES_ARRETEES_PAR_ISSUE`, mêmes récepteurs) : le serveur n'annonce
  // que `joint`.
  if (issue === 'interesse') return 'joint'
  return issue
}

/** Les codes d'effet que le serveur annonce pour `reponse` sur `etape`. */
export function codesSuite(etape, reponse) {
  const cle = cleSuite(reponse)
  if (!cle) return []
  const codes = etape?.suites?.[cle]
  return Array.isArray(codes) ? codes : []
}

/** La phrase complète annoncée sous les réponses : les phrases des codes
 *  d'effet (dérivées du moteur), suivies de la précision propre à la réponse
 *  (`precision` — un geste d'ÉCRAN, jamais un effet moteur : « l'accusé vous
 *  est proposé juste après », « cochez ci-dessous… »). */
export function suiteAnnoncee(etape, reponse) {
  const morceaux = codesSuite(etape, reponse).map(phraseEffet).filter(Boolean)
  if (reponse?.precision) morceaux.push(reponse.precision)
  return morceaux.join(' ')
}
