// T9 — modal d'import réutilisable (CSV/XLSX). Étape 1 : choisir un fichier →
// aperçu (10 lignes + mapping colonne→champ + colonnes non reconnues). Étape 2 :
// valider → import. `target` = leads|clients|products. Le périmètre société
// est toujours serveur.
// P169 — plus aucun style={} en dur : tout passe par des classes Tailwind/tokens.
// XPLT1 — mode d'import (création seule / mise à jour seule / upsert par
// identifiant externe ou correspondance de contact).
// XPLT2 — mapping colonne→champ sauvegardable/réapplicable + lien CSV des
// lignes en échec après un commit partiel.
import { useEffect, useState } from 'react'
import importApi, { downloadBlob, filenameFromResponse } from '../api/importApi'

const TARGET_LABEL = {
  leads: 'leads', clients: 'clients', products: 'produits',
  fournisseurs: 'fournisseurs', equipements: 'équipements',
}

const MODES = [
  { value: 'creer', label: 'Créer seulement (doublons ignorés)' },
  { value: 'maj', label: 'Mettre à jour seulement (jamais de création)' },
  { value: 'upsert', label: 'Créer ou mettre à jour (upsert)' },
]

export default function ExcelImport({ target, onClose, onDone }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  // XPLT1 — mode d'import.
  const [mode, setMode] = useState('creer')
  // XPLT2 — mapping sauvegardé sélectionné + nom pour en sauvegarder un nouveau.
  const [savedMappings, setSavedMappings] = useState([])
  const [mappingChoice, setMappingChoice] = useState('')
  const [newMappingName, setNewMappingName] = useState('')
  const [savingMapping, setSavingMapping] = useState(false)
  const [erreursCsvBusy, setErreursCsvBusy] = useState(false)

  useEffect(() => {
    let active = true
    importApi.getSavedMappings(target)
      .then((r) => { if (active) setSavedMappings(r.data || []) })
      .catch(() => {})
    return () => { active = false }
  }, [target])

  const doDryRun = async (f, mappingName) => {
    setBusy(true); setErr(null); setResult(null)
    try {
      const { data } = await importApi.dryRun(f, target, { mapping: mappingName || undefined })
      setPreview(data)
    } catch (e) {
      setErr(e?.response?.data?.detail ?? 'Lecture du fichier impossible.')
    } finally { setBusy(false) }
  }

  const onPick = (e) => {
    const f = e.target.files?.[0]
    setFile(f || null); setPreview(null); setResult(null)
    if (f) doDryRun(f, mappingChoice)
  }

  // XPLT2 — changer le mapping sélectionné relance l'aperçu avec ce mapping.
  const onMappingChoiceChange = (nom) => {
    setMappingChoice(nom)
    if (file) doDryRun(file, nom)
  }

  const doCommit = async () => {
    if (!file) return
    setBusy(true); setErr(null)
    try {
      const { data } = await importApi.commit(file, target, {
        mode, mapping: mappingChoice || undefined,
      })
      setResult(data)
      onDone?.()
    } catch (e) {
      setErr(e?.response?.data?.detail ?? 'Import impossible.')
    } finally { setBusy(false) }
  }

  // XPLT2 — sauvegarde le mapping courant (issu de l'aperçu) sous un nom.
  const doSaveMapping = async () => {
    const nom = newMappingName.trim()
    if (!nom || !preview) return
    setSavingMapping(true); setErr(null)
    try {
      await importApi.saveMapping(target, nom, preview.mapping)
      const { data } = await importApi.getSavedMappings(target)
      setSavedMappings(data || [])
      setMappingChoice(nom)
      setNewMappingName('')
    } catch (e) {
      setErr(e?.response?.data?.detail ?? 'Sauvegarde du mapping impossible.')
    } finally { setSavingMapping(false) }
  }

  // XPLT2 — télécharge le CSV des seules lignes en échec du job venant d'être créé.
  const downloadErreursCsv = async () => {
    if (!result?.job_id) return
    setErreursCsvBusy(true)
    try {
      const res = await importApi.jobErreursCsv(result.job_id)
      downloadBlob(res.data, filenameFromResponse(res, `import_${result.job_id}_erreurs.csv`))
    } catch { /* best-effort */ } finally { setErreursCsvBusy(false) }
  }

  const fields = preview ? Object.values(preview.mapping) : []

  return (
    <div
      className="fixed inset-0 z-[var(--z-overlay)] flex items-center justify-center bg-black/45"
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

        {/* XPLT1 — mode d'import (création seule par défaut, historique). */}
        <label className="mt-3 flex flex-col gap-1 text-[13px]" htmlFor="excel-import-mode">
          Mode d'import
          <select
            id="excel-import-mode"
            className="rounded-md border border-input bg-card px-2 py-1.5 text-sm"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            disabled={busy}
          >
            {MODES.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </label>

        {/* XPLT2 — mapping colonne→champ sauvegardé, réapplicable au dry-run. */}
        {savedMappings.length > 0 && (
          <label className="mt-2 flex flex-col gap-1 text-[13px]" htmlFor="excel-import-mapping">
            Mapping sauvegardé
            <select
              id="excel-import-mapping"
              className="rounded-md border border-input bg-card px-2 py-1.5 text-sm"
              value={mappingChoice}
              onChange={(e) => onMappingChoiceChange(e.target.value)}
              disabled={busy}
            >
              <option value="">Mapping automatique</option>
              {savedMappings.map((m) => (
                <option key={m.id} value={m.nom}>{m.nom}</option>
              ))}
            </select>
          </label>
        )}

        <input type="file" accept=".csv,.xlsx" className="mt-3" onChange={onPick} disabled={busy} />

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

            {/* XPLT2 — sauvegarder ce mapping colonne→champ pour le réutiliser. */}
            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              <input
                type="text"
                aria-label="Nom du mapping à sauvegarder"
                placeholder="Nom du mapping (ex. Export CRM X)"
                className="min-w-[180px] flex-1 rounded-md border border-input bg-card px-2 py-1.5 text-sm"
                value={newMappingName}
                onChange={(e) => setNewMappingName(e.target.value)}
                disabled={savingMapping}
              />
              <button
                type="button"
                className="btn btn-outline"
                onClick={doSaveMapping}
                disabled={savingMapping || !newMappingName.trim()}
              >
                {savingMapping ? 'Sauvegarde…' : 'Sauvegarder ce mapping'}
              </button>
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
              <strong>{result.created}</strong> créé(s)
              {typeof result.updated === 'number' ? <> · <strong>{result.updated}</strong> mis à jour</> : null}
              {' '}· {result.skipped.length} ignoré(s).
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
            {/* XPLT2 — CSV des seules lignes en échec du job, ré-importable tel quel. */}
            {result.job_id && result.skipped.length > 0 && (
              <div className="mt-2.5">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={downloadErreursCsv}
                  disabled={erreursCsvBusy}
                >
                  {erreursCsvBusy ? 'Génération…' : 'Télécharger le CSV des lignes en échec'}
                </button>
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
