import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, List, LayoutGrid } from 'lucide-react'
import coreApi from '../../api/coreApi'
import useResource from '../../hooks/useResource'
import {
  DataTable, Button, Badge, StatusPill, Segmented, Checkbox, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import SavedViewsBar, { SaveViewButton } from '../../components/SavedViewsBar'
import { useSavedViews } from '../../hooks/useSavedViews'
import { formatDate } from '../../lib/format'
import {
  TYPE_DOSSIER_OPTIONS, STATUT_DOSSIER_OPTIONS, PRIORITE_DOSSIER_OPTIONS,
  prioriteTone, estEnRetard, filtrerDossiers,
} from '../../features/workflow/dossiers'
import DossierKanbanView from './views/DossierKanbanView'

// NTWFL22 — vues sauvegardées : même mécanisme que ClientList/DevisList
// (`useSavedViews`, localStorage PAR NAVIGATEUR donc PAR UTILISATEUR — jamais
// partagé entre postes), aucun nouveau composant.
const DOSSIERS_SAVED_VIEWS_KEY = 'taqinor.core.dossiers.savedViews'

// NTWFL21 — bascule liste/kanban (patron déjà éprouvé : chantiers/leads).
// `Segmented` instancie `opt.icon` lui-même (`<Icon .../>`) : passer le
// COMPOSANT, jamais un élément déjà rendu.
const VUE_OPTIONS = [
  { value: 'liste', label: 'Liste', icon: List },
  { value: 'kanban', label: 'Kanban', icon: LayoutGrid },
]

/* ============================================================================
   NTWFL19 — liste des dossiers transverses (`/dossiers`).
   ----------------------------------------------------------------------------
   Filtre type/statut (transmis au serveur, `DossierViewSet.get_queryset`) +
   priorité (côté écran, cf. `features/workflow/dossiers.js`). Ouvrir un
   dossier navigue vers `/dossiers/:id` (DossierDetail, NTWFL19). Créer un
   dossier passe par un petit formulaire modal — `titre` + `type_dossier`
   requis, le reste optionnel — puis ouvre directement le dossier créé.
   ========================================================================== */

const TOUS = '__tous__'

const AUJOURD_HUI = () => new Date().toISOString().slice(0, 10)

function dossierVide() {
  return { titre: '', type_dossier: 'autre', priorite: 'normale', echeance: '' }
}

// La liste ne lisait que la première page (paginée DRF, 50 par défaut) : le
// kanban et le filtre « en retard uniquement » (NTWFL22, côté écran) ne
// voyaient qu'un sous-ensemble, ce qui pouvait afficher « Aucun dossier » à
// tort dès que le vrai résultat vivait sur une page suivante. On suit `next`
// jusqu'au bout, borné à `DOSSIERS_MAX_PAGES` — au-delà, l'écran prévient
// plutôt que de continuer en silence avec une liste incomplète.
const DOSSIERS_MAX_PAGES = 20

async function fetchTousLesDossiers(params) {
  const first = await coreApi.dossiers.list({ ...params, page: 1 })
  const firstData = first.data
  if (Array.isArray(firstData)) return firstData
  let rows = firstData?.results ?? []
  let next = firstData?.next
  let page = 2
  while (next && page <= DOSSIERS_MAX_PAGES) {
    const r = await coreApi.dossiers.list({ ...params, page })
    const d = r.data
    rows = rows.concat(Array.isArray(d) ? d : (d?.results ?? []))
    next = Array.isArray(d) ? null : d?.next
    page += 1
  }
  if (next) {
    toast.error(
      `Liste des dossiers tronquée (plus de ${DOSSIERS_MAX_PAGES} pages) — affinez les filtres.`,
    )
  }
  return rows
}

function NouveauDossierDialog({ open, onOpenChange, onCreated }) {
  const [form, setForm] = useState(dossierVide)
  const [busy, setBusy] = useState(false)

  const majChamp = (champ, valeur) => setForm((f) => ({ ...f, [champ]: valeur }))

  const submit = async (e) => {
    e.preventDefault()
    const titre = form.titre.trim()
    if (!titre) return
    setBusy(true)
    try {
      const r = await coreApi.dossiers.create({
        titre,
        type_dossier: form.type_dossier,
        priorite: form.priorite,
        echeance: form.echeance || null,
      })
      setForm(dossierVide())
      onCreated(r.data)
    } catch (err) {
      // DRF renvoie les erreurs de champ sous forme de LISTE (`{titre: [...]}`),
      // jamais une chaîne brute : afficher le tableau tel quel rendrait
      // `[object Object]`/une virgule illisible dans le toast.
      const titre = err?.response?.data?.titre
      const message = Array.isArray(titre) ? titre.join(' ') : titre
      toast.error(message || 'Création du dossier impossible.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouveau dossier</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-3" onSubmit={submit}>
          <div className="flex flex-col gap-1">
            <Label required htmlFor="dossier-titre">Titre</Label>
            <Input
              id="dossier-titre"
              value={form.titre}
              onChange={(e) => majChamp('titre', e.target.value)}
              autoFocus
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="dossier-type">Type de dossier</Label>
            <Select value={form.type_dossier} onValueChange={(v) => majChamp('type_dossier', v)}>
              <SelectTrigger id="dossier-type"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TYPE_DOSSIER_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="dossier-priorite">Priorité</Label>
            <Select value={form.priorite} onValueChange={(v) => majChamp('priorite', v)}>
              <SelectTrigger id="dossier-priorite"><SelectValue /></SelectTrigger>
              <SelectContent>
                {PRIORITE_DOSSIER_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="dossier-echeance">Échéance (optionnelle)</Label>
            <Input
              id="dossier-echeance"
              type="date"
              value={form.echeance}
              onChange={(e) => majChamp('echeance', e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={busy || !form.titre.trim()}>
              Créer le dossier
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function DossierList() {
  const navigate = useNavigate()
  const [filtreType, setFiltreType] = useState(TOUS)
  const [filtreStatut, setFiltreStatut] = useState(TOUS)
  const [filtrePriorite, setFiltrePriorite] = useState(TOUS)
  const [enRetardSeulement, setEnRetardSeulement] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [vue, setVue] = useState('liste')

  // NTWFL22 — vues sauvegardées PRIVÉES par utilisateur : le combiné
  // type/statut/priorité/« en retard uniquement »/vue, retrouvé après
  // rafraîchissement (localStorage, jamais envoyé au serveur).
  const { savedViews, saveView, deleteView } = useSavedViews(DOSSIERS_SAVED_VIEWS_KEY)
  const enregistrerVue = () => {
    const nom = window.prompt('Nom de la vue enregistrée :')
    saveView(nom, { filtreType, filtreStatut, filtrePriorite, enRetardSeulement, vue })
  }
  const appliquerVue = (v) => {
    const etat = v.state || {}
    if (etat.filtreType) setFiltreType(etat.filtreType)
    if (etat.filtreStatut) setFiltreStatut(etat.filtreStatut)
    if (etat.filtrePriorite) setFiltrePriorite(etat.filtrePriorite)
    setEnRetardSeulement(!!etat.enRetardSeulement)
    if (etat.vue) setVue(etat.vue)
  }

  const params = useMemo(() => ({
    type_dossier: filtreType === TOUS ? undefined : filtreType,
    statut: filtreStatut === TOUS ? undefined : filtreStatut,
  }), [filtreType, filtreStatut])

  const { data: brutes, loading, error, refetch } = useResource(
    fetchTousLesDossiers,
    params,
    { initialData: [], errorMessage: 'Impossible de charger les dossiers.' },
  )

  // NTWFL22 — priorité et « en retard uniquement » filtrent côté écran (le
  // serveur ne filtre que type/statut, cf. DossierViewSet.get_queryset).
  const rows = useMemo(() => filtrerDossiers(
    brutes,
    { priorite: filtrePriorite === TOUS ? '' : filtrePriorite, enRetardSeulement },
    AUJOURD_HUI(),
  ), [brutes, filtrePriorite, enRetardSeulement])

  const aujourdHui = AUJOURD_HUI()

  // NTWFL21 — changement de statut depuis le kanban : optimiste (la carte
  // change de colonne immédiatement), le chatter (NTWFL18) est journalisé
  // côté serveur par `DossierViewSet.perform_update`, jamais dupliqué ici.
  const changerStatut = async (dossier, statut) => {
    try {
      await coreApi.dossiers.update(dossier.id, { statut })
      refetch()
    } catch {
      toast.error('Changement de statut impossible.')
    }
  }

  const columns = useMemo(() => [
    {
      id: 'type_dossier',
      header: 'Type',
      width: 170,
      accessor: (d) => d.type_dossier_label || '',
      cell: (v) => v || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'titre',
      header: 'Titre',
      width: 240,
      accessor: (d) => d.titre || '',
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 130,
      searchable: false,
      accessor: (d) => d.statut,
      cell: (v, d) => <StatusPill status={v} label={d.statut_label} dot={false} />,
    },
    {
      id: 'priorite',
      header: 'Priorité',
      width: 110,
      searchable: false,
      accessor: (d) => d.priorite,
      cell: (v, d) => <Badge tone={prioriteTone(v)}>{d.priorite_label}</Badge>,
    },
    {
      id: 'proprietaire',
      header: 'Propriétaire',
      width: 150,
      accessor: (d) => d.proprietaire_username || '',
      cell: (v) => v || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'echeance',
      header: 'Échéance',
      width: 170,
      align: 'right',
      searchable: false,
      accessor: (d) => d.echeance || '',
      cell: (v, d) => {
        if (!v) return <span className="text-muted-foreground">—</span>
        return (
          <span className="inline-flex items-center justify-end gap-1.5">
            {formatDate(v)}
            {estEnRetard(d, aujourdHui) && <StatusPill tone="danger" label="En retard" dot={false} />}
          </span>
        )
      },
    },
    {
      id: 'liens',
      header: 'Objets liés',
      width: 100,
      align: 'right',
      searchable: false,
      accessor: (d) => (d.liens ?? []).length,
      cell: (v) => v,
    },
    {
      id: 'checklist',
      header: 'Checklist',
      width: 100,
      align: 'right',
      searchable: false,
      accessor: (d) => {
        const items = d.checklist ?? []
        return items.length ? items.filter((it) => it.fait).length / items.length : null
      },
      cell: (_v, d) => {
        const items = d.checklist ?? []
        if (!items.length) return <span className="text-muted-foreground">—</span>
        return `${items.filter((it) => it.fait).length}/${items.length}`
      },
    },
  ], [aujourdHui])

  return (
    <div className="p-4 sm:p-6">
      <PageHeader
        title="Dossiers"
        subtitle="Réclamations complexes, onboarding grand compte, litiges, projets transverses."
        actions={(
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="size-4" aria-hidden="true" /> Nouveau dossier
          </Button>
        )}
      />

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Select value={filtreType} onValueChange={setFiltreType}>
          <SelectTrigger className="h-9 w-48 text-sm" aria-label="Filtrer par type de dossier">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={TOUS}>Tous les types</SelectItem>
            {TYPE_DOSSIER_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={filtreStatut} onValueChange={setFiltreStatut}>
          <SelectTrigger className="h-9 w-40 text-sm" aria-label="Filtrer par statut">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={TOUS}>Tous les statuts</SelectItem>
            {STATUT_DOSSIER_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={filtrePriorite} onValueChange={setFiltrePriorite}>
          <SelectTrigger className="h-9 w-36 text-sm" aria-label="Filtrer par priorité">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={TOUS}>Toutes priorités</SelectItem>
            {PRIORITE_DOSSIER_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={enRetardSeulement} onCheckedChange={setEnRetardSeulement} />
          En retard uniquement
        </label>
        <Segmented options={VUE_OPTIONS} value={vue} onChange={setVue} size="sm" />
        <SaveViewButton onSave={enregistrerVue} />
        <SavedViewsBar savedViews={savedViews} onApply={appliquerVue} onDelete={deleteView} />
      </div>

      {vue === 'kanban' ? (
        <DossierKanbanView
          items={rows}
          aujourdHui={aujourdHui}
          onOpen={(d) => navigate(`/dossiers/${d.id}`)}
          onChangeStatus={changerStatut}
        />
      ) : (
        <DataTable
          data={rows}
          columns={columns}
          getRowId={(d) => d.id}
          loading={loading}
          searchable
          searchPlaceholder="Rechercher un titre, un propriétaire…"
          onRowClick={(d) => navigate(`/dossiers/${d.id}`)}
          emptyTitle="Aucun dossier"
          emptyDescription={error || 'Aucun dossier ne correspond à cette vue.'}
          aria-label="Liste des dossiers"
        />
      )}

      <NouveauDossierDialog
        open={showCreate}
        onOpenChange={setShowCreate}
        onCreated={(d) => {
          setShowCreate(false)
          toast.success('Dossier créé.')
          refetch()
          navigate(`/dossiers/${d.id}`)
        }}
      />
    </div>
  )
}
