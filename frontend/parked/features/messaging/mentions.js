// Helpers PURS pour l'autocomplétion @mention (testés en .mjs).

// Détecte un token @mention en cours de frappe à la position du curseur.
// Renvoie { query, start } si le curseur suit un "@mot" (lettres/chiffres/._-),
// précédé d'un début de ligne ou d'un espace ; sinon null.
export function activeMention(text, caret) {
  if (text == null) return null
  const upto = text.slice(0, caret)
  const m = /(^|\s)@([\w.-]*)$/.exec(upto)
  if (!m) return null
  return { query: m[2], start: caret - m[2].length - 1 }
}

// Remplace le token @query (à partir de `start`) par "@label " et renvoie le
// nouveau texte + la nouvelle position du curseur.
export function insertMention(text, start, queryLen, label) {
  const before = text.slice(0, start)
  const after = text.slice(start + 1 + queryLen)
  const inserted = `@${label} `
  return { text: before + inserted + after, caret: before.length + inserted.length }
}

// Filtre les membres selon la requête (insensible aux accents/casse).
const norm = (s) => String(s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export function filterMembers(members, query, limit = 8) {
  const q = norm(query)
  const out = (members || []).filter((m) => {
    if (!q) return true
    return norm(m.label).includes(q) || norm(m.username).includes(q)
  })
  return out.slice(0, limit)
}

// Construit le tableau MessageMention attendu par l'API à partir du corps et de
// la liste des membres mentionnés (par étiquette exacte "@label").
export function extractMentions(body, members) {
  const ids = []
  for (const m of members || []) {
    const label = m.label || m.username
    if (label && body.includes(`@${label}`)) ids.push(m.id ?? Number(m.value))
  }
  return [...new Set(ids)].filter((x) => x != null && !Number.isNaN(x))
}
