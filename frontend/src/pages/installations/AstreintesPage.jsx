import { useCallback, useEffect, useState } from 'react'
import { CalendarClock, PlusCircle, Trash2 } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Button, IconButton, Spinner, EmptyState,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDate } from '../../lib/format'
import installationsApi from '../../api/installationsApi'
import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'

/* ============================================================================
   WIR114 — Interventions avancées : astreintes, indisponibilités ressource
   (FG302) et récurrences d'intervention (ZFSM3). `/planification/astreintes`.
   ----------------------------------------------------------------------------
   Gestion (liste + création + suppression) des tours de garde, des créneaux
   d'indisponibilité (technicien OU camionnette) et des règles de récurrence
   d'intervention. Les dates saisies restent des `<input type=date>` non
   contraignants ; la garde métier (une seule cible, ordre des dates) est
   re-validée côté serveur (400 affiché tel quel).
   ========================================================================== */

const INDISPO_TYPES = [
  ['conge', 'Congé'], ['formation', 'Formation'],
  ['arret', 'Arrêt (maladie / panne)'], ['autre', 'Autre'],
]
const RECURRENCE_REGLES = [
  ['mensuelle', 'Mensuelle'], ['trimestrielle', 'Trimestrielle'],
  ['semestrielle', 'Semestrielle'], ['annuelle', 'Annuelle'],
]

function useList(fetcher) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetcher()
      .then((res) => {
        if (cancelled) return
        const p = res?.data
        setRows(Array.isArray(p) ? p : (p?.results ?? []))
      })
      .catch((err) => { if (!cancelled) setError(err?.response?.data?.detail || 'Chargement impossible.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
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
  return children ?? <EmptyState icon={CalendarClock} title={empty} className="py-6" />
}

// ── Astreintes ──────────────────────────────────────────────────────────────
function AstreintesTab({ techniciens }) {
  const { rows, loading, error, reload } = useList(installationsApi.getAstreintes)
  const [showCreate, setShowCreate] = useState(false)
  const del = async (id) => {
    if (!window.confirm('Supprimer cette astreinte ?')) return
    await installationsApi.deleteAstreinte(id).catch(() => {})
    reload()
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle astreinte
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucune astreinte planifiée">
        {rows.length > 0 && rows.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`astreinte-${r.id}`}>
            <span className="font-medium text-sm">{r.technicien_nom || `#${r.technicien}`}</span>
            <span className="text-sm text-muted-foreground">
              {formatDate(r.date_debut)} → {formatDate(r.date_fin)}
            </span>
            {r.telephone_astreinte && <Badge tone="info">{r.telephone_astreinte}</Badge>}
            <IconButton size="md" variant="outline" label="Supprimer"
              className="ml-auto text-destructive hover:text-destructive"
              onClick={() => del(r.id)}>
              <Trash2 className="size-4" aria-hidden="true" />
            </IconButton>
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <AstreinteDialog techniciens={techniciens}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

function AstreinteDialog({ techniciens, onClose, onCreated }) {
  const [technicien, setTechnicien] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [tel, setTel] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!technicien || !dateDebut || !dateFin) {
      setError('Technicien, date de début et date de fin sont requis.')
      return
    }
    setBusy(true); setError(null)
    try {
      await installationsApi.createAstreinte({
        technicien: Number(technicien), date_debut: dateDebut,
        date_fin: dateFin, telephone_astreinte: tel || '',
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle astreinte</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="as-tech">Technicien d'astreinte</label>
        <select id="as-tech" className="form-control" value={technicien} onChange={(e) => setTechnicien(e.target.value)} autoFocus>
          <option value="">— Choisir —</option>
          {techniciens.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
        </select>
        <label className="form-label" htmlFor="as-debut">Début</label>
        <input id="as-debut" type="date" className="form-control" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
        <label className="form-label" htmlFor="as-fin">Fin</label>
        <input id="as-fin" type="date" className="form-control" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
        <label className="form-label" htmlFor="as-tel">Téléphone d'astreinte (optionnel)</label>
        <input id="as-tel" type="tel" className="form-control" value={tel} onChange={(e) => setTel(e.target.value)} />
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

// ── Indisponibilités ──────────────────────────────────────────────────────────
function IndisposTab({ techniciens, emplacements }) {
  const { rows, loading, error, reload } = useList(installationsApi.getIndisponibilites)
  const [showCreate, setShowCreate] = useState(false)
  const del = async (id) => {
    if (!window.confirm('Supprimer cette indisponibilité ?')) return
    await installationsApi.deleteIndisponibilite(id).catch(() => {})
    reload()
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle indisponibilité
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucune indisponibilité">
        {rows.length > 0 && rows.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`indispo-${r.id}`}>
            <span className="font-medium text-sm">
              {r.technicien_nom || r.camionnette_nom || '—'}
            </span>
            <Badge tone="neutral">{r.type_indispo_display || r.type_indispo}</Badge>
            <span className="text-sm text-muted-foreground">
              {formatDate(r.date_debut)} → {formatDate(r.date_fin)}
            </span>
            <IconButton size="md" variant="outline" label="Supprimer"
              className="ml-auto text-destructive hover:text-destructive"
              onClick={() => del(r.id)}>
              <Trash2 className="size-4" aria-hidden="true" />
            </IconButton>
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <IndispoDialog techniciens={techniciens} emplacements={emplacements}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

function IndispoDialog({ techniciens, emplacements, onClose, onCreated }) {
  const [technicien, setTechnicien] = useState('')
  const [camionnette, setCamionnette] = useState('')
  const [type, setType] = useState('conge')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [motif, setMotif] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if ((!technicien && !camionnette) || (technicien && camionnette)) {
      setError('Renseignez exactement une cible : un technicien OU une camionnette.')
      return
    }
    if (!dateDebut || !dateFin) { setError('Les dates de début et de fin sont requises.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createIndisponibilite({
        technicien: technicien ? Number(technicien) : null,
        camionnette: camionnette ? Number(camionnette) : null,
        type_indispo: type, date_debut: dateDebut, date_fin: dateFin,
        motif: motif || null,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle indisponibilité</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="in-tech">Technicien (ou laisser vide)</label>
        <select id="in-tech" className="form-control" value={technicien} onChange={(e) => { setTechnicien(e.target.value); if (e.target.value) setCamionnette('') }}>
          <option value="">—</option>
          {techniciens.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
        </select>
        <label className="form-label" htmlFor="in-cam">Camionnette / emplacement (ou laisser vide)</label>
        <select id="in-cam" className="form-control" value={camionnette} onChange={(e) => { setCamionnette(e.target.value); if (e.target.value) setTechnicien('') }}>
          <option value="">—</option>
          {emplacements.map((e) => <option key={e.id} value={e.id}>{e.nom}</option>)}
        </select>
        <label className="form-label" htmlFor="in-type">Type</label>
        <select id="in-type" className="form-control" value={type} onChange={(e) => setType(e.target.value)}>
          {INDISPO_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <label className="form-label" htmlFor="in-debut">Début</label>
        <input id="in-debut" type="date" className="form-control" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
        <label className="form-label" htmlFor="in-fin">Fin</label>
        <input id="in-fin" type="date" className="form-control" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
        <label className="form-label" htmlFor="in-motif">Motif (optionnel)</label>
        <textarea id="in-motif" className="form-control" rows={2} value={motif} onChange={(e) => setMotif(e.target.value)} />
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

// ── Récurrences ──────────────────────────────────────────────────────────────
function RecurrencesTab({ techniciens, installations }) {
  const { rows, loading, error, reload } = useList(installationsApi.getRecurrencesIntervention)
  const [showCreate, setShowCreate] = useState(false)
  const del = async (id) => {
    if (!window.confirm('Supprimer cette récurrence ?')) return
    await installationsApi.deleteRecurrenceIntervention(id).catch(() => {})
    reload()
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle récurrence
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucune récurrence d'intervention">
        {rows.length > 0 && rows.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`recurrence-${r.id}`}>
            <span className="font-medium text-sm">{r.installation_reference || `#${r.installation}`}</span>
            <Badge tone="info">{r.regle_display || r.regle}</Badge>
            <span className="text-sm text-muted-foreground">{r.type_intervention}</span>
            <span className="text-xs text-muted-foreground">
              Prochaine : {formatDate(r.prochaine_echeance)} · {r.nb_generees ?? 0} générée(s)
            </span>
            <IconButton size="md" variant="outline" label="Supprimer"
              className="ml-auto text-destructive hover:text-destructive"
              onClick={() => del(r.id)}>
              <Trash2 className="size-4" aria-hidden="true" />
            </IconButton>
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <RecurrenceDialog techniciens={techniciens} installations={installations}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

function RecurrenceDialog({ techniciens, installations, onClose, onCreated }) {
  const [installation, setInstallation] = useState('')
  const [typeItv, setTypeItv] = useState('')
  const [technicien, setTechnicien] = useState('')
  const [regle, setRegle] = useState('mensuelle')
  const [echeance, setEcheance] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!installation || !typeItv.trim() || !echeance) {
      setError('Chantier, type d\'intervention et prochaine échéance sont requis.')
      return
    }
    setBusy(true); setError(null)
    try {
      await installationsApi.createRecurrenceIntervention({
        installation: Number(installation),
        type_intervention: typeItv.trim(),
        technicien_defaut: technicien ? Number(technicien) : null,
        regle, prochaine_echeance: echeance,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle récurrence d'intervention</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="re-inst">Chantier</label>
        <select id="re-inst" className="form-control" value={installation} onChange={(e) => setInstallation(e.target.value)} autoFocus>
          <option value="">— Choisir —</option>
          {installations.map((i) => <option key={i.id} value={i.id}>{i.reference || i.nom || `#${i.id}`}</option>)}
        </select>
        <label className="form-label" htmlFor="re-type">Type d'intervention</label>
        <input id="re-type" type="text" className="form-control" value={typeItv} onChange={(e) => setTypeItv(e.target.value)} placeholder="ex. maintenance" />
        <label className="form-label" htmlFor="re-tech">Technicien par défaut (optionnel)</label>
        <select id="re-tech" className="form-control" value={technicien} onChange={(e) => setTechnicien(e.target.value)}>
          <option value="">—</option>
          {techniciens.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
        </select>
        <label className="form-label" htmlFor="re-regle">Règle</label>
        <select id="re-regle" className="form-control" value={regle} onChange={(e) => setRegle(e.target.value)}>
          {RECURRENCE_REGLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <label className="form-label" htmlFor="re-echeance">Prochaine échéance</label>
        <input id="re-echeance" type="date" className="form-control" value={echeance} onChange={(e) => setEcheance(e.target.value)} />
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

export default function AstreintesPage() {
  const [techniciens, setTechniciens] = useState([])
  const [installations, setInstallations] = useState([])
  const [emplacements, setEmplacements] = useState([])

  useEffect(() => {
    let alive = true
    Promise.all([
      crmApi.getAssignableUsers().catch(() => ({ data: [] })),
      installationsApi.getInstallations({ page_size: 200 }).catch(() => ({ data: [] })),
      stockApi.getEmplacements().catch(() => ({ data: [] })),
    ]).then(([u, i, e]) => {
      if (!alive) return
      setTechniciens(u.data?.results ?? u.data ?? [])
      setInstallations(i.data?.results ?? i.data ?? [])
      setEmplacements(e.data?.results ?? e.data ?? [])
    })
    return () => { alive = false }
  }, [])

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Astreintes & indisponibilités"
        subtitle="Tours de garde, créneaux d'indisponibilité des ressources et récurrences d'intervention."
      />
      <Tabs defaultValue="astreintes" className="flex flex-col gap-4">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="astreintes">Astreintes</TabsTrigger>
          <TabsTrigger value="indispos">Indisponibilités</TabsTrigger>
          <TabsTrigger value="recurrences">Récurrences</TabsTrigger>
        </TabsList>
        <TabsContent value="astreintes">
          <AstreintesTab techniciens={techniciens} />
        </TabsContent>
        <TabsContent value="indispos">
          <IndisposTab techniciens={techniciens} emplacements={emplacements} />
        </TabsContent>
        <TabsContent value="recurrences">
          <RecurrencesTab techniciens={techniciens} installations={installations} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
