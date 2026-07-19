// Vue kanban des leads CRM, façon Odoo : 6 colonnes canoniques (stages.js,
// miroir de STAGES.py — jamais de liste d'étapes en dur ici), glisser-déposer
// via @dnd-kit/core. Le parent gère l'optimistic update : on ne mute rien.
import { memo, useCallback, useMemo, useState } from 'react'
import { ChevronDown, LayoutGrid } from 'lucide-react'
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
  formatMAD, groupLeadsByStage, isStageMoveAllowed, PIPELINE_STAGES, STAGE_LABELS,
} from '../../../../features/crm/stages'
import {
  buildKanbanAnnouncements,
  kanbanScreenReaderInstructions,
} from '../../../../features/kanban/kanbanA11y'
import { readCollapsedStages, writeCollapsedStages } from '../../../../features/kanban/collapsedColumns'
import { useOptimisticSave } from '../../../../hooks/useOptimisticSave'
import { usePrefersReducedMotion } from '../../../../hooks/usePrefersReducedMotion'
import { toast } from '../../../../ui/confirm'
import { EmptyState, Button } from '../../../../ui'
import { isSigneIntercept } from '../signeIntercept'
import LeadCard from './LeadCard'

// VX135 — dropAnimation dnd-kit par défaut désalignée des tokens de
// mouvement de l'app ; alignée --motion-*/--ease-out (tokens.css). Sous
// reduced-motion, quasi instantanée (dnd-kit exige une durée > 0).
const DROP_ANIMATION = { duration: 180, easing: 'cubic-bezier(0.23, 1, 0.32, 1)' }
const DROP_ANIMATION_REDUCED = { duration: 1, easing: 'linear' }

// J140 + L151 — alternative CLAVIER au glisser-déposer : un sélecteur d'étape
// accessible sous chaque carte. Enregistrement OPTIMISTE avec rollback via
// useOptimisticSave (n'utilise que le commit existant `onInlineSave` → thunk
// updateLead). Affiche le libellé inline « Enregistrement… / Enregistré » et
// estompe la carte pendant le commit (affordance « ligne en cours »).
const STAGE_MOVE_OPTIONS = PIPELINE_STAGES.map(
  (s) => ({ value: s, label: STAGE_LABELS[s] ?? s }),
)

export function StageMover({ lead, onInlineSave }) {
  // LB3 — l'entrée dans SIGNED rejette avec la sentinelle SIGNE_INTERCEPT
  // (signeIntercept.js) : ce n'est PAS une erreur (SigneDialog vient de
  // s'ouvrir, useOptimisticSave fait son rollback normal — le select revient
  // à l'étape réelle), donc on ne toaste QUE les vrais échecs réseau.
  const { value, statusLabel, isSaving, rowProps, save } = useOptimisticSave(
    lead.stage,
    {
      onError: (err) => {
        if (isSigneIntercept(err)) return
        toast.error("Changement d'étape non enregistré — réessayez.")
      },
    },
  )
  if (!onInlineSave) return null
  const onChange = (e) => {
    const next = e.target.value
    if (next === value) return
    save(next, (v) => onInlineSave(lead, 'stage', v))
  }
  // stopPropagation : interagir avec le select ne doit jamais démarrer un drag.
  return (
    <div
      className="kb-stage-mover"
      {...rowProps}
      onClick={(e) => e.stopPropagation()}
      onPointerDown={(e) => e.stopPropagation()}
      onTouchStart={(e) => e.stopPropagation()}
    >
      <label className="sr-only" htmlFor={`kb-stage-${lead.id}`}>
        Changer l'étape de {lead.nom || 'ce lead'}
      </label>
      <select
        id={`kb-stage-${lead.id}`}
        className="form-control kb-stage-select"
        value={value}
        disabled={isSaving}
        onChange={onChange}
      >
        {/* LB4 — options interdites grisées : MÊME garde que le drag
            (isStageMoveAllowed, miroir _bulk_stage_allowed) — le chemin
            clavier ne pouvait auparavant PAS reproduire le recul-guard
            (bug #8). L'étape courante reste toujours sélectionnable. */}
        {STAGE_MOVE_OPTIONS.map((o) => (
          <option
            key={o.value}
            value={o.value}
            disabled={o.value !== lead.stage && !isStageMoveAllowed(lead.stage, o.value)}
          >
            {o.label}
          </option>
        ))}
      </select>
      {statusLabel && (
        <span className="kb-stage-status text-xs text-muted-foreground">
          {statusLabel}
        </span>
      )}
    </div>
  )
}

// Probabilité de conversion par étape (entonnoir) — UI seulement, sert au
// prévisionnel pondéré (proba × total devis). Les leads perdus comptent 0.
// XSAL15 — exportée pour être réutilisée telle quelle par la vue « Prévision »
// (regroupement par mois plutôt que par étape, MÊME calcul de pondération —
// jamais une seconde table de probabilités déclarée ailleurs).
// eslint-disable-next-line react-refresh/only-export-components -- STAGE_PROBABILITY co-localisé
export const STAGE_PROBABILITY = {
  NEW: 0.1,
  CONTACTED: 0.25,
  QUOTE_SENT: 0.5,
  FOLLOW_UP: 0.7,
  SIGNED: 1,
  COLD: 0.05,
}

// Enveloppe draggable d'une carte ; l'original reste en place (style fantôme)
// pendant que le DragOverlay suit le pointeur.
// LB6 — memo() (blueprint I4, bug #4) : sans lui, KanbanView re-rendait
// TOUTES les instances de DraggableCard (donc ré-exécutait useDraggable +
// recréait la sous-arborescence) à chaque rendu du parent, même quand seule
// UNE carte avait réellement changé — LeadCard(memo) protège son PROPRE
// re-rendu mais pas le travail de DraggableCard lui-même en amont.
const DraggableCard = memo(function DraggableCard({
  lead, busy, onOpen, onAutoQuote, users, onReassign,
  selected, onToggleSelect, onPlanifierRelance, onInlineSave, onMarkPerdu,
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: lead.id,
    data: { lead },
    disabled: busy,
  })
  return (
    <div
      ref={setNodeRef}
      className={isDragging ? 'kb-drag-wrap kb-drag-source' : 'kb-drag-wrap'}
    >
      {/* Le drag n'est rattaché qu'à la carte ; le sélecteur d'étape (clavier)
          vit hors de la poignée pour rester utilisable au clavier/souris. */}
      <div {...listeners} {...attributes}>
        <LeadCard lead={lead} busy={busy} onOpen={onOpen} onAutoQuote={onAutoQuote}
                  users={users} onReassign={onReassign}
                  selected={selected} onToggleSelect={onToggleSelect}
                  onPlanifierRelance={onPlanifierRelance} onMarkPerdu={onMarkPerdu} />
      </div>
      <StageMover lead={lead} onInlineSave={onInlineSave} />
    </div>
  )
})

// Colonne d'étape : zone droppable, accent couleur, compteur, total devis.
// LB9 — région nommée (axe/lecteur d'écran atteignent chaque colonne par son
// libellé + compteur) ; en-têtes déjà épinglés hors du corps scrollant depuis
// LB2 (P0 fondateur), aucune retouche nécessaire pour ça ici.
// LB10 — `collapsed`/`onToggleCollapse` (état + persistance possédés par
// KanbanView, `features/kanban/collapsedColumns.js`) : une colonne repliée
// REND SEULEMENT le rail 44px (chevron + compteur + libellé pivoté), les
// cartes (`children`) ne sont même pas montées — mais le `<section>` garde
// EXACTEMENT le même `ref={setNodeRef}`/`id: col.key` qu'en dépliée : elle
// reste une zone droppable à part entière (surbrillance `kb-over` incluse).
function StageColumn({ col, collapsed, onToggleCollapse, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key })
  // Prévisionnel pondéré : total devis × probabilité de l'étape.
  const forecast = col.totalDevis * (STAGE_PROBABILITY[col.key] ?? 0)
  const chevronLabel = collapsed
    ? `Déplier la colonne ${col.label}`
    : `Replier la colonne ${col.label}`
  const sectionClassName = [
    'kb-col',
    isOver && 'kb-over',
    collapsed && 'kb-col-collapsed',
  ].filter(Boolean).join(' ')
  return (
    <section
      ref={setNodeRef}
      aria-label={`Étape ${col.label} — ${col.count} lead${col.count === 1 ? '' : 's'}`}
      className={sectionClassName}
      style={{ '--kb-accent': col.color }}
    >
      <header className="kb-col-header">
        <div className="kb-col-title-row">
          <button
            type="button"
            className="kb-col-collapse-btn"
            aria-expanded={!collapsed}
            aria-label={chevronLabel}
            title={chevronLabel}
            onClick={onToggleCollapse}
          >
            <ChevronDown
              className={collapsed ? 'kb-col-chevron kb-col-chevron-collapsed' : 'kb-col-chevron'}
              aria-hidden="true"
            />
          </button>
          {!collapsed && <span className="kb-col-title">{col.label}</span>}
          <span className="kb-col-count">{col.count}</span>
        </div>
        {/* LB9 — une SEULE rangée « total MAD · Prév. pondéré » (au lieu de
            deux lignes empilées) ; le tooltip explique la pondération
            STAGE_PROBABILITY importée de plus haut (jamais une seconde table). */}
        {!collapsed && col.totalDevis > 0 && (
          <span
            className="kb-col-money"
            title={`Prévisionnel pondéré à ${Math.round((STAGE_PROBABILITY[col.key] ?? 0) * 100)} % (probabilité de conversion à cette étape)`}
          >
            {formatMAD(col.totalDevis)} · Prév. {formatMAD(forecast)}
          </span>
        )}
      </header>
      {collapsed ? (
        <div className="kb-col-rail-label">{col.label}</div>
      ) : (
        /* LB9 — `tabindex=0` + aria-label : zone de scroll interne atteignable
           au clavier (recon-05 a11y #6), indépendamment du sélecteur d'étape
           (StageMover) déjà focalisable sous chaque carte. */
        <div
          className="kb-col-body"
          tabIndex={0}
          aria-label={`Cartes de l'étape ${col.label}`}
        >
          {col.count === 0 ? (
            <div className="kb-col-empty">Déposer un lead ici</div>
          ) : (
            children
          )}
        </div>
      )}
    </section>
  )
}

export default function KanbanView({
  leads,
  onOpenLead,
  onChangeStage,
  onAutoQuote,
  busyLeadId,
  users,
  onReassign,
  selected = new Set(),
  onToggleSelect,
  onPlanifierRelance,
  onInlineSave,
  onMarkPerdu,
  // LB9 — coach d'état vide à DEUX paliers, même idiome que ChartsView
  // (totalLeads/onClearFilters déjà câblés là-bas sur `leads.length`/
  // `setFilters(EMPTY_FILTERS)`) : `totalLeads` (non filtré) distingue
  // « aucun lead du tout » de « aucun résultat pour CES filtres ». Tous
  // optionnels — tant que `<KanbanView {...viewProps} />` (LeadsPage.jsx) ne
  // les câble pas encore, on dégrade proprement sur le message filtré
  // générique, jamais un crash ni un CTA mort.
  totalLeads = null,
  onClearFilters,
  onNewLead,
  onImportLeads,
}) {
  // VX135 — préférence reduced-motion lue en JS : le tilt (transform statique
  // posé par dnd-kit/CSS) et le dropAnimation (JS pur) échappent tous deux au
  // garde global CSS.
  const prefersReducedMotion = usePrefersReducedMotion()
  // Message éphémère « On ne recule pas une étape » lors d'un drag refusé.
  const [reculMsg, setReculMsg] = useState(false)
  // distance 6px : un clic simple ouvre la fiche, le drag exige un mouvement ;
  // sur mobile, appui long 150 ms pour glisser, le scroll reste naturel.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 150, tolerance: 8 },
    }),
    // VX192 — sensor clavier natif (@dnd-kit/core), 0 dépendance.
    useSensor(KeyboardSensor),
  )
  const columns = useMemo(() => groupLeadsByStage(leads), [leads])
  const [activeLead, setActiveLead] = useState(null)

  // LB10 — repli de colonne PERSISTÉ (localStorage, features/kanban/
  // collapsedColumns.js) : lu UNE FOIS au montage (lazy useState — jamais de
  // repli par défaut, `readCollapsedStages()` renvoie `[]` tant que
  // l'utilisatrice n'a jamais replié une colonne), écrit à chaque bascule.
  const [collapsedStages, setCollapsedStages] = useState(() => new Set(readCollapsedStages()))
  const toggleCollapsed = useCallback((stageKey) => {
    setCollapsedStages((prev) => {
      const next = new Set(prev)
      if (next.has(stageKey)) next.delete(stageKey)
      else next.add(stageKey)
      writeCollapsedStages([...next])
      return next
    })
  }, [])

  // VX192 — annonces FR : id de lead → nom, id de colonne → libellé d'étape.
  const announcements = useMemo(() => {
    const byId = new Map((leads ?? []).map((l) => [l.id, l]))
    const labelFor = (id) => {
      if (STAGE_LABELS[id]) return STAGE_LABELS[id]
      const l = byId.get(id)
      return l?.nom || `#${id}`
    }
    return buildKanbanAnnouncements(labelFor)
  }, [leads])

  const handleDragStart = ({ active }) => {
    setActiveLead(active.data.current?.lead ?? null)
  }

  const handleDragEnd = ({ active, over }) => {
    setActiveLead(null)
    const lead = active.data.current?.lead
    if (!lead || !over || over.id === lead.stage) return
    // LB4 — garde-fou UI : MÊME règle que le serveur (isStageMoveAllowed,
    // miroir _bulk_stage_allowed, stages.js). Bug #7 (recon2-03) : l'ancien
    // `stageRank` local classait COLD au rang le plus HAUT → tout drag
    // COLD→actif était refusé comme un recul, alors que le serveur autorise
    // DÉJÀ cette réactivation (COLD est un parking, pas un rang avancé).
    if (!isStageMoveAllowed(lead.stage, over.id)) {
      setReculMsg(true)
      window.setTimeout(() => setReculMsg(false), 4000)
      return // l'étape reste inchangée
    }
    onChangeStage(lead, over.id)
  }

  const handleDragCancel = () => setActiveLead(null)

  // VX147 — « 0 lead » unifié sur `EmptyState` (calqué sur ChartsView, la
  // seule vue déjà correcte) au lieu de 6 colonnes vides en texte brut.
  // LB9 — désormais à DEUX paliers : `totalLeads === 0` (vraiment aucun lead)
  // reçoit le coach illustré (VX40 — leads est un des 4-5 écrans les plus vus)
  // + CTA création/import ; « filtré à 0 » garde le message générique + un
  // CTA « Effacer les filtres » réel quand le parent le fournit.
  if (!leads || leads.length === 0) {
    const aucunDuTout = totalLeads != null && totalLeads === 0
    if (aucunDuTout) {
      return (
        <EmptyState
          illustrated
          title="Aucun lead"
          description="Créez votre premier lead ou importez votre liste pour démarrer le pipeline."
          action={(onNewLead || onImportLeads) ? (
            <div className="flex flex-wrap items-center justify-center gap-2">
              {onNewLead && (
                <Button type="button" size="sm" onClick={onNewLead}>+ Nouveau lead</Button>
              )}
              {onImportLeads && (
                <Button type="button" variant="outline" size="sm" onClick={onImportLeads}>
                  Importer
                </Button>
              )}
            </div>
          ) : null}
        />
      )
    }
    return (
      <EmptyState
        icon={LayoutGrid}
        title="Aucun lead"
        description="Aucun lead ne correspond à ces filtres."
        action={onClearFilters ? (
          <Button type="button" variant="outline" size="sm" onClick={onClearFilters}>
            Effacer les filtres
          </Button>
        ) : null}
      />
    )
  }

  return (
    <DndContext
      sensors={sensors}
      accessibility={{
        announcements,
        screenReaderInstructions: kanbanScreenReaderInstructions,
      }}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      {reculMsg && (
        <div
          className="kb-recul-msg mb-2 rounded-lg border border-destructive/30 bg-destructive/12 px-3 py-1.5 text-[13px] font-semibold text-destructive"
          role="status"
        >
          On ne recule pas une étape
        </div>
      )}
      <div className="kb-board">
        {columns.map((col) => (
          <StageColumn
            key={col.key}
            col={col}
            collapsed={collapsedStages.has(col.key)}
            onToggleCollapse={() => toggleCollapsed(col.key)}
          >
            {col.leads.map((lead) => (
              <DraggableCard
                key={lead.id}
                lead={lead}
                busy={lead.id === busyLeadId}
                onOpen={onOpenLead}
                onAutoQuote={onAutoQuote}
                users={users}
                onReassign={onReassign}
                selected={selected.has(lead.id)}
                onToggleSelect={onToggleSelect}
                onPlanifierRelance={onPlanifierRelance}
                onInlineSave={onInlineSave}
                onMarkPerdu={onMarkPerdu}
              />
            ))}
          </StageColumn>
        ))}
      </div>
      <DragOverlay dropAnimation={prefersReducedMotion ? DROP_ANIMATION_REDUCED : DROP_ANIMATION}>
        {activeLead ? (
          <div className={prefersReducedMotion ? 'kb-drag-overlay kb-drag-overlay--flat' : 'kb-drag-overlay'}>
            <LeadCard lead={activeLead} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
