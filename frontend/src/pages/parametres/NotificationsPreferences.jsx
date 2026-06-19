import { useEffect, useState } from 'react'
import PageHeader from '../../components/layout/PageHeader'
import { Card, CardContent, Switch, Spinner, toast } from '../../ui'
import notificationsApi from '../../api/notificationsApi'

// N75 — Préférences de notifications par événement et par canal.
// Chaque ligne = un événement métier ; chaque colonne = un canal (in-app,
// WhatsApp, email). In-app est toujours disponible ; WhatsApp/email ne
// diffusent que si le canal correspondant est réellement configuré côté serveur
// (sinon no-op silencieux). Les préférences sont propres à l'utilisateur.
const CHANNELS = [
  { key: 'in_app', label: 'In-app' },
  { key: 'whatsapp', label: 'WhatsApp' },
  { key: 'email', label: 'Email' },
]

export default function NotificationsPreferences() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [savingKey, setSavingKey] = useState('')

  useEffect(() => {
    notificationsApi.getPreferences()
      .then((r) => setRows(Array.isArray(r.data) ? r.data : []))
      .catch(() => toast.error('Préférences indisponibles.'))
      .finally(() => setLoading(false))
  }, [])

  const toggle = (eventType, channel, value) => {
    // Optimiste : on applique localement, puis on persiste l'unique champ.
    setRows((prev) => prev.map((r) =>
      r.event_type === eventType ? { ...r, [channel]: value } : r))
    setSavingKey(`${eventType}:${channel}`)
    notificationsApi.savePreference(eventType, { [channel]: value })
      .catch(() => {
        toast.error('Échec de l’enregistrement.')
        // Revert en cas d'échec.
        setRows((prev) => prev.map((r) =>
          r.event_type === eventType ? { ...r, [channel]: !value } : r))
      })
      .finally(() => setSavingKey(''))
  }

  return (
    <div className="page">
      <PageHeader
        title="Préférences de notifications"
        subtitle="Choisissez comment être prévenu pour chaque événement." />
      <Card>
        <CardContent>
          {loading ? (
            <div className="np-loading"><Spinner /> Chargement…</div>
          ) : (
            <table className="np-table">
              <thead>
                <tr>
                  <th scope="col">Événement</th>
                  {CHANNELS.map((c) => (
                    <th key={c.key} scope="col" className="np-channel-head">
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.event_type}>
                    <td>{r.event_label}</td>
                    {CHANNELS.map((c) => (
                      <td key={c.key} className="np-channel-cell">
                        <Switch
                          checked={Boolean(r[c.key])}
                          disabled={savingKey === `${r.event_type}:${c.key}`}
                          onCheckedChange={(v) => toggle(r.event_type, c.key, v)}
                          aria-label={`${r.event_label} — ${c.label}`} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="np-note">
            Les notifications in-app sont toujours disponibles. WhatsApp et email
            ne sont envoyés que si le canal correspondant est configuré.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
