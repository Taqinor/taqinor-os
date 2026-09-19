import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, List, LayoutGrid } from 'lucide-react'
import coreApi from '../../api/coreApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'
import {
  DataTable, Button, Badge, StatusPill, Segmented, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { formatDate } from '../../lib/format'
import {
  TYPE_DOSSIER_OPTIONS, STATUT_DOSSIER_OPTIONS, PRIORITE_DOSSIER_OPTIONS,
  prioriteTone, estEnRetard,
} from '../../features/workflow/dossiers'
import DossierKanbanView from './views/DossierKanbanView'

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
      toast.error(err?.response?.data?.titre || 'Création du dossier impossible.')
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
  const [showCreate, setShowCreate] = useState(false)
  const [vue, setVue] = useState('liste')

  const params = useMemo(() => ({
    type_dossier: filtreType === TOUS ? undefined : filtreType,
    statut: filtreStatut === TOUS ? undefined : filtreStatut,
  }), [filtreType, filtreStatut])

  const { data: rows, loading, error, refetch } = useResource(
    (p) => coreApi.dossiers.list(p),
    params,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les dossiers.' },
  )

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
        <Segmented options={VUE_OPTIONS} value={vue} onChange={setVue} size="sm" />
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
