/* ============================================================================
   AOF107 (2/3) — logique PURE de `ExportQR.jsx`, extraite dans ce fichier
   voisin : `react-refresh/only-export-components` (HMR de dev) exige qu'un
   fichier de COMPOSANT n'exporte que des composants. Ces fonctions n'en sont
   pas — `ExportQR.jsx` les importe pour son propre usage. Comportement
   inchangé (déplacement mécanique, corrections structurelles ESLint).
   ========================================================================== */

export const MAX_CARACTERES_LIGNE = 78

/** Retour à la ligne PUR, sans dépendance — coupe aux espaces. */
export function envelopperTexte(texte, maxCaracteres = MAX_CARACTERES_LIGNE) {
  const mots = String(texte ?? '').trim().split(/\s+/).filter(Boolean)
  if (mots.length === 0) return ['']
  const lignes = []
  let courante = ''
  for (const mot of mots) {
    const essai = courante ? `${courante} ${mot}` : mot
    if (essai.length > maxCaracteres && courante) {
      lignes.push(courante)
      courante = mot
    } else {
      courante = essai
    }
  }
  if (courante) lignes.push(courante)
  return lignes
}

/** Les lignes FINALES du bloc « liste numérotée », déjà enveloppées. */
export function construireLignesExport(questions = [], maxCaracteres = MAX_CARACTERES_LIGNE) {
  const lignes = []
  questions.forEach((q, i) => {
    const entete = `${i + 1}. Repère ${q.repere} — ${q.texte ?? ''}`
    lignes.push(...envelopperTexte(entete, maxCaracteres))
  })
  return lignes
}

/** Champs RÉELLEMENT rendus dans l'export, nommés par repère — c'est ce que
 * le contrôle de vocabulaire interroge (jamais la réponse/décision interne,
 * qui ne sort pas dans cet export). */
export function champsAControler(questions = []) {
  const champs = {}
  for (const q of questions) {
    if (q.texte) champs[`Repère ${q.repere}`] = q.texte
  }
  return champs
}
