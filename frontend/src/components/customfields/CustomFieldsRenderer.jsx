import { useEffect, useState } from 'react'
import customFieldsApi from '../../api/customFieldsApi'
import { defaultValueFor } from '../../features/customfields/customFields'

/**
 * Rendu dynamique des champs personnalisés d'un module (T11).
 *
 * Récupère le schéma du module ({definitions, hidden_standard}) et peint un
 * champ de saisie par définition, en lisant/écrivant l'objet `values`
 * (= record.custom_fields). Réutilisé par LeadForm / ClientForm / ProduitForm.
 *
 * Props :
 *   - module : 'lead' | 'client' | 'produit'
 *   - values : objet { field_key: value } (custom_fields du record)
 *   - onChange : (newValues) => void
 *   - errors : objet optionnel { field_key: message } (erreurs serveur)
 *   - onHiddenStandard : (Set<string>) => void  — clés standard masquées
 *       (le formulaire parent peut s'en servir pour cacher ses champs natifs)
 */
export default function CustomFieldsRenderer({
  module, values = {}, onChange, errors = {}, onHiddenStandard,
}) {
  const [defs, setDefs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    customFieldsApi.getSchema(module)
      .then((res) => {
        if (!alive) return
        setDefs(res.data?.definitions || [])
        if (onHiddenStandard) {
          onHiddenStandard(new Set(res.data?.hidden_standard || []))
        }
      })
      .catch(() => { if (alive) setDefs([]) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
    // module est la seule dépendance volontaire (onHiddenStandard stable).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [module])

  if (loading || defs.length === 0) return null

  const setVal = (key, v) => onChange?.({ ...values, [key]: v })

  return (
    <div className="cf-section">
      <div className="cf-title">Champs personnalisés</div>
      {defs.map((d) => {
        const val = values?.[d.field_key] ?? defaultValueFor(d.field_type)
        const err = errors?.[d.field_key]
        return (
          <div className="form-group" key={d.id}>
            {d.field_type !== 'boolean' && (
              <label className="form-label">
                {d.label}{d.required && <span className="req"> *</span>}
              </label>
            )}
            {d.field_type === 'text' && (
              <input
                className={`form-control${err ? ' is-invalid' : ''}`}
                value={val ?? ''}
                onChange={(e) => setVal(d.field_key, e.target.value)}
              />
            )}
            {d.field_type === 'number' && (
              <input
                type="number"
                step="any"
                className={`form-control${err ? ' is-invalid' : ''}`}
                value={val ?? ''}
                onChange={(e) => setVal(d.field_key, e.target.value)}
              />
            )}
            {d.field_type === 'date' && (
              <input
                type="date"
                className={`form-control${err ? ' is-invalid' : ''}`}
                value={val ?? ''}
                onChange={(e) => setVal(d.field_key, e.target.value)}
              />
            )}
            {d.field_type === 'choice' && (
              <select
                className={`form-control${err ? ' is-invalid' : ''}`}
                value={val ?? ''}
                onChange={(e) => setVal(d.field_key, e.target.value)}
              >
                <option value="">— Choisir —</option>
                {(d.choices || []).map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            )}
            {d.field_type === 'boolean' && (
              <label className="cf-check">
                <input
                  type="checkbox"
                  checked={!!val}
                  onChange={(e) => setVal(d.field_key, e.target.checked)}
                />
                <span>{d.label}{d.required && <span className="req"> *</span>}</span>
              </label>
            )}
            {err && <div className="form-feedback">{err}</div>}
          </div>
        )
      })}
      <style>{`
        .cf-section { margin-top: .5rem; padding-top: .75rem; border-top: 1px dashed #e2e8f0; }
        .cf-title { font-size: 12px; font-weight: 700; color: #64748b;
          text-transform: uppercase; letter-spacing: .04em; margin-bottom: .6rem; }
        .cf-check { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 14px; }
      `}</style>
    </div>
  )
}
