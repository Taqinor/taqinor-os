// Helpers PURS de formatage temporel pour le module Discuter (testés en .mjs).

// Horodatage court relatif pour la liste des conversations :
//   < 1 min  → "à l'instant"
//   < 60 min → "12 min"
//   aujourd'hui → "14:05"
//   hier     → "Hier"
//   < 7 j    → "3 j"
//   sinon    → "21/06"
export function shortTime(iso, now = new Date()) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const ms = now.getTime() - d.getTime()
  const min = Math.floor(ms / 60000)
  if (min < 1) return "à l'instant"
  if (min < 60) return `${min} min`
  const sameDay = d.toDateString() === now.toDateString()
  if (sameDay) {
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (d.toDateString() === yesterday.toDateString()) return 'Hier'
  const days = Math.floor(ms / 86400000)
  if (days < 7) return `${days} j`
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`
}

// Heure d'une bulle de message ("HH:MM").
export function bubbleTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// Étiquette d'une conversation : nom du canal, ou nom de l'autre membre d'un DM.
export function conversationTitle(conv, currentUserId) {
  if (!conv) return ''
  if (conv.kind === 'channel' || conv.name) return conv.name || 'Canal'
  const others = (conv.members || []).filter((m) => m.id !== currentUserId)
  if (others.length) return others.map((m) => displayName(m)).join(', ')
  return conv.title || 'Conversation'
}

export function displayName(user) {
  if (!user) return ''
  return (
    user.full_name ||
    [user.first_name, user.last_name].filter(Boolean).join(' ') ||
    user.username ||
    user.email ||
    ''
  )
}
