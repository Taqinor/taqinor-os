import { useState, useRef, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { queryAgent, clearMessages, loadChatHistory, clearChatHistory } from '../../features/ia/store/iaSlice'

const SUGGESTIONS = [
  'Quels produits sont en rupture de stock ?',
  'Quel est le chiffre d\'affaires du mois ?',
  'Combien de clients actifs avons-nous ?',
  'Quels sont les 5 produits les plus vendus ?',
  'Affiche les factures impayées',
]

export default function AgentChat() {
  const dispatch = useDispatch()
  const { messages, agentLoading, agentError } = useSelector((s) => s.ia)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Charge l'historique Redis au montage du composant
  useEffect(() => {
    dispatch(loadChatHistory())
  }, [dispatch])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentLoading])

  const handleSubmit = (e) => {
    e.preventDefault()
    const q = input.trim()
    if (!q || agentLoading) return
    dispatch(queryAgent(q))
    setInput('')
  }

  const handleSuggestion = (text) => {
    if (agentLoading) return
    dispatch(queryAgent(text))
    inputRef.current?.focus()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="agent-page">

      {/* ── Header ── */}
      <div className="agent-header">
        <div className="agent-header-left">
          <div className="agent-avatar-lg">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
            </svg>
          </div>
          <div>
            <h2 className="agent-title">Agent IA Conversationnel</h2>
            <span className="agent-subtitle">Groq · llama-3.3-70b · Données en temps réel</span>
          </div>
        </div>
        {messages.length > 0 && (
          <button className="btn btn-sm btn-outline" onClick={() => dispatch(clearChatHistory())}>
            Nouvelle conversation
          </button>
        )}
      </div>

      {/* ── Zone messages ── */}
      <div className="agent-messages">

        {messages.length === 0 && !agentLoading && (
          <div className="agent-empty">
            <div className="agent-empty-icon">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <h3 className="agent-empty-title">Posez une question sur vos données</h3>
            <p className="agent-empty-desc">
              L'agent analyse votre base de données en temps réel et répond en français.
            </p>
            <div className="agent-suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="agent-suggestion-chip" onClick={() => handleSuggestion(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`agent-msg agent-msg-${msg.role}`}>
            {msg.role === 'agent' && (
              <div className="agent-msg-avatar">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
                </svg>
              </div>
            )}
            <div className="agent-msg-body">
              <p className="agent-msg-text">{msg.content}</p>
              {msg.sql_query && (
                <details className="agent-sql">
                  <summary>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
                    </svg>
                    Requête SQL générée
                  </summary>
                  <pre className="agent-sql-code"><code>{msg.sql_query}</code></pre>
                </details>
              )}
            </div>
          </div>
        ))}

        {agentLoading && (
          <div className="agent-msg agent-msg-agent">
            <div className="agent-msg-avatar">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="12" cy="12" r="3" />
                <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
              </svg>
            </div>
            <div className="agent-msg-body">
              <div className="agent-typing">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}

        {agentError && (
          <div className="page-error" style={{ margin: '0 0 1rem' }}>
            Erreur : {typeof agentError === 'string' ? agentError : JSON.stringify(agentError)}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input ── */}
      <div className="agent-input-area">
        {messages.length > 0 && !agentLoading && (
          <div className="agent-suggestions agent-suggestions-inline">
            {SUGGESTIONS.slice(0, 3).map((s) => (
              <button key={s} className="agent-suggestion-chip agent-suggestion-chip-sm" onClick={() => handleSuggestion(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
        <form className="agent-input-row" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            className="agent-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Posez votre question en français..."
            disabled={agentLoading}
            autoComplete="off"
          />
          <button
            className="agent-send-btn"
            type="submit"
            disabled={agentLoading || !input.trim()}
            title="Envoyer"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </form>
        <p className="agent-disclaimer">
          L'agent peut faire des erreurs. Vérifiez les informations importantes.
        </p>
      </div>
    </div>
  )
}
