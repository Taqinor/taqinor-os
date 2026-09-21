// S12 — Helpers PURS du module Discuter, extraits du slice pour être testés
// avec node:test (*.test.mjs). Aucune dépendance React/Redux/axios ici.

// Trie les conversations : non-lues d'abord, puis par dernier message le plus
// récent (les conversations sans message passent en fin).
export function sortConversations(list) {
  return [...(list || [])].sort((a, b) => {
    const ua = a?.unread_count > 0 ? 1 : 0
    const ub = b?.unread_count > 0 ? 1 : 0
    if (ua !== ub) return ub - ua
    const ta = a?.last_message?.created_at || a?.updated_at || ''
    const tb = b?.last_message?.created_at || b?.updated_at || ''
    if (ta === tb) return 0
    return ta > tb ? -1 : 1
  })
}

// Insère / met à jour une conversation dans la liste (par id), puis re-trie.
export function upsertConversation(list, conv) {
  if (!conv) return list || []
  const next = [...(list || [])]
  const i = next.findIndex((c) => c.id === conv.id)
  if (i === -1) next.push(conv)
  else next[i] = { ...next[i], ...conv }
  return sortConversations(next)
}

// Total des non-lus (somme des unread_count). Source de vérité du badge si
// l'endpoint dédié n'a pas (encore) répondu.
export function totalUnread(list) {
  return (list || []).reduce((sum, c) => sum + (c?.unread_count || 0), 0)
}

// Fusionne une page de messages PLUS ANCIENS (scroll-up) en tête de la liste,
// en dédupliquant par id et en gardant l'ordre chronologique croissant
// (le plus ancien en premier — l'UI rend du haut vers le bas).
export function mergeOlderMessages(existing, olderPage) {
  return dedupeById([...(toAsc(olderPage)), ...(existing || [])])
}

// Ajoute des messages NOUVEAUX (poll / envoi) en fin de liste, dédupliqués.
export function mergeNewerMessages(existing, newer) {
  return dedupeById([...(existing || []), ...(toAsc(newer))])
}

// Remplace / insère un seul message (édition, suppression douce, envoi optimiste
// confirmé). Garde l'ordre existant ; insère en fin si nouveau.
export function upsertMessage(existing, msg) {
  if (!msg) return existing || []
  const next = [...(existing || [])]
  const i = next.findIndex((m) => m.id === msg.id)
  if (i === -1) next.push(msg)
  else next[i] = { ...next[i], ...msg }
  return next
}

export function removeMessage(existing, id) {
  return (existing || []).filter((m) => m.id !== id)
}

// Une API DRF renvoie le plus récent d'abord ; nos vues affichent le plus
// ancien en haut. On normalise toujours en ordre croissant par created_at.
export function toAsc(page) {
  const arr = Array.isArray(page) ? [...page] : page?.results ? [...page.results] : []
  return arr.sort((a, b) => {
    const ta = a?.created_at || ''
    const tb = b?.created_at || ''
    if (ta === tb) return (a?.id || 0) - (b?.id || 0)
    return ta > tb ? 1 : -1
  })
}

export function dedupeById(arr) {
  const seen = new Set()
  const out = []
  for (const m of arr || []) {
    if (m == null) continue
    if (seen.has(m.id)) {
      // Conserve la version la plus récente (déjà placée) en la fusionnant.
      const idx = out.findIndex((x) => x.id === m.id)
      if (idx !== -1) out[idx] = { ...out[idx], ...m }
      continue
    }
    seen.add(m.id)
    out.push(m)
  }
  return out
}

// Bascule une réaction emoji d'un message pour l'utilisateur courant (toggle
// optimiste local, en miroir du comportement serveur).
export function toggleReactionLocal(message, emoji, userId) {
  if (!message) return message
  const reactions = Array.isArray(message.reactions) ? [...message.reactions] : []
  const i = reactions.findIndex((r) => r.emoji === emoji)
  if (i === -1) {
    reactions.push({ emoji, count: 1, user_ids: [userId] })
  } else {
    const r = { ...reactions[i] }
    const users = new Set(r.user_ids || [])
    if (users.has(userId)) {
      users.delete(userId)
    } else {
      users.add(userId)
    }
    r.user_ids = [...users]
    r.count = r.user_ids.length
    if (r.count === 0) reactions.splice(i, 1)
    else reactions[i] = r
  }
  return { ...message, reactions }
}
