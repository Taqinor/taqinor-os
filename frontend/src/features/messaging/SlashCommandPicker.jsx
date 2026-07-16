import { useEffect } from 'react'
import { Wand2 } from 'lucide-react'

/* XKB31 — Liste de suggestions slash-command, même forme que
   MentionAutocomplete (popover piloté par le parent : items déjà filtrés +
   index actif, clic/clavier remonte la sélection). Une commande
   `available: false` (action absente du registre de l'utilisateur) reste
   visible mais désactivée — jamais silencieusement masquée. */
export default function SlashCommandPicker({ items, activeIndex, onPick, onClose, listId, getOptionId }) {
  useEffect(() => {
    const onDoc = (e) => {
      if (!e.target.closest?.('.chat-slash-pop')) onClose?.()
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [onClose])

  if (!items?.length) return null

  return (
    <ul className="chat-slash-pop chat-mention-pop" role="listbox" aria-label="Commandes" id={listId}>
      {items.map((c, i) => (
        <li key={c.cmd} id={getOptionId?.(i)} role="option" aria-selected={i === activeIndex}>
          <button
            type="button"
            className={`chat-mention-item${i === activeIndex ? ' active' : ''}`}
            disabled={!c.available}
            aria-disabled={!c.available}
            onMouseDown={(e) => {
              e.preventDefault()
              if (c.available) onPick?.(c)
            }}
          >
            <Wand2 size={14} aria-hidden="true" />
            <span>
              <strong>{c.label}</strong>{' '}
              <span className="chat-slash-hint">{c.hint}</span>
              {!c.available && (
                <span className="chat-slash-unavailable"> (indisponible pour votre rôle)</span>
              )}
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}
