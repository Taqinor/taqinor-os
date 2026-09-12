// NTUX12 — Favoris épinglés : widget autonome (Dashboard/sidebar) listant les
// enregistrements épinglés par l'utilisateur courant avec accès direct.
// STRICTEMENT PERSONNEL côté serveur (get_queryset filtre déjà owner=user) :
// ce widget n'affiche jamais les favoris d'un collègue.
//
// NTUX21 — glisser-déposer : réordonnancement persisté CÔTÉ SERVEUR (`ordre`
// sur `FavoriUtilisateur`, `useFavoris().reorder`) — `@dnd-kit/core` SEUL,
// même patron que `pages/home/HomeMenu.jsx` (ODY13) ; `@dnd-kit/sortable`
// n'est PAS installé et reste interdit (NE PAS FAIRE VX).
//
// NTUX35 — export/import CSV à la reprise de poste (démission, changement de
// portefeuille) : l'IMPORT doit rester atteignable même quand l'utilisateur
// n'a ENCORE aucun favori (compte tout juste repris) — le widget ne rend donc
// plus RIEN quand la liste est vide (contrairement au patron NTUX11 de
// `RecentEntitiesWidget.jsx`, qui reste lui purement informatif) : il garde
// son en-tête + ses actions, seul le corps de liste se dérobe.
import { useCallback, useMemo, useRef, useState } from 'react'
import {
  DndContext, KeyboardSensor, PointerSensor, TouchSensor,
  closestCenter, useDraggable, useDroppable, useSensor, useSensors,
} from '@dnd-kit/core'
import { Download, GripVertical, Star, Upload } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, IconButton,
} from '../../ui'
import { toast } from '../../ui/confirm'
import uxviewsApi from '../../api/uxviewsApi'
import { downloadBlob, stampedFilename } from '../../utils/downloadBlob'
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
  const { favoris, loading, reorder, refresh } = useFavoris()
  const [exporting, setExporting] = useState(false)
  const [importing, setImporting] = useState(false)
  const fileRef = useRef(null)

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

  // NTUX35 — export CSV de MES favoris (identifiant métier, jamais l'id
  // numérique brut — cf. apps/uxviews/views.py::export_csv).
  const exporter = () => {
    setExporting(true)
    uxviewsApi.exportFavorisCsv()
      .then((res) => downloadBlob(res.data, stampedFilename('favoris', 'csv')))
      .catch(() => toast.error('Export impossible.'))
      .finally(() => setExporting(false))
  }

  // NTUX35 — import : transfert manuel des favoris d'un utilisateur qui
  // change de compte. Jamais tout-ou-rien — les lignes non résolues sont
  // ignorées silencieusement côté serveur, leur nombre est rapporté ici.
  const importer = (file) => {
    if (!file) return
    setImporting(true)
    uxviewsApi.importFavoris(file)
      .then((res) => {
        const { importes, non_resolues: nonResolues } = res.data
        if (importes > 0) {
          toast.success(`${importes} favori(s) importé(s).`)
          refresh()
        }
        if (nonResolues > 0) {
          toast.error(`${nonResolues} ligne(s) non résolue(s), ignorée(s).`)
        }
        if (!importes && !nonResolues) toast.error('Aucune ligne à importer.')
      })
      .catch(() => toast.error('Import impossible.'))
      .finally(() => {
        setImporting(false)
        if (fileRef.current) fileRef.current.value = ''
      })
  }

  if (loading) return null

  return (
    <Card className="cv-auto" data-testid="favoris-widget">
      <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Star className="size-4 text-muted-foreground" aria-hidden="true" />
            Favoris
          </CardTitle>
          <CardDescription>Vos enregistrements épinglés</CardDescription>
        </div>
        {/* NTUX35 — reste atteignable même sans AUCUN favori (compte tout
            juste repris, rien à exporter mais tout à importer). */}
        <div className="flex shrink-0 items-center gap-0.5">
          <IconButton
            label="Exporter mes favoris"
            variant="ghost" size="icon" className="size-7"
            disabled={exporting || !favoris.length}
            onClick={exporter}
          >
            <Download />
          </IconButton>
          <IconButton
            label="Importer des favoris"
            variant="ghost" size="icon" className="size-7"
            disabled={importing}
            onClick={() => fileRef.current?.click()}
          >
            <Upload />
          </IconButton>
          <input
            ref={fileRef} type="file" accept=".csv,.xlsx" className="hidden"
            onChange={(e) => importer(e.target.files?.[0])}
          />
        </div>
      </CardHeader>
      {favoris.length > 0 && (
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
      )}
    </Card>
  )
}
