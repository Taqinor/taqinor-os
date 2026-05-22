import { useState, useRef, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { queryAgent, clearMessages } from '../../features/ia/store/iaSlice'

/**
 * Interface de chat avec l'Agent SQL conversationnel.
 * TODO Phase 3 Sem. 5 : connecter au vrai Agent LangChain.
 */
export default function AgentChat() {
  const dispatch = useDispatch()
  const { messages, agentLoading, agentError } = useSelector((s) => s.ia)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e) => {
    e.preventDefault()
    const q = input.trim()
    if (!q) return
    dispatch(queryAgent(q))
    setInput('')
  }

  return (
    <div className="chat-page">
      <div className="chat-header">
        <h2>Agent IA — Questions sur vos données</h2>
        <button className="btn btn-sm btn-outline" onClick={() => dispatch(clearMessages())}>
          Réinitialiser
        </button>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>💡 Exemples de questions :</p>
            <ul>
              <li>« Quel est le chiffre d'affaires du mois ? »</li>
              <li>« Quels produits sont en rupture de stock ? »</li>
              <li>« Combien de devis ont été acceptés ce trimestre ? »</li>
            </ul>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble chat-bubble-${msg.role}`}>
            <p>{msg.content}</p>
            {msg.sql_query && (
              <details className="chat-sql">
                <summary>Requête SQL générée</summary>
                <pre><code>{msg.sql_query}</code></pre>
              </details>
            )}
          </div>
        ))}

        {agentLoading && (
          <div className="chat-bubble chat-bubble-agent">
            <span className="typing-indicator">● ● ●</span>
          </div>
        )}

        {agentError && (
          <p className="page-error">Erreur : {JSON.stringify(agentError)}</p>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-row" onSubmit={handleSubmit}>
        <input
          className="chat-input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Posez votre question en langage naturel..."
          disabled={agentLoading}
        />
        <button className="btn btn-primary" type="submit" disabled={agentLoading || !input.trim()}>
          Envoyer
        </button>
      </form>
    </div>
  )
}
