import { useEffect } from 'react'
import { Avatar, AvatarFallback, initials } from '../../ui'

/* S16 — Liste de suggestions @mention. Affichée par le Composer quand un token
   @ est en cours de frappe. Pilotée par le parent (membres déjà filtrés +
   index actif). Navigation clavier ↑/↓/Entrée/Échap gérée dans le Composer ;
   ici on rend la liste et on remonte la sélection au clic. */
export default function MentionAutocomplete({ items, activeIndex, onPick, onClose, listId, getOptionId }) {
  useEffect(() => {
    const onDoc = (e) => {
      if (!e.target.closest?.('.chat-mention-pop')) onClose?.()
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [onClose])

  if (!items?.length) return null

  return (
    <ul className="chat-mention-pop" role="listbox" aria-label="Membres à mentionner" id={listId}>
      {items.map((m, i) => (
        <li key={m.value ?? m.id} id={getOptionId?.(i)} role="option" aria-selected={i === activeIndex}>
          <button
            type="button"
            className={`chat-mention-item${i === activeIndex ? ' active' : ''}`}
            onMouseDown={(e) => { e.preventDefault(); onPick?.(m) }}
          >
            <Avatar className="size-6">
              <AvatarFallback>{initials(m.label) || '?'}</AvatarFallback>
            </Avatar>
            <span>{m.label}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}
