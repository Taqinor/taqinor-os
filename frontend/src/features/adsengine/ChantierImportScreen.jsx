import { useState } from 'react'
import { Camera, Upload } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   PUB73 — Écran « Importer une photo de chantier » (créathèque).
   ----------------------------------------------------------------------------
   Les techniciens uploadent déjà des photos géotaguées ; les meilleures
   n'atteignaient jamais la bibliothèque créative. On sélectionne une photo (par
   chantier + pièce jointe) et on la propose à la créathèque comme asset de
   provenance « chantier ». Le backend BLOQUE sans consentement client (PUB75) :
   le refus est affiché tel quel (« sans consentement → refus expliqué »).
   ========================================================================== */

const EMPTY = {
  chantier_id: '', attachment_id: '', client_id: '',
  puissance_kwc: '', ville: '', note: '',
}

export default function ChantierImportScreen() {
  const [form, setForm] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const setField = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr(''); setMsg('')
    try {
      const payload = { ...form }
      if (!payload.puissance_kwc) delete payload.puissance_kwc
      const r = await adsengineApi.chantierImport.importPhoto(payload)
      setMsg(r.data?.message || 'Photo importée dans la créathèque.')
      setForm(EMPTY)
    } catch (e2) {
      // Refus EXPLIQUÉ (ex. consentement manquant) renvoyé par le backend.
      setErr(e2?.response?.data?.detail || 'Import impossible.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="p-4" data-testid="ae-chantier-import-screen">
      <h1 className="h4 d-flex align-items-center gap-2">
        <Camera size={20} aria-hidden="true" /> Importer une photo de chantier
      </h1>
      <p className="text-muted">
        Proposez une photo de chantier à la créathèque. L'import est bloqué sans
        consentement client (CNDP) — un asset « client réel » ne se diffuse jamais
        sans accord signé.
      </p>

      {msg && <div className="alert alert-success" data-testid="ae-chantier-import-msg">{msg}</div>}
      {err && <div className="alert alert-danger" data-testid="ae-chantier-import-err">{err}</div>}

      <form onSubmit={submit} data-testid="ae-chantier-import-form" noValidate className="card p-3">
        <div className="row g-2">
          <div className="col-md-4">
            <label className="form-label">ID chantier</label>
            <input
              className="form-control" data-testid="ae-chantier-import-chantier"
              value={form.chantier_id}
              onChange={e => setField('chantier_id', e.target.value)} required />
          </div>
          <div className="col-md-4">
            <label className="form-label">ID pièce jointe (photo)</label>
            <input
              className="form-control" data-testid="ae-chantier-import-attachment"
              value={form.attachment_id}
              onChange={e => setField('attachment_id', e.target.value)} required />
          </div>
          <div className="col-md-4">
            <label className="form-label">ID client</label>
            <input
              className="form-control" data-testid="ae-chantier-import-client"
              value={form.client_id}
              onChange={e => setField('client_id', e.target.value)} required />
          </div>
          <div className="col-md-3">
            <label className="form-label">Puissance (kWc)</label>
            <input
              className="form-control" data-testid="ae-chantier-import-kwc"
              value={form.puissance_kwc}
              onChange={e => setField('puissance_kwc', e.target.value)} />
          </div>
          <div className="col-md-3">
            <label className="form-label">Ville</label>
            <input
              className="form-control" data-testid="ae-chantier-import-ville"
              value={form.ville}
              onChange={e => setField('ville', e.target.value)} />
          </div>
        </div>
        <div className="mt-3">
          <button
            type="submit" className="btn btn-primary"
            data-testid="ae-chantier-import-submit" disabled={busy}>
            <Upload size={15} aria-hidden="true" /> Proposer à la créathèque
          </button>
        </div>
      </form>
    </div>
  )
}
