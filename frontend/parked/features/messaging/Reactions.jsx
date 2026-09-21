import { SmilePlus } from 'lucide-react'
import {
  Popover, PopoverTrigger, PopoverContent,
} from '../../ui'

/* S18 — Réactions emoji. Jeu d'emojis CURATÉ (pas de bibliothèque de picker).
   Le backend renvoie `reactions` comme une liste PLATE de lignes
   { id, user, emoji, created_at } (une ligne par couple user+emoji). On agrège
   ici par emoji en puces { emoji, count, mine } où `mine` = il existe une ligne
   dont `user` est l'utilisateur courant. Cliquer une puce (ou un emoji du
   sélecteur) bascule cet emoji via `onToggle(emoji)`. */

const REACTION_SET = ['👍', '❤️', '😂', '🎉', '✅']

// Agrège la liste plate de réactions en puces ordonnées (par 1ère apparition).
function aggregateReactions(reactions, currentUserId) {
  const list = Array.isArray(reactions) ? reactions : []
  const order = []
  const map = new Map()
  for (const r of list) {
    if (!r || !r.emoji) continue
    if (!map.has(r.emoji)) {
      map.set(r.emoji, { emoji: r.emoji, count: 0, mine: false })
      order.push(r.emoji)
    }
    const agg = map.get(r.emoji)
    agg.count += 1
    if (currentUserId != null && String(r.user) === String(currentUserId)) {
      agg.mine = true
    }
  }
  return order.map((e) => map.get(e))
}

export default function Reactions({ reactions, currentUserId, onToggle }) {
  const chips = aggregateReactions(reactions, currentUserId)

  return (
    <div className="chat-reactions" data-testid="reactions">
      {chips.map((c) => (
        <button
          key={c.emoji}
          type="button"
          className={`chat-reaction-chip${c.mine ? ' mine' : ''}`}
          aria-pressed={c.mine}
          aria-label={`${c.emoji} ${c.count}${c.mine ? ' (vous avez réagi)' : ''}`}
          onClick={() => onToggle?.(c.emoji)}
        >
          <span className="chat-reaction-emoji" aria-hidden="true">{c.emoji}</span>
          <span className="chat-reaction-count">{c.count}</span>
        </button>
      ))}

      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            className="chat-reaction-add"
            aria-label="Ajouter une réaction"
          >
            <SmilePlus size={14} aria-hidden="true" />
          </button>
        </PopoverTrigger>
        <PopoverContent className="chat-reaction-picker" align="start">
          <div className="chat-reaction-picker-row" role="group" aria-label="Choisir une réaction">
            {REACTION_SET.map((emoji) => (
              <button
                key={emoji}
                type="button"
                className="chat-reaction-pick"
                aria-label={`Réagir avec ${emoji}`}
                onClick={() => onToggle?.(emoji)}
              >
                {emoji}
              </button>
            ))}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  )
}
