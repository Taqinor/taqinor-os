// NTUX2 — Écran de gestion des vues par liste : bouton « Vues » dans le
// header, ouvre un Popover listant les vues personnelles + partagées
// d'équipe (NTUX1), avec dupliquer/renommer/supprimer et « Définir par
// défaut pour mon rôle » (si permission Directeur/Admin).
//
// NTUX21 — glisser-déposer : réordonnancement de « Mes vues » UNIQUEMENT
// (jamais les vues d'équipe, dont l'ordre reste celui du serveur), persisté
// en localStorage (`useServerSavedViews().reorderMine`, voir
// `personalViewOrder.js`) — `@dnd-kit/core` SEUL, même patron que
// `pages/home/HomeMenu.jsx` (ODY13) ; `@dnd-kit/sortable` n'est PAS installé
// et reste interdit (NE PAS FAIRE VX).
import { useCallback, useMemo, useState } from 'react'
import {
  DndContext, KeyboardSensor, PointerSensor, TouchSensor,
  closestCenter, useDraggable, useDroppable, useSensor, useSensors,
} from '@dnd-kit/core'
import { Star, Copy, Pencil, Trash2, LayoutList, GripVertical } from 'lucide-react'
import {
  Button, Popover, PopoverTrigger, PopoverContent, Input, IconButton,
} from '../../ui'
import { toast } from '../../ui/confirm'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { buildDndListAnnouncements, dndListScreenReaderInstructions, reorderIds } from './dndA11y'
import { useServerSavedViews } from './useServerSavedViews'

function ViewRow({
  view, active, canSetDefault, reordonnable,
  onApply, onDuplicate, onRename, onDelete, onSetDefault,
}) {
  const [renaming, setRenaming] = useState(false)
  const [draftName, setDraftName] = useState(view.nom)
  const { attributes, listeners, setNodeRef: setDrag, isDragging } = useDraggable({
    id: view.id, disabled: !reordonnable,
  })
  const { setNodeRef: setDrop, isOver } = useDroppable({
    id: view.id, disabled: !reordonnable,
  })
  const setRefs = useCallback((node) => { setDrag(node); setDrop(node) }, [setDrag, setDrop])

  const commitRename = () => {
    setRenaming(false)
    const trimmed = draftName.trim()
    if (trimmed && trimmed !== view.nom) onRename(view.id, trimmed)
    else setDraftName(view.nom)
  }

  return (
    <div
      ref={setRefs}
      data-testid="uxviews-view-row"
      className={[
        'flex items-center gap-1.5 rounded-lg px-2 py-1.5',
        active ? 'bg-primary/10' : 'hover:bg-muted/50',
        isDragging ? 'opacity-60' : '',
        isOver ? 'ring-1 ring-inset ring-primary/40' : '',
      ].filter(Boolean).join(' ')}
    >
      {reordonnable && (
        <IconButton
          label={`Déplacer ${view.nom}`}
          variant="ghost" size="icon" className="size-7 shrink-0 cursor-grab touch-none active:cursor-grabbing"
          {...attributes}
          {...listeners}
        >
          <GripVertical />
        </IconButton>
      )}
      {renaming ? (
        <Input
          autoFocus
          value={draftName}
          onChange={(e) => setDraftName(e.target.value)}
          onBlur={commitRename}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitRename()
            if (e.key === 'Escape') { setDraftName(view.nom); setRenaming(false) }
          }}
          className="h-7 text-sm"
        />
      ) : (
        <button
          type="button"
          className="flex-1 truncate text-left text-sm"
          onClick={() => onApply(view)}
        >
          {view.est_defaut_role && <Star className="mr-1 inline size-3 fill-warning text-warning" aria-hidden="true" />}
          {view.nom}
        </button>
      )}
      {!renaming && (
        <div className="flex items-center gap-0.5">
          {canSetDefault && !view.est_defaut_role && (
            <IconButton
              label="Définir par défaut pour mon rôle"
              variant="ghost" size="icon" className="size-7"
              onClick={() => onSetDefault(view)}
            >
              <Star />
            </IconButton>
          )}
          <IconButton
            label="Dupliquer" variant="ghost" size="icon" className="size-7"
            onClick={() => onDuplicate(view)}
          >
            <Copy />
          </IconButton>
          <IconButton
            label="Renommer" variant="ghost" size="icon" className="size-7"
            onClick={() => setRenaming(true)}
          >
            <Pencil />
          </IconButton>
          <IconButton
            label="Supprimer" variant="ghost" size="icon" className="size-7 text-destructive"
            onClick={() => onDelete(view)}
          >
            <Trash2 />
          </IconButton>
        </div>
      )}
    </div>
  )
}

/**
 * ViewsManagerPopover — `<ViewsManagerPopover ecran="crm.leads" onApply={(configuration) => …} />`
 * `onApply` reçoit `view.configuration` (filtres/tri/colonnes/groupement, NTUX1/3/4/19)
 * chaque fois qu'une vue est appliquée (clic manuel ou vue par défaut au chargement —
 * l'appelant est responsable de câbler l'effet initial via `activeView`).
 */
export default function ViewsManagerPopover({ ecran, onApply }) {
  const [open, setOpen] = useState(false)
  const canSetDefault = useIsAdminOrResponsable()
  const {
    mine, team, activeView, loading,
    applyView, duplicateView, renameView, deleteView, setDefaultForMyRole,
    reorderMine,
  } = useServerSavedViews(ecran)

  const apply = (view) => {
    applyView(view)
    onApply?.(view.configuration || {})
    setOpen(false)
  }

  // NTUX21 — glisser-déposer de « Mes vues » (jamais les vues d'équipe).
  const mineReordonnable = mine.length > 1
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
    useSensor(KeyboardSensor),
  )
  const labelForMine = useCallback(
    (id) => mine.find((v) => v.id === id)?.nom ?? String(id), [mine])
  const announcements = useMemo(() => buildDndListAnnouncements(labelForMine), [labelForMine])
  const onDragEndMine = useCallback((event) => {
    const ids = mine.map((v) => v.id)
    const next = reorderIds(ids, event)
    if (next) reorderMine(next)
  }, [mine, reorderMine])

  const handleDelete = (view) => {
    if (view.est_defaut_role && !canSetDefault) {
      toast.error('Seul un Directeur/Admin peut supprimer une vue par défaut de rôle.')
      return
    }
    deleteView(view.id).catch(() => toast.error('Suppression impossible.'))
  }

  const handleSetDefault = (view) => {
    setDefaultForMyRole(view)
      .then(() => toast.success(`« ${view.nom} » est maintenant la vue par défaut de votre rôle.`))
      .catch(() => toast.error('Impossible de définir cette vue par défaut.'))
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" data-testid="uxviews-open-btn">
          <LayoutList />
          Vues
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 p-2">
        {loading ? (
          <p className="p-2 text-sm text-muted-foreground">Chargement…</p>
        ) : (
          <>
            {mine.length > 0 && (
              <div className="mb-2">
                <p className="px-2 py-1 text-xs font-semibold uppercase text-muted-foreground">Mes vues</p>
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  accessibility={{ announcements, screenReaderInstructions: dndListScreenReaderInstructions }}
                  onDragEnd={onDragEndMine}
                >
                  {mine.map((v) => (
                    <ViewRow
                      key={v.id} view={v} active={activeView?.id === v.id}
                      canSetDefault={canSetDefault} reordonnable={mineReordonnable}
                      onApply={apply} onDuplicate={duplicateView} onRename={renameView}
                      onDelete={handleDelete} onSetDefault={handleSetDefault}
                    />
                  ))}
                </DndContext>
              </div>
            )}
            {team.length > 0 && (
              <div>
                <p className="px-2 py-1 text-xs font-semibold uppercase text-muted-foreground">Vues d'équipe</p>
                {team.map((v) => (
                  <ViewRow
                    key={v.id} view={v} active={activeView?.id === v.id}
                    canSetDefault={canSetDefault}
                    onApply={apply} onDuplicate={duplicateView} onRename={renameView}
                    onDelete={handleDelete} onSetDefault={handleSetDefault}
                  />
                ))}
              </div>
            )}
            {mine.length === 0 && team.length === 0 && (
              <p className="p-2 text-sm text-muted-foreground">Aucune vue enregistrée pour cet écran.</p>
            )}
          </>
        )}
      </PopoverContent>
    </Popover>
  )
}
