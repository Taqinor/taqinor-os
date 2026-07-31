// T11 — rend dynamiquement les champs personnalisés d'un module (lead, client,
// produit) dans un formulaire. Charge les définitions, affiche un input par
// type, et remonte l'objet custom_data via onChange. Si aucun champ défini,
// n'affiche rien.
import { useEffect, useState } from 'react'
import customFieldsApi from '../api/customFieldsApi'

export default function CustomFieldsInput({ module, value, onChange, onDefsLoaded }) {
  const [defs, setDefs] = useState([])
  const data = value || {}

  useEffect(() => {
    customFieldsApi.getDefs(module)
      .then(r => {
        const actifs = (r.data.results ?? r.data).filter(d => d.actif)
        setDefs(actifs)
        onDefsLoaded?.(actifs)
      })
      .catch(() => { setDefs([]); onDefsLoaded?.([]) })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onDefsLoaded n'est volontairement pas une dépendance (callback stable côté appelant non garanti)
  }, [module])

  if (!defs.length) return null

  const set = (code, v) => onChange({ ...data, [code]: v })

  return (
    <div className="cf-section">
      <h4 style={{ margin: '0 0 8px', fontSize: 13, color: '#475569' }}>Champs personnalisés</h4>
      {defs.map((d) => (
        <div className="form-group" key={d.id} style={{ marginBottom: 8 }}>
          <label className="form-label">
            {d.libelle}{d.obligatoire ? ' *' : ''}
          </label>
          {d.type === 'boolean' ? (
            <input type="checkbox" checked={!!data[d.code]}
                   onChange={e => set(d.code, e.target.checked)} />
          ) : d.type === 'choice' ? (
            <select className="form-control" value={data[d.code] ?? ''}
                    onChange={e => set(d.code, e.target.value)}>
              <option value="">—</option>
              {(d.options || []).map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : (
            <input
              className="form-control"
              type={d.type === 'number' ? 'number' : d.type === 'date' ? 'date' : 'text'}
              step={d.type === 'number' ? 'any' : undefined}
              value={data[d.code] ?? ''}
              onChange={e => set(d.code, e.target.value)}
            />
          )}
        </div>
      ))}
    </div>
  )
}
