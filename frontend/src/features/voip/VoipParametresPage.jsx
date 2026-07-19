import { useEffect, useState } from 'react'

import voipApi from '../../api/voipApi'

/* ============================================================================
   WIR160 — Configuration VoIP DE LA société (singleton, réservé
   responsable/admin ; le backend re-vérifie). Fournisseur + serveur SIP +
   activation ; `est_configure` indique si le softphone est prêt.
   ========================================================================== */

export default function VoipParametresPage() {
  const [form, setForm] = useState({
    fournisseur: '', serveur_sip: '', actif: false,
  })
  const [estConfigure, setEstConfigure] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    voipApi
      .getParametres()
      .then((res) => {
        if (!alive) return
        const d = res.data || {}
        setForm({
          fournisseur: d.fournisseur || '',
          serveur_sip: d.serveur_sip || '',
          actif: !!d.actif,
        })
        setEstConfigure(!!d.est_configure)
      })
      .catch(() => {
        if (alive) setError('Impossible de charger la configuration VoIP.')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  async function enregistrer(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const res = await voipApi.updateParametres(form)
      setEstConfigure(!!res.data?.est_configure)
      setMessage('Configuration enregistrée.')
    } catch (err) {
      if (err?.response?.status === 403) {
        setError('Réservé au responsable / administrateur.')
      } else {
        setError('Enregistrement impossible.')
      }
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="voip-parametres">Chargement…</div>

  return (
    <form className="voip-parametres" data-testid="voip-parametres" onSubmit={enregistrer} noValidate>
      <p className="voip-parametres__statut">
        Softphone : {estConfigure ? 'configuré' : 'non configuré'}
      </p>
      <label>
        Fournisseur
        <input
          type="text"
          value={form.fournisseur}
          onChange={(e) => setField('fournisseur', e.target.value)}
          placeholder="ex. noop / twilio / 3cx"
        />
      </label>
      <label>
        Serveur SIP
        <input
          type="text"
          value={form.serveur_sip}
          onChange={(e) => setField('serveur_sip', e.target.value)}
          placeholder="sip.exemple.ma"
        />
      </label>
      <label className="voip-parametres__actif">
        <input
          type="checkbox"
          checked={form.actif}
          onChange={(e) => setField('actif', e.target.checked)}
        />
        Softphone actif
      </label>
      {message && <p className="voip-parametres__ok" role="status">{message}</p>}
      {error && <p className="voip-parametres__error" role="alert">{error}</p>}
      <button type="submit" disabled={saving}>Enregistrer</button>
    </form>
  )
}
