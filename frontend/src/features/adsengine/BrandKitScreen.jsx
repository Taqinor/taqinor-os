import { useEffect, useState, useCallback } from 'react'
import { Palette, Save } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   PUB83 — Écran « Kit de marque » (singleton par société).
   ----------------------------------------------------------------------------
   Logo / couleurs / zones de sécurité / polices persistés, consommés par le
   TemplatedAdapter côté backend (au lieu d'un payload de marque ad hoc). Édition
   simple d'un OneToOne : on charge le kit (ou on le crée au premier
   enregistrement), puis on le met à jour. Aucun secret exposé (logo = clé MinIO).
   ========================================================================== */

const EMPTY = { name: '', logo_key: '', primary: '', secondary: '', fonts: '' }

function fromRecord(rec) {
  const colors = rec.colors || {}
  return {
    id: rec.id,
    name: rec.name || '',
    logo_key: rec.logo_key || '',
    primary: colors.primary || '',
    secondary: colors.secondary || '',
    fonts: (rec.fonts || []).join(', '),
  }
}

function toPayload(form) {
  return {
    name: form.name,
    logo_key: form.logo_key,
    colors: { primary: form.primary, secondary: form.secondary },
    fonts: form.fonts.split(',').map(s => s.trim()).filter(Boolean),
  }
}

export default function BrandKitScreen() {
  const [form, setForm] = useState(EMPTY)
  const [kitId, setKitId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.brandKit.list()
      .then(r => {
        const rows = Array.isArray(r.data) ? r.data : (r.data?.results || [])
        if (rows.length > 0) {
          const rec = fromRecord(rows[0])
          setForm(rec)
          setKitId(rec.id)
        }
      })
      .catch(() => setErr('Chargement du kit de marque impossible.'))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const setField = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const save = async (e) => {
    e.preventDefault()
    setBusy(true); setErr(''); setMsg('')
    try {
      const payload = toPayload(form)
      if (kitId) {
        await adsengineApi.brandKit.update(kitId, payload)
      } else {
        const r = await adsengineApi.brandKit.create(payload)
        setKitId(r.data?.id ?? null)
      }
      setMsg('Kit de marque enregistré.')
    } catch {
      setErr('Enregistrement impossible.')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p data-testid="ae-brandkit-loading">Chargement…</p>

  return (
    <div className="p-4" data-testid="ae-brandkit-screen">
      <h1 className="h4 d-flex align-items-center gap-2">
        <Palette size={20} aria-hidden="true" /> Kit de marque
      </h1>
      <p className="text-muted">
        Logo, couleurs, zones de sécurité et polices utilisés par la génération
        créative (Templated).
      </p>

      {msg && <div className="alert alert-success" data-testid="ae-brandkit-msg">{msg}</div>}
      {err && <div className="alert alert-danger" data-testid="ae-brandkit-err">{err}</div>}

      <form onSubmit={save} data-testid="ae-brandkit-form" noValidate className="card p-3">
        <div className="row g-2">
          <div className="col-md-6">
            <label className="form-label">Nom du kit</label>
            <input
              className="form-control" data-testid="ae-brandkit-name"
              value={form.name} onChange={e => setField('name', e.target.value)} />
          </div>
          <div className="col-md-6">
            <label className="form-label">Clé logo (MinIO)</label>
            <input
              className="form-control" data-testid="ae-brandkit-logo"
              value={form.logo_key}
              onChange={e => setField('logo_key', e.target.value)} />
          </div>
          <div className="col-md-3">
            <label className="form-label">Couleur primaire</label>
            <input
              className="form-control" data-testid="ae-brandkit-primary"
              value={form.primary}
              onChange={e => setField('primary', e.target.value)} />
          </div>
          <div className="col-md-3">
            <label className="form-label">Couleur secondaire</label>
            <input
              className="form-control" data-testid="ae-brandkit-secondary"
              value={form.secondary}
              onChange={e => setField('secondary', e.target.value)} />
          </div>
          <div className="col-md-6">
            <label className="form-label">Polices (séparées par des virgules)</label>
            <input
              className="form-control" data-testid="ae-brandkit-fonts"
              value={form.fonts}
              onChange={e => setField('fonts', e.target.value)} />
          </div>
        </div>
        <div className="mt-3">
          <button
            type="submit" className="btn btn-primary"
            data-testid="ae-brandkit-save" disabled={busy}>
            <Save size={15} aria-hidden="true" /> Enregistrer
          </button>
        </div>
      </form>
    </div>
  )
}
