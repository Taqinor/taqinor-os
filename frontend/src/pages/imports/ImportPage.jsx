import { useState } from 'react'
import importsApi from '../../api/importsApi'
import {
  IMPORT_TARGETS, statusLabel, summarize, canConfirm,
} from '../../features/imports/importPreview'

/**
 * Import réutilisable CSV / Excel (leads, clients, produits).
 *
 * Flux : choisir la cible → téléverser un fichier → APERÇU dry-run (10 lignes,
 * mapping inféré + colonnes non reconnues) → confirmer l'import complet.
 * Création seule : rien n'est écrasé silencieusement (les doublons sont
 * signalés « ignorés »). Tout est scopé société côté serveur.
 */
export default function ImportPage() {
  const [target, setTarget] = useState('lead')
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const reset = () => {
    setPreview(null)
    setResult(null)
    setError(null)
  }

  const onFile = (e) => {
    setFile(e.target.files[0] || null)
    reset()
  }

  const onTarget = (e) => {
    setTarget(e.target.value)
    setFile(null)
    reset()
  }

  const doPreview = async () => {
    if (!file) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await importsApi.preview(target, file)
      setPreview(res.data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Aperçu impossible.')
      setPreview(null)
    } finally {
      setBusy(false)
    }
  }

  const doConfirm = async () => {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const res = await importsApi.confirm(target, file)
      setResult(res.data)
      setPreview(null)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Import impossible.')
    } finally {
      setBusy(false)
    }
  }

  const mapping = preview?.mapping || []
  const unmapped = preview?.unmapped_columns || []

  return (
    <div className="page" style={{ maxWidth: 900, margin: '0 auto' }}>
      <h1>Importer CSV / Excel</h1>
      <p className="text-muted">
        Téléversez un fichier .csv ou .xlsx. Un aperçu vous montre le mapping
        des colonnes avant l'import. L'import crée de nouvelles fiches
        uniquement — les doublons sont ignorés, rien n'est écrasé.
      </p>

      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end',
        flexWrap: 'wrap', margin: '16px 0' }}>
        <label>
          <div>Type de données</div>
          <select value={target} onChange={onTarget}>
            {IMPORT_TARGETS.map(t => (
              <option key={t.target} value={t.target}>{t.label}</option>
            ))}
          </select>
        </label>
        <label>
          <div>Fichier (.csv / .xlsx)</div>
          <input type="file" accept=".csv,.xlsx,.xls,.txt" onChange={onFile} />
        </label>
        <button type="button" className="btn btn-primary"
          disabled={!file || busy} onClick={doPreview}>
          {busy ? '…' : 'Aperçu'}
        </button>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {result && (
        <div className="alert alert-success">
          Import terminé : {result.created} fiche(s) créée(s),
          {' '}{result.skipped} ignorée(s) sur {result.total_rows}.
        </div>
      )}

      {preview && (
        <div className="import-preview">
          <h2>Aperçu — {preview.label}</h2>
          <p>{summarize(preview)}</p>

          <h3>Colonnes reconnues</h3>
          <ul>
            {mapping.map(m => (
              <li key={m.column}>
                <strong>{m.column}</strong> → {m.label}
              </li>
            ))}
          </ul>

          {unmapped.length > 0 && (
            <>
              <h3>Colonnes non reconnues (ignorées)</h3>
              <ul>
                {unmapped.map(c => <li key={c}>{c}</li>)}
              </ul>
            </>
          )}

          <h3>{preview.preview_rows} premières lignes</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Statut</th>
                {mapping.map(m => <th key={m.field}>{m.label}</th>)}
                <th>Remarques</th>
              </tr>
            </thead>
            <tbody>
              {preview.preview.map((row, i) => (
                <tr key={i}>
                  <td>{statusLabel(row.status)}</td>
                  {mapping.map(m => (
                    <td key={m.field}>{row.values[m.field] || ''}</td>
                  ))}
                  <td>{(row.problems || []).join(' ; ')}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ marginTop: 16 }}>
            <button type="button" className="btn btn-success"
              disabled={!canConfirm(preview) || busy} onClick={doConfirm}>
              Confirmer l'import ({preview.will_create} fiche(s))
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
