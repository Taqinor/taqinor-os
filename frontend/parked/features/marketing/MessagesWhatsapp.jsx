import { useEffect, useState, useCallback } from 'react'
import marketingApi from '../../api/marketingApi'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   PACT108 — Journal des messages WhatsApp entrants (FG207).
   ----------------------------------------------------------------------------
   `MessageWhatsAppEntrantViewSet` (route `/marketing/messages-whatsapp/`) est
   un `ReadOnlyModelViewSet` : chaque message entrant capturé par le webhook
   Meta (gated — NO-OP tant que le jeton WhatsApp Business n'est pas
   provisionné) crée déjà un lead brouillon côté serveur (`crm.services`,
   jamais un import direct des modèles crm). Aucun écran ne consultait ce
   journal. LECTURE SEULE STRICTE : aucune action d'écriture n'est ajoutée
   côté client sur une ressource que le serveur expose en lecture seule —
   distinct de l'aperçu sortant avant `wa.me` câblé ailleurs.
   ========================================================================== */

export default function MessagesWhatsapp() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.messagesWhatsapp.list()
      .then(r => setMessages(marketingApi.unwrapList(r)))
      .catch(() => setMessages([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  return (
    <div className="page">
      <div className="page-header">
        <h2>Messages WhatsApp entrants</h2>
      </div>
      <p style={{ color: '#64748b', margin: '0 0 1rem' }}>
        Journal en lecture seule des messages capturés par le webhook Meta.
        Chaque message crée ou rattache déjà un lead brouillon côté serveur.
      </p>

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="wa-messages-table">
            <thead>
              <tr>
                <th>Reçu le</th><th>Expéditeur</th><th>Profil</th>
                <th>Message</th><th>Lead</th><th>Traité</th>
              </tr>
            </thead>
            <tbody>
              {messages.map(m => (
                <tr key={m.id} data-testid="wa-message-row">
                  <td>{m.date_reception ? formatDateTime(m.date_reception) : '—'}</td>
                  <td>{m.expediteur}</td>
                  <td>{m.nom_profil || '—'}</td>
                  <td>{m.texte || '—'}</td>
                  <td>{m.lead_id != null ? `#${m.lead_id}` : '—'}</td>
                  <td>
                    <span className="badge" style={{
                      background: m.traite ? '#dcfce7' : '#f1f5f9',
                      color: m.traite ? '#166534' : '#64748b' }}>
                      {m.traite ? 'Traité' : 'Non traité'}
                    </span>
                  </td>
                </tr>
              ))}
              {messages.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun message WhatsApp reçu
                </td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}
