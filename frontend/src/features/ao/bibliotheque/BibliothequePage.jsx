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
   RÉPARATION 03/08/2026 — cet écran appelait `/ao/bibliotheque/`, une route
   INEXISTANTE côté serveur (404 en production). Les quatre catégories sont
   quatre ressources RÉELLES (`kits-calepinage`, `presets-calepinage`,
   `modeles-pack`, `sections-memoire`) : `aoApi.bibliotheque` n'est qu'une
   façade de lecture qui choisit la bonne, et cet écran consomme la FORME
   réelle de chaque sérialiseur (`code`/`libelle`, `nom`, `titre`/`corps`) —
   plus aucun champ supposé.

   « Modifier » un texte normalisé PARTAGÉ charge et affiche la liste des
   dossiers impactés (`dossiersImpactes()`) AVANT toute validation possible —
   le bouton Enregistrer reste désactivé tant que cette liste n'a pas fini de
   charger. La sauvegarde est un PATCH sur le MÊME `id` (`update()`, jamais
   `create()`) : aucune duplication silencieuse de texte.

   « Appliquer » n'existe PLUS ici : côté serveur, appliquer un jeu de
   paramètres écrit sur une TOITURE (`services.appliquer_preset`) et cet écran
   global n'en désigne aucune. Le bouton d'origine appelait un endpoint
   inventé ; plutôt que de deviner une cible, l'écran dit d'où l'application
   se fait réellement. Endpoint à construire le jour où la cible est tranchée.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const CATEGORIES = [
  { value: 'kit', label: 'Kits de pose', icon: LayoutGrid },
  { value: 'preset', label: 'Jeux de paramètres', icon: SlidersHorizontal },
  { value: 'gabarit_pack', label: 'Gabarits de pack', icon: FileText },
  { value: 'texte_normalise', label: 'Textes normalisés', icon: ClipboardList },
]

/* Chaque ressource a SES champs — la bibliothèque ne les renomme pas côté
   serveur, c'est donc l'écran qui lit la forme réelle de chacune. */
const LECTURES = {
  kit: (r) => ({ nom: r.libelle || r.code, description: r.code }),
  preset: (r) => ({ nom: r.nom, description: r.description }),
  gabarit_pack: (r) => ({ nom: r.libelle || r.code, description: r.description }),
  texte_normalise: (r) => ({ nom: r.titre || r.code, description: '', corps: r.corps }),
}

const normaliser = (type) => (r) => ({ ...r, ...LECTURES[type](r) })

export default function BibliothequePage() {
  const [categorie, setCategorie] = useState(CATEGORIES[0].value)
  const [editing, setEditing] = useState(null) // item texte_normalise en édition

  const params = useMemo(() => ({ type: categorie }), [categorie])
  const { data: items, loading, error, refetch } = useResource(
    () => aoApi.bibliotheque.list(params), params,
    {
      initialData: [],
      select: (res) => unwrapList(res).map(normaliser(categorie)),
      errorMessage: 'Impossible de charger la bibliothèque.',
    },
  )

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
                {item.actif === false && <Badge tone="neutral">Retiré</Badge>}
              </div>
              {item.description && <p className="text-sm text-muted-foreground">{item.description}</p>}
              <div className="mt-1 flex items-center justify-end gap-2">
                {isTexte ? (
                  <Button size="sm" variant="outline" onClick={() => setEditing(item)}>Modifier</Button>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    Application depuis la toiture concernée
                  </span>
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
      // PATCH sur le MÊME id de la ressource RÉELLE (`sections-memoire`) —
      // jamais un `create()` : aucune duplication silencieuse de texte.
      await aoApi.bibliotheque.update('texte_normalise', item.id, { corps })
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
                    <Badge tone="warning">{d.reference || `#${d.id}`}</Badge>
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
