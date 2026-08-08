/* ============================================================================
   PACT58 — Contrôle documentaire de projet : registre et révisions.
   ----------------------------------------------------------------------------
   Trou (a) : `DocumentProjetViewSet` (schéma unifilaire, calepinage, note de
   calcul par chantier) et `RevisionDocumentViewSet` (indice, date, auteur,
   fichier) dans `views/document.py` — aucun appelant.
   ========================================================================== */
import { useCallback, useEffect, useState } from 'react'
import { PlusCircle } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import { Badge, Button, Spinner, EmptyState } from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDate } from '../../lib/format'
import installationsApi from '../../api/installationsApi'

const TYPES_DOC = [
  ['schema_unifilaire', 'Schéma unifilaire'], ['calepinage', 'Calepinage'],
  ['note_calcul', 'Note de calcul'], ['autre', 'Autre'],
]

function unwrap(res) {
  const p = res?.data
  return Array.isArray(p) ? p : (p?.results ?? [])
}

function useFilteredList(fetcher, params) {
  const key = JSON.stringify(params)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const load = useCallback(() => {
    let cancelled = false
    setLoading(true); setError(null)
    fetcher(params)
      .then((res) => { if (!cancelled) setRows(unwrap(res)) })
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.detail || 'Chargement impossible.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage/changement de filtre
  useEffect(() => load(), [load])
  return { rows, loading, error, reload: load }
}

function ListShell({ loading, error, empty, children }) {
  if (loading) return (
    <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (error) return <EmptyState title="Impossible de charger" description={error} className="py-6" />
  if (!children) return <EmptyState title={empty} className="py-6" />
  return children
}

function CreateDocumentDialog({ installationId, onClose, onCreated }) {
  const [titre, setTitre] = useState('')
  const [typeDoc, setTypeDoc] = useState('autre')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!titre.trim()) { setError('Le titre est obligatoire.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createDocumentProjet({
        installation: installationId, titre: titre.trim(), type_doc: typeDoc,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouveau document technique</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="dp-titre">Titre</label>
        <input id="dp-titre" type="text" className="form-control" value={titre} onChange={(e) => setTitre(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="dp-type">Type de document</label>
        <select id="dp-type" className="form-control" value={typeDoc} onChange={(e) => setTypeDoc(e.target.value)}>
          {TYPES_DOC.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Création…' : 'Créer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

function AddRevisionDialog({ documentId, onClose, onCreated }) {
  const [indice, setIndice] = useState('A')
  const [dateRevision, setDateRevision] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!indice.trim() || !dateRevision) {
      setError('Indice et date de révision sont requis.')
      return
    }
    setBusy(true); setError(null)
    try {
      await installationsApi.createRevisionDocument({
        document: documentId, indice: indice.trim(),
        date_revision: dateRevision, notes: notes || undefined,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.non_field_errors?.[0]
        || err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-sm" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle révision</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="rd-indice">Indice</label>
        <input id="rd-indice" type="text" className="form-control" value={indice} onChange={(e) => setIndice(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="rd-date">Date de révision</label>
        <input id="rd-date" type="date" className="form-control" value={dateRevision} onChange={(e) => setDateRevision(e.target.value)} />
        <label className="form-label" htmlFor="rd-notes">Notes (optionnel)</label>
        <textarea id="rd-notes" className="form-control" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Création…' : 'Créer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

function DocumentRow({ doc, onChanged }) {
  const [showRevision, setShowRevision] = useState(false)
  const revisions = doc.inst_revisions || []
  const courante = revisions[0] || null
  return (
    <div className="rounded-xl border border-border bg-card p-3" data-testid={`document-${doc.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-sm">{doc.titre}</span>
        <Badge tone="neutral">{doc.type_doc_display || doc.type_doc}</Badge>
        <Badge tone="info">Indice courant : {courante?.indice ?? '—'}</Badge>
        <span className="text-xs text-muted-foreground">{doc.nb_revisions ?? revisions.length} révision(s)</span>
        <Button size="sm" variant="outline" className="ml-auto" onClick={() => setShowRevision(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle révision
        </Button>
      </div>
      {revisions.length > 0 && (
        <div className="mt-2 flex flex-col gap-1 pl-3 border-l border-border">
          {revisions.map((r) => (
            <div key={r.id} className="flex items-center gap-2 text-sm" data-testid={`revision-${r.id}`}>
              <span className="font-medium">Rev. {r.indice}</span>
              <span className="text-muted-foreground">{formatDate(r.date_revision)}</span>
              {r.auteur_nom && <span className="text-xs text-muted-foreground">{r.auteur_nom}</span>}
            </div>
          ))}
        </div>
      )}
      {showRevision && (
        <AddRevisionDialog documentId={doc.id}
          onClose={() => setShowRevision(false)}
          onCreated={() => { setShowRevision(false); onChanged?.() }} />
      )}
    </div>
  )
}

function DocumentsForInstallation({ installationId }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getDocumentsProjet, { installation: installationId })
  const [showCreate, setShowCreate] = useState(false)
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouveau document
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucun document technique enregistré">
        {rows.length > 0 && (
          <div className="flex flex-col gap-2">
            {rows.map((d) => <DocumentRow key={d.id} doc={d} onChanged={reload} />)}
          </div>
        )}
      </ListShell>
      {showCreate && (
        <CreateDocumentDialog installationId={installationId}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

export default function DocumentsProjet() {
  const [chantiers, setChantiers] = useState([])
  const [loadingChantiers, setLoadingChantiers] = useState(true)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    let alive = true
    installationsApi.getInstallations({ page_size: 200 })
      .then((res) => {
        if (!alive) return
        const rows = unwrap(res)
        setChantiers(rows)
        setSelected((cur) => cur ?? rows[0]?.id ?? null)
      })
      .catch(() => {})
      .finally(() => { if (alive) setLoadingChantiers(false) })
    return () => { alive = false }
  }, [])

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Contrôle documentaire de projet"
        subtitle="Registre des documents techniques (schéma unifilaire, calepinage, note de calcul) et leurs révisions."
      />
      {loadingChantiers ? (
        <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
          <Spinner className="size-4 text-primary" /> Chargement…
        </p>
      ) : chantiers.length === 0 ? (
        <EmptyState title="Aucun chantier" description="Créez un chantier avant d'attacher des documents techniques." className="py-10" />
      ) : (
        <>
          <label className="form-label" htmlFor="dp-chantier">Chantier</label>
          <select id="dp-chantier" className="form-control max-w-sm" value={selected ?? ''} onChange={(e) => setSelected(Number(e.target.value))}>
            {chantiers.map((c) => <option key={c.id} value={c.id}>{c.reference || `#${c.id}`}</option>)}
          </select>
          {selected != null && <DocumentsForInstallation installationId={selected} />}
        </>
      )}
    </div>
  )
}
