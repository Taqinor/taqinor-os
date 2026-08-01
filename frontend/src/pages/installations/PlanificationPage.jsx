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
  Wrench, Gauge, GripVertical,
} from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent,
  Badge, Spinner, EmptyState, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem, Tabs, TabsList, TabsTrigger, TabsContent,
  Input, Button, toast,
  // APX28 — confirmation avant d'écrire un créneau (fenêtre de RDV client).
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '../../ui'
// APX28 — mobile = grille en lecture seule (aucun glisser-déposer au pouce).
import { useIsMobile } from '../../ui/ResponsiveDialog'
// APX29 — carte + liste des arrêts, partagée avec « Ma journée ».
import TourneeStops from '../../features/installations/TourneeStops'
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

// ── APX28 — VRAIE grille horaire (jour) × techniciens ────────────────────────
// CHAMPS RÉELLEMENT SERVIS (vérifiés dans `apps/installations/models_intervention.py`
// + `InterventionSerializer(fields='__all__')`) : `date_prevue` est un DateField
// (AUCUNE heure), il n'existe AUCUN champ de durée, et la seule information
// horaire est la fenêtre de RDV XFSM5 `fenetre_debut`/`fenetre_fin` (TimeField,
// nullable, écrivable par le PATCH générique).
// CONSÉQUENCE ASSUMÉE : une intervention SANS fenêtre n'est JAMAIS placée à une
// heure inventée — elle va dans la bande « Sans créneau » de sa colonne, en
// blocs séquencés à hauteur fixe. Poser/déplacer une intervention sur la grille
// ÉCRIT la fenêtre choisie (action explicite de l'utilisateur, confirmée).
const HEURE_DEBUT = 7
const HEURE_FIN = 19
const SLOT_PX = 44 // 1 h = 44 px (une cible de dépôt tactile ≥ 44 px)
const HEURES = Array.from(
  { length: HEURE_FIN - HEURE_DEBUT }, (_, i) => HEURE_DEBUT + i)
// Hauteurs FIXES de l'en-tête de colonne et de la bande « Sans créneau » : la
// gouttière des heures se cale dessus, sinon les libellés dérivent dès qu'une
// colonne a plus d'interventions sans horaire qu'une autre.
const ENTETE_PX = 68
const BANDE_PX = 88
const GUTTER_TOP_PX = ENTETE_PX + BANDE_PX + 2 // + les 2 bordures 1 px

// 'HH:MM' / 'HH:MM:SS' → minutes depuis minuit ; null si absent/illisible.
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé
export function minutesDeHeure(t) {
  if (typeof t !== 'string') return null
  const m = /^(\d{1,2}):(\d{2})/.exec(t.trim())
  if (!m) return null
  const h = Number(m[1]), min = Number(m[2])
  if (h > 23 || min > 59) return null
  return h * 60 + min
}

const deuxChiffres = (n) => String(n).padStart(2, '0')
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé
export const heureEnTime = (h, min = 0) => `${deuxChiffres(h)}:${deuxChiffres(min)}:00`

// Géométrie d'un bloc sur l'axe des heures. `null` = pas de fenêtre servie
// (l'intervention n'a rien à faire sur l'axe : elle ira en « Sans créneau »).
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé
export function blocGeometry(iv) {
  const debut = minutesDeHeure(iv?.fenetre_debut)
  if (debut == null) return null
  const finBrute = minutesDeHeure(iv?.fenetre_fin)
  // Fenêtre sans fin servie : on ne DEVINE pas une durée — un créneau d'une
  // graduation, la hauteur minimale de la grille.
  const fin = finBrute != null && finBrute > debut ? finBrute : debut + 60
  const min0 = HEURE_DEBUT * 60, min1 = HEURE_FIN * 60
  const d = Math.max(debut, min0)
  const f = Math.min(fin, min1)
  if (f <= min0 || d >= min1) return null // entièrement hors de la plage rendue
  return {
    topPx: ((d - min0) / 60) * SLOT_PX,
    heightPx: Math.max(((f - d) / 60) * SLOT_PX, 22),
    debutMin: debut,
    finMin: fin,
    horsPlage: debut < min0 || fin > min1,
  }
}

// Corps EXACT du PATCH d'un dépôt (endpoint EXISTANT `updateIntervention`) :
// technicien + jour, et la fenêtre UNIQUEMENT quand un créneau a été visé.
// Aucune durée n'est inventée : un créneau vaut la graduation de la grille (1 h).
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé
export function payloadDeplacement(toKey, jourCible, heure) {
  return {
    technicien: String(toKey) === NON_ASSIGNE ? null : Number(toKey),
    date_prevue: jourCible,
    ...(heure != null
      ? { fenetre_debut: heureEnTime(heure), fenetre_fin: heureEnTime(heure + 1) }
      : {}),
  }
}

// Chevauchements RÉELS au sein d'une même colonne (même technicien, même jour) :
// renvoie l'ensemble des ids en conflit. Deux interventions sans fenêtre ne
// sont PAS un conflit (aucune heure n'est connue — on n'invente rien).
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé
export function chevauchements(interventions) {
  const avecHeure = (interventions ?? [])
    .map((iv) => ({ id: iv.id, geo: blocGeometry(iv) }))
    .filter((x) => x.geo)
  const enConflit = new Set()
  for (let i = 0; i < avecHeure.length; i += 1) {
    for (let j = i + 1; j < avecHeure.length; j += 1) {
      const a = avecHeure[i].geo, b = avecHeure[j].geo
      if (a.debutMin < b.finMin && b.debutMin < a.finMin) {
        enConflit.add(avecHeure[i].id)
        enConflit.add(avecHeure[j].id)
      }
    }
  }
  return enConflit
}

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
function DispatchCard({ iv, technicienId, conflit = false, compact = false, style, draggable = true }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `iv-${iv.id}`,
    data: { iv, fromTechnicien: technicienId },
    disabled: !draggable,
  })
  const titre = iv.installation_reference ?? `#${iv.id}`
  const fenetre = iv.fenetre_debut
    ? `${String(iv.fenetre_debut).slice(0, 5)}${iv.fenetre_fin ? `–${String(iv.fenetre_fin).slice(0, 5)}` : ''}`
    : null
  return (
    <div ref={setNodeRef} style={style}
      data-testid={`iv-${iv.id}`}
      data-conflit={conflit ? 'true' : undefined}
      className={[
        'flex items-center gap-2 overflow-hidden rounded border px-2 py-1.5 text-sm',
        conflit
          ? 'border-destructive bg-destructive/10 text-destructive-foreground'
          : 'border-border bg-card',
        isDragging ? 'opacity-40' : '',
        compact ? 'text-xs' : '',
      ].join(' ')}
      title={conflit ? `${titre} — chevauchement de créneau` : titre}>
      {draggable && (
        <button type="button" {...listeners} {...attributes}
          className="shrink-0 cursor-grab touch-none text-muted-foreground active:cursor-grabbing"
          aria-label={`Déplacer l'intervention ${titre}`}>
          <GripVertical className="size-4" aria-hidden="true" />
        </button>
      )}
      <span className="min-w-0 flex-1 truncate">
        {titre} — {iv.client_nom ?? '—'}
      </span>
      {conflit && <AlertTriangle className="size-3.5 shrink-0 text-destructive" aria-label="Conflit" />}
      <span className="shrink-0 text-xs text-muted-foreground">
        {fenetre ?? formatDate(iv.date_prevue)}
      </span>
    </div>
  )
}

// APX28 — l'ancienne colonne-technicien en kanban (VX251) est remplacée par les
// colonnes de la grille horaire ci-dessous : même cible de dépôt « technicien
// seul » (bande « Sans créneau »), plus les cases d'heure.

// APX28 — une case d'heure de la grille : c'est ELLE la cible de dépôt qui
// donne un CRÉNEAU (et pas seulement un technicien).
function CaseHoraire({ techKey, heure }) {
  const { setNodeRef, isOver } = useDroppable({ id: `slot:${techKey}:${heure}` })
  return (
    <div ref={setNodeRef}
      data-testid={`slot-${techKey}-${heure}`}
      style={{ height: `${SLOT_PX}px` }}
      className={`border-t border-border/60 ${isOver ? 'bg-primary/15' : ''}`} />
  )
}

// APX28 — bande « Sans créneau » : les interventions dont l'heure n'est PAS
// connue (aucune fenêtre XFSM5 servie). Blocs séquencés à hauteur fixe — on ne
// les pose jamais sur l'axe à une heure inventée. Déposer ici = affectation au
// technicien seule (comportement VX251 d'origine, conservé).
function BandeSansCreneau({ techKey, interventions, draggable, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: `col:${techKey}` })
  return (
    <div ref={setNodeRef} data-testid={`sans-creneau-${techKey}`}
      style={{ height: `${BANDE_PX}px` }}
      className={`flex flex-col gap-1 overflow-y-auto border-b border-dashed border-border p-1 ${isOver ? 'bg-primary/10' : ''}`}>
      {interventions.length === 0 ? (
        <span className="px-1 py-2 text-[11px] text-muted-foreground">
          {draggable ? 'Déposez ici (sans créneau)' : 'Aucune intervention sans créneau'}
        </span>
      ) : children}
    </div>
  )
}

// APX28 — la grille du JOUR : axe 7 h → 19 h × colonnes techniciens.
function GrilleJour({ data, jour, estAujourdhui, draggable }) {
  const maintenant = new Date()
  const minutesMaintenant = maintenant.getHours() * 60 + maintenant.getMinutes()
  const ligneNow = estAujourdhui
    && minutesMaintenant >= HEURE_DEBUT * 60 && minutesMaintenant <= HEURE_FIN * 60
    ? ((minutesMaintenant - HEURE_DEBUT * 60) / 60) * SLOT_PX
    : null

  return (
    <div className="overflow-x-auto" data-testid="grille-jour" data-jour={jour}>
      <div className="flex min-w-max gap-2">
        {/* Gouttière des heures */}
        <div className="shrink-0" style={{ paddingTop: `${GUTTER_TOP_PX}px` }} aria-hidden="true">
          {HEURES.map((h) => (
            <div key={h} style={{ height: `${SLOT_PX}px` }}
              className="w-12 border-t border-transparent pr-2 text-right text-[11px] tabular-nums text-muted-foreground">
              {deuxChiffres(h)}:00
            </div>
          ))}
        </div>

        {(data ?? []).map((grp) => {
          const key = colKey(grp)
          const enConflit = chevauchements(grp.interventions)
          const surAxe = grp.interventions.filter((iv) => blocGeometry(iv))
          const sansCreneau = grp.interventions.filter((iv) => !blocGeometry(iv))
          return (
            <div key={key} className="w-56 shrink-0" data-testid={`col-${key}`}>
              <div style={{ height: `${ENTETE_PX}px` }}
                className="flex flex-col justify-center gap-1 rounded-t-lg border border-b-0 border-border bg-muted/40 px-2">
                <span className="flex items-center gap-1.5 truncate text-sm font-semibold">
                  <Users className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  {grp.technicien.nom}
                  <Badge tone="primary">{grp.interventions.length}</Badge>
                </span>
                {enConflit.size > 0 && (
                  <Badge tone="danger">
                    <AlertTriangle className="size-3" aria-hidden="true" />
                    {enConflit.size} en conflit
                  </Badge>
                )}
              </div>
              <div className="border-x border-border">
                <BandeSansCreneau techKey={key} interventions={sansCreneau} draggable={draggable}>
                  {sansCreneau.map((iv) => (
                    <DispatchCard key={iv.id} iv={iv} technicienId={key} compact
                      draggable={draggable} />
                  ))}
                </BandeSansCreneau>
              </div>
              <div className="relative border-x border-b border-border">
                {HEURES.map((h) => <CaseHoraire key={h} techKey={key} heure={h} />)}
                {ligneNow != null && (
                  <div className="pointer-events-none absolute inset-x-0 h-0.5 bg-destructive"
                    style={{ top: `${ligneNow}px` }} data-testid="ligne-maintenant" aria-hidden="true" />
                )}
                {surAxe.map((iv) => {
                  const geo = blocGeometry(iv)
                  return (
                    <div key={iv.id} className="absolute inset-x-1"
                      style={{ top: `${geo.topPx}px`, height: `${geo.heightPx}px` }}>
                      <DispatchCard iv={iv} technicienId={key} compact
                        draggable={draggable}
                        conflit={enConflit.has(iv.id)}
                        style={{ height: '100%' }} />
                    </div>
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

// APX28 — semaine CONDENSÉE : lignes = techniciens, colonnes = les 7 jours.
// Déposer une carte dans une case = changer de technicien ET/OU de jour.
function SemaineCondensee({ data, jours, draggable }) {
  return (
    <div className="overflow-x-auto" data-testid="grille-semaine">
      <div className="min-w-max">
        <div className="flex gap-2 pl-40">
          {jours.map((j) => (
            <div key={j.iso} className={`w-40 shrink-0 px-1 pb-1 text-center text-xs font-semibold ${j.aujourdhui ? 'text-primary' : 'text-muted-foreground'}`}>
              {j.label}{j.aujourdhui ? ' · aujourd’hui' : ''}
            </div>
          ))}
        </div>
        {(data ?? []).map((grp) => {
          const key = colKey(grp)
          return (
            <div key={key} className="flex gap-2 border-t border-border py-1">
              <div className="flex w-40 shrink-0 items-center gap-1.5 px-1 text-sm font-medium">
                <Users className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="truncate">{grp.technicien.nom}</span>
                <Badge tone="primary">{grp.interventions.length}</Badge>
              </div>
              {jours.map((j) => (
                <CaseJour key={j.iso} techKey={key} jour={j.iso}
                  interventions={grp.interventions.filter((iv) => iv.date_prevue === j.iso)}
                  draggable={draggable} />
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function CaseJour({ techKey, jour, interventions, draggable }) {
  const { setNodeRef, isOver } = useDroppable({ id: `day:${techKey}:${jour}` })
  return (
    <div ref={setNodeRef} data-testid={`day-${techKey}-${jour}`}
      className={`flex min-h-11 w-40 shrink-0 flex-col gap-1 rounded border border-dashed border-border p-1 ${isOver ? 'bg-primary/15' : ''}`}>
      {interventions.map((iv) => (
        <DispatchCard key={iv.id} iv={iv} technicienId={techKey} compact draggable={draggable} />
      ))}
    </div>
  )
}

function CalendrierTab() {
  // APX28 — deux vues : Jour (grille horaire) et Semaine condensée.
  const [mode, setMode] = useState('jour')
  const [jour, setJour] = useState(todayISO)
  const [range, setRange] = useState(defaultWeek)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeIv, setActiveIv] = useState(null)
  // APX28 — dépôt sur un créneau : confirmé avant d'écrire (le PATCH pose une
  // fenêtre de RDV, une donnée que le client voit).
  const [pendingDrop, setPendingDrop] = useState(null)
  // Mobile = lecture seule (pas de glisser-déposer au pouce sur une grille).
  const isMobile = useIsMobile()
  const draggable = !isMobile

  const debut = mode === 'jour' ? jour : range.debut
  const fin = mode === 'jour' ? jour : range.fin

  // Fetch du calendrier au changement de plage : `setLoading(true)` ouvre le
  // cycle et `finally` le referme — motif de chargement standard, borne par
  // le drapeau `alive`, sans cascade possible.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => {
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true)
    installationsApi.getCalendrierInterventions(debut, fin)
      .then((r) => { if (alive) { setData(r.data ?? []); setError(null) } })
      .catch(() => { if (alive) setError('Impossible de charger le calendrier.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [debut, fin])

  const jours = useMemo(() => {
    const out = []
    const d = new Date(range.debut)
    const aujourdhui = todayISO()
    for (let i = 0; i < 7 && !Number.isNaN(d.getTime()); i += 1) {
      const iso = isoOf(d)
      if (iso > range.fin) break
      out.push({
        iso,
        label: d.toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit' }),
        aujourdhui: iso === aujourdhui,
      })
      d.setDate(d.getDate() + 1)
    }
    return out
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

  // VX251 — réaffectation TECHNICIEN seule (dépôt hors grille horaire) :
  // optimiste + undo 6 s, comportement d'origine inchangé.
  const reaffecter = (iv, fromKey, toKey) => {
    setData((prev) => moveInterventionLocal(prev, iv.id, fromKey, toKey))
    const nouveauTechnicien = toKey === NON_ASSIGNE ? null : Number(toKey)
    installationsApi.updateIntervention(iv.id, { technicien: nouveauTechnicien })
      .catch(() => {
        setData((prev) => moveInterventionLocal(prev, iv.id, toKey, fromKey))
        toast.error('Réaffectation impossible — réessayez.')
      })
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

  const handleDragEnd = ({ active, over }) => {
    setActiveIv(null)
    const iv = active.data.current?.iv
    const fromKey = String(active.data.current?.fromTechnicien ?? NON_ASSIGNE)
    if (!iv || !over) return
    const overId = String(over.id)

    // APX28 — dépôt sur une case d'heure : on demande confirmation (le PATCH
    // écrit une fenêtre de RDV) avant d'écrire quoi que ce soit.
    if (overId.startsWith('slot:')) {
      const [, toKey, heureStr] = overId.split(':')
      setPendingDrop({ iv, fromKey, toKey, heure: Number(heureStr), jour: debut })
      return
    }
    // APX28 — dépôt sur une case de la semaine condensée : technicien + jour.
    if (overId.startsWith('day:')) {
      const [, toKey, jourIso] = overId.split(':')
      if (toKey === fromKey && jourIso === iv.date_prevue) return
      setPendingDrop({ iv, fromKey, toKey, jour: jourIso, heure: null })
      return
    }
    const toKey = overId.startsWith('col:') ? overId.slice(4) : overId
    if (toKey === fromKey) return // déposé dans la même colonne : aucun effet
    reaffecter(iv, fromKey, toKey)
  }

  // APX28 — application du dépôt confirmé : UN SEUL PATCH sur l'endpoint
  // EXISTANT (`updateIntervention`) — aucune écriture serveur nouvelle.
  const confirmerDrop = () => {
    const drop = pendingDrop
    setPendingDrop(null)
    if (!drop) return
    const { iv, fromKey, toKey, heure, jour: jourCible } = drop
    const avant = {
      technicien: fromKey === NON_ASSIGNE ? null : Number(fromKey),
      date_prevue: iv.date_prevue ?? null,
      fenetre_debut: iv.fenetre_debut ?? null,
      fenetre_fin: iv.fenetre_fin ?? null,
    }
    const apres = payloadDeplacement(toKey, jourCible, heure)
    // Optimiste : la carte change de colonne ET porte tout de suite son créneau.
    setData((prev) => {
      const deplacee = toKey === fromKey ? prev : moveInterventionLocal(prev, iv.id, fromKey, toKey)
      return (deplacee ?? []).map((grp) => ({
        ...grp,
        interventions: grp.interventions.map((x) => (
          String(x.id) === String(iv.id) ? { ...x, ...apres } : x)),
      }))
    })
    installationsApi.updateIntervention(iv.id, apres)
      .catch(() => {
        setData((prev) => {
          const remise = toKey === fromKey ? prev : moveInterventionLocal(prev, iv.id, toKey, fromKey)
          return (remise ?? []).map((grp) => ({
            ...grp,
            interventions: grp.interventions.map((x) => (
              String(x.id) === String(iv.id) ? { ...x, ...avant } : x)),
          }))
        })
        toast.error('Placement impossible — réessayez.')
      })
    toastWithUndo({
      message: heure != null
        ? `Intervention placée à ${deuxChiffres(heure)}:00.`
        : `Intervention déplacée au ${formatDate(jourCible)}.`,
      onUndo: () => {
        setData((prev) => {
          const remise = toKey === fromKey ? prev : moveInterventionLocal(prev, iv.id, toKey, fromKey)
          return (remise ?? []).map((grp) => ({
            ...grp,
            interventions: grp.interventions.map((x) => (
              String(x.id) === String(iv.id) ? { ...x, ...avant } : x)),
          }))
        })
        installationsApi.updateIntervention(iv.id, avant)
          .catch(() => toast.error('Annulation impossible — réessayez.'))
      },
    })
  }

  const estAujourdhui = jour === todayISO()
  const contenu = mode === 'jour'
    ? <GrilleJour data={data} jour={jour} estAujourdhui={estAujourdhui} draggable={draggable} />
    : <SemaineCondensee data={data} jours={jours} draggable={draggable} />

  return (
    <div className="flex flex-col gap-3" data-testid="calendrier-techniciens">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex overflow-hidden rounded-lg border border-border" role="group" aria-label="Vue du calendrier">
          <button type="button" onClick={() => setMode('jour')}
            aria-pressed={mode === 'jour'}
            className={`min-h-11 px-3 text-sm ${mode === 'jour' ? 'bg-primary text-primary-foreground' : 'bg-card'}`}>
            Jour
          </button>
          <button type="button" onClick={() => setMode('semaine')}
            aria-pressed={mode === 'semaine'}
            className={`min-h-11 px-3 text-sm ${mode === 'semaine' ? 'bg-primary text-primary-foreground' : 'bg-card'}`}>
            Semaine
          </button>
        </div>
        {mode === 'jour' ? (
          <>
            <Input type="date" value={jour} aria-label="Jour"
              onChange={(e) => setJour(e.target.value)} className="w-40" />
            {estAujourdhui && <Badge tone="primary">Aujourd’hui</Badge>}
          </>
        ) : (
          <>
            <Input type="date" value={range.debut} aria-label="Du"
              onChange={(e) => setRange((r) => ({ ...r, debut: e.target.value }))} className="w-40" />
            <span className="text-muted-foreground">→</span>
            <Input type="date" value={range.fin} aria-label="Au"
              onChange={(e) => setRange((r) => ({ ...r, fin: e.target.value }))} className="w-40" />
          </>
        )}
      </div>
      {loading ? (
        <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner className="size-4" /> Chargement…</p>
      ) : error ? (
        <EmptyState icon={AlertTriangle} title="Calendrier indisponible" description={error} />
      ) : (data ?? []).length === 0 ? (
        <EmptyState icon={CalendarRange} title="Aucune intervention sur la période" />
      ) : !draggable ? (
        <>
          <p className="text-xs text-muted-foreground">
            Lecture seule sur mobile — la replanification se fait au bureau.
          </p>
          {contenu}
        </>
      ) : (
        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}
          onDragCancel={() => setActiveIv(null)}>
          <p className="text-xs text-muted-foreground">
            Glissez une intervention vers un autre technicien, ou sur une case d’heure
            pour lui poser un créneau. Les interventions sans horaire connu restent
            dans la bande « Sans créneau ».
          </p>
          {contenu}
          <DragOverlay>
            {activeIv ? (
              <div className="rounded border border-primary bg-background px-2 py-1.5 text-sm shadow-lg">
                {activeIv.installation_reference ?? `#${activeIv.id}`} — {activeIv.client_nom ?? '—'}
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}

      {/* APX28 — confirmation avant écriture (le créneau posé est une donnée
          client : fenêtre de RDV XFSM5). */}
      <AlertDialog open={!!pendingDrop} onOpenChange={(o) => { if (!o) setPendingDrop(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmer la replanification</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDrop && (pendingDrop.heure != null
                ? `Placer l'intervention ${pendingDrop.iv.installation_reference ?? `#${pendingDrop.iv.id}`} `
                  + `le ${formatDate(pendingDrop.jour)} de ${deuxChiffres(pendingDrop.heure)}:00 `
                  + `à ${deuxChiffres(pendingDrop.heure + 1)}:00 (fenêtre de RDV) ?`
                : `Déplacer l'intervention ${pendingDrop.iv.installation_reference ?? `#${pendingDrop.iv.id}`} `
                  + `au ${formatDate(pendingDrop.jour)} ?`)}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={confirmerDrop}>Confirmer</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
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
        // APX29 — carte + liste, composant PARTAGÉ avec « Ma journée » (la
        // liste numérotée était dupliquée entre les deux écrans).
        <TourneeStops stops={data.stops} />
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
