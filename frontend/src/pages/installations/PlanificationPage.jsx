// WR10 — Planification & logistique chantiers/interventions : câble les
// endpoints de scheduling/logistique qui n'avaient aucune UI. Regroupe en
// onglets le Gantt multi-chantier (FG74), le calendrier dispatch techniciens
// (FG68), « ma tournée » (FG73), le plan de charge / conflits / nivellement
// (FG299-301), le planning camionnettes (FG303) et deux outils par chantier
// (suggestion de régime loi 82-21 N43 + génération des interventions
// standard FG79). La synthèse coût/marge (FG71, INTERNE admin-only) vit dans
// un onglet séparé, jamais exposée hors du rôle admin.
//
// Ne touche PAS à InstallationDetail.jsx / InstallationsPage.jsx (Group CH
// possède la refonte du statut/stepper) : ce module est une surface neuve,
// autonome, réutilisant le kit ui/ existant (Card, Tabs, DataTable, Select…).
import { useEffect, useMemo, useState } from 'react'
import {
  DndContext, DragOverlay, PointerSensor, TouchSensor,
  useDraggable, useDroppable, useSensor, useSensors,
} from '@dnd-kit/core'
import { useIsAdmin } from '../../hooks/useHasPermission'
import {
  CalendarRange, Navigation, Users, AlertTriangle, Scale, Truck,
  Wrench, Gauge, ExternalLink, GripVertical,
} from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent,
  Badge, Spinner, EmptyState, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem, Tabs, TabsList, TabsTrigger, TabsContent,
  Input, Button, toast,
} from '../../ui'
import { toastWithUndo } from '../../lib/toast'
import { timelineBounds, barGeometry, markerGeometry } from '../../features/gestion_projet/gantt'
import { formatDate } from '../../lib/format'

function todayISO() {
  const d = new Date()
  const tz = d.getTimezoneOffset() * 60000
  return new Date(d - tz).toISOString().slice(0, 10)
}

function mondayOf(date) {
  const d = new Date(date)
  const day = (d.getDay() + 6) % 7 // 0 = lundi
  d.setDate(d.getDate() - day)
  return d
}

function isoOf(d) { return d.toISOString().slice(0, 10) }

function defaultWeek() {
  const today = new Date()
  const debut = mondayOf(today)
  const fin = new Date(debut)
  fin.setDate(fin.getDate() + 6)
  return { debut: isoOf(debut), fin: isoOf(fin) }
}

// ── FG74 — Gantt multi-chantier ──────────────────────────────────────────────
const GANTT_JALON_ORDER = [
  ['signature', 'Signature'],
  ['materiel_commande', 'Matériel commandé'],
  ['pose_prevue', 'Pose prévue'],
  ['pose_reelle', 'Pose réelle'],
  ['mise_en_service', 'Mise en service'],
  ['reception', 'Réception'],
  ['cloture', 'Clôture'],
]

function GanttTab() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    installationsApi.getGanttChantiers()
      .then((r) => { if (alive) setRows(r.data ?? []) })
      .catch(() => { if (alive) setError('Impossible de charger le Gantt des chantiers.') })
    return () => { alive = false }
  }, [])

  const bounds = useMemo(() => {
    if (!rows) return null
    const bars = rows.map((row) => {
      const dates = GANTT_JALON_ORDER
        .map(([k]) => row.jalons?.[k])
        .filter(Boolean)
      return { date_debut: dates[0], date_fin: dates[dates.length - 1] }
    }).filter((b) => b.date_debut)
    return timelineBounds(bars)
  }, [rows])

  if (error) {
    return <EmptyState icon={AlertTriangle} title="Gantt indisponible" description={error} />
  }
  if (!rows) {
    return <p className="flex items-center gap-2 py-8 text-sm text-muted-foreground"><Spinner className="size-4" /> Chargement du Gantt…</p>
  }
  if (rows.length === 0 || !bounds) {
    return (
      <EmptyState icon={CalendarRange} title="Aucun chantier actif daté"
        description="Les chantiers actifs (non clôturés, non annulés) avec au moins un jalon daté apparaîtront ici." />
    )
  }

  const { min, max } = bounds
  return (
    <div className="flex flex-col gap-3" data-testid="gantt-chantiers">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{formatDate(min)}</span>
        <span>{formatDate(max)}</span>
      </div>
      <div className="flex flex-col gap-1.5" role="list" aria-label="Gantt multi-chantier">
        {rows.map((row) => {
          const dates = GANTT_JALON_ORDER.map(([k]) => row.jalons?.[k]).filter(Boolean)
          const debut = dates[0]
          const fin = dates[dates.length - 1]
          const geo = debut ? barGeometry(debut, fin || debut, min, max) : { offsetPct: 0, widthPct: 0 }
          return (
            <div key={row.id} className="grid grid-cols-[minmax(140px,220px)_1fr] items-center gap-2" role="listitem">
              <span className="truncate text-sm" title={row.client_nom || row.reference}>
                <span className="mr-1 font-mono text-xs text-muted-foreground">{row.reference}</span>
                {row.client_nom}
              </span>
              <div className="relative h-5 rounded bg-muted/50">
                {geo.widthPct > 0 && (
                  <div className="absolute top-0.5 h-4 rounded bg-primary/80"
                    style={{ left: `${geo.offsetPct}%`, width: `${geo.widthPct}%` }}
                    title={`${row.reference} — ${formatDate(debut)} → ${formatDate(fin)}`} />
                )}
                {GANTT_JALON_ORDER.map(([k, label]) => {
                  const d = row.jalons?.[k]
                  if (!d) return null
                  const m = markerGeometry(d, min, max)
                  if (!m) return null
                  return (
                    <span key={k} className="absolute top-0 h-5 w-0.5 bg-foreground/40"
                      style={{ left: `${m.leftPct}%` }} title={`${label} — ${formatDate(d)}`} />
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── FG68 / VX251 — Calendrier dispatch techniciens (glisser-déposer) ──────────
// VX251 — glisser une carte intervention d'une colonne-technicien à une autre
// réaffecte réellement (PATCH `technicien` EXISTANT) avec un toastWithUndo 6 s
// (VX95, jamais un 2ᵉ primitif undo) : « Annuler » restaure l'affectation.
// Le geste réplique le pattern drag+recul-guard prouvé par KanbanView.jsx
// (CRM). Le Gantt (FG74) reste lecture seule — ce module n'y touche pas.
const NON_ASSIGNE = '__non_assigne__'

// Clé droppable stable d'une colonne technicien (id numérique ou sentinelle).
const colKey = (grp) => String(grp?.technicien?.id ?? NON_ASSIGNE)

// VX251 — déplacement PUR (testable) d'une intervention entre colonnes
// technicien de l'état du calendrier. Renvoie un nouvel état (jamais de
// mutation) ; renvoie l'entrée inchangée si l'intervention est introuvable
// dans la colonne source.
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé
export function moveInterventionLocal(list, ivId, fromKey, toKey) {
  let moved = null
  const stripped = (list ?? []).map((grp) => {
    if (colKey(grp) !== String(fromKey)) return grp
    const kept = grp.interventions.filter((x) => {
      if (String(x.id) === String(ivId)) { moved = x; return false }
      return true
    })
    return { ...grp, interventions: kept }
  })
  if (!moved) return list
  return stripped.map((grp) => (colKey(grp) === String(toKey)
    ? { ...grp, interventions: [...grp.interventions, moved] }
    : grp))
}

// Carte intervention draggable — l'original reste en place (fantôme) pendant
// que le DragOverlay suit le pointeur.
function DispatchCard({ iv, technicienId }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `iv-${iv.id}`,
    data: { iv, fromTechnicien: technicienId },
  })
  return (
    <div ref={setNodeRef}
      className={`flex items-center gap-2 rounded border border-border px-2 py-1.5 text-sm${isDragging ? ' opacity-40' : ''}`}>
      <button type="button" {...listeners} {...attributes}
        className="shrink-0 cursor-grab touch-none text-muted-foreground active:cursor-grabbing"
        aria-label={`Déplacer l'intervention ${iv.installation_reference ?? `#${iv.id}`}`}>
        <GripVertical className="size-4" aria-hidden="true" />
      </button>
      <span className="min-w-0 flex-1 truncate">
        {iv.installation_reference ?? `#${iv.id}`} — {iv.client_nom ?? '—'}
      </span>
      <span className="shrink-0 text-xs text-muted-foreground">{formatDate(iv.date_prevue)}</span>
    </div>
  )
}

// Colonne-technicien droppable. Le ref droppable est posé sur un div wrapper
// (Card est un composant sans forwardRef).
function TechnicienColumn({ grp, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: colKey(grp) })
  return (
    <div ref={setNodeRef} data-testid={`col-${colKey(grp)}`}>
      <Card className={isOver ? 'ring-2 ring-primary' : undefined}>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Users className="size-4 text-muted-foreground" aria-hidden="true" />
            {grp.technicien.nom}
            <Badge tone="primary">{grp.interventions.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-1.5 pt-0">
          {grp.interventions.length === 0
            ? <span className="text-xs text-muted-foreground">Déposez une intervention ici.</span>
            : children}
        </CardContent>
      </Card>
    </div>
  )
}

function CalendrierTab() {
  const [range, setRange] = useState(defaultWeek)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeIv, setActiveIv] = useState(null)

  useEffect(() => {
    let alive = true
    installationsApi.getCalendrierInterventions(range.debut, range.fin)
      .then((r) => { if (alive) { setData(r.data ?? []); setError(null) } })
      .catch(() => { if (alive) setError('Impossible de charger le calendrier.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [range.debut, range.fin])

  // distance 6px : un clic simple n'entraîne pas de drag ; sur mobile appui
  // long 150 ms pour glisser, le scroll reste naturel. Même réglage que le
  // Kanban CRM.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
  )

  const handleDragStart = ({ active }) => {
    setActiveIv(active.data.current?.iv ?? null)
  }

  const handleDragEnd = ({ active, over }) => {
    setActiveIv(null)
    const iv = active.data.current?.iv
    const fromKey = String(active.data.current?.fromTechnicien ?? NON_ASSIGNE)
    if (!iv || !over) return
    const toKey = String(over.id)
    if (toKey === fromKey) return // déposé dans la même colonne : aucun effet

    // Réaffectation OPTIMISTE : on déplace la carte tout de suite…
    setData((prev) => moveInterventionLocal(prev, iv.id, fromKey, toKey))
    const nouveauTechnicien = toKey === NON_ASSIGNE ? null : Number(toKey)

    // …on PATCH le serveur (endpoint EXISTANT — zéro backend nouveau ; la notif
    // au nouveau technicien part côté serveur)…
    installationsApi.updateIntervention(iv.id, { technicien: nouveauTechnicien })
      .catch(() => {
        // Échec serveur : on remet la carte dans sa colonne d'origine.
        setData((prev) => moveInterventionLocal(prev, iv.id, toKey, fromKey))
        toast.error('Réaffectation impossible — réessayez.')
      })

    // …et on offre « Annuler » 6 s : restaure l'affectation d'origine (UI +
    // serveur). onUndo seul — l'effet a déjà eu lieu (VX95, jamais 2ᵉ primitif).
    const ancienTechnicien = fromKey === NON_ASSIGNE ? null : Number(fromKey)
    const cibleNom = data?.find((g) => colKey(g) === toKey)?.technicien?.nom ?? 'non assigné'
    toastWithUndo({
      message: `Intervention réaffectée à ${cibleNom}.`,
      onUndo: () => {
        setData((prev) => moveInterventionLocal(prev, iv.id, toKey, fromKey))
        installationsApi.updateIntervention(iv.id, { technicien: ancienTechnicien })
          .catch(() => toast.error('Annulation impossible — réessayez.'))
      },
    })
  }

  return (
    <div className="flex flex-col gap-3" data-testid="calendrier-techniciens">
      <div className="flex flex-wrap items-center gap-2">
        <Input type="date" value={range.debut} aria-label="Du"
          onChange={(e) => setRange((r) => ({ ...r, debut: e.target.value }))} className="w-40" />
        <span className="text-muted-foreground">→</span>
        <Input type="date" value={range.fin} aria-label="Au"
          onChange={(e) => setRange((r) => ({ ...r, fin: e.target.value }))} className="w-40" />
      </div>
      {loading ? (
        <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner className="size-4" /> Chargement…</p>
      ) : error ? (
        <EmptyState icon={AlertTriangle} title="Calendrier indisponible" description={error} />
      ) : (data ?? []).length === 0 ? (
        <EmptyState icon={CalendarRange} title="Aucune intervention sur la période" />
      ) : (
        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}
          onDragCancel={() => setActiveIv(null)}>
          <p className="text-xs text-muted-foreground">
            Glissez une intervention vers un autre technicien pour la réaffecter.
          </p>
          <div className="flex flex-col gap-3">
            {data.map((grp) => (
              <TechnicienColumn key={colKey(grp)} grp={grp}>
                {grp.interventions.map((iv) => (
                  <DispatchCard key={iv.id} iv={iv} technicienId={colKey(grp)} />
                ))}
              </TechnicienColumn>
            ))}
          </div>
          <DragOverlay>
            {activeIv ? (
              <div className="rounded border border-primary bg-background px-2 py-1.5 text-sm shadow-lg">
                {activeIv.installation_reference ?? `#${activeIv.id}`} — {activeIv.client_nom ?? '—'}
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}
    </div>
  )
}

// ── FG73 — Ma tournée ─────────────────────────────────────────────────────────
function MaTourneeTab() {
  const [date, setDate] = useState(todayISO)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    installationsApi.getMaTournee(date)
      .then((r) => { if (alive) { setData(r.data ?? { stops: [] }); setError(null) } })
      .catch(() => { if (alive) setError('Impossible de charger votre tournée.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [date])

  return (
    <div className="flex flex-col gap-3" data-testid="ma-tournee">
      <Input type="date" value={date} aria-label="Date de la tournée"
        onChange={(e) => setDate(e.target.value)} className="w-40" />
      {loading ? (
        <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner className="size-4" /> Chargement…</p>
      ) : error ? (
        <EmptyState icon={AlertTriangle} title="Tournée indisponible" description={error} />
      ) : (data?.stops ?? []).length === 0 ? (
        <EmptyState icon={Navigation} title="Aucun arrêt ce jour" description="Vos interventions du jour, ordonnées géographiquement, apparaîtront ici." />
      ) : (
        <ol className="flex flex-col gap-2">
          {data.stops.map((stop, i) => (
            <li key={stop.id}>
              <Card>
                <CardContent className="flex items-center gap-3 p-3">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{stop.client_nom ?? stop.installation_reference ?? `#${stop.id}`}</div>
                    <div className="text-xs text-muted-foreground">{stop.site_ville ?? '—'}</div>
                  </div>
                  {stop.itineraire_url && (
                    <a href={stop.itineraire_url} target="_blank" rel="noreferrer"
                      className="flex shrink-0 items-center gap-1 text-xs text-primary hover:underline">
                      Itinéraire <ExternalLink className="size-3.5" aria-hidden="true" />
                    </a>
                  )}
                </CardContent>
              </Card>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

// ── FG299/300/301 — Plan de charge, conflits, nivellement ───────────────────
function ChargeTab() {
  const [range, setRange] = useState(defaultWeek)
  const [heures, setHeures] = useState('8')
  const [plan, setPlan] = useState(null)
  const [conflits, setConflits] = useState(null)
  const [nivellement, setNivellement] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    const params = { debut: range.debut, fin: range.fin, heures_par_jour: heures || undefined }
    Promise.all([
      installationsApi.getPlanDeCharge(params),
      installationsApi.getConflitsAffectation({ debut: range.debut, fin: range.fin }),
      installationsApi.getNivellementCharge(params),
    ])
      .then(([p, c, n]) => {
        if (!alive) return
        setPlan(p.data); setConflits(c.data); setNivellement(n.data); setError(null)
      })
      .catch(() => { if (alive) setError('Impossible de charger le plan de charge.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [range.debut, range.fin, heures])

  return (
    <div className="flex flex-col gap-4" data-testid="plan-de-charge">
      <div className="flex flex-wrap items-center gap-2">
        <Input type="date" value={range.debut} aria-label="Du"
          onChange={(e) => setRange((r) => ({ ...r, debut: e.target.value }))} className="w-40" />
        <span className="text-muted-foreground">→</span>
        <Input type="date" value={range.fin} aria-label="Au"
          onChange={(e) => setRange((r) => ({ ...r, fin: e.target.value }))} className="w-40" />
        <Input type="number" min="0" step="0.5" value={heures} aria-label="Heures par jour"
          onChange={(e) => setHeures(e.target.value)} className="w-28" placeholder="h/jour" />
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner className="size-4" /> Chargement…</p>
      ) : error ? (
        <EmptyState icon={AlertTriangle} title="Plan de charge indisponible" description={error} />
      ) : (
        <>
          {/* FG299 — capacité vs affecté */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Gauge className="size-4 text-muted-foreground" aria-hidden="true" /> Plan de charge des équipes
              </CardTitle>
              <CardDescription>
                {plan?.jours_ouvres ?? 0} jour(s) ouvré(s) · capacité {plan?.capacite_heures ?? 0} h/technicien
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              {(plan?.techniciens ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune affectation sur la période.</p>
              ) : (
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Technicien</th>
                        <th>Affecté</th>
                        <th>Capacité</th>
                        <th>Charge</th>
                        <th>Statut</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plan.techniciens.map((t) => (
                        <tr key={t.technicien_id ?? 'na'}>
                          <td data-label="Technicien">{t.nom}</td>
                          <td data-label="Affecté">{t.affecte_count}</td>
                          <td data-label="Capacité">{t.capacite_heures} h</td>
                          <td data-label="Charge">{t.charge_pct}%</td>
                          <td data-label="Statut">
                            {t.sur_reservation
                              ? <Badge tone="danger">Sur-réservé</Badge>
                              : <Badge tone="success">OK</Badge>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* FG300 — conflits d'affectation */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <AlertTriangle className="size-4 text-muted-foreground" aria-hidden="true" /> Conflits d'affectation
                {(conflits?.conflits ?? []).length > 0 && (
                  <Badge tone="danger">{conflits.conflits.length}</Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {(conflits?.conflits ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucun conflit détecté sur la période.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {conflits.conflits.map((c, i) => (
                    <li key={`${c.type}-${c.ressource_id}-${c.date}-${i}`}
                      className="rounded border border-destructive/40 p-2 text-sm">
                      <span className="font-medium">{c.ressource_nom}</span>
                      {' — '}{formatDate(c.date)} · {c.count} interventions ({c.type})
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* FG301 — nivellement de charge (proposition, lecture seule) */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Scale className="size-4 text-muted-foreground" aria-hidden="true" /> Nivellement proposé
              </CardTitle>
              <CardDescription>Proposition en lecture seule — rien n'est modifié automatiquement.</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              {(nivellement?.propositions ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucun rééquilibrage à proposer.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {nivellement.propositions.map((p) => (
                    <li key={p.intervention_id} className="rounded border border-border p-2 text-sm">
                      {formatDate(p.date)} · intervention #{p.intervention_id} : {p.de_nom} → {p.vers_nom}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

// ── FG303 — Planning camionnettes ────────────────────────────────────────────
function CamionnettesTab() {
  const [range, setRange] = useState(defaultWeek)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    installationsApi.getPlanningCamionnettes({ debut: range.debut, fin: range.fin })
      .then((r) => { if (alive) { setData(r.data); setError(null) } })
      .catch(() => { if (alive) setError('Impossible de charger le planning des camionnettes.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [range.debut, range.fin])

  const camionnettes = data?.camionnettes ?? data?.vehicules ?? []

  return (
    <div className="flex flex-col gap-3" data-testid="planning-camionnettes">
      <div className="flex flex-wrap items-center gap-2">
        <Input type="date" value={range.debut} aria-label="Du"
          onChange={(e) => setRange((r) => ({ ...r, debut: e.target.value }))} className="w-40" />
        <span className="text-muted-foreground">→</span>
        <Input type="date" value={range.fin} aria-label="Au"
          onChange={(e) => setRange((r) => ({ ...r, fin: e.target.value }))} className="w-40" />
      </div>
      {loading ? (
        <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner className="size-4" /> Chargement…</p>
      ) : error ? (
        <EmptyState icon={AlertTriangle} title="Planning indisponible" description={error} />
      ) : camionnettes.length === 0 ? (
        <EmptyState icon={Truck} title="Aucune camionnette avec intervention sur la période" />
      ) : (
        <div className="flex flex-col gap-3">
          {camionnettes.map((v, i) => (
            <Card key={v.id ?? v.camionnette_id ?? i}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Truck className="size-4 text-muted-foreground" aria-hidden="true" />
                  {v.nom ?? v.camionnette_nom ?? `Véhicule #${v.id ?? i}`}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                {(v.interventions ?? []).length === 0 ? (
                  <p className="text-sm text-muted-foreground">Aucune intervention sur la période.</p>
                ) : (
                  <ul className="flex flex-col gap-1 text-sm">
                    {v.interventions.map((iv) => (
                      <li key={iv.id} className="flex justify-between">
                        <span>{iv.installation_reference ?? `#${iv.id}`} — {iv.technicien_nom ?? '—'}</span>
                        <span className="text-muted-foreground">{formatDate(iv.date_prevue ?? iv.date)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Outils par chantier — N43 (régime 82-21) + FG79 (interventions standard) +
// FG71 (coût/marge, admin-only) ──────────────────────────────────────────────
export function OutilsChantierTab() {
  const isAdmin = useIsAdmin()
  const [chantiers, setChantiers] = useState([])
  const [chantierId, setChantierId] = useState('')
  const [kwc, setKwc] = useState('')
  const [regime, setRegime] = useState(null)
  const [busyStd, setBusyStd] = useState(false)
  const [cout, setCout] = useState(null)
  const [coutError, setCoutError] = useState(null)
  const [tarifJour, setTarifJour] = useState('')

  useEffect(() => {
    installationsApi.getInstallations({ annule: 'sans' })
      .then((r) => setChantiers(r.data?.results ?? r.data ?? []))
      .catch(() => setChantiers([]))
  }, [])

  const suggestRegime = () => {
    installationsApi.getRegimeSuggestion(kwc)
      .then((r) => setRegime(r.data))
      .catch(() => toast.error('Suggestion de régime indisponible.'))
  }

  const creerStandard = () => {
    if (!chantierId) return
    setBusyStd(true)
    installationsApi.creerInterventionsStandard(chantierId)
      .then((r) => {
        const nb = r.data?.created?.length ?? 0
        toast.success(nb > 0
          ? `${nb} intervention(s) standard créée(s).`
          : 'Aucune nouvelle intervention (déjà présentes ou plan absent).')
      })
      .catch(() => toast.error('Génération des interventions standard impossible.'))
      .finally(() => setBusyStd(false))
  }

  const loadCout = () => {
    if (!chantierId) return
    setCoutError(null)
    installationsApi.getChantierCout(chantierId, tarifJour || undefined)
      .then((r) => setCout(r.data))
      .catch(() => setCoutError('Synthèse coût indisponible (réservé admin).'))
  }

  return (
    <div className="flex flex-col gap-4" data-testid="outils-chantier">
      {/* N43 — suggestion de régime loi 82-21 */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Suggestion de régime — loi 82-21</CardTitle>
          <CardDescription>Renseignez la puissance (kWc) pour obtenir le régime suggéré.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2 pt-0">
          <Input type="number" min="0" step="0.1" value={kwc} placeholder="kWc"
            aria-label="Puissance en kWc" onChange={(e) => setKwc(e.target.value)} className="w-32" />
          <Button size="sm" onClick={suggestRegime} disabled={!kwc}>Suggérer</Button>
          {regime && (
            <span className="text-sm">
              Régime suggéré : <Badge tone="primary">{regime.label}</Badge>
              {' '}(seuil déclaration {regime.seuil_declaration_kwc} kWc, seuil ANRE {regime.seuil_anre_kwc} kWc)
            </span>
          )}
        </CardContent>
      </Card>

      {/* Sélecteur de chantier commun aux deux outils suivants */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Chantier</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <Select value={chantierId || '__none__'} onValueChange={(v) => setChantierId(v === '__none__' ? '' : v)}>
            <SelectTrigger className="w-full sm:w-80" aria-label="Choisir un chantier">
              <SelectValue placeholder="— Choisir un chantier —" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">— Choisir un chantier —</SelectItem>
              {chantiers.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>
                  {c.reference} — {c.client_nom ?? '—'}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {/* FG79 — générer les interventions standard */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Wrench className="size-4 text-muted-foreground" aria-hidden="true" />
            Générer les interventions standard
          </CardTitle>
          <CardDescription>
            Matérialise la chaîne d'interventions standard du type d'installation du chantier. Idempotent.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <Button size="sm" onClick={creerStandard} disabled={!chantierId || busyStd}>
            {busyStd ? 'Génération…' : 'Générer les interventions standard'}
          </Button>
        </CardContent>
      </Card>

      {/* FG71 — coût/marge (INTERNE, admin-only) */}
      {isAdmin && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Synthèse coût / marge (interne)</CardTitle>
            <CardDescription>Réservé admin — jamais affiché ni exporté sur un document client.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 pt-0">
            <div className="flex flex-wrap items-center gap-2">
              <Input type="number" min="0" step="1" value={tarifJour} placeholder="Tarif/jour (MAD)"
                aria-label="Tarif journalier" onChange={(e) => setTarifJour(e.target.value)} className="w-44" />
              <Button size="sm" onClick={loadCout} disabled={!chantierId}>Calculer</Button>
            </div>
            {coutError && <p className="text-sm text-destructive">{coutError}</p>}
            {cout && (
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <div><div className="text-muted-foreground">Matériel retenu</div><div>{cout.materiel?.cout_retenu} MAD</div></div>
                <div><div className="text-muted-foreground">Main-d'œuvre (réel)</div><div>{cout.labour?.cout_reel ?? '—'} MAD</div></div>
                <div><div className="text-muted-foreground">Devis HT</div><div>{cout.devis_total_ht ?? '—'} MAD</div></div>
                <div><div className="text-muted-foreground">Marge</div><div>{cout.marge ?? '—'} {cout.marge_taux != null ? `(${cout.marge_taux}%)` : ''}</div></div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

const TABS = [
  { value: 'gantt', label: 'Gantt chantiers', icon: CalendarRange },
  { value: 'calendrier', label: 'Calendrier techniciens', icon: Users },
  { value: 'ma-tournee', label: 'Ma tournée', icon: Navigation },
  { value: 'charge', label: 'Plan de charge', icon: Gauge },
  { value: 'camionnettes', label: 'Camionnettes', icon: Truck },
  { value: 'outils', label: 'Outils chantier', icon: Wrench },
]

export default function PlanificationPage() {
  return (
    <div className="page lp-page">
      <div className="page-header lp-header">
        <h2>Planification &amp; logistique</h2>
      </div>

      <Tabs defaultValue="gantt">
        <TabsList className="flex w-full flex-wrap gap-1">
          {TABS.map((tab) => {
            const Icon = tab.icon
            return (
              <TabsTrigger key={tab.value} value={tab.value} className="flex items-center gap-1.5">
                <Icon className="size-4" aria-hidden="true" />
                {tab.label}
              </TabsTrigger>
            )
          })}
        </TabsList>
        <TabsContent value="gantt"><GanttTab /></TabsContent>
        <TabsContent value="calendrier"><CalendrierTab /></TabsContent>
        <TabsContent value="ma-tournee"><MaTourneeTab /></TabsContent>
        <TabsContent value="charge"><ChargeTab /></TabsContent>
        <TabsContent value="camionnettes"><CamionnettesTab /></TabsContent>
        <TabsContent value="outils"><OutilsChantierTab /></TabsContent>
      </Tabs>
    </div>
  )
}
