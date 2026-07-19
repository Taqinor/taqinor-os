import { useEffect, useState } from 'react'

import voipApi from '../../api/voipApi'

/* ============================================================================
   WIR160 — « Mes identifiants » SIP de l'utilisateur courant (chacun les
   siens ; posés côté serveur). Le secret est write-only côté backend : jamais
   renvoyé, on ne le pré-remplit donc pas — le laisser vide conserve l'existant.
   ========================================================================== */

export default function MesIdentifiantsPage() {
  const [identifiantSip, setIdentifiantSip] = useState('')
  const [secret, setSecret] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    voipApi
      .getMesIdentifiants()
      .then((res) => {
        if (alive) setIdentifiantSip(res.data?.identifiant_sip || '')
      })
      .catch(() => {
        if (alive) setError('Impossible de charger vos identifiants.')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  async function enregistrer(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      // Le secret n'est envoyé que s'il a été (re)saisi (write-only côté backend).
      const payload = { identifiant_sip: identifiantSip }
      if (secret) payload.secret = secret
      await voipApi.updateMesIdentifiants(payload)
      setSecret('')
      setMessage('Identifiants enregistrés.')
    } catch {
      setError('Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="voip-identifiants">Chargement…</div>

  return (
    <form className="voip-identifiants" data-testid="voip-identifiants" onSubmit={enregistrer} noValidate>
      <label>
        Identifiant SIP
        <input
          type="text"
          value={identifiantSip}
          onChange={(e) => setIdentifiantSip(e.target.value)}
          placeholder="ex. 1001"
          autoComplete="username"
        />
      </label>
      <label>
        Secret SIP
        <input
          type="password"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          placeholder="Laisser vide pour conserver l'actuel"
          autoComplete="new-password"
        />
      </label>
      {message && <p className="voip-identifiants__ok" role="status">{message}</p>}
      {error && <p className="voip-identifiants__error" role="alert">{error}</p>}
      <button type="submit" disabled={saving}>Enregistrer</button>
    </form>
  )
}
