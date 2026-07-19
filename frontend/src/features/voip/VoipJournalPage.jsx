import { useCallback, useEffect, useState } from 'react'

import voipApi from '../../api/voipApi'

/* ============================================================================
   WIR160 — Journal d'appels + widget click-to-call. Composer un numéro et
   « Appeler » amorce un appel sortant (le backend refuse en 409 si le softphone
   n'est pas configuré/actif — message clair). Le journal liste les appels de la
   société (lecture seule ; la journalisation est orchestrée côté serveur).
   ========================================================================== */

export default function VoipJournalPage() {
  const [appels, setAppels] = useState([])
  const [loading, setLoading] = useState(true)
  const [numero, setNumero] = useState('')
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const charger = useCallback(() => {
    let alive = true
    voipApi
      .getAppels()
      .then((res) => {
        if (alive) setAppels(res.data?.results ?? res.data ?? [])
      })
      .catch(() => {
        if (alive) setError("Impossible de charger le journal d'appels.")
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => charger(), [charger])

  async function appeler(e) {
    e.preventDefault()
    const n = numero.trim()
    if (!n) { setError('Numéro requis.'); return }
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      await voipApi.appelSortant(n)
      setMessage(`Appel vers ${n} amorcé.`)
      setNumero('')
      charger()
    } catch (err) {
      if (err?.response?.status === 409) {
        setError('Softphone VoIP non configuré/actif — voir « Config société ».')
      } else {
        setError("Impossible d'amorcer l'appel.")
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="voip-journal" data-testid="voip-journal">
      <form className="voip-journal__dialer" onSubmit={appeler} noValidate>
        <input
          type="tel"
          value={numero}
          onChange={(e) => setNumero(e.target.value)}
          placeholder="Numéro à appeler"
          aria-label="Numéro à appeler"
        />
        <button type="submit" disabled={busy}>Appeler</button>
      </form>
      {message && <p className="voip-journal__ok" role="status">{message}</p>}
      {error && <p className="voip-journal__error" role="alert">{error}</p>}

      {loading ? (
        <p>Chargement…</p>
      ) : appels.length === 0 ? (
        <p>Aucun appel enregistré.</p>
      ) : (
        <table className="voip-journal__table">
          <thead>
            <tr>
              <th>Sens</th>
              <th>Numéro</th>
              <th>Contact</th>
              <th>Statut</th>
              <th>Début</th>
              <th>Durée</th>
            </tr>
          </thead>
          <tbody>
            {appels.map((a) => (
              <tr key={a.id}>
                <td>{a.direction}</td>
                <td>{a.numero}</td>
                <td>{a.cible?.libelle || '—'}</td>
                <td>{a.statut}{a.issue ? ` (${a.issue})` : ''}</td>
                <td>{a.started_at ? new Date(a.started_at).toLocaleString('fr-FR') : '—'}</td>
                <td>{a.duree_secondes != null ? `${a.duree_secondes}s` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
