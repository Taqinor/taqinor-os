import { useEffect, useState, useCallback } from 'react'
import { ShieldCheck, Plus, Ban, MessageCircle } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   PUB75 — Écran « Consentements » (registre image/témoignage, CNDP loi 09-08).
   ----------------------------------------------------------------------------
   `policy.py` interdit les FAUX témoignages, mais rien ne vérifiait le
   consentement RÉEL d'un vrai visage / chantier / nom. Cet écran est l'UI de
   collecte SIMPLE : on enregistre un consentement recueilli (portées
   photo / vidéo / témoignage / géo, date, expiration) et on peut générer un
   lien WhatsApp signable à envoyer au client. La révocation retire aussitôt les
   assets liés de la rotation (garanti côté serveur — `policy.revoke_consent`).
   Aucun jugement automatique : on ne fait qu'ENREGISTRER un accord humain.
   ========================================================================== */

const SCOPES = [
  ['portee_photo', 'Photo'],
  ['portee_video', 'Vidéo'],
  ['portee_temoignage', 'Témoignage (nom/citation)'],
  ['portee_geo', 'Localisation / chantier'],
]

const CANAUX = [
  ['whatsapp', 'Lien WhatsApp signé'],
  ['papier', 'Formulaire papier'],
  ['email', 'Email'],
  ['verbal', 'Accord verbal consigné'],
  ['autre', 'Autre'],
]

const EMPTY = {
  client_nom: '', canal: 'whatsapp',
  portee_photo: false, portee_video: false,
  portee_temoignage: false, portee_geo: false,
  date_consentement: '', expiration: '', note: '',
}

function statusOf(rec) {
  if (rec.revoked_at) return { label: 'Révoqué', tone: 'danger' }
  if (rec.is_active === false) return { label: 'Expiré', tone: 'warning' }
  return { label: 'Actif', tone: 'success' }
}

// Lien WhatsApp signable simple : message FR pré-rempli demandant l'accord.
function whatsappLink(rec) {
  const msg = `Bonjour ${rec.client_nom || ''}, confirmez-vous votre accord `
    + `pour l'utilisation de votre image / témoignage par Taqinor ? `
    + `(référence ${rec.reference || rec.id})`
  return `https://wa.me/?text=${encodeURIComponent(msg)}`
}

export default function ConsentScreen() {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [draft, setDraft] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.consents.list()
      .then(r => setRecords(Array.isArray(r.data) ? r.data : (r.data?.results || [])))
      .catch(() => setErr('Chargement des consentements impossible.'))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const setField = (key, value) => setDraft(d => ({ ...d, [key]: value }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr(''); setMsg('')
    try {
      const payload = { ...draft }
      if (!payload.expiration) delete payload.expiration
      await adsengineApi.consents.create(payload)
      setMsg('Consentement enregistré.')
      setDraft(EMPTY)
      load()
    } catch {
      setErr('Enregistrement impossible (nom et date requis).')
    } finally {
      setBusy(false)
    }
  }

  const revoke = async (id) => {
    setBusy(true); setErr(''); setMsg('')
    try {
      const r = await adsengineApi.consents.revoke(id)
      const n = r.data?.assets_retires ?? 0
      setMsg(`Consentement révoqué (${n} asset(s) retiré(s) de la rotation).`)
      load()
    } catch {
      setErr('Révocation impossible.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="p-4" data-testid="ae-consent-screen">
      <h1 className="h4 d-flex align-items-center gap-2">
        <ShieldCheck size={20} aria-hidden="true" /> Consentements (CNDP)
      </h1>
      <p className="text-muted">
        Registre des accords image / témoignage. Un asset montrant un client réel
        ne peut être diffusé sans un consentement actif couvrant la portée requise.
      </p>

      {msg && <div className="alert alert-success" data-testid="ae-consent-msg">{msg}</div>}
      {err && <div className="alert alert-danger" data-testid="ae-consent-err">{err}</div>}

      <form onSubmit={submit} data-testid="ae-consent-form" noValidate className="card p-3 mb-4">
        <div className="row g-2">
          <div className="col-md-6">
            <label className="form-label">Nom du client / de la personne</label>
            <input
              className="form-control" data-testid="ae-consent-nom"
              value={draft.client_nom}
              onChange={e => setField('client_nom', e.target.value)} required />
          </div>
          <div className="col-md-3">
            <label className="form-label">Canal</label>
            <select
              className="form-select" data-testid="ae-consent-canal"
              value={draft.canal} onChange={e => setField('canal', e.target.value)}>
              {CANAUX.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div className="col-md-3">
            <label className="form-label">Date de recueil</label>
            <input
              type="date" className="form-control" data-testid="ae-consent-date"
              value={draft.date_consentement}
              onChange={e => setField('date_consentement', e.target.value)} required />
          </div>
          <div className="col-md-3">
            <label className="form-label">Expiration (optionnelle)</label>
            <input
              type="date" className="form-control" data-testid="ae-consent-expiration"
              value={draft.expiration}
              onChange={e => setField('expiration', e.target.value)} />
          </div>
          <div className="col-12">
            <span className="form-label d-block">Portées consenties</span>
            {SCOPES.map(([key, label]) => (
              <label key={key} className="form-check form-check-inline">
                <input
                  type="checkbox" className="form-check-input"
                  data-testid={`ae-consent-${key}`}
                  checked={draft[key]}
                  onChange={e => setField(key, e.target.checked)} />
                <span className="form-check-label">{label}</span>
              </label>
            ))}
          </div>
        </div>
        <div className="mt-3">
          <button
            type="submit" className="btn btn-primary"
            data-testid="ae-consent-submit" disabled={busy}>
            <Plus size={15} aria-hidden="true" /> Enregistrer le consentement
          </button>
        </div>
      </form>

      {loading ? (
        <p data-testid="ae-consent-loading">Chargement…</p>
      ) : records.length === 0 ? (
        <p className="text-muted" data-testid="ae-consent-empty">
          Aucun consentement enregistré.
        </p>
      ) : (
        <table className="table" data-testid="ae-consent-table">
          <thead>
            <tr>
              <th>Client</th><th>Portées</th><th>Statut</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {records.map(rec => {
              const st = statusOf(rec)
              return (
                <tr key={rec.id} data-testid={`ae-consent-row-${rec.id}`}>
                  <td>{rec.client_nom}</td>
                  <td>{(rec.scopes || []).join(', ') || '—'}</td>
                  <td>
                    <span
                      className={`badge bg-${st.tone}`}
                      data-testid={`ae-consent-status-${rec.id}`}>
                      {st.label}
                    </span>
                  </td>
                  <td className="d-flex gap-2">
                    <a
                      className="btn btn-sm btn-light"
                      data-testid={`ae-consent-wa-${rec.id}`}
                      href={whatsappLink(rec)}
                      target="_blank" rel="noreferrer">
                      <MessageCircle size={14} aria-hidden="true" /> Lien WhatsApp
                    </a>
                    {!rec.revoked_at && (
                      <button
                        className="btn btn-sm btn-outline-danger"
                        data-testid={`ae-consent-revoke-${rec.id}`}
                        onClick={() => revoke(rec.id)} disabled={busy}>
                        <Ban size={14} aria-hidden="true" /> Révoquer
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
