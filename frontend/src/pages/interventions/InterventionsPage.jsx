// F4 — Interventions (sorties chantier) : liste + kanban groupé par statut
// PROPRE de l'intervention (machine à états distincte du chantier et de
// STAGES.py). Même langage visuel que le kanban chantiers/leads : glisser pour
// changer de statut, réassignation du technicien, cartes portant client,
// ville, type, date prévue, équipe et statut. Tout le texte est en français.
import { useEffect, useMemo, useState } from 'react'
import { MapPin, CalendarDays, Users, Wrench } from 'lucide-react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import installationsApi from '../../api/installationsApi'
import crmApi from '../../api/crmApi'
import { hapticTap } from '../../lib/haptics'
import {
  INTERVENTION_STATUSES,
  INTERVENTION_STATUS_LABELS,
  INTERVENTION_STATUS_COLORS,
  interventionStatusLabel,
  INTERVENTION_TYPES,
} from '../../features/installations/statuses'
import {
  Button,
  Badge,
  Segmented,
  Spinner,
  EmptyState,
  Card,
  StatusPill,
  StatusAccentCard,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  Textarea,
  toast,
} from '../../ui'
import { useIsMobile } from '../../ui/ResponsiveDialog'
import { usePullToRefresh } from '../../ui/usePullToRefresh'
import {
  PreparationPanel, TrajetPanel, PhotosPanel,
} from '../../features/installations/InterventionFieldExecution'
import {
  SerialsPanel, ConsommationPanel, MemosPanel, ReservesPanel,
  ToolReturnPanel, SafetyPanel, CompteRenduButton, CodePanel,
} from '../../features/installations/InterventionCapturePanels'
import { SignatureClientPanel } from '../../features/installations/SignatureClientPanel'
import OfflineSyncIndicator from '../../features/installations/offline/OfflineSyncIndicator'
import { formatDate, formatDateTime } from '../../lib/format'

// VX43 — repli « changer le statut au menu » sans drag, sous 768px : le
// glisser-déposer @dnd-kit (TouchSensor delay 150ms) reste utilisable au
// pouce, mais un menu <select> natif est une alternative sans ambigüité de
// geste sur les petits écrans (même besoin que StageMover côté leads).
function useIsMobileViewport() {
  return useIsMobile('(max-width: 767px)')
}

const TYPE_LABELS = Object.fromEntries(
  INTERVENTION_TYPES.map((t) => [t.value, t.label]))
const typeLabel = (k) => TYPE_LABELS[k] ?? k ?? '—'

// Sentinelle « aucun technicien » (le Select du design system n'accepte pas '').
const NO_TECH = '__none__'

function InterventionCard({ it, users, onReassign, onChangeStatus }) {
  const techValue = it.technicien ? String(it.technicien) : NO_TECH
  return (
    <StatusAccentCard accent={INTERVENTION_STATUS_COLORS[it.statut]}>
      <div className="kc-card-top">
        <span className="kc-card-ref">{it.installation_reference ?? `#${it.id}`}</span>
        <StatusPill status={it.statut} label={interventionStatusLabel(it.statut)} dot={false} />
      </div>
      <div className="kc-card-sub">{it.client_nom ?? '—'}</div>
      <div className="kc-chips">
        <span className="kc-chip"><Wrench className="kc-chip-icon" aria-hidden="true" />{typeLabel(it.type_intervention)}</span>
        {it.site_ville && (
          <span className="kc-chip"><MapPin className="kc-chip-icon" aria-hidden="true" />{it.site_ville}</span>
        )}
        {formatDate(it.date_prevue) !== '—' && (
          <span className="kc-chip"><CalendarDays className="kc-chip-icon" aria-hidden="true" />{formatDate(it.date_prevue)}</span>
        )}
        {(it.equipe_noms?.length ?? 0) > 0 && (
          <span className="kc-chip"><Users className="kc-chip-icon" aria-hidden="true" />{it.equipe_noms.join(', ')}</span>
        )}
      </div>
      {/* VX43 — repli SANS glisser sous 768px : le glisser-déposer @dnd-kit
          reste actif (delay tactile 150ms), mais un <select> natif offre une
          alternative univoque au pouce, masqué en desktop (`sm:hidden`, comme
          le reste du repli mobile du DataTable). */}
      {onChangeStatus && (
        <div className="kc-status-mover sm:hidden"
             onPointerDown={(e) => e.stopPropagation()}
             onTouchStart={(e) => e.stopPropagation()}
             onClick={(e) => e.stopPropagation()}>
          <label className="sr-only" htmlFor={`kc-status-${it.id}`}>
            Changer le statut de {it.client_nom || it.installation_reference || `l'intervention #${it.id}`}
          </label>
          <select
            id={`kc-status-${it.id}`}
            className="form-control h-8 w-full rounded-md border border-input bg-card px-2 text-xs"
            value={it.statut}
            onChange={(e) => onChangeStatus(it, e.target.value)}
          >
            {INTERVENTION_STATUSES.map((s) => (
              <option key={s} value={s}>{INTERVENTION_STATUS_LABELS[s]}</option>
            ))}
          </select>
        </div>
      )}
      {onReassign && (
        <div className="kc-reassign"
             onPointerDown={(e) => e.stopPropagation()}
             onClick={(e) => e.stopPropagation()}>
          <Select value={techValue}
                  onValueChange={(v) => onReassign(it, v === NO_TECH ? null : v)}>
            <SelectTrigger className="h-8 text-xs" aria-label="Technicien">
              <SelectValue placeholder="Technicien" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_TECH}>— Technicien —</SelectItem>
              {(users ?? []).map((u) => (
                <SelectItem key={u.id} value={String(u.id)}>
                  {u.username ?? u.nom ?? `#${u.id}`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    </StatusAccentCard>
  )
}

function DraggableCard({ it, users, onReassign, onChangeStatus }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: it.id, data: { it },
  })
  return (
    <div ref={setNodeRef}
         className={isDragging ? 'kb-drag-wrap kb-drag-source' : 'kb-drag-wrap'}
         {...listeners} {...attributes}>
      <InterventionCard it={it} users={users} onReassign={onReassign} onChangeStatus={onChangeStatus} />
    </div>
  )
}

function StatusColumn({ col, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key })
  return (
    <section ref={setNodeRef} className={isOver ? 'kb-col kb-over' : 'kb-col'}
             style={{ '--kb-accent': col.color }}>
      <header className="kb-col-header">
        <div className="kb-col-title-row">
          <span className="kb-col-title">{col.label}</span>
          <span className="kb-col-count">{col.items.length}</span>
        </div>
      </header>
      <div className="kb-col-body">
        {col.items.length === 0
          ? <div className="kb-col-empty">Aucune intervention</div>
          : children}
      </div>
    </section>
  )
}

function KanbanView({ items, onOpen, onChangeStatus, users, onReassign }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
  )
  const [active, setActive] = useState(null)

  const columns = useMemo(() => {
    const byCol = Object.fromEntries(INTERVENTION_STATUSES.map((s) => [s, []]))
    for (const it of items ?? []) {
      if (byCol[it.statut]) byCol[it.statut].push(it)
      else byCol[INTERVENTION_STATUSES[0]].push(it)
    }
    return INTERVENTION_STATUSES.map((s) => ({
      key: s,
      label: INTERVENTION_STATUS_LABELS[s],
      color: INTERVENTION_STATUS_COLORS[s],
      items: byCol[s],
    }))
  }, [items])

  const handleDragEnd = ({ active: a, over }) => {
    setActive(null)
    const it = a.data.current?.it
    if (it && over && over.id !== it.statut) onChangeStatus?.(it, over.id)
  }

  return (
    <DndContext sensors={sensors}
                onDragStart={({ active: a }) => setActive(a.data.current?.it ?? null)}
                onDragEnd={handleDragEnd}
                onDragCancel={() => setActive(null)}>
      <div className="kb-board">
        {columns.map((col) => (
          <StatusColumn key={col.key} col={col}>
            {col.items.map((it) => (
              <div key={it.id} onClick={() => onOpen?.(it)}>
                <DraggableCard it={it} users={users} onReassign={onReassign} onChangeStatus={onChangeStatus} />
              </div>
            ))}
          </StatusColumn>
        ))}
      </div>
      <DragOverlay>
        {active ? (
          <div className="kb-drag-overlay"><InterventionCard it={active} /></div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}

function ListView({ items, onOpen }) {
  if (!items.length) {
    return (
      <Card className="p-0">
        <EmptyState
          title="Aucune intervention"
          description="Les interventions se créent depuis la fiche d'un chantier."
          className="border-0"
        />
      </Card>
    )
  }
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>Chantier</th>
            <th>Client</th>
            <th className="m-hide">Ville</th>
            <th>Type</th>
            <th className="m-hide">Date prévue</th>
            <th className="m-hide">Équipe</th>
            <th>Statut</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.id} className="lv-row" onClick={() => onOpen(it)} style={{ cursor: 'pointer' }}>
              <td data-label="Chantier">{it.installation_reference ?? `#${it.id}`}</td>
              <td data-label="Client">{it.client_nom ?? '—'}</td>
              <td data-label="Ville" className="m-hide">{it.site_ville ?? '—'}</td>
              <td data-label="Type">{typeLabel(it.type_intervention)}</td>
              <td data-label="Date prévue" className="m-hide">{formatDate(it.date_prevue)}</td>
              <td data-label="Équipe" className="m-hide">{(it.equipe_noms ?? []).join(', ') || '—'}</td>
              <td data-label="Statut">
                <StatusPill status={it.statut} label={interventionStatusLabel(it.statut)} dot={false} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DetailSheet({ intervention, users, onClose, onChanged }) {
  const [hist, setHist] = useState([])
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  // VX43 — bottom-sheet sous 768px (glisser-vers-le-bas-pour-fermer inclus
  // nativement par Sheet.jsx pour side="bottom") ; tiroir latéral inchangé
  // sur desktop.
  const isMobile = useIsMobileViewport()

  useEffect(() => {
    let alive = true
    installationsApi.getInterventionHistorique(intervention.id)
      .then((r) => { if (alive) setHist(r.data ?? []) })
      .catch(() => { if (alive) setHist([]) })
    return () => { alive = false }
  }, [intervention.id])

  const reloadHist = () =>
    installationsApi.getInterventionHistorique(intervention.id)
      .then((r) => setHist(r.data ?? [])).catch(() => {})

  const setStatut = async (statut) => {
    setBusy(true)
    try {
      await installationsApi.updateIntervention(intervention.id, { statut })
      toast.success('Statut mis à jour.')
      hapticTap()
      await reloadHist()
      onChanged?.()
    } catch {
      toast.error('Impossible de changer le statut.')
    } finally { setBusy(false) }
  }

  const setTech = async (v) => {
    setBusy(true)
    try {
      await installationsApi.updateIntervention(
        intervention.id, { technicien: v === NO_TECH ? null : v })
      toast.success('Technicien mis à jour.')
      onChanged?.()
    } catch {
      toast.error('Impossible de réassigner.')
    } finally { setBusy(false) }
  }

  const addNote = async () => {
    const body = note.trim()
    if (!body) return
    setBusy(true)
    try {
      await installationsApi.noterIntervention(intervention.id, body)
      setNote('')
      await reloadHist()
      toast.success('Note ajoutée.')
    } catch {
      toast.error('Note non enregistrée — réessayez.')
    } finally { setBusy(false) }
  }

  const techValue = intervention.technicien ? String(intervention.technicien) : NO_TECH

  // Badges d'alerte F5/F8 sur les onglets : préparation non confirmée, photos
  // obligatoires manquantes.
  const prepPct = intervention.preparation_completion
  const photosManquantes = intervention.photos_obligatoires_manquantes ?? 0

  return (
    <Sheet open onOpenChange={(o) => { if (!o) onClose() }}>
      <SheetContent
        side={isMobile ? 'bottom' : 'right'}
        className={isMobile ? 'max-h-[85vh] w-full overflow-y-auto' : 'w-full sm:max-w-md overflow-y-auto'}
      >
        <SheetHeader>
          <SheetTitle>
            {typeLabel(intervention.type_intervention)} — {intervention.installation_reference ?? `#${intervention.id}`}
          </SheetTitle>
        </SheetHeader>

        {/* N91/F21 — état de la synchro terrain hors-ligne (silencieux si en
            ligne et file vide). */}
        <OfflineSyncIndicator />

        <Tabs defaultValue="detail" className="mt-2">
          <TabsList className="flex w-full justify-start overflow-x-auto">
            <TabsTrigger value="detail" className="shrink-0">Détail</TabsTrigger>
            <TabsTrigger value="preparation" className="shrink-0">
              Préparation
              {!intervention.preparation_confirmee && prepPct != null && (
                <Badge tone="warning" className="ml-1.5">{prepPct}%</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="trajet" className="shrink-0">Trajet</TabsTrigger>
            <TabsTrigger value="securite" className="shrink-0">Sécurité</TabsTrigger>
            <TabsTrigger value="photos" className="shrink-0">
              Photos
              {photosManquantes > 0 && (
                <Badge tone="danger" className="ml-1.5">{photosManquantes}</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="serie" className="shrink-0">N° série</TabsTrigger>
            <TabsTrigger value="conso" className="shrink-0">Consommé</TabsTrigger>
            <TabsTrigger value="memos" className="shrink-0">Mémos</TabsTrigger>
            <TabsTrigger value="reserves" className="shrink-0">Réserves</TabsTrigger>
            <TabsTrigger value="signature" className="shrink-0">Signature</TabsTrigger>
            <TabsTrigger value="outils" className="shrink-0">Outils</TabsTrigger>
          </TabsList>

          <TabsContent value="preparation">
            <PreparationPanel intervention={intervention} onChanged={onChanged} />
          </TabsContent>
          <TabsContent value="trajet">
            <TrajetPanel intervention={intervention} onChanged={onChanged} />
          </TabsContent>
          <TabsContent value="securite">
            <SafetyPanel intervention={intervention} onChanged={onChanged} />
          </TabsContent>
          <TabsContent value="photos">
            <PhotosPanel intervention={intervention} onChanged={onChanged} />
          </TabsContent>
          <TabsContent value="serie">
            <SerialsPanel intervention={intervention} onChanged={onChanged} />
          </TabsContent>
          <TabsContent value="conso">
            <ConsommationPanel intervention={intervention} onChanged={onChanged} />
          </TabsContent>
          <TabsContent value="memos">
            <MemosPanel intervention={intervention} onChanged={onChanged} />
          </TabsContent>
          <TabsContent value="reserves">
            <ReservesPanel intervention={intervention} onChanged={onChanged} />
          </TabsContent>
          <TabsContent value="signature">
            <SignatureClientPanel intervention={intervention} onChanged={onChanged} />
          </TabsContent>
          <TabsContent value="outils">
            <div className="flex flex-col gap-3 py-2">
              <CompteRenduButton intervention={intervention} />
              <ToolReturnPanel intervention={intervention} onChanged={onChanged} />
              <CodePanel intervention={intervention} />
            </div>
          </TabsContent>

          <TabsContent value="detail">
        <div className="flex flex-col gap-4 py-2 text-sm">
          <div className="flex flex-col gap-1">
            <span className="text-muted-foreground">Client</span>
            <span>{intervention.client_nom ?? '—'}</span>
          </div>
          {intervention.site_ville && (
            <div className="flex flex-col gap-1">
              <span className="text-muted-foreground">Ville</span>
              <span>{intervention.site_ville}</span>
            </div>
          )}
          <div className="flex flex-col gap-1">
            <span className="text-muted-foreground">Date prévue</span>
            <span>{formatDate(intervention.date_prevue)}</span>
          </div>
          {(intervention.equipe_noms?.length ?? 0) > 0 && (
            <div className="flex flex-col gap-1">
              <span className="text-muted-foreground">Équipe</span>
              <span>{intervention.equipe_noms.join(', ')}</span>
            </div>
          )}

          <div className="flex flex-col gap-1">
            <span className="text-muted-foreground">Statut</span>
            <Select value={intervention.statut} onValueChange={setStatut} disabled={busy}>
              <SelectTrigger aria-label="Statut">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INTERVENTION_STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>{INTERVENTION_STATUS_LABELS[s]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-muted-foreground">Technicien</span>
            <Select value={techValue} onValueChange={setTech} disabled={busy}>
              <SelectTrigger aria-label="Technicien">
                <SelectValue placeholder="— Technicien —" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_TECH}>— Technicien —</SelectItem>
                {(users ?? []).map((u) => (
                  <SelectItem key={u.id} value={String(u.id)}>
                    {u.username ?? u.nom ?? `#${u.id}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-muted-foreground">Historique</span>
            {hist.length === 0
              ? <span className="text-muted-foreground">Aucune activité.</span>
              : (
                <ul className="flex flex-col gap-2">
                  {hist.map((e) => (
                    <li key={e.id} className="rounded border border-border p-2">
                      <div className="text-xs text-muted-foreground">
                        {e.user_nom ?? '—'} · {formatDateTime(e.created_at)}
                      </div>
                      <div>
                        {e.kind === 'modification'
                          ? `${e.field_label} : ${e.old_value} → ${e.new_value}`
                          : e.body}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            <Textarea value={note} onChange={(e) => setNote(e.target.value)}
                      placeholder="Ajouter une note…" rows={2} />
            <Button size="sm" onClick={addNote} disabled={busy || !note.trim()}>
              Ajouter la note
            </Button>
          </div>
        </div>
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  )
}

const VIEW_KEY = 'taqinor.interventions.view'
const VALID_VIEWS = ['liste', 'kanban']

export default function InterventionsPage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [users, setUsers] = useState([])
  const [selected, setSelected] = useState(null)
  const [fStatut, setFStatut] = useState('')
  const [fType, setFType] = useState('')

  const [view, setView] = useState(() => {
    try {
      const saved = localStorage.getItem(VIEW_KEY)
      return VALID_VIEWS.includes(saved) ? saved : 'kanban'
    } catch { return 'kanban' }
  })
  useEffect(() => {
    try { localStorage.setItem(VIEW_KEY, view) } catch { /* stockage indisponible */ }
  }, [view])

  // Récupère sans toucher `loading` de façon synchrone (compat règle hooks) :
  // l'état initial est déjà `true`, et un rafraîchissement de fond ne fait pas
  // clignoter le spinner du kanban.
  const fetchData = () => installationsApi.getInterventions()
    .then((r) => { setItems(r.data?.results ?? r.data ?? []); setError(null) })
    .catch(() => setError('Impossible de charger les interventions. Réessayez.'))
    .finally(() => setLoading(false))
  const reload = () => { setLoading(true); return fetchData() }
  useEffect(() => { fetchData() }, [])
  useEffect(() => {
    crmApi.getAssignableUsers()
      .then((r) => setUsers(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  const filtered = useMemo(() => (items ?? []).filter((it) =>
    (!fStatut || it.statut === fStatut)
    && (!fType || it.type_intervention === fType)
  ), [items, fStatut, fType])

  const patchStatus = (it, statut) => {
    // Optimiste : reflète immédiatement, recharge en arrière-plan.
    setItems((prev) => prev.map((x) => (x.id === it.id ? { ...x, statut } : x)))
    installationsApi.updateIntervention(it.id, { statut })
      .then(() => { toast.success('Statut mis à jour.'); fetchData() })
      .catch(() => { toast.error('Changement de statut impossible.'); fetchData() })
  }
  const reassign = (it, technicien) => {
    // Optimiste : reflète immédiatement, puis resynchronise. En cas d'échec on
    // recharge (rollback) pour que le Select ne reste pas sur le technicien
    // choisi alors que le serveur garde l'ancien.
    setItems((prev) => prev.map((x) => (x.id === it.id ? { ...x, technicien } : x)))
    installationsApi.updateIntervention(it.id, { technicien })
      .then(() => { toast.success('Technicien mis à jour.'); fetchData() })
      .catch(() => { toast.error('Réassignation impossible.'); fetchData() })
  }

  // VX43 — pull-to-refresh maison : `overscroll-behavior: contain` a coupé le
  // rubber-band natif sans rien remettre à sa place. Relance `fetchData` (pas
  // `reload` — un rafraîchissement de fond ne doit pas faire clignoter la vue).
  // Appelé AVANT tout early-return : les hooks doivent s'exécuter dans le même
  // ordre à chaque rendu (rules-of-hooks).
  const { containerProps, pullDistance, refreshing } = usePullToRefresh(fetchData)

  if (loading) {
    return (
      <div className="page lp-page">
        <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
          <Spinner /> Chargement des interventions…
        </div>
      </div>
    )
  }
  if (error) {
    return (
      <div className="page lp-page">
        <EmptyState
          title="Impossible de charger les interventions"
          description={error}
          action={<Button size="sm" onClick={reload}>Réessayer</Button>}
          className="my-8 border-destructive/40"
        />
      </div>
    )
  }

  return (
    <div className="page lp-page overflow-y-auto" {...containerProps}>
      {(pullDistance > 0 || refreshing) && (
        <div
          className="flex items-center justify-center gap-2 text-xs text-muted-foreground"
          style={{ height: `${Math.max(pullDistance, refreshing ? 32 : 0)}px`, overflow: 'hidden', transition: refreshing ? 'height 150ms ease' : 'none' }}
          role="status"
        >
          {refreshing ? <Spinner className="size-4" /> : null}
          {refreshing ? 'Actualisation…' : 'Tirer pour actualiser'}
        </div>
      )}
      <div className="page-header lp-header">
        <h2 className="flex items-center gap-2">
          Interventions
          <Badge tone="primary">{filtered.length}</Badge>
        </h2>
        <div className="page-header-actions lp-header-actions flex flex-wrap items-center gap-2">
          <Select value={fStatut || '__all__'}
                  onValueChange={(v) => setFStatut(v === '__all__' ? '' : v)}>
            <SelectTrigger className="h-9 w-40" aria-label="Filtrer par statut">
              <SelectValue placeholder="Statut" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">Tous les statuts</SelectItem>
              {INTERVENTION_STATUSES.map((s) => (
                <SelectItem key={s} value={s}>{INTERVENTION_STATUS_LABELS[s]}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={fType || '__all__'}
                  onValueChange={(v) => setFType(v === '__all__' ? '' : v)}>
            <SelectTrigger className="h-9 w-44" aria-label="Filtrer par type">
              <SelectValue placeholder="Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">Tous les types</SelectItem>
              {INTERVENTION_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Segmented
            size="sm"
            value={view}
            onChange={setView}
            aria-label="Changer de vue"
            options={[
              { value: 'liste', label: 'Liste' },
              { value: 'kanban', label: 'Kanban' },
            ]}
          />
        </div>
      </div>

      <div className="lp-view-area">
        {view === 'liste' && <ListView items={filtered} onOpen={setSelected} />}
        {view === 'kanban' && (
          <KanbanView items={filtered} onOpen={setSelected}
                      onChangeStatus={patchStatus} users={users} onReassign={reassign} />
        )}
      </div>

      {selected && (
        <DetailSheet
          intervention={filtered.find((x) => x.id === selected.id) ?? selected}
          users={users}
          onClose={() => setSelected(null)}
          onChanged={fetchData}
        />
      )}
    </div>
  )
}
