/* ============================================================================
   NTMKT8 — EnqueteBuilder : manipulation PURE du tableau `questions` JSON
   (testable au node). Forme backend (`apps.compta.services.
   valider_questions_enquete`) : {id, type, libelle, options, obligatoire,
   condition: {question_id, valeur} | null}.
   ========================================================================== */

export function emptyQuestion(index) {
  return {
    id: `q${index}`, type: 'texte', libelle: '', options: [],
    obligatoire: false, condition: null,
  }
}

export function addQuestion(questions) {
  return [...(questions || []), emptyQuestion((questions || []).length + 1)]
}

export function removeQuestion(questions, index) {
  return (questions || []).filter((_, i) => i !== index)
}

export function updateQuestion(questions, index, patch) {
  return (questions || []).map((q, i) => (i === index ? { ...q, ...patch } : q))
}

// Options texte libre (une par ligne) ↔ tableau, pour le champ `choix`.
export function optionsFromText(text) {
  return String(text || '').split('\n').map(s => s.trim()).filter(Boolean)
}
export function optionsToText(options) {
  return (options || []).join('\n')
}
