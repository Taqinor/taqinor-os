/* ============================================================================
   PACT59 — Suivi projet du chantier : jalons, modèles, comptes-rendus.
   ----------------------------------------------------------------------------
   Trou (a) : `JalonProjetViewSet` (phases étude/appro/pose/mes/réception, dates
   cible vs réelles), `ModeleProjetViewSet` (patron de chantier type qui
   pré-crée jalons + nomenclature) et `ReunionChantierViewSet` (comptes-rendus
   horodatés) dans `views/projet.py` — 3 ressources sans appelant.
   ========================================================================== */
import { useCallback, useEffect, useState } from 'react'
import { PlusCircle } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Button, Spinner, EmptyState,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDate } from '../../lib/format'
import installationsApi from '../../api/installationsApi'

const PHASES = [
  ['etude', 'Étude'], ['appro', 'Approvisionnement'], ['pose', 'Pose'],
  ['mes', 'Mise en service'], ['reception', 'Réception'],
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

// ── Onglet Jalons ────────────────────────────────────────────────────────────
function CreateJalonDialog({ installationId, onClose, onCreated }) {
  const [phase, setPhase] = useState('etude')
  const [libelle, setLibelle] = useState('')
  const [dateCible, setDateCible] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!libelle.trim()) { setError('Le libellé est obligatoire.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createJalonProjet({
        installation: installationId, phase, libelle: libelle.trim(),
        date_cible: dateCible || null,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouveau jalon</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="jp-phase">Phase</label>
        <select id="jp-phase" className="form-control" value={phase} onChange={(e) => setPhase(e.target.value)} autoFocus>
          {PHASES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <label className="form-label" htmlFor="jp-libelle">Libellé</label>
        <input id="jp-libelle" type="text" className="form-control" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
        <label className="form-label" htmlFor="jp-date">Date cible (optionnel)</label>
        <input id="jp-date" type="date" className="form-control" value={dateCible} onChange={(e) => setDateCible(e.target.value)} />
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

function JalonsTab({ installationId }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getJalonsProjet, { installation: installationId })
  const [showCreate, setShowCreate] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const marquerAtteint = async (jalon) => {
    setBusyId(jalon.id)
    await installationsApi.updateJalonProjet(jalon.id, {
      atteint: true, date_reelle: new Date().toISOString().slice(0, 10),
    }).catch(() => {})
    setBusyId(null); reload()
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouveau jalon
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucun jalon défini">
        {rows.length > 0 && rows.map((j) => (
          <div key={j.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`jalon-${j.id}`}>
            <Badge tone="neutral">{j.phase_display || j.phase}</Badge>
            <span className="font-medium text-sm">{j.libelle}</span>
            <span className="text-xs text-muted-foreground">
              Cible {formatDate(j.date_cible)} · Réelle {j.date_reelle ? formatDate(j.date_reelle) : '—'}
            </span>
            <Badge tone={j.atteint ? 'success' : 'warning'} className="ml-auto">
              {j.atteint ? 'Atteint' : 'En cours'}
            </Badge>
            {!j.atteint && (
              <Button size="sm" variant="outline" disabled={busyId === j.id} onClick={() => marquerAtteint(j)}>
                Marquer atteint
              </Button>
            )}
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <CreateJalonDialog installationId={installationId}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

// ── Onglet Modèles de projet ─────────────────────────────────────────────────
function ModelesTab({ installationId }) {
  const { rows, loading, error } = useFilteredList(installationsApi.getModelesProjet, {})
  const [busyId, setBusyId] = useState(null)
  const [resultat, setResultat] = useState(null)

  const instancier = async (modele) => {
    setBusyId(modele.id); setResultat(null)
    try {
      const res = await installationsApi.instancierModeleProjet(modele.id, installationId)
      setResultat({ modele: modele.nom, ...res.data })
    } catch { /* affiché nulle part : réessai possible depuis le bouton */ }
    finally { setBusyId(null) }
  }

  return (
    <div className="flex flex-col gap-3">
      {resultat && (
        <p className="text-sm text-muted-foreground" data-testid="resultat-instanciation">
          Modèle « {resultat.modele} » appliqué : {resultat.jalons_crees ?? 0} jalon(s) créé(s),
          {' '}{resultat.bom_lignes_ajoutees ?? 0} ligne(s) de nomenclature ajoutée(s).
        </p>
      )}
      <ListShell loading={loading} error={error} empty="Aucun modèle de projet configuré">
        {rows.length > 0 && rows.map((m) => (
          <div key={m.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`modele-projet-${m.id}`}>
            <span className="font-medium text-sm">{m.nom}</span>
            {m.type_installation_display && <Badge tone="neutral">{m.type_installation_display}</Badge>}
            <span className="text-xs text-muted-foreground">
              {(m.jalons || []).length} jalon(s) modèle · {(m.bom_lignes || []).length} ligne(s) BoM
            </span>
            <Button size="sm" variant="outline" className="ml-auto" disabled={busyId === m.id}
              onClick={() => instancier(m)}>
              Instancier sur ce chantier
            </Button>
          </div>
        ))}
      </ListShell>
    </div>
  )
}

// ── Onglet Réunions de chantier ──────────────────────────────────────────────
function CreateReunionDialog({ installationId, onClose, onCreated }) {
  const [titre, setTitre] = useState('')
  const [dateReunion, setDateReunion] = useState('')
  const [ordreDuJour, setOrdreDuJour] = useState('')
  const [decisions, setDecisions] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!titre.trim() || !dateReunion) {
      setError('Titre et date de réunion sont requis.')
      return
    }
    setBusy(true); setError(null)
    try {
      await installationsApi.createReunionChantier({
        installation: installationId, titre: titre.trim(),
        date_reunion: dateReunion, ordre_du_jour: ordreDuJour || undefined,
        decisions: decisions || undefined,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouveau compte-rendu</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="rc-titre">Titre</label>
        <input id="rc-titre" type="text" className="form-control" value={titre} onChange={(e) => setTitre(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="rc-date">Date de réunion</label>
        <input id="rc-date" type="date" className="form-control" value={dateReunion} onChange={(e) => setDateReunion(e.target.value)} />
        <label className="form-label" htmlFor="rc-odj">Ordre du jour (optionnel)</label>
        <textarea id="rc-odj" className="form-control" rows={2} value={ordreDuJour} onChange={(e) => setOrdreDuJour(e.target.value)} />
        <label className="form-label" htmlFor="rc-decisions">Décisions (optionnel)</label>
        <textarea id="rc-decisions" className="form-control" rows={2} value={decisions} onChange={(e) => setDecisions(e.target.value)} />
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

function ReunionsTab({ installationId }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getReunionsChantier, { installation: installationId })
  const [showCreate, setShowCreate] = useState(false)
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouveau compte-rendu
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucun compte-rendu de réunion">
        {rows.length > 0 && rows.map((r) => (
          <div key={r.id} className="flex flex-col gap-1 rounded-xl border border-border bg-card p-3" data-testid={`reunion-${r.id}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-sm">{r.titre}</span>
              <span className="text-xs text-muted-foreground">{formatDate(r.date_reunion)}</span>
              {r.redige_par_nom && <span className="text-xs text-muted-foreground">— {r.redige_par_nom}</span>}
            </div>
            {r.decisions && <p className="text-sm text-muted-foreground">{r.decisions}</p>}
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <CreateReunionDialog installationId={installationId}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

export default function SuiviProjetChantier() {
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
        title="Suivi projet du chantier"
        subtitle="Jalons de phase, modèles de projet et comptes-rendus de réunion."
      />
      {loadingChantiers ? (
        <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
          <Spinner className="size-4 text-primary" /> Chargement…
        </p>
      ) : chantiers.length === 0 ? (
        <EmptyState title="Aucun chantier" description="Créez un chantier avant de suivre son projet." className="py-10" />
      ) : (
        <>
          <label className="form-label" htmlFor="spc-chantier">Chantier</label>
          <select id="spc-chantier" className="form-control max-w-sm" value={selected ?? ''} onChange={(e) => setSelected(Number(e.target.value))}>
            {chantiers.map((c) => <option key={c.id} value={c.id}>{c.reference || `#${c.id}`}</option>)}
          </select>
          {selected != null && (
            <Tabs defaultValue="jalons" className="flex flex-col gap-4">
              <TabsList className="flex flex-wrap">
                <TabsTrigger value="jalons">Jalons</TabsTrigger>
                <TabsTrigger value="modeles">Modèles de projet</TabsTrigger>
                <TabsTrigger value="reunions">Réunions de chantier</TabsTrigger>
              </TabsList>
              <TabsContent value="jalons">
                <JalonsTab installationId={selected} />
              </TabsContent>
              <TabsContent value="modeles">
                <ModelesTab installationId={selected} />
              </TabsContent>
              <TabsContent value="reunions">
                <ReunionsTab installationId={selected} />
              </TabsContent>
            </Tabs>
          )}
        </>
      )}
    </div>
  )
}
