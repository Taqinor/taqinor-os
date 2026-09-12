// NTUX12 — Favoris épinglés : widget autonome (Dashboard/sidebar) listant les
// enregistrements épinglés par l'utilisateur courant avec accès direct.
// STRICTEMENT PERSONNEL côté serveur (get_queryset filtre déjà owner=user) :
// ce widget n'affiche jamais les favoris d'un collègue. Même patron que
// `RecentEntitiesWidget.jsx` (NTUX11) — rend RIEN si la liste est vide.
//
// NTUX21 — glisser-déposer : réordonnancement persisté CÔTÉ SERVEUR (`ordre`
// sur `FavoriUtilisateur`, `useFavoris().reorder`) — `@dnd-kit/core` SEUL,
// même patron que `pages/home/HomeMenu.jsx` (ODY13) ; `@dnd-kit/sortable`
// n'est PAS installé et reste interdit (NE PAS FAIRE VX).
import { useCallback, useMemo } from 'react'
import {
  DndContext, KeyboardSensor, PointerSensor, TouchSensor,
  closestCenter, useDraggable, useDroppable, useSensor, useSensors,
} from '@dnd-kit/core'
import { GripVertical, Star } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../ui'
import { ROUTE, TYPE_LABEL, TYPE_ACCENT } from '../../lib/search/entityRoutes'
import { buildDndListAnnouncements, dndListScreenReaderInstructions, reorderIds } from './dndA11y'
import { useFavoris } from './useFavoris'

// Clé de modèle serveur ('<app_label>.<model>', cf. FavoriUtilisateurSerializer)
// → clé de type ROUTE/TYPE_LABEL/TYPE_ACCENT (lib/search/entityRoutes.js) —
// même table que la palette ⌘K et les Récents, aucune route dupliquée. Un
// `modele` absent d'ici (favori sur un type encore non câblé à la recherche
// globale) reste affiché — juste sans navigation directe, jamais masqué.
const MODELE_TO_TYPE = {
  'crm.lead': 'lead',
  'crm.client': 'client',
  'ventes.devis': 'devis',
  'facturation.facture': 'facture',
  'installations.installation': 'chantier',
  'sav.ticket': 'ticket',
  'stock.produit': 'produit',
}

function favoriLabel(f) {
  const type = MODELE_TO_TYPE[f.modele]
  return f.libelle || (type && TYPE_LABEL[type]) || 'Élément épinglé'
}

// FavoriRow — un favori de la liste. Poignée de déplacement SÉPARÉE du bouton
// de navigation (deux contrôles frères, jamais imbriqués — `nested-interactive`) :
// le capteur clavier de dnd-kit s'active sur Entrée/Espace, qui ouvrent déjà
// le favori sur le bouton principal.
function FavoriRow({ favori, onOuvrir, reordonnable }) {
  const { attributes, listeners, setNodeRef: setDrag, isDragging } = useDraggable({
    id: favori.id, disabled: !reordonnable,
  })
  const { setNodeRef: setDrop, isOver } = useDroppable({
    id: favori.id, disabled: !reordonnable,
  })
  const setRefs = useCallback((node) => { setDrag(node); setDrop(node) }, [setDrag, setDrop])
  const type = MODELE_TO_TYPE[favori.modele]
  const make = type && ROUTE[type]

  return (
    <li
      ref={setRefs}
      className={`flex items-center gap-1 rounded-lg ${isDragging ? 'opacity-60' : ''} ${isOver ? 'bg-accent/40' : ''}`}
    >
      {reordonnable && (
        <button
          type="button"
          className="shrink-0 cursor-grab touch-none rounded p-1 text-muted-foreground hover:text-foreground focus-ring active:cursor-grabbing"
          aria-label={`Déplacer ${favoriLabel(favori)}`}
          {...attributes}
          {...listeners}
        >
          <GripVertical size={13} strokeWidth={1.75} aria-hidden="true" />
        </button>
      )}
      <button
        type="button"
        disabled={!make}
        onClick={() => make && onOuvrir(make(favori.object_id))}
        className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-accent/60 focus-ring disabled:cursor-default disabled:opacity-60 disabled:hover:bg-transparent"
      >
        {type && TYPE_ACCENT[type] && (
          <span
            className="size-1.5 shrink-0 rounded-full"
            style={{ background: `var(--module-accent-${TYPE_ACCENT[type]})` }}
            aria-hidden="true"
          />
        )}
        <span className="min-w-0 flex-1 truncate font-medium text-foreground">
          {favoriLabel(favori)}
        </span>
      </button>
    </li>
  )
}

export default function FavorisWidget() {
  const navigate = useNavigate()
  const { favoris, loading, reorder } = useFavoris()

  // NTUX21 — poignée souris/tactile avec seuil (un clic ne doit jamais
  // démarrer un glisser) + capteur clavier natif de @dnd-kit/core.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
    useSensor(KeyboardSensor),
  )
  const labelFor = useCallback(
    (id) => favoriLabel(favoris.find((f) => f.id === id) || {}), [favoris])
  const announcements = useMemo(() => buildDndListAnnouncements(labelFor), [labelFor])

  const onDragEnd = useCallback((event) => {
    const ids = favoris.map((f) => f.id)
    const next = reorderIds(ids, event)
    if (!next) return
    reorder(event.active.id, next.indexOf(event.active.id))
  }, [favoris, reorder])

  if (loading || !favoris.length) return null

  return (
    <Card className="cv-auto" data-testid="favoris-widget">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Star className="size-4 text-muted-foreground" aria-hidden="true" />
          Favoris
        </CardTitle>
        <CardDescription>Vos enregistrements épinglés</CardDescription>
      </CardHeader>
      <CardContent>
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          accessibility={{ announcements, screenReaderInstructions: dndListScreenReaderInstructions }}
          onDragEnd={onDragEnd}
        >
          <ul className="flex flex-col gap-1" role="list">
            {favoris.map((f) => (
              <FavoriRow
                key={f.id} favori={f} onOuvrir={navigate}
                reordonnable={favoris.length > 1}
              />
            ))}
          </ul>
        </DndContext>
      </CardContent>
    </Card>
  )
}
