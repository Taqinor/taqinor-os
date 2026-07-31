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
  // WIR48/XFLT22/ARC13 — cibles déjà implémentées côté serveur mais jusqu'ici
  // non listées ici (aucun écran ne les instanciait).
  vehicules: 'véhicules', contrats: 'contrats', dossiers_rh: 'dossiers RH',
}

const MODES = [
  { value: 'creer', label: 'Créer seulement (doublons ignorés)' },
  { value: 'maj', label: 'Mettre à jour seulement (jamais de création)' },
  { value: 'upsert', label: 'Créer ou mettre à jour (upsert)' },
]

// WIR48/XPLT1 — le rapprochement maj/upsert n'est câblé côté serveur que pour
// leads et clients (services.py refuse les autres cibles avec une 400). On
// n'expose donc maj/upsert QUE pour ces cibles, sinon « Créer seulement » seul
// (fin de l'option qui provoquait une erreur backend évitable).
const UPSERT_TARGETS = new Set(['leads', 'clients'])

export default function ExcelImport({ target, onClose, onDone }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  // XPLT1 — mode d'import.
  const [mode, setMode] = useState('creer')
  // Garde-fou anti-écrasement : par défaut un import ne fait que RENSEIGNER les
  // champs vides. Cocher la case autorise le remplacement des valeurs déjà
  // saisies — l'aperçu liste alors exactement lesquelles.
  const [ecraser, setEcraser] = useState(false)
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

  const doDryRun = async (f, mappingName, opts = {}) => {
    setBusy(true); setErr(null); setResult(null)
    try {
      const { data } = await importApi.dryRun(f, target, {
        mapping: mappingName || undefined,
        mode: opts.mode ?? mode,
        ecraser: opts.ecraser ?? ecraser,
      })
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

  // Le mode et le garde-fou changent ce que l'import ferait : l'aperçu doit
  // être recalculé, sinon il annoncerait des écrasements qui n'ont plus cours.
  const onModeChange = (valeur) => {
    setMode(valeur)
    if (file) doDryRun(file, mappingChoice, { mode: valeur })
  }

  const onEcraserChange = (valeur) => {
    setEcraser(valeur)
    if (file) doDryRun(file, mappingChoice, { ecraser: valeur })
  }

  const doCommit = async () => {
    if (!file) return
    setBusy(true); setErr(null)
    try {
      const { data } = await importApi.commit(file, target, {
        mode, ecraser, mapping: mappingChoice || undefined,
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
  // WIR48 — modes proposés selon la cible (maj/upsert masqués hors leads/clients).
  // `target` est fixé au montage : le sélecteur n'est rendu que pour les cibles
  // qui supportent maj/upsert, donc `mode` reste « creer » ailleurs (pas besoin
  // d'un effet correctif — jamais de mode refusé soumis).
  const supporteUpsert = UPSERT_TARGETS.has(target)
  const modesDisponibles = supporteUpsert
    ? MODES
    : MODES.filter((m) => m.value === 'creer')

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
          s'affiche avant l'import.
          {mode === 'creer'
            ? " Rien n'est écrasé : les doublons sont ignorés."
            : " Les champs déjà remplis ne sont pas remplacés, sauf si vous"
              + ' cochez « Écraser les valeurs déjà saisies ».'}
        </p>

        {/* XPLT1/WIR48 — mode d'import. maj/upsert ne sont câblés que pour
            leads/clients : pour les autres cibles, seule la création est
            possible (le sélecteur est masqué, plus d'option refusée). */}
        {modesDisponibles.length > 1 && (
          <label className="mt-3 flex flex-col gap-1 text-[13px]" htmlFor="excel-import-mode">
            Mode d'import
            <select
              id="excel-import-mode"
              className="rounded-md border border-input bg-card px-2 py-1.5 text-sm"
              value={mode}
              onChange={(e) => onModeChange(e.target.value)}
              disabled={busy}
            >
              {modesDisponibles.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </label>
        )}

        {/* Garde-fou anti-écrasement : opt-in explicite, jamais le défaut. */}
        {modesDisponibles.length > 1 && mode !== 'creer' && (
          <label className="mt-2 flex items-start gap-2 text-[13px]">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={ecraser}
              onChange={(e) => onEcraserChange(e.target.checked)}
              disabled={busy}
            />
            <span>
              Écraser les valeurs déjà saisies
              <span className="block text-xs text-muted-foreground">
                Décoché (recommandé) : l'import ne fait que renseigner les champs
                vides. Coché : il remplace aussi les valeurs existantes — chaque
                valeur remplacée est conservée dans le journal d'import.
              </span>
            </span>
          </label>
        )}

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

            {/* Aperçu des écrasements : ce que ce fichier remplacerait dans des
                données déjà saisies, champ par champ, AVANT toute écriture. */}
            {preview.ecrasements_total > 0 && (
              <div className="form-error-box mb-2">
                <strong>{preview.ecrasements_total}</strong> valeur(s) déjà
                saisie(s) sur <strong>{preview.lignes_ecrasees}</strong> ligne(s)
                diffèrent de ce fichier.
                {preview.ecrasements_appliques > 0
                  ? ` ${preview.ecrasements_appliques} seront REMPLACÉES.`
                  : ' Elles seront CONSERVÉES (case « Écraser » décochée).'}
                <div className="mt-1.5 max-w-full overflow-x-auto rounded-lg border border-border">
                  <table className="data-table text-xs">
                    <thead>
                      <tr>
                        <th className="whitespace-nowrap">Ligne</th>
                        <th className="whitespace-nowrap">Fiche</th>
                        <th className="whitespace-nowrap">Champ</th>
                        <th className="whitespace-nowrap">Valeur actuelle</th>
                        <th className="whitespace-nowrap">Valeur du fichier</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(preview.conflits || []).flatMap((c) =>
                        (c.ecrasements || []).map((e) => (
                          <tr key={`${c.ligne}-${e.champ}`}>
                            <td className="whitespace-nowrap">{c.ligne}</td>
                            <td>{c.cible_libelle}</td>
                            <td className="whitespace-nowrap">{e.champ}</td>
                            <td>{e.ancienne}</td>
                            <td>{e.nouvelle}</td>
                          </tr>
                        )))}
                    </tbody>
                  </table>
                </div>
                {preview.conflits_tronques && (
                  <div className="mt-1 text-xs">
                    Seules les premières lignes concernées sont détaillées.
                  </div>
                )}
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
              {' '}· {result.skipped.length} ignoré(s)
              {result.ecrasements ? <> · <strong>{result.ecrasements}</strong> valeur(s) remplacée(s)</> : null}.
            </div>
            {/* Valeurs protégées par le garde-fou : rien n'est avalé en
                silence, l'utilisateur voit ce qu'il devrait autoriser. */}
            {result.refuses?.length > 0 && (
              <div className="mt-2.5 text-[13px]">
                <strong>{result.refuses.length}</strong> valeur(s) déjà saisie(s)
                ont été conservées (case « Écraser » décochée) :{' '}
                {[...new Set(result.refuses.map((r) => r.champ))].join(', ')}.
              </div>
            )}
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
