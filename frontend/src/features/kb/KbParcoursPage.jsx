import { useEffect, useMemo, useState } from 'react'
import { GraduationCap, Plus, UserPlus } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Button, Badge, EmptyState, Spinner, Input, Label, toast } from '../../ui'
import kbApi from '../../api/kbApi'
import messagesApi from '../../api/messagesApi'
import FilterSelect from './FilterSelect'

/* ============================================================================
   XKB22 — « Parcours » d'intégration : séquences ordonnées d'articles
   assignées nominativement (ex. onboarding poseur/commercial). Écran dédié
   sous /kb/parcours (module.config), gaté responsable/admin comme le reste
   de la gestion KB — la LECTURE d'un parcours assigné reste un simple suivi
   de lecture d'article (déjà géré par KbPage/ArticleDetail).
   ========================================================================== */

function ProgressionRow({ assignation }) {
  const [progression, setProgression] = useState(null)

  useEffect(() => {
    kbApi.assignationProgression(assignation.id)
      .then((res) => setProgression(res.data))
      .catch(() => setProgression(null))
  }, [assignation.id])

  return (
    <li className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
      <span className="flex items-center gap-2">
        <UserPlus className="size-4 text-muted-foreground" aria-hidden="true" />
        {assignation.utilisateur_nom || `Utilisateur #${assignation.utilisateur}`}
      </span>
      {progression ? (
        <Badge tone={progression.complet ? 'success' : 'neutral'}>
          {progression.nombre_lus}/{progression.nombre_total}
          {progression.complet ? ' · Terminé' : ''}
        </Badge>
      ) : (
        <Spinner className="size-4" />
      )}
    </li>
  )
}

export default function KbParcoursPage() {
  const [parcoursList, setParcoursList] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [membres, setMembres] = useState([])
  const [assignations, setAssignations] = useState([])
  const [users, setUsers] = useState([])
  const [nom, setNom] = useState('')
  const [assignUser, setAssignUser] = useState('')

  const load = () => {
    setLoading(true)
    kbApi.listParcours()
      .then((res) => setParcoursList(
        Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => toast.error('Impossible de charger les parcours.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
    messagesApi.listCompanyMembers()
      .then((res) => setUsers(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setUsers([]))
  }, [])

  const openParcours = (p) => {
    setSelected(p)
    kbApi.parcoursArticles(p.id)
      .then((res) => setMembres(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setMembres([]))
    kbApi.listAssignations({ parcours: p.id })
      .then((res) => setAssignations(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setAssignations([]))
  }

  const creerParcours = async () => {
    if (!nom.trim()) { toast.error('Le nom est requis.'); return }
    try {
      await kbApi.createParcours({ nom })
      toast.success('Parcours créé.')
      setNom('')
      load()
    } catch { toast.error('Création impossible.') }
  }

  const assigner = async () => {
    if (!assignUser || !selected) return
    try {
      await kbApi.createAssignation({ parcours: selected.id, utilisateur: Number(assignUser) })
      toast.success('Parcours assigné.')
      setAssignUser('')
      const res = await kbApi.listAssignations({ parcours: selected.id })
      setAssignations(Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
    } catch { toast.error('Assignation impossible (déjà assigné ?).') }
  }

  const userOptions = useMemo(() => [
    { value: '', label: 'Choisir une personne…' },
    ...users.map((u) => ({
      value: String(u.id),
      label: u.get_full_name || u.full_name || u.username || `#${u.id}`,
    })),
  ], [users])

  const columns = useMemo(() => [
    { id: 'nom', header: 'Nom', accessor: (p) => p.nom },
    {
      id: 'metier', header: 'Métier / rôle', accessor: (p) => p.role_cible_display || p.metier || '',
      cell: (v) => v || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'actif', header: 'Actif', accessor: (p) => p.actif,
      cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Actif' : 'Inactif'}</Badge>,
    },
  ], [])

  if (selected) {
    return (
      <div className="page flex flex-col gap-4">
        <button
          type="button"
          onClick={() => setSelected(null)}
          className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          ← Retour aux parcours
        </button>
        <h1 className="font-display text-xl font-semibold tracking-tight">{selected.nom}</h1>

        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium">Articles du parcours ({membres.length})</h2>
          {membres.length ? (
            <ol className="flex flex-col gap-1.5">
              {membres.map((m) => (
                <li key={m.id} className="rounded-lg border border-border px-3 py-2 text-sm">
                  {m.ordre + 1}. {m.article_titre}
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState title="Aucun article" description="Ajoutez des articles à ce parcours." />
          )}
        </section>

        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium">Assigner à une personne</h2>
          <div className="flex flex-wrap items-end gap-2">
            <FilterSelect value={assignUser} onChange={setAssignUser} options={userOptions} aria-label="Personne à assigner" />
            <Button type="button" variant="outline" onClick={assigner}>
              <UserPlus /> Assigner
            </Button>
          </div>
          {assignations.length ? (
            <ul className="flex flex-col gap-1.5">
              {assignations.map((a) => <ProgressionRow key={a.id} assignation={a} />)}
            </ul>
          ) : (
            <EmptyState title="Aucune assignation" description="Personne n’est encore assigné à ce parcours." />
          )}
        </section>
      </div>
    )
  }

  return (
    <div className="page">
      <ListShell
        title="Parcours de lecture"
        subtitle={
          <span className="inline-flex items-center gap-1.5">
            <GraduationCap className="size-4" aria-hidden="true" />
            Séquences d’onboarding assignées nominativement
          </span>
        }
        actions={(
          <div className="flex items-center gap-2">
            <Label htmlFor="kb-parcours-nom" className="sr-only">Nom du parcours</Label>
            <Input
              id="kb-parcours-nom" placeholder="Nom du nouveau parcours"
              value={nom} onChange={(e) => setNom(e.target.value)}
            />
            <Button onClick={creerParcours}><Plus /> Créer</Button>
          </div>
        )}
        columns={columns}
        rows={parcoursList}
        loading={loading}
        onRowClick={openParcours}
        emptyTitle="Aucun parcours"
        emptyDescription="Créez un premier parcours d’intégration."
      />
    </div>
  )
}
