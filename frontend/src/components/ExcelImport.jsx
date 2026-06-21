// T9 — modal d'import réutilisable (CSV/XLSX). Étape 1 : choisir un fichier →
// aperçu (10 lignes + mapping colonne→champ + colonnes non reconnues). Étape 2 :
// valider → import (création seule, doublons ignorés). `target` = leads|clients|
// products. Rien n'est écrasé silencieusement ; le périmètre société est serveur.
// P169 — plus aucun style={} en dur : tout passe par des classes Tailwind/tokens.
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
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/45"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-[640px] overflow-y-auto rounded-xl bg-card p-6"
        onClick={e => e.stopPropagation()}
      >
        <h3 className="mt-0">Importer des {TARGET_LABEL[target] ?? target} (CSV / Excel)</h3>
        <p className="text-[13px] text-muted-foreground">
          Choisissez un fichier .csv ou .xlsx. Un aperçu des 10 premières lignes
          s'affiche avant l'import. Rien n'est écrasé : les doublons sont ignorés.
        </p>

        <input type="file" accept=".csv,.xlsx" onChange={onPick} disabled={busy} />

        {err && <div className="form-error-box mt-3">{err}</div>}
        {busy && <p className="gen-hint">⏳ Traitement…</p>}

        {/* L869 — fichier lu mais aucune colonne reconnue : on l'explique et on
            désactive l'import (au lieu d'un bouton désactivé sans raison). */}
        {preview && !result && fields.length === 0 && (
          <div className="form-error-box mt-3">
            Aucune colonne reconnue — vérifiez les en-têtes.
            {preview.colonnes?.length ? (
              <div className="mt-1 text-xs">
                En-têtes lus : {preview.colonnes.join(', ')}
              </div>
            ) : null}
          </div>
        )}

        {preview && !result && fields.length > 0 && (
          <div className="mt-4">
            <div className="mb-1.5 text-[13px]">
              <strong>{preview.total_lignes}</strong> ligne(s) · colonnes reconnues :
              {' '}{fields.join(', ') || '—'}
            </div>
            {preview.non_mappees.length > 0 && (
              <div className="mb-1.5 text-xs text-warning">
                Colonnes ignorées : {preview.non_mappees.join(', ')}
              </div>
            )}
            {/* L871 — aperçu 10 lignes utilisable sur 375px : 12px, scroll
                horizontal seulement (cellules non coupées), borné au modal. */}
            <div className="max-w-full overflow-x-auto rounded-lg border border-border">
              <table className="data-table text-xs">
                <thead>
                  <tr>{fields.map(f => (
                    <th key={f} className="whitespace-nowrap">{f}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {preview.apercu.map((row, i) => (
                    <tr key={i}>{fields.map(f => (
                      <td key={f} className="whitespace-nowrap">{String(row[f] ?? '')}</td>
                    ))}</tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3.5 flex justify-end gap-2">
              <button type="button" className="btn btn-outline" onClick={onClose}>Annuler</button>
              <button type="button" className="btn btn-primary" onClick={doCommit} disabled={busy || !fields.length}>
                Importer {preview.total_lignes} ligne(s)
              </button>
            </div>
          </div>
        )}

        {result && (
          <div className="mt-4">
            <div className="alert alert-info rounded-lg border border-success/40 bg-success/12 px-4 py-3 text-success">
              <strong>{result.created}</strong> créé(s) ·
              {' '}{result.skipped.length} ignoré(s).
            </div>
            {/* L870 — détail des lignes ignorées (numéro + raison), pas que le
                compte. Le backend renvoie skipped:[{ligne, raison}]. */}
            {result.skipped.length > 0 && (
              <div className="mt-2.5">
                <div className="mb-1 text-[13px] font-semibold">
                  Lignes ignorées
                </div>
                <div className="max-w-full overflow-x-auto rounded-lg border border-border">
                  <table className="data-table text-xs">
                    <thead>
                      <tr>
                        <th className="whitespace-nowrap">Ligne</th>
                        <th className="whitespace-nowrap">Raison</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.skipped.map((s, i) => (
                        <tr key={i}>
                          <td className="whitespace-nowrap">{s.ligne ?? '—'}</td>
                          <td>{s.raison ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            <div className="mt-3 text-right">
              <button type="button" className="btn btn-primary" onClick={onClose}>Fermer</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
