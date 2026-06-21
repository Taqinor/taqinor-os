import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { MessageSquare } from 'lucide-react'
import { fetchUnreadCount, selectUnreadTotal } from '../../features/messaging/store/messagingSlice'

// S13 — Icône de chat dans l'en-tête avec badge du total de non-lus (miroir de
// NotificationBell). Un clic ouvre /messages — c'est aussi la cible du deep-link
// des notifications push. Sonde le compteur toutes les 30 s, suspendu quand
// l'onglet est masqué.
export default function ChatBell() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const total = useSelector(selectUnreadTotal)

  useEffect(() => {
    const poll = () => {
      if (document.visibilityState === 'hidden') return
      dispatch(fetchUnreadCount())
    }
    poll()
    const iv = setInterval(poll, 30 * 1000)
    document.addEventListener('visibilitychange', poll)
    return () => {
      clearInterval(iv)
      document.removeEventListener('visibilitychange', poll)
    }
  }, [dispatch])

  return (
    <button
      type="button"
      className="nb-btn chat-bell"
      aria-label={`Messages (${total})`}
      onClick={() => navigate('/messages')}
    >
      <MessageSquare size={19} aria-hidden="true" />
      {total > 0 && <span className="nb-badge">{total > 99 ? '99+' : total}</span>}
    </button>
  )
}
