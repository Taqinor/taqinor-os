/* NTMKT32 — logique pure du wizard « Créer une enquête NPS/personnalisée ».
 *
 * Chaque type prédéfini pré-remplit des questions ÉDITABLES (l'utilisateur
 * peut tout modifier avant publication) ; « personnalisé » démarre vide.
 */

export const TYPES_ENQUETE = [
  { key: 'nps', label: 'NPS pur' },
  { key: 'satisfaction_installation', label: 'Satisfaction post-installation' },
  { key: 'satisfaction_sav', label: 'Satisfaction SAV' },
  { key: 'personnalise', label: 'Personnalisé' },
]

function q(id, type, libelle, extra = {}) {
  return { id, type, libelle, obligatoire: true, ...extra }
}

const QUESTIONS_PAR_TYPE = {
  nps: [
    // White-label (SCA29) : jamais de marque en dur — libellé générique, éditable
    // avant publication (voir le commentaire d'en-tête du fichier).
    q('q1', 'nps', 'Sur une échelle de 0 à 10, recommanderiez-vous notre entreprise ?'),
  ],
  satisfaction_installation: [
    q('q1', 'nps', "Recommanderiez-vous notre équipe d'installation ?"),
    q('q2', 'echelle', 'Le respect du délai annoncé', { options: [1, 2, 3, 4, 5] }),
    q('q3', 'echelle', 'La propreté du chantier', { options: [1, 2, 3, 4, 5] }),
    q('q4', 'texte', "Un commentaire sur l'installation ?", { obligatoire: false }),
  ],
  satisfaction_sav: [
    q('q1', 'nps', 'Recommanderiez-vous notre SAV ?'),
    q('q2', 'echelle', 'La rapidité de prise en charge', { options: [1, 2, 3, 4, 5] }),
    q('q3', 'echelle', 'La résolution du problème', { options: [1, 2, 3, 4, 5] }),
    q('q4', 'texte', 'Un commentaire sur le SAV ?', { obligatoire: false }),
  ],
  personnalise: [],
}

export function emptyWizardState() {
  return { type: '', titre: '', questions: [], cible: { mode: '', ref: '' } }
}

export function choisirType(state, typeKey) {
  const questions = (QUESTIONS_PAR_TYPE[typeKey] || []).map(qq => ({ ...qq }))
  return { ...state, type: typeKey, questions }
}

export function majQuestion(state, index, patch) {
  return {
    ...state,
    questions: state.questions.map((qq, i) => (i === index ? { ...qq, ...patch } : qq)),
  }
}

export function peutPublier(state) {
  return !!state.type && state.titre.trim().length > 0 && state.questions.length > 0
}

export function buildPayload(state) {
  return { titre: state.titre, questions: state.questions }
}
