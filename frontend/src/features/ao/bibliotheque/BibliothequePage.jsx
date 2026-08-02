import { useMemo, useState } from 'react'
import { LayoutGrid, SlidersHorizontal, FileText, ClipboardList, AlertTriangle } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import {
  Segmented, Card, Button, Badge, Textarea, EmptyState, Skeleton, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'

/* ============================================================================
   AOF173 — Bibliothèque : kits, presets, gabarits de dossier, textes
   normalisés.
   ----------------------------------------------------------------------------
   Un seul type de ressource serveur (`aoApi.bibliotheque`, AOF11), filtré par
   `type` ('kit' | 'preset' | 'gabarit_pack' | 'texte_normalise').

   « Appliquer » (kits/presets) est UN clic → UN appel réseau tracé côté
   serveur (`appliquer()`) : aucun assistant multi-étapes ici, le service
   serveur porte la traçabilité (qui/quand/quoi).

   « Modifier » un texte normalisé PARTAGÉ (repris dans plusieurs dossiers)
   charge et affiche la liste des dossiers impactés (`dossiersImpactes()`)
   AVANT toute validation possible — le bouton Enregistrer reste désactivé
   tant que cette liste n'a pas fini de charger. La sauvegarde est un PATCH
   sur le MÊME `id` (`update()`, jamais `create()`) : aucune duplication
   silencieuse de texte.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const CATEGORIES = [
  { value: 'kit', label: 'Kits de pose', icon: LayoutGrid },
  { value: 'preset', label: 'Jeux de paramètres', icon: SlidersHorizontal },
  { value: 'gabarit_pack', label: 'Gabarits de pack', icon: FileText },
  { value: 'texte_normalise', label: 'Textes normalisés', icon: ClipboardList },
]

export default function BibliothequePage() {
  const [categorie, setCategorie] = useState(CATEGORIES[0].value)
  const [editing, setEditing] = useState(null) // item texte_normalise en édition

  const params = useMemo(() => ({ type: categorie }), [categorie])
  const { data: items, loading, error, refetch } = useResource(
    () => aoApi.bibliotheque.list(params), params,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger la bibliothèque.' },
  )

  const appliquer = async (item) => {
    try {
      await aoApi.bibliotheque.appliquer(item.id)
      toast.success(`« ${item.nom} » appliqué.`)
    } catch (e) {
      toast.error(errMsg(e, 'Application impossible.'))
    }
  }

  const activeCategory = CATEGORIES.find((c) => c.value === categorie)
  const Icon = activeCategory.icon
  const isTexte = categorie === 'texte_normalise'

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Bibliothèque</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Kits de pose, jeux de paramètres, gabarits de pack et textes normalisés — réutilisables en un clic.
          </p>
        </div>
        <Segmented
          options={CATEGORIES.map((c) => ({ value: c.value, label: c.label }))}
          value={categorie}
          onChange={setCategorie}
          aria-label="Catégorie de bibliothèque"
        />
      </div>

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((unused, i) => (
            <Card key={i} className="p-4"><Skeleton className="h-5 w-2/3" /><Skeleton className="mt-3 h-4 w-full" /></Card>
          ))}
        </div>
      ) : error ? (
        <EmptyState icon={AlertTriangle} title="Impossible de charger la bibliothèque" description={error} />
      ) : items.length === 0 ? (
        <EmptyState icon={Icon} title="Rien ici pour le moment" description={`Aucun élément dans « ${activeCategory.label} ».`} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <Card key={item.id} className="flex flex-col gap-2 p-4">
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium">{item.nom}</span>
                {item.dossiers_utilisant_count > 0 && (
                  <Badge tone="info">{item.dossiers_utilisant_count} dossier(s)</Badge>
                )}
              </div>
              {item.description && <p className="text-sm text-muted-foreground">{item.description}</p>}
              <div className="mt-1 flex justify-end gap-2">
                {isTexte ? (
                  <Button size="sm" variant="outline" onClick={() => setEditing(item)}>Modifier</Button>
                ) : (
                  <Button size="sm" onClick={() => appliquer(item)}>Appliquer</Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {editing && (
        <ModifierTexteDialog
          item={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); refetch() }}
        />
      )}
    </div>
  )
}

// AOF173 — modifier un texte normalisé PARTAGÉ : la liste des dossiers
// impactés est chargée et affichée AVANT toute validation possible.
function ModifierTexteDialog({ item, onClose, onSaved }) {
  const [corps, setCorps] = useState(item.corps ?? '')
  const [saving, setSaving] = useState(false)

  const { data: dossiersImpactes, loading: loadingImpact, error: errorImpact } = useResource(
    () => aoApi.bibliotheque.dossiersImpactes(item.id), item.id,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de vérifier les dossiers impactés.' },
  )

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      // PATCH sur le MÊME id — jamais un `create()` : aucune duplication
      // silencieuse de texte.
      await aoApi.bibliotheque.update(item.id, { corps })
      toast.success('Texte normalisé mis à jour.')
      onSaved()
    } catch (e2) {
      toast.error(errMsg(e2, 'Mise à jour impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Modifier « {item.nom} »</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="rounded-lg border border-warning/40 bg-warning/5 p-3 text-sm">
            <p className="mb-1.5 flex items-center gap-1.5 font-medium text-warning">
              <AlertTriangle className="size-4" aria-hidden="true" />
              Texte partagé — repris dans {loadingImpact ? '…' : dossiersImpactes.length} dossier(s)
            </p>
            {loadingImpact ? (
              <Skeleton className="h-4 w-full" />
            ) : errorImpact ? (
              <p className="text-destructive">{errorImpact}</p>
            ) : dossiersImpactes.length === 0 ? (
              <p className="text-muted-foreground">Aucun dossier ne reprend ce texte pour le moment.</p>
            ) : (
              <ul className="flex flex-wrap gap-1.5">
                {dossiersImpactes.map((d) => (
                  <li key={d.id}>
                    <Badge tone="warning">{d.reference || d.affaire_reference || `#${d.id}`}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Textarea
            value={corps}
            onChange={(e) => setCorps(e.target.value)}
            rows={6}
            aria-label="Corps du texte normalisé"
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving || loadingImpact}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
