// T9 — modal d'import réutilisable (CSV/XLSX). Étape 1 : choisir un fichier →
// aperçu (10 lignes + mapping colonne→champ + colonnes non reconnues). Étape 2 :
// valider → import (création seule, doublons ignorés). `target` = leads|clients|
// products. Rien n'est écrasé silencieusement ; le périmètre société est serveur.
import { useState } from 'react'
import importApi from '../api/importApi'

const TARGET_LABEL = { leads: 'leads', clients: 'clients', products: 'produits' }

export default function ExcelImport({ target, onClose, onDone }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const doDryRun = async (f) => {
    setBusy(true); setErr(null); setResult(null)
    try {
      const { data } = await importApi.dryRun(f, target)
      setPreview(data)
    } catch (e) {
      setErr(e?.response?.data?.detail ?? 'Lecture du fichier impossible.')
    } finally { setBusy(false) }
  }

  const onPick = (e) => {
    const f = e.target.files?.[0]
    setFile(f || null); setPreview(null); setResult(null)
    if (f) doDryRun(f)
  }

  const doCommit = async () => {
    if (!file) return
    setBusy(true); setErr(null)
    try {
      const { data } = await importApi.commit(file, target)
      setResult(data)
      onDone?.()
    } catch (e) {
      setErr(e?.response?.data?.detail ?? 'Import impossible.')
    } finally { setBusy(false) }
  }

  const fields = preview ? Object.values(preview.mapping) : []

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
         onClick={onClose}>
      <div style={{ background: '#fff', borderRadius: 12, padding: '1.5rem', width: '100%', maxWidth: 640, maxHeight: '85vh', overflowY: 'auto' }}
           onClick={e => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>Importer des {TARGET_LABEL[target] ?? target} (CSV / Excel)</h3>
        <p style={{ color: '#64748b', fontSize: 13 }}>
          Choisissez un fichier .csv ou .xlsx. Un aperçu des 10 premières lignes
          s'affiche avant l'import. Rien n'est écrasé : les doublons sont ignorés.
        </p>

        <input type="file" accept=".csv,.xlsx" onChange={onPick} disabled={busy} />

        {err && <div className="form-error-box" style={{ marginTop: 12 }}>{err}</div>}
        {busy && <p className="gen-hint">⏳ Traitement…</p>}

        {/* L869 — fichier lu mais aucune colonne reconnue : on l'explique et on
            désactive l'import (au lieu d'un bouton désactivé sans raison). */}
        {preview && !result && fields.length === 0 && (
          <div className="form-error-box" style={{ marginTop: 12 }}>
            Aucune colonne reconnue — vérifiez les en-têtes.
            {preview.colonnes?.length ? (
              <div style={{ fontSize: 12, marginTop: 4 }}>
                En-têtes lus : {preview.colonnes.join(', ')}
              </div>
            ) : null}
          </div>
        )}

        {preview && !result && fields.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 13, marginBottom: 6 }}>
              <strong>{preview.total_lignes}</strong> ligne(s) · colonnes reconnues :
              {' '}{fields.join(', ') || '—'}
            </div>
            {preview.non_mappees.length > 0 && (
              <div style={{ fontSize: 12, color: '#b45309', marginBottom: 6 }}>
                Colonnes ignorées : {preview.non_mappees.join(', ')}
              </div>
            )}
            {/* L871 — aperçu 10 lignes utilisable sur 375px : 12px, scroll
                horizontal seulement (cellules non coupées), borné au modal. */}
            <div style={{ overflowX: 'auto', maxWidth: '100%', border: '1px solid #e2e8f0', borderRadius: 8 }}>
              <table className="data-table" style={{ fontSize: 12 }}>
                <thead>
                  <tr>{fields.map(f => (
                    <th key={f} style={{ whiteSpace: 'nowrap' }}>{f}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {preview.apercu.map((row, i) => (
                    <tr key={i}>{fields.map(f => (
                      <td key={f} style={{ whiteSpace: 'nowrap' }}>{String(row[f] ?? '')}</td>
                    ))}</tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 14 }}>
              <button type="button" className="btn btn-outline" onClick={onClose}>Annuler</button>
              <button type="button" className="btn btn-primary" onClick={doCommit} disabled={busy || !fields.length}>
                Importer {preview.total_lignes} ligne(s)
              </button>
            </div>
          </div>
        )}

        {result && (
          <div style={{ marginTop: 16 }}>
            <div className="alert alert-info" style={{ background: '#ecfdf5', border: '1px solid #6ee7b7', color: '#065f46', borderRadius: 8, padding: '0.7rem 1rem' }}>
              <strong>{result.created}</strong> créé(s) ·
              {' '}{result.skipped.length} ignoré(s).
            </div>
            {/* L870 — détail des lignes ignorées (numéro + raison), pas que le
                compte. Le backend renvoie skipped:[{ligne, raison}]. */}
            {result.skipped.length > 0 && (
              <div style={{ marginTop: 10 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                  Lignes ignorées
                </div>
                <div style={{ overflowX: 'auto', maxWidth: '100%', border: '1px solid #e2e8f0', borderRadius: 8 }}>
                  <table className="data-table" style={{ fontSize: 12 }}>
                    <thead>
                      <tr>
                        <th style={{ whiteSpace: 'nowrap' }}>Ligne</th>
                        <th style={{ whiteSpace: 'nowrap' }}>Raison</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.skipped.map((s, i) => (
                        <tr key={i}>
                          <td style={{ whiteSpace: 'nowrap' }}>{s.ligne ?? '—'}</td>
                          <td>{s.raison ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            <div style={{ textAlign: 'right', marginTop: 12 }}>
              <button type="button" className="btn btn-primary" onClick={onClose}>Fermer</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
