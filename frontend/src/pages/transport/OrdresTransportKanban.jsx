import { useCallback, useMemo, useState } from 'react'
import {
  DndContext, DragOverlay, KeyboardSensor, PointerSensor, TouchSensor,
  useDraggable, useDroppable, useSensor, useSensors,
} from '@dnd-kit/core'
import { AlertTriangle } from 'lucide-react'

import api from '../../api/axios'
import { Badge, Button } from '../../ui'
import { toast } from '../../ui/confirm'
import {
  buildKanbanAnnouncements, kanbanScreenReaderInstructions,
} from '../../features/kanban/kanbanA11y'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

/* ============================================================================
   NTLOG25 — vue kanban des ordres de transport, groupée par `statut`
   (motif `TachesKanbanView` du module gestion_projet). `statut` est un champ
   SERVEUR calculé depuis les étapes (`services.recalculer_statut_ordre`,
   `OrdreTransportSerializer.read_only_fields`) : glisser une carte ne le
   PATCH jamais directement — seule la colonne « Livré » déclenche une action
   réelle (`etapes-transport/{id}/livrer/`, NTLOG9 — exige au moins une pièce
   jointe POD, sinon 400 explicite, jamais un déplacement optimiste qui
   mentirait). Les autres colonnes restent informatives : glisser dessus
   explique que le statut avance depuis les étapes, jamais un no-op muet.
   Le bouton « Marquer livré » de chaque carte appelle EXACTEMENT la même
   action que le dépôt sur la colonne « Livré » — alternative clavier/tactile
   au glisser-déposer (motif `TachesKanbanView`'s `<select>`).
   ========================================================================== */

const DROP_ANIMATION = { duration: 180, easing: 'cubic-bezier(0.23, 1, 0.32, 1)' }
const DROP_ANIMATION_REDUCED = { duration: 1, easing: 'linear' }

const COLONNES = [
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'planifie', label: 'Planifié' },
  { key: 'en_cours', label: 'En cours' },
  { key: 'livre', label: 'Livré' },
  { key: 'annule', label: 'Annulé' },
]

function groupByStatut(ordres) {
  const parKey = Object.fromEntries(COLONNES.map((c) => [c.key, []]))
  for (const o of ordres) {
    if (parKey[o.statut]) parKey[o.statut].push(o)
    else parKey.brouillon.push(o)
  }
  return COLONNES.map((c) => ({ ...c, ordres: parKey[c.key], count: parKey[c.key].length }))
}

function livraisonEtape(ordre) {
  return (ordre.etapes || []).find((e) => e.type_etape === 'livraison')
}

function enRetard(ordre) {
  const etape = livraisonEtape(ordre)
  return Boolean(etape?.date_reelle && etape?.date_prevue && etape.date_reelle > etape.date_prevue)
}

function OrdreCard({ ordre, busy, onMarquerLivre }) {
  const retard = enRetard(ordre)
  const peutLivrer = ordre.statut !== 'livre' && ordre.statut !== 'annule'
  return (
    <div className="rounded-lg border bg-card p-3 shadow-ui-xs">
      <div className="flex items-start justify-between gap-2">
        <span className="font-mono text-xs">{ordre.numero || `#${ordre.id}`}</span>
        {retard && (
          <Badge tone="danger" className="flex items-center gap-1">
            <AlertTriangle className="size-3" aria-hidden="true" /> Retard
          </Badge>
        )}
      </div>
      <div className="mt-1 text-sm font-medium">{ordre.destinataire_nom || '—'}</div>
      <div className="mt-1 text-xs text-muted-foreground">
        {ordre.mode_transport_display || ordre.mode_transport || '—'}
        {' · '}
        {ordre.poids_total_kg ? `${ordre.poids_total_kg} kg` : '— kg'}
      </div>
      {ordre.date_livraison_prevue && (
        <div className="mt-1 text-xs text-muted-foreground">
          Livraison prévue : {ordre.date_livraison_prevue}
        </div>
      )}
      {peutLivrer && onMarquerLivre && (
        <div className="mt-2" onClick={(e) => e.stopPropagation()} onPointerDown={(e) => e.stopPropagation()}>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => onMarquerLivre(ordre)}>
            {busy ? 'Livraison…' : 'Marquer livré'}
          </Button>
        </div>
      )}
    </div>
  )
}

function DraggableCard({ ordre, busy, onMarquerLivre }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: ordre.id,
    data: { ordre },
    disabled: busy,
  })
  return (
    <div ref={setNodeRef} className={isDragging ? 'opacity-40' : ''}>
      <div {...listeners} {...attributes}>
        <OrdreCard ordre={ordre} busy={busy} onMarquerLivre={onMarquerLivre} />
      </div>
    </div>
  )
}

function StatutColumn({ col, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key })
  return (
    <section
      ref={setNodeRef}
      className={`flex min-w-56 flex-1 flex-col gap-2 rounded-lg border bg-muted/20 p-2 ${isOver ? 'ring-2 ring-primary/40' : ''}`}
    >
      <header className="flex items-center justify-between px-1">
        <span className="text-sm font-semibold">{col.label}</span>
        <Badge tone="neutral">{col.count}</Badge>
      </header>
      <div className="flex flex-col gap-2">
        {col.count === 0 ? (
          <div className="rounded-md border border-dashed p-3 text-center text-xs text-muted-foreground">
            Aucun ordre
          </div>
        ) : children}
      </div>
    </section>
  )
}

export default function OrdresTransportKanban({ ordres = [], onChanged }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
    useSensor(KeyboardSensor),
  )
  const columns = useMemo(() => groupByStatut(ordres), [ordres])
  const [activeOrdre, setActiveOrdre] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const prefersReducedMotion = usePrefersReducedMotion()

  const announcements = useMemo(() => {
    const colLabel = Object.fromEntries(COLONNES.map((c) => [c.key, c.label]))
    const byId = new Map(ordres.map((o) => [o.id, o]))
    const labelFor = (id) => colLabel[id] || byId.get(id)?.numero || String(id)
    return buildKanbanAnnouncements(labelFor)
  }, [ordres])

  // NTLOG9/NTLOG25 — SEULE action réelle du kanban : clôturer la livraison
  // via `etapes-transport/{id}/livrer/`, qui exige une pièce jointe POD
  // (sinon 400). Jamais de déplacement optimiste de la carte : elle ne
  // change de colonne qu'après confirmation serveur (via `onChanged`, un
  // refetch de la liste).
  const tenterLivrer = useCallback(async (ordre) => {
    const etape = livraisonEtape(ordre)
    if (!etape) {
      toast.error('Aucune étape de livraison sur cet ordre.')
      return
    }
    setBusyId(ordre.id)
    try {
      await api.post(`/transport/etapes-transport/${etape.id}/livrer/`)
      toast.success('Ordre livré.')
      onChanged?.()
    } catch (err) {
      const msg = err?.response?.data?.detail
        || 'Photo ou signature requise avant de clôturer la livraison.'
      toast.error(msg)
    } finally {
      setBusyId(null)
    }
  }, [onChanged])

  const handleDragStart = ({ active }) => setActiveOrdre(active.data.current?.ordre ?? null)
  const handleDragCancel = () => setActiveOrdre(null)

  const handleDragEnd = ({ active, over }) => {
    setActiveOrdre(null)
    const ordre = active.data.current?.ordre
    if (!ordre || !over || over.id === ordre.statut) return

    if (over.id !== 'livre') {
      toast.info(
        "Le statut d'un ordre de transport avance automatiquement depuis "
        + 'ses étapes — ouvrez l’ordre pour faire progresser une étape.',
      )
      return
    }
    tenterLivrer(ordre)
  }

  return (
    <DndContext
      sensors={sensors}
      accessibility={{ announcements, screenReaderInstructions: kanbanScreenReaderInstructions }}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div className="flex gap-3 overflow-x-auto pb-2">
        {columns.map((col) => (
          <StatutColumn key={col.key} col={col}>
            {col.ordres.map((o) => (
              <DraggableCard
                key={o.id}
                ordre={o}
                busy={busyId === o.id}
                onMarquerLivre={tenterLivrer}
              />
            ))}
          </StatutColumn>
        ))}
      </div>
      <DragOverlay dropAnimation={prefersReducedMotion ? DROP_ANIMATION_REDUCED : DROP_ANIMATION}>
        {activeOrdre ? <OrdreCard ordre={activeOrdre} /> : null}
      </DragOverlay>
    </DndContext>
  )
}
