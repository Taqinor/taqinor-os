// N2 — Vue kanban des chantiers : colonnes = entonnoir chantier canonique
// (statuses.js, miroir du backend), glisser-déposer via @dnd-kit/core, même
// langage visuel que le kanban des leads. Le parent gère le changement de
// statut (optimistic) ; cette vue ne mute rien directement.
// J43 — cartes portées sur le système de design (StatusPill, Progress, Select)
// SANS toucher au câblage du drag (dnd-kit) : la structure kb-* est conservée.
import { useMemo, useState } from 'react'
import { MapPin, Zap, CalendarDays } from 'lucide-react'
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  INSTALLATION_STATUSES,
  STATUS_LABELS,
  STATUS_COLORS,
  canonicalStatus,
  canMoveStatus,
  adjacentStatuses,
  isPoseEnRetard,
} from '../../../features/installations/statuses'
import {
  buildKanbanAnnouncements,
  kanbanScreenReaderInstructions,
} from '../../../features/kanban/kanbanA11y'
import {
  StatusPill,
  Progress,
  Badge,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '../../../ui'
import { formatDate } from '../../../lib/format'
import { usePrefersReducedMotion } from '../../../hooks/usePrefersReducedMotion'

// VX135 — dropAnimation dnd-kit par défaut désalignée des tokens de
// mouvement de l'app ; alignée --motion-*/--ease-out (tokens.css). Sous
// reduced-motion, quasi instantanée (dnd-kit exige une durée > 0).
const DROP_ANIMATION = { duration: 180, easing: 'cubic-bezier(0.23, 1, 0.32, 1)' }
const DROP_ANIMATION_REDUCED = { duration: 1, easing: 'linear' }

// Sentinelle « aucun installateur » (le Select du design system n'accepte pas '').
const NO_TECH = '__none__'

// VX192 — alternative CLAVIER au glisser-déposer pour les chantiers (miroir du
// StageMover du kanban leads). Un <select> natif sous chaque carte n'offre que
// les statuts atteignables (règle « un seul pas dans l'entonnoir »,
// adjacentStatuses) ; le changement passe par onChangeStatus (optimistic géré
// par le parent). stopPropagation : manipuler le select ne démarre jamais un
// drag ni n'ouvre la fiche.
export function StatusMover({ inst, onChangeStatus }) {
  if (!onChangeStatus) return null
  const current = canonicalStatus(inst.statut)
  const options = adjacentStatuses(current)
  const stop = (e) => e.stopPropagation()
  return (
    <div
      className="kb-stage-mover"
      onClick={stop}
      onPointerDown={stop}
      onTouchStart={stop}
    >
      <label className="sr-only" htmlFor={`kc-statut-${inst.id}`}>
        Changer le statut du chantier {inst.reference || ''}
      </label>
      <select
        id={`kc-statut-${inst.id}`}
        className="form-control kb-stage-select"
        value={current}
        onChange={(e) => {
          const next = e.target.value
          if (next !== current) onChangeStatus(inst, next)
        }}
      >
        {options.map((s) => (
          <option key={s} value={s}>{STATUS_LABELS[s]}</option>
        ))}
      </select>
    </div>
  )
}

// VX192 — réassignation de l'installateur extraite de ChantierCard : c'est un
// contrôle INTERACTIF (Select) et ne peut donc pas vivre à l'intérieur du
// <button> d'ouverture de carte (imbrication interactive invalide). Rendu comme
// frère du bouton dans DraggableCard.
function ChantierReassign({ inst, users, onReassign }) {
  if (!onReassign) return null
  const techValue = inst.technicien_responsable ? String(inst.technicien_responsable) : NO_TECH
  return (
    <div
      className="kc-reassign"
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
    >
      <Select
        value={techValue}
        onValueChange={(v) => onReassign(inst, v === NO_TECH ? null : v)}
      >
        <SelectTrigger className="h-8 text-xs" aria-label="Installateur">
          <SelectValue placeholder="Installateur" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NO_TECH}>— Installateur —</SelectItem>
          {(users ?? []).map((u) => (
            <SelectItem key={u.id} value={String(u.id)}>
              {u.username ?? u.nom ?? `#${u.id}`}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function ChantierCard({ inst, isNew }) {
  return (
    <div className="kb-card kc-card" style={{ '--kb-accent': STATUS_COLORS[canonicalStatus(inst.statut)] }}>
      <div className="kc-card-top">
        <span className="kc-card-ref">{inst.reference}</span>
        {/* VX218 — badge « Nouveau » : chantier assigné depuis ma dernière visite. */}
        {isNew && <Badge tone="success">Nouveau</Badge>}
        <StatusPill status={inst.statut} label={STATUS_LABELS[canonicalStatus(inst.statut)]} dot={false} />
      </div>
      <div className="kc-card-sub">{inst.client_nom ?? '—'}</div>
      <div className="kc-chips">
        {inst.site_ville && (
          <span className="kc-chip"><MapPin className="kc-chip-icon" aria-hidden="true" />{inst.site_ville}</span>
        )}
        {inst.puissance_installee_kwc && (
          <span className="kc-chip"><Zap className="kc-chip-icon" aria-hidden="true" />{inst.puissance_installee_kwc} kWc</span>
        )}
        {formatDate(inst.date_pose_prevue) !== '—' && (
          <span className="kc-chip"><CalendarDays className="kc-chip-icon" aria-hidden="true" />{formatDate(inst.date_pose_prevue)}</span>
        )}
        {isPoseEnRetard(inst) && (
          <StatusPill tone="danger" label="Pose en retard" dot={false} />
        )}
      </div>
      {Number.isInteger(inst.checklist_completion) && (
        <div className="kc-progress">
          <Progress
            value={inst.checklist_completion}
            tone={inst.checklist_completion === 100 ? 'success' : 'primary'}
          />
          <span className="kc-progress-label">{inst.checklist_completion}%</span>
        </div>
      )}
    </div>
  )
}

function DraggableCard({ inst, users, onReassign, isNew, onOpen, onChangeStatus }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: inst.id, data: { inst },
  })
  return (
    <div ref={setNodeRef}
         className={isDragging ? 'kb-drag-wrap kb-drag-source' : 'kb-drag-wrap'}>
      {/* VX192 — carte ouverte au clavier : <button> focalisable (Entrée/Espace
          ouvre la fiche) au lieu d'un <div onClick> non atteignable au clavier.
          La poignée de drag (listeners/attributes) est portée par ce bouton. Le
          bouton n'enveloppe QUE l'affichage : les contrôles interactifs
          (réassignation, sélecteur de statut) restent frères pour ne pas
          imbriquer d'interactif dans le bouton. */}
      <button
        type="button"
        className="kb-card-open"
        onClick={() => onOpen?.(inst)}
        {...listeners}
        {...attributes}
      >
        <ChantierCard inst={inst} isNew={isNew} />
      </button>
      <ChantierReassign inst={inst} users={users} onReassign={onReassign} />
      <StatusMover inst={inst} onChangeStatus={onChangeStatus} />
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
        {col.items.length === 0 ? (
          <div className="kb-col-empty">Aucun chantier</div>
        ) : children}
      </div>
    </section>
  )
}

export default function KanbanView({ items, onOpen, onChangeStatus, users, onReassign, nouveauxIds }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
    // VX192 — 0 dépendance : sensor clavier natif de @dnd-kit/core.
    useSensor(KeyboardSensor),
  )
  const [active, setActive] = useState(null)
  // VX135 — préférence reduced-motion lue en JS : tilt + dropAnimation
  // échappent tous deux au garde global CSS (transforms/animations posés
  // impérativement par dnd-kit).
  const prefersReducedMotion = usePrefersReducedMotion()
  // VX192 — remplace window.alert (bloquant, inaccessible) par un bandeau
  // role="status" annoncé (patron du kanban leads « On ne recule pas… »).
  const [refusMsg, setRefusMsg] = useState('')

  const columns = useMemo(() => {
    const byCol = Object.fromEntries(INSTALLATION_STATUSES.map((s) => [s, []]))
    for (const it of items ?? []) {
      const col = canonicalStatus(it.statut)
      if (byCol[col]) byCol[col].push(it)
      else (byCol[INSTALLATION_STATUSES[0]]).push(it)
    }
    return INSTALLATION_STATUSES.map((s) => ({
      key: s, label: STATUS_LABELS[s], color: STATUS_COLORS[s], items: byCol[s],
    }))
  }, [items])

  // VX192 — annonces FR partagées : traduit un id de chantier (référence) ou de
  // colonne (libellé de statut) pour le lecteur d'écran.
  const announcements = useMemo(() => {
    const byId = new Map((items ?? []).map((it) => [it.id, it]))
    const labelFor = (id) => {
      if (STATUS_LABELS[id]) return STATUS_LABELS[id]
      const it = byId.get(id)
      return it?.reference ?? String(id)
    }
    return buildKanbanAnnouncements(labelFor)
  }, [items])

  const handleDragEnd = ({ active: a, over }) => {
    setActive(null)
    const inst = a.data.current?.inst
    if (!inst || !over || over.id === canonicalStatus(inst.statut)) return
    // N2 — n'accepte qu'un mouvement d'un seul pas sur l'entonnoir : un dépôt
    // à plus d'un pas « snap back » (aucune mutation) avec un message FR.
    if (!canMoveStatus(inst.statut, over.id)) {
      setRefusMsg(
        'Mouvement impossible : un chantier ne peut avancer ou reculer que '
        + "d'une étape à la fois dans l'entonnoir.")
      window.setTimeout(() => setRefusMsg(''), 4000)
      return
    }
    onChangeStatus?.(inst, over.id)
  }

  return (
    <DndContext sensors={sensors}
                accessibility={{
                  announcements,
                  screenReaderInstructions: kanbanScreenReaderInstructions,
                }}
                onDragStart={({ active: a }) => setActive(a.data.current?.inst ?? null)}
                onDragEnd={handleDragEnd}
                onDragCancel={() => setActive(null)}>
      {refusMsg && (
        <div
          className="kb-recul-msg mb-2 rounded-lg border border-destructive/30 bg-destructive/12 px-3 py-1.5 text-[13px] font-semibold text-destructive"
          role="status"
        >
          {refusMsg}
        </div>
      )}
      <div className="kb-board">
        {columns.map((col) => (
          <StatusColumn key={col.key} col={col}>
            {col.items.map((inst) => (
              <DraggableCard key={inst.id} inst={inst} users={users}
                             onReassign={onReassign} onOpen={onOpen}
                             onChangeStatus={onChangeStatus}
                             isNew={nouveauxIds?.has(inst.id)} />
            ))}
          </StatusColumn>
        ))}
      </div>
      <DragOverlay dropAnimation={prefersReducedMotion ? DROP_ANIMATION_REDUCED : DROP_ANIMATION}>
        {active ? (
          <div className={prefersReducedMotion ? 'kb-drag-overlay kb-drag-overlay--flat' : 'kb-drag-overlay'}>
            <ChantierCard inst={active} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
