// Helpers purs (sans React) pour les champs personnalisés côté client.
// Testables en isolation (node --test) ; partagés par le renderer / l'admin.

export const FIELD_TYPES = ['text', 'number', 'date', 'choice', 'boolean']

export const TYPE_LABELS = {
  text: 'Texte', number: 'Nombre', date: 'Date',
  choice: 'Liste de choix', boolean: 'Oui / Non',
}

// Valeur par défaut affichée pour un type donné (avant saisie).
export function defaultValueFor(fieldType) {
  return fieldType === 'boolean' ? false : ''
}

// Construit le payload `custom_fields` à envoyer : ne garde que les clés
// connues (définitions), normalise les vides en null (sauf booléen).
export function buildCustomFieldsPayload(defs, values) {
  const out = {}
  for (const d of defs || []) {
    const raw = values?.[d.field_key]
    if (d.field_type === 'boolean') {
      out[d.field_key] = !!raw
    } else if (raw === '' || raw === undefined || raw === null) {
      out[d.field_key] = null
    } else {
      out[d.field_key] = raw
    }
  }
  return out
}

// Découpe une saisie multi-ligne en liste d'options (choice), sans doublon ni
// vide, ordre préservé.
export function parseChoices(text) {
  const seen = new Set()
  const out = []
  for (const line of String(text || '').split('\n')) {
    const s = line.trim()
    if (s && !seen.has(s)) { seen.add(s); out.push(s) }
  }
  return out
}

// Vrai si la définition de type 'choice' est valide (au moins une option).
export function isDefinitionComplete(draft) {
  if (!draft || !draft.label || !String(draft.label).trim()) return false
  if (!FIELD_TYPES.includes(draft.field_type)) return false
  if (draft.field_type === 'choice') {
    return parseChoices(draft.choices).length > 0
  }
  return true
}
