import { useEffect, useState } from 'react'
import PageHeader from '../../components/layout/PageHeader'
import { Card, CardContent, Switch, Spinner, toast } from '../../ui'
import notificationsApi from '../../api/notificationsApi'
import {
  pushSupported, subscribeToPush, unsubscribeFromPush,
} from '../../features/pwa/pushSubscribe'

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

// N92 — Opt-in Web Push par appareil. Additif : si le navigateur ne supporte
// pas le push, ou si le serveur n'a pas de clés VAPID configurées, le toggle
// reste un NO-OP (un message explique pourquoi). N'altère aucune préférence
// d'événement existante.
function PushToggle() {
  const [enabled, setEnabled] = useState(false)
  const [busy, setBusy] = useState(false)
  const supported = pushSupported()

  // Reflète l'état réel de l'abonnement de cet appareil au montage.
  useEffect(() => {
    let active = true
    if (!supported) return undefined
    navigator.serviceWorker?.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => { if (active) setEnabled(Boolean(sub)) })
      .catch(() => { /* best-effort : reste désactivé */ })
    return () => { active = false }
  }, [supported])

  const onToggle = async (value) => {
    setBusy(true)
    try {
      if (value) {
        const res = await subscribeToPush()
        if (res.ok) {
          setEnabled(true)
          toast.success('Notifications push activées sur cet appareil.')
        } else if (res.reason === 'unconfigured') {
          toast.error('Le push n’est pas encore configuré côté serveur.')
        } else if (res.reason === 'denied') {
          toast.error('Permission de notifications refusée.')
        } else if (res.reason === 'unsupported') {
          toast.error('Cet appareil ne prend pas en charge le push.')
        } else {
          toast.error('Activation du push impossible.')
        }
      } else {
        await unsubscribeFromPush()
        setEnabled(false)
        toast.success('Notifications push désactivées sur cet appareil.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardContent>
        <div className="np-push-row">
          <div>
            <strong>Activer les notifications push sur cet appareil</strong>
            <p className="np-note">
              {supported
                ? 'Recevez les alertes même quand l’app est fermée. Réglage propre à cet appareil.'
                : 'Cet appareil ou ce navigateur ne prend pas en charge les notifications push.'}
            </p>
          </div>
          <Switch
            checked={enabled}
            disabled={!supported || busy}
            onCheckedChange={onToggle}
            aria-label="Activer les notifications push sur cet appareil" />
        </div>
      </CardContent>
    </Card>
  )
}

export default function NotificationsPreferences() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [savingKey, setSavingKey] = useState('')
  // VX212(a) — deep-link « Régler » depuis une notif (cloche) :
  // `/parametres/notifications#<event_type>` doit ouvrir DIRECTEMENT la
  // bonne ligne. `highlighted` = event_type mis en évidence temporairement.
  const [highlighted, setHighlighted] = useState('')

  useEffect(() => {
    notificationsApi.getPreferences()
      .then((r) => setRows(Array.isArray(r.data) ? r.data : []))
      .catch(() => toast.error('Préférences indisponibles.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (loading || rows.length === 0) return
    const hash = (window.location.hash || '').replace(/^#/, '')
    if (!hash) return
    const el = document.getElementById(`np-row-${hash}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setHighlighted(hash)
    const t = setTimeout(() => setHighlighted(''), 3000)
    return () => clearTimeout(t)
  }, [loading, rows])

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
                  <tr key={r.event_type} id={`np-row-${r.event_type}`}
                      style={highlighted === r.event_type
                        ? { outline: '2px solid var(--primary, #2563eb)', outlineOffset: '-2px' }
                        : undefined}>
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
      <PushToggle />
    </div>
  )
}
