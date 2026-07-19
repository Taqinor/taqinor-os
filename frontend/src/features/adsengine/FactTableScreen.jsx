import { useEffect, useState, useCallback, useMemo } from 'react'
import { Table2, Send, Pencil, Trash2, Plus } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   PUB6/AGEN1 — Écran « Table des faits ».
   ----------------------------------------------------------------------------
   Les viewsets `table-faits/` (FactTable, versionnée) + `faits/` (FactEntry)
   n'avaient AUCUNE surface UI — le moteur de génération créative ANCRÉE
   (dd-assumption-engine.md §10.2 point 1 : « aucun chiffre publiable hors de
   cette table ») était ingérable depuis la console. Cycle complet à l'écran :
   - liste des versions (brouillon/publiée) ;
   - « Nouveau brouillon » (version calculée côté serveur, jamais count()+1) ;
   - édition des `FactEntry` (clé → valeur + unité + source + date vérifiée)
     de la version sélectionnée ;
   - « Publier » (dépublie l'ancienne version côté serveur — jamais un PATCH
     direct de statut) ;
   - diff entre deux versions (ajouts/retraits/changements de clé) — comparaison
     PURE des entrées déjà chargées, aucune valeur inventée.
   ========================================================================== */

const EMPTY_ENTRY = { cle: '', valeur: '', unite: '', source: '', verifie_le: '' }

// Diff pur entre deux jeux d'entrées (comparaison par `cle`) — aucune valeur
// inventée, seulement une comparaison des chiffres déjà chargés depuis l'API.
export function diffFactEntries(fromEntries, toEntries) {
  const from = new Map((fromEntries || []).map(e => [e.cle, e]))
  const to = new Map((toEntries || []).map(e => [e.cle, e]))
  const added = []
  const removed = []
  const changed = []
  for (const [cle, entry] of to) {
    if (!from.has(cle)) {
      added.push(entry)
    } else {
      const prev = from.get(cle)
      if (prev.valeur !== entry.valeur || prev.unite !== entry.unite) {
        changed.push({ cle, avant: prev, apres: entry })
      }
    }
  }
  for (const [cle, entry] of from) {
    if (!to.has(cle)) removed.push(entry)
  }
  return { added, removed, changed }
}

export default function FactTableScreen() {
  const [tables, setTables] = useState([])
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedTableId, setSelectedTableId] = useState(null)
  const [compareTableId, setCompareTableId] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editDraft, setEditDraft] = useState(EMPTY_ENTRY)
  const [newEntry, setNewEntry] = useState(EMPTY_ENTRY)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      adsengineApi.factTables.list()
        .then(r => Array.isArray(r.data) ? r.data : (r.data?.results || []))
        .catch(() => []),
      adsengineApi.factEntries.list()
        .then(r => Array.isArray(r.data) ? r.data : (r.data?.results || []))
        .catch(() => []),
    ]).then(([tbls, ents]) => {
      // Le back trie déjà par version décroissante (Meta.ordering) ; on ne
      // fait que rendre — jamais de re-tri qui pourrait diverger de la
      // logique serveur.
      setTables(tbls)
      setEntries(ents)
      setSelectedTableId(prev => {
        if (prev != null && tbls.some(t => t.id === prev)) return prev
        const published = tbls.find(t => t.statut === 'publiee')
        return (published || tbls[0])?.id ?? null
      })
    }).finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const entriesByTable = useCallback(
    (tableId) => entries.filter(e => e.table === tableId),
    [entries])

  const selectedTable = tables.find(t => t.id === selectedTableId) || null
  const selectedEntries = useMemo(
    () => entriesByTable(selectedTableId), [entriesByTable, selectedTableId])
  const compareEntries = useMemo(
    () => (compareTableId ? entriesByTable(Number(compareTableId)) : []),
    [entriesByTable, compareTableId])
  const diff = useMemo(
    () => (compareTableId ? diffFactEntries(compareEntries, selectedEntries) : null),
    [compareTableId, compareEntries, selectedEntries])

  const createDraft = async () => {
    setBusy(true); setErr(''); setMsg('')
    try {
      const r = await adsengineApi.factTables.create({})
      setMsg(`Brouillon v${r.data?.version ?? ''} créé.`)
      await load()
      if (r.data?.id) setSelectedTableId(r.data.id)
    } catch {
      setErr('Création du brouillon impossible.')
    } finally {
      setBusy(false)
    }
  }

  const publish = async (id) => {
    setBusy(true); setErr(''); setMsg('')
    try {
      await adsengineApi.factTables.publish(id)
      setMsg('Version publiée.')
      load()
    } catch {
      setErr('Publication impossible.')
    } finally {
      setBusy(false)
    }
  }

  const startEdit = (entry) => {
    setEditingId(entry.id)
    setEditDraft({
      cle: entry.cle, valeur: entry.valeur, unite: entry.unite || '',
      source: entry.source || '', verifie_le: entry.verifie_le || '',
    })
  }
  const cancelEdit = () => { setEditingId(null); setEditDraft(EMPTY_ENTRY) }

  const saveEdit = async (id) => {
    setBusy(true); setErr('')
    try {
      await adsengineApi.factEntries.update(id, editDraft)
      setMsg('Fait mis à jour.')
      setEditingId(null)
      load()
    } catch {
      setErr('Mise à jour du fait impossible.')
    } finally {
      setBusy(false)
    }
  }

  const removeEntry = async (id) => {
    setBusy(true); setErr('')
    try {
      await adsengineApi.factEntries.remove(id)
      setMsg('Fait supprimé.')
      load()
    } catch {
      setErr('Suppression impossible.')
    } finally {
      setBusy(false)
    }
  }

  const addEntry = async (e) => {
    e.preventDefault()
    if (!selectedTableId || !newEntry.cle || !newEntry.valeur || !newEntry.verifie_le) {
      setErr('Clé, valeur et date de vérification sont obligatoires.')
      return
    }
    setBusy(true); setErr('')
    try {
      await adsengineApi.factEntries.create({ ...newEntry, table: selectedTableId })
      setNewEntry(EMPTY_ENTRY)
      setMsg('Fait ajouté.')
      load()
    } catch {
      setErr("Ajout du fait impossible (clé déjà utilisée dans cette version ?).")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page ae-facttable" data-testid="ae-facttable">
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Table2 size={20} aria-hidden="true" /> Table des faits
        </h2>
        <button type="button" className="btn btn-primary" data-testid="ae-facttable-new-draft"
          disabled={busy} onClick={createDraft}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
          <Plus size={15} aria-hidden="true" /> Nouveau brouillon
        </button>
      </div>

      {msg && <p data-testid="ae-facttable-msg" style={{ color: '#16a34a' }}>{msg}</p>}
      {err && <p data-testid="ae-facttable-err" style={{ color: '#dc2626' }}>{err}</p>}

      {loading ? <p className="page-loading">Chargement…</p> : (
        <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'minmax(0, 220px) minmax(0, 1fr)' }}>
          {/* ── Colonne versions ── */}
          <aside>
            <h3 style={{ margin: '0 0 0.5rem' }}>Versions</h3>
            {tables.length === 0
              ? <p data-testid="ae-facttable-versions-empty" style={{ color: '#64748b' }}>Aucune version.</p>
              : (
                <ul data-testid="ae-facttable-versions" style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.35rem' }}>
                  {tables.map(t => (
                    <li key={t.id}>
                      <button type="button" data-testid={`ae-facttable-version-${t.id}`}
                        aria-current={selectedTableId === t.id}
                        onClick={() => setSelectedTableId(t.id)}
                        className={`btn ${selectedTableId === t.id ? 'btn-primary' : 'btn-light'}`}
                        style={{ width: '100%', display: 'flex', justifyContent: 'space-between', gap: '0.4rem' }}>
                        <span>v{t.version}</span>
                        <span className="badge" style={{
                          background: t.statut === 'publiee' ? '#dcfce7' : '#f1f5f9',
                          color: t.statut === 'publiee' ? '#166534' : '#475569' }}>
                          {t.statut === 'publiee' ? 'Publiée' : 'Brouillon'}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
          </aside>

          {/* ── Colonne détail de la version sélectionnée ── */}
          <div>
            {!selectedTable
              ? <p data-testid="ae-facttable-select-empty" style={{ color: '#64748b' }}>
                  Créez un brouillon pour commencer.</p>
              : (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                    <h3 style={{ margin: 0 }}>
                      Version {selectedTable.version} — {selectedTable.statut === 'publiee' ? 'Publiée' : 'Brouillon'}
                    </h3>
                    {selectedTable.statut !== 'publiee' && (
                      <button type="button" className="btn btn-success" data-testid="ae-facttable-publish"
                        disabled={busy} onClick={() => publish(selectedTable.id)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                        <Send size={14} aria-hidden="true" /> Publier
                      </button>
                    )}
                  </div>

                  {/* Entrées de la version */}
                  {selectedEntries.length === 0
                    ? <p data-testid="ae-facttable-entries-empty" style={{ color: '#64748b' }}>
                        Aucun fait dans cette version.</p>
                    : (
                      <table className="data-table" data-testid="ae-facttable-entries-table">
                        <thead>
                          <tr><th>Clé</th><th>Valeur</th><th>Unité</th><th>Source</th><th>Vérifié le</th><th /></tr>
                        </thead>
                        <tbody>
                          {selectedEntries.map(en => (
                            <tr key={en.id} data-testid="ae-facttable-entry-row">
                              {editingId === en.id ? (
                                <>
                                  <td>{en.cle}</td>
                                  <td><input className="form-input" data-testid={`ae-facttable-edit-valeur-${en.id}`}
                                    value={editDraft.valeur} onChange={e => setEditDraft(d => ({ ...d, valeur: e.target.value }))} /></td>
                                  <td><input className="form-input" data-testid={`ae-facttable-edit-unite-${en.id}`}
                                    value={editDraft.unite} onChange={e => setEditDraft(d => ({ ...d, unite: e.target.value }))} /></td>
                                  <td><input className="form-input" data-testid={`ae-facttable-edit-source-${en.id}`}
                                    value={editDraft.source} onChange={e => setEditDraft(d => ({ ...d, source: e.target.value }))} /></td>
                                  <td><input className="form-input" type="date" data-testid={`ae-facttable-edit-verifie-${en.id}`}
                                    value={editDraft.verifie_le} onChange={e => setEditDraft(d => ({ ...d, verifie_le: e.target.value }))} /></td>
                                  <td style={{ display: 'flex', gap: '0.3rem' }}>
                                    <button type="button" className="btn btn-success" data-testid={`ae-facttable-save-${en.id}`}
                                      disabled={busy} onClick={() => saveEdit(en.id)}>Enregistrer</button>
                                    <button type="button" className="btn btn-light" onClick={cancelEdit}>Annuler</button>
                                  </td>
                                </>
                              ) : (
                                <>
                                  <td>{en.cle}</td>
                                  <td>{en.valeur}</td>
                                  <td>{en.unite || '—'}</td>
                                  <td>{en.source || '—'}</td>
                                  <td>{en.verifie_le || '—'}</td>
                                  <td style={{ display: 'flex', gap: '0.3rem' }}>
                                    <button type="button" className="btn btn-light" data-testid={`ae-facttable-edit-${en.id}`}
                                      onClick={() => startEdit(en)} aria-label={`Modifier ${en.cle}`}>
                                      <Pencil size={14} aria-hidden="true" />
                                    </button>
                                    <button type="button" className="btn btn-danger-outline" data-testid={`ae-facttable-delete-${en.id}`}
                                      disabled={busy} onClick={() => removeEntry(en.id)} aria-label={`Supprimer ${en.cle}`}>
                                      <Trash2 size={14} aria-hidden="true" />
                                    </button>
                                  </td>
                                </>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}

                  {/* Ajouter un fait */}
                  <form onSubmit={addEntry} data-testid="ae-facttable-add-form"
                    style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'end', marginTop: '0.9rem' }}>
                    <label style={{ display: 'grid', gap: '0.2rem' }}>
                      <span style={{ fontSize: '0.85rem', color: '#475569' }}>Clé</span>
                      <input className="form-input" data-testid="ae-facttable-add-cle"
                        value={newEntry.cle} onChange={e => setNewEntry(n => ({ ...n, cle: e.target.value }))} />
                    </label>
                    <label style={{ display: 'grid', gap: '0.2rem' }}>
                      <span style={{ fontSize: '0.85rem', color: '#475569' }}>Valeur</span>
                      <input className="form-input" data-testid="ae-facttable-add-valeur"
                        value={newEntry.valeur} onChange={e => setNewEntry(n => ({ ...n, valeur: e.target.value }))} />
                    </label>
                    <label style={{ display: 'grid', gap: '0.2rem' }}>
                      <span style={{ fontSize: '0.85rem', color: '#475569' }}>Unité</span>
                      <input className="form-input" data-testid="ae-facttable-add-unite"
                        value={newEntry.unite} onChange={e => setNewEntry(n => ({ ...n, unite: e.target.value }))} />
                    </label>
                    <label style={{ display: 'grid', gap: '0.2rem' }}>
                      <span style={{ fontSize: '0.85rem', color: '#475569' }}>Source</span>
                      <input className="form-input" data-testid="ae-facttable-add-source"
                        value={newEntry.source} onChange={e => setNewEntry(n => ({ ...n, source: e.target.value }))} />
                    </label>
                    <label style={{ display: 'grid', gap: '0.2rem' }}>
                      <span style={{ fontSize: '0.85rem', color: '#475569' }}>Vérifié le</span>
                      <input className="form-input" type="date" data-testid="ae-facttable-add-verifie"
                        value={newEntry.verifie_le} onChange={e => setNewEntry(n => ({ ...n, verifie_le: e.target.value }))} />
                    </label>
                    <button type="submit" className="btn btn-primary" data-testid="ae-facttable-add-submit" disabled={busy}>
                      Ajouter un fait
                    </button>
                  </form>

                  {/* Diff entre versions */}
                  <section style={{ marginTop: '1.25rem' }}>
                    <h4 style={{ margin: '0 0 0.4rem' }}>Comparer à une autre version</h4>
                    <select className="form-input" data-testid="ae-facttable-compare-select"
                      value={compareTableId} onChange={e => setCompareTableId(e.target.value)}
                      style={{ maxWidth: 220 }}>
                      <option value="">Choisir une version…</option>
                      {tables.filter(t => t.id !== selectedTableId).map(t => (
                        <option key={t.id} value={t.id}>v{t.version}</option>
                      ))}
                    </select>

                    {diff && (
                      <div data-testid="ae-facttable-diff" style={{ marginTop: '0.6rem', display: 'grid', gap: '0.5rem' }}>
                        {diff.added.length === 0 && diff.removed.length === 0 && diff.changed.length === 0 && (
                          <p data-testid="ae-facttable-diff-empty" style={{ color: '#64748b', margin: 0 }}>
                            Aucune différence entre ces deux versions.</p>
                        )}
                        {diff.added.length > 0 && (
                          <div data-testid="ae-facttable-diff-added">
                            <strong style={{ color: '#166534' }}>Ajoutés</strong>
                            <ul style={{ margin: '0.2rem 0 0', paddingLeft: '1.1rem' }}>
                              {diff.added.map(e => <li key={e.cle}>{e.cle} = {e.valeur}{e.unite ? ` ${e.unite}` : ''}</li>)}
                            </ul>
                          </div>
                        )}
                        {diff.removed.length > 0 && (
                          <div data-testid="ae-facttable-diff-removed">
                            <strong style={{ color: '#991b1b' }}>Retirés</strong>
                            <ul style={{ margin: '0.2rem 0 0', paddingLeft: '1.1rem' }}>
                              {diff.removed.map(e => <li key={e.cle}>{e.cle} = {e.valeur}{e.unite ? ` ${e.unite}` : ''}</li>)}
                            </ul>
                          </div>
                        )}
                        {diff.changed.length > 0 && (
                          <div data-testid="ae-facttable-diff-changed">
                            <strong style={{ color: '#92400e' }}>Modifiés</strong>
                            <ul style={{ margin: '0.2rem 0 0', paddingLeft: '1.1rem' }}>
                              {diff.changed.map(c => (
                                <li key={c.cle}>{c.cle} : {c.avant.valeur}{c.avant.unite ? ` ${c.avant.unite}` : ''}
                                  {' → '}{c.apres.valeur}{c.apres.unite ? ` ${c.apres.unite}` : ''}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </section>
                </>
              )}
          </div>
        </div>
      )}
    </div>
  )
}
