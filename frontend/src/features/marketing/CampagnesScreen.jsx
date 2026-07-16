import { useEffect, useState, useCallback } from 'react'
import comptaApi from '../../api/comptaApi'

/* ============================================================================
   FG201/XMKT10/XMKT34 — Éditeur de campagnes marketing (email/SMS/WhatsApp).
   ----------------------------------------------------------------------------
   Liste + formulaire de création/édition (nom, canal, objet, corps). XMKT34 :
   le bouton « Générer avec l'IA » n'apparaît QUE si la sonde
   `campagnes/generer-ia-disponible/` renvoie configured=true (clé LLM
   présente) — sans clé, AUCUNE trace UI. La génération remplit objet/corps
   comme SUGGESTION éditable : rien n'est sauvegardé ni envoyé sans action
   explicite de l'utilisateur. XMKT10 : le canal WhatsApp est sélectionnable
   (envoi gated côté backend — file wa.me sans jeton BSP).
   ========================================================================== */

const CANAUX = [
  { key: 'email', label: 'Email' },
  { key: 'sms', label: 'SMS' },
  { key: 'whatsapp', label: 'WhatsApp' },
]

const EMPTY_FORM = { nom: '', canal: 'email', objet: '', corps: '' }

export default function CampagnesScreen() {
  const [campagnes, setCampagnes] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null) // null = création
  const [form, setForm] = useState(EMPTY_FORM)
  const [err, setErr] = useState('')
  // XMKT34 — gating : false tant que la sonde n'a pas confirmé la clé.
  const [iaDisponible, setIaDisponible] = useState(false)
  const [iaOptions, setIaOptions] = useState(
    { segment_label: '', offre: '', instruction: '', langue: 'fr' })
  const [iaLoading, setIaLoading] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    comptaApi.campagnes.list()
      .then(r => setCampagnes(Array.isArray(r.data) ? r.data : (r.data.results || [])))
      .catch(() => setCampagnes([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  useEffect(() => {
    // Sonde gating IA (aucun appel LLM) : sans clé → bouton jamais rendu.
    comptaApi.campagnes.genererIaDisponible()
      .then(r => setIaDisponible(!!r.data?.configured))
      .catch(() => setIaDisponible(false))
  }, [])

  const setField = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const startEdit = (c) => {
    setEditingId(c.id)
    setForm({ nom: c.nom || '', canal: c.canal || 'email',
      objet: c.objet || '', corps: c.corps || '' })
  }

  const reset = () => { setEditingId(null); setForm(EMPTY_FORM); setErr('') }

  const save = async (e) => {
    e.preventDefault()
    setErr('')
    try {
      if (editingId) await comptaApi.campagnes.update(editingId, form)
      else await comptaApi.campagnes.create(form)
      reset()
      load()
    } catch {
      setErr('Enregistrement impossible.')
    }
  }

  const genererIa = async () => {
    setIaLoading(true)
    setErr('')
    try {
      const r = await comptaApi.campagnes.genererIa(iaOptions)
      if (r.data?.ok) {
        // SUGGESTION éditable : remplit les champs, ne sauvegarde rien.
        setForm(f => ({
          ...f,
          objet: r.data.objet || f.objet,
          corps: r.data.corps || f.corps,
        }))
      } else {
        setErr('Génération indisponible.')
      }
    } catch {
      setErr('Génération impossible.')
    } finally {
      setIaLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Campagnes marketing</h2>
      </div>

      <form onSubmit={save} data-testid="campagne-form"
        style={{ display: 'grid', gap: '0.6rem', maxWidth: 720,
          marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
          <input className="form-input" data-testid="campagne-nom"
            placeholder="Nom de la campagne" required
            value={form.nom} onChange={setField('nom')}
            style={{ flex: '2 1 220px' }} />
          <select className="form-input" data-testid="campagne-canal"
            value={form.canal} onChange={setField('canal')}
            style={{ flex: '1 1 140px' }}>
            {CANAUX.map(c => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
          </select>
        </div>
        <input className="form-input" data-testid="campagne-objet"
          placeholder="Objet (email)" value={form.objet}
          onChange={setField('objet')} />
        <textarea className="form-input" data-testid="campagne-corps"
          placeholder="Corps du message" rows={5} value={form.corps}
          onChange={setField('corps')} />

        {iaDisponible && (
          <fieldset data-testid="campagne-ia-panel"
            style={{ border: '1px dashed #cbd5e1', borderRadius: 8,
              padding: '0.6rem', display: 'grid', gap: '0.5rem' }}>
            <legend style={{ fontSize: '0.8rem', color: '#475569',
              padding: '0 6px' }}>
              Assistant IA (suggestion éditable — jamais envoyée seule)
            </legend>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <input className="form-input" data-testid="campagne-ia-segment"
                placeholder="Segment ciblé (ex. leads froids résidentiel)"
                value={iaOptions.segment_label}
                onChange={e => setIaOptions(o => ({ ...o, segment_label: e.target.value }))}
                style={{ flex: '1 1 220px' }} />
              <input className="form-input" data-testid="campagne-ia-offre"
                placeholder="Offre / contexte (ex. -20% panneaux)"
                value={iaOptions.offre}
                onChange={e => setIaOptions(o => ({ ...o, offre: e.target.value }))}
                style={{ flex: '1 1 220px' }} />
              <select className="form-input" data-testid="campagne-ia-langue"
                value={iaOptions.langue}
                onChange={e => setIaOptions(o => ({ ...o, langue: e.target.value }))}
                style={{ flex: '0 1 120px' }}>
                <option value="fr">Français</option>
                <option value="ar">Arabe</option>
              </select>
            </div>
            <input className="form-input" data-testid="campagne-ia-instruction"
              placeholder="Consigne (ton, longueur, réécriture…)"
              value={iaOptions.instruction}
              onChange={e => setIaOptions(o => ({ ...o, instruction: e.target.value }))} />
            <div>
              <button type="button" className="btn btn-light"
                data-testid="campagne-ia-generer"
                disabled={iaLoading} onClick={genererIa}>
                {iaLoading ? 'Génération…' : "Générer avec l'IA"}
              </button>
            </div>
          </fieldset>
        )}

        {err && <p style={{ color: '#dc2626', margin: 0 }}>{err}</p>}
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button type="submit" className="btn btn-primary"
            data-testid="campagne-save">
            {editingId ? 'Enregistrer' : 'Créer la campagne'}
          </button>
          {editingId && (
            <button type="button" className="btn btn-light" onClick={reset}>
              Annuler
            </button>
          )}
        </div>
      </form>

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="campagnes-table">
            <thead>
              <tr>
                <th>Nom</th><th>Canal</th><th>Statut</th><th>Envoyés</th><th />
              </tr>
            </thead>
            <tbody>
              {campagnes.map(c => (
                <tr key={c.id}>
                  <td>{c.nom}</td>
                  <td>{c.canal_display || c.canal}</td>
                  <td>{c.statut_display || c.statut}</td>
                  <td>{c.nb_envois ?? 0}</td>
                  <td>
                    <button className="btn btn-light" type="button"
                      onClick={() => startEdit(c)}>Éditer</button>
                  </td>
                </tr>
              ))}
              {campagnes.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center',
                  color: '#64748b' }}>Aucune campagne</td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}
