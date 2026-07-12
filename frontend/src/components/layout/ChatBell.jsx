import { useEffect, useRef, useState } from 'react'
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

  // VX134(d) — le badge changeait de valeur à chaque poll de 30 s SANS AUCUN
  // signal visuel. Pulse UNIQUEMENT quand le total AUGMENTE (jamais à la
  // baisse après lecture, jamais quand le poll ne change rien).
  const prevTotalRef = useRef(total)
  const [pulsing, setPulsing] = useState(false)
  useEffect(() => {
    if (total > prevTotalRef.current) setPulsing(true)
    prevTotalRef.current = total
  }, [total])

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
      {total > 0 && (
        <span
          className={`nb-badge${pulsing ? ' nb-badge-pulse' : ''}`}
          onAnimationEnd={() => setPulsing(false)}
        >
          {total > 99 ? '99+' : total}
        </span>
      )}
    </button>
  )
}
