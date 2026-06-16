import { useEffect, useState, useCallback } from 'react'
import customFieldsApi from '../../api/customFieldsApi'

// Modules pilotables + libellés FR (identifiants en anglais côté serveur).
const MODULES = [
  { key: 'lead', label: 'Leads' },
  { key: 'client', label: 'Clients' },
  { key: 'produit', label: 'Produits' },
]

const TYPE_LABELS = {
  text: 'Texte', number: 'Nombre', date: 'Date',
  choice: 'Liste de choix', boolean: 'Oui / Non',
}

// Champs standard masquables par module (priorité aux champs marketing/
// techniques rarement utiles). On NE TOUCHE jamais au code du modèle natif :
// masquer = override réversible dans le registre.
const HIDEABLE_STANDARD = {
  lead: [
    ['utm_source', 'UTM source'],
    ['utm_medium', 'UTM medium'],
    ['utm_campaign', 'UTM campaign'],
    ['fbclid', 'Facebook click id'],
    ['consent', 'Consentement'],
  ],
  client: [
    ['rc', 'RC (Registre de Commerce)'],
    ['if_fiscal', 'IF (Identifiant Fiscal)'],
    ['cin', 'CIN'],
  ],
  produit: [
    ['seuil_alerte', "Seuil d'alerte"],
    ['garantie_production_mois', 'Garantie production (mois)'],
  ],
}

const TYPE_OPTIONS = Object.entries(TYPE_LABELS)

const emptyDraft = () => ({
  label: '', field_type: 'text', choices: '', required: false,
  show_in_list: false, show_in_filter: false,
})

export default function CustomFieldsAdmin() {
  const [module, setModule] = useState('lead')
  const [defs, setDefs] = useState([])
  const [hidden, setHidden] = useState([])  // [{id, field_key}]
  const [loading, setLoading] = useState(true)
  const [draft, setDraft] = useState(emptyDraft())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      const [d, h] = await Promise.all([
        customFieldsApi.listDefinitions(module),
        customFieldsApi.listHidden(module),
      ])
      setDefs((d.data.results ?? d.data).filter(x => x.module === module))
      setHidden((h.data.results ?? h.data).filter(x => x.module === module))
      setError(null)
    } catch {
      setError('Chargement impossible.')
    } finally {
      setLoading(false)
    }
  }, [module])

  useEffect(() => {
    let alive = true
    customFieldsApi.listDefinitions(module)
      .then((d) => { if (alive) setDefs((d.data.results ?? d.data).filter(x => x.module === module)) })
      .catch(() => {})
    customFieldsApi.listHidden(module)
      .then((h) => { if (alive) setHidden((h.data.results ?? h.data).filter(x => x.module === module)) })
      .catch(() => {})
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [module])

  const hiddenKeys = new Set(hidden.map(h => h.field_key))

  const addField = async () => {
    if (!draft.label.trim()) { setError('Le libellé est requis.'); return }
    // Question de portée (scope) — toujours bornée à la société.
    const ok = window.confirm(
      `Ajouter « ${draft.label.trim()} » et l'appliquer à tous les ` +
      `${MODULES.find(m => m.key === module).label.toLowerCase()} de la société ?`)
    if (!ok) return
    setBusy(true)
    setError(null)
    try {
      const payload = {
        module,
        label: draft.label.trim(),
        field_type: draft.field_type,
        required: draft.required,
        show_in_list: draft.show_in_list,
        show_in_filter: draft.show_in_filter,
        order: defs.length,
      }
      if (draft.field_type === 'choice') {
        payload.choices = draft.choices.split('\n').map(s => s.trim()).filter(Boolean)
      }
      await customFieldsApi.createDefinition(payload)
      setDraft(emptyDraft())
      await load()
    } catch (err) {
      const data = err?.response?.data
      setError(typeof data === 'object' ? JSON.stringify(data) : 'Création impossible.')
    } finally {
      setBusy(false)
    }
  }

  const removeField = async (d) => {
    if (!window.confirm(`Retirer « ${d.label} » ? Les valeurs déjà saisies sont conservées.`)) return
    setBusy(true)
    try { await customFieldsApi.deleteDefinition(d.id); await load() }
    finally { setBusy(false) }
  }

  const toggleDef = async (d, key) => {
    setBusy(true)
    try { await customFieldsApi.updateDefinition(d.id, { [key]: !d[key] }); await load() }
    finally { setBusy(false) }
  }

  const move = async (idx, dir) => {
    const next = idx + dir
    if (next < 0 || next >= defs.length) return
    const ids = defs.map(d => d.id)
    const tmp = ids[idx]; ids[idx] = ids[next]; ids[next] = tmp
    setBusy(true)
    try { await customFieldsApi.reorderDefinitions(ids); await load() }
    finally { setBusy(false) }
  }

  const toggleHidden = async (field_key) => {
    setBusy(true)
    try {
      const existing = hidden.find(h => h.field_key === field_key)
      if (existing) await customFieldsApi.unhideField(existing.id)
      else await customFieldsApi.hideField(module, field_key)
      await load()
    } finally { setBusy(false) }
  }

  const restore = async () => {
    if (!window.confirm(
      'Réinitialiser ce module par défaut ? Les champs standard masqués ' +
      'seront ré-affichés et les champs personnalisés archivés (les valeurs ' +
      'restent en base).')) return
    setBusy(true)
    try { await customFieldsApi.restoreDefaults(module); await load() }
    finally { setBusy(false) }
  }

  return (
    <div className="cfa">
      <div className="cfa-head">
        <div className="cfa-modules">
          {MODULES.map(m => (
            <button key={m.key} type="button"
              className={`cfa-tab${module === m.key ? ' active' : ''}`}
              onClick={() => setModule(m.key)}>{m.label}</button>
          ))}
        </div>
        <button type="button" className="btn btn-outline" onClick={restore} disabled={busy}>
          Réinitialiser par défaut
        </button>
      </div>

      {error && <div className="form-error-box">{error}</div>}

      {/* Définitions existantes */}
      {loading ? <p className="cfa-hint">Chargement…</p> : (
        <div className="cfa-list">
          {defs.length === 0 && <p className="cfa-hint">Aucun champ personnalisé.</p>}
          {defs.map((d, idx) => (
            <div className="cfa-row" key={d.id}>
              <div className="cfa-reorder">
                <button type="button" onClick={() => move(idx, -1)} disabled={idx === 0 || busy}>▲</button>
                <button type="button" onClick={() => move(idx, 1)} disabled={idx === defs.length - 1 || busy}>▼</button>
              </div>
              <div className="cfa-main">
                <div className="cfa-label">{d.label}</div>
                <div className="cfa-meta">{TYPE_LABELS[d.field_type] || d.field_type}
                  {d.field_type === 'choice' && d.choices?.length ? ` — ${d.choices.join(', ')}` : ''}
                  {' · '}<code>{d.field_key}</code></div>
              </div>
              <label className="cfa-chk"><input type="checkbox" checked={d.required}
                onChange={() => toggleDef(d, 'required')} disabled={busy} /> Obligatoire</label>
              <label className="cfa-chk"><input type="checkbox" checked={d.show_in_list}
                onChange={() => toggleDef(d, 'show_in_list')} disabled={busy} /> Liste</label>
              <label className="cfa-chk"><input type="checkbox" checked={d.show_in_filter}
                onChange={() => toggleDef(d, 'show_in_filter')} disabled={busy} /> Filtre</label>
              <button type="button" className="cfa-del" onClick={() => removeField(d)} disabled={busy}>Retirer</button>
            </div>
          ))}
        </div>
      )}

      {/* Ajout d'un champ */}
      <div className="cfa-add">
        <div className="cfa-add-title">Ajouter un champ</div>
        <div className="cfa-add-grid">
          <input className="form-control" placeholder="Libellé (ex : Numéro de compteur ONEE)"
            value={draft.label} onChange={e => setDraft({ ...draft, label: e.target.value })} />
          <select className="form-control" value={draft.field_type}
            onChange={e => setDraft({ ...draft, field_type: e.target.value })}>
            {TYPE_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        {draft.field_type === 'choice' && (
          <textarea className="form-control" rows={3} placeholder="Une option par ligne"
            value={draft.choices} onChange={e => setDraft({ ...draft, choices: e.target.value })} />
        )}
        <div className="cfa-add-opts">
          <label className="cfa-chk"><input type="checkbox" checked={draft.required}
            onChange={e => setDraft({ ...draft, required: e.target.checked })} /> Obligatoire</label>
          <label className="cfa-chk"><input type="checkbox" checked={draft.show_in_list}
            onChange={e => setDraft({ ...draft, show_in_list: e.target.checked })} /> Afficher en liste</label>
          <label className="cfa-chk"><input type="checkbox" checked={draft.show_in_filter}
            onChange={e => setDraft({ ...draft, show_in_filter: e.target.checked })} /> Filtrable</label>
          <button type="button" className="btn btn-primary" onClick={addField} disabled={busy}>
            Ajouter le champ
          </button>
        </div>
      </div>

      {/* Masquer des champs standard */}
      <div className="cfa-add">
        <div className="cfa-add-title">Masquer des champs standard</div>
        <div className="cfa-std">
          {(HIDEABLE_STANDARD[module] || []).map(([key, label]) => (
            <label className="cfa-chk" key={key}>
              <input type="checkbox" checked={hiddenKeys.has(key)}
                onChange={() => toggleHidden(key)} disabled={busy} />
              {label}
            </label>
          ))}
        </div>
      </div>

      <style>{`
        .cfa-head { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:1rem; flex-wrap:wrap; }
        .cfa-modules { display:flex; gap:.4rem; }
        .cfa-tab { padding:.4rem .9rem; border:1px solid #e2e8f0; background:#fff; border-radius:8px; cursor:pointer; font-size:13px; font-weight:600; color:#475569; }
        .cfa-tab.active { background:#1d4ed8; border-color:#1d4ed8; color:#fff; }
        .cfa-list { display:flex; flex-direction:column; gap:.5rem; margin-bottom:1.2rem; }
        .cfa-row { display:flex; align-items:center; gap:.75rem; padding:.6rem .75rem; border:1px solid #e2e8f0; border-radius:8px; flex-wrap:wrap; }
        .cfa-reorder { display:flex; flex-direction:column; gap:2px; }
        .cfa-reorder button { border:none; background:#f1f5f9; border-radius:4px; cursor:pointer; font-size:10px; line-height:1; padding:2px 5px; }
        .cfa-main { flex:1 1 220px; }
        .cfa-label { font-weight:600; font-size:14px; color:#1e293b; }
        .cfa-meta { font-size:11.5px; color:#64748b; }
        .cfa-meta code { background:#f1f5f9; padding:0 4px; border-radius:3px; }
        .cfa-chk { display:flex; align-items:center; gap:5px; font-size:12.5px; color:#475569; cursor:pointer; }
        .cfa-del { border:1px solid #fecaca; color:#dc2626; background:#fff; border-radius:6px; padding:.3rem .6rem; cursor:pointer; font-size:12px; }
        .cfa-add { border:1px dashed #cbd5e1; border-radius:10px; padding:1rem; margin-top:1rem; display:flex; flex-direction:column; gap:.7rem; }
        .cfa-add-title { font-weight:700; font-size:13px; color:#1e293b; }
        .cfa-add-grid { display:grid; grid-template-columns:1fr 180px; gap:.6rem; }
        .cfa-add-opts { display:flex; align-items:center; gap:1rem; flex-wrap:wrap; }
        .cfa-std { display:flex; gap:1rem; flex-wrap:wrap; }
        .cfa-hint { font-size:13px; color:#94a3b8; }
        @media (max-width:600px){ .cfa-add-grid { grid-template-columns:1fr; } }
      `}</style>
    </div>
  )
}
