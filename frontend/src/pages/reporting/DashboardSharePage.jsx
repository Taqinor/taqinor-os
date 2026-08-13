import { useEffect, useMemo, useState } from 'react'
import { Copy, Link2, Plus, Ban, Users } from 'lucide-react'
import coreApi from '../../api/coreApi'
import {
  Badge, Button, DataTable, EmptyState, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem, Spinner,
} from '../../ui'
import { toast } from '../../ui/confirm'

/* ============================================================================
   XPLT10 — Partage de dashboard : lien public tokenisé (créer/révoquer).
   ----------------------------------------------------------------------------
   `core.PartageDashboard` — un lien PUBLIC lecture seule par dashboard, sans
   login (résolu depuis le seul jeton, `GET /core/dashboards-partages/public/
   <token>/`). Révoquer = kill-switch (`actif=False`), jamais de suppression
   physique tant que non explicitement demandée. Le mode TV (rotation plein
   écran) vit dans `DashboardsTvPage` (`/dashboards-tv`).

   PACT120 — DEUXIÈME MÉCANISME, sur le même écran : le partage INTERNE fin
   (`core.DashboardPartageInterne`) donne un accès NOMMÉ — un utilisateur ou un
   rôle — en lecture ou en édition, sans rendre le dashboard visible à toute la
   société (`Dashboard.partage`, inchangé) ni exposer un lien anonyme. Les deux
   cohabitent et ne se remplacent pas : l'un ouvre une URL publique sans login,
   l'autre nomme des destinataires internes. Le bloc ci-dessous est le second,
   qui n'avait aucune interface alors que la table, la vue et la règle de
   visibilité (`user_can_view_dashboard`) existaient déjà côté serveur.
   ========================================================================== */

function publicUrl(token) {
  return `${window.location.origin}/dashboards-partages/public/${token}`
}

// Rôles legacy servis par le serveur (`CustomUser.ROLE_CHOICES`) — le champ
// `role` du partage interne est ce texte-là, jamais une FK.
const ROLES_INTERNES = [
  ['admin', 'Administrateur'],
  ['responsable', 'Utilisateur Responsable'],
  ['normal', 'Utilisateur Normal'],
]
const LIBELLE_ROLE = Object.fromEntries(ROLES_INTERNES)

const NIVEAUX = [['lecture', 'Lecture'], ['edition', 'Édition']]
const LIBELLE_NIVEAU = Object.fromEntries(NIVEAUX)

function nomUtilisateur(membre) {
  const complet = `${membre.first_name || ''} ${membre.last_name || ''}`.trim()
  return complet || membre.username || membre.email || `#${membre.id}`
}

const PARTAGE_INTERNE_VIDE = {
  dashboard: '', cible: 'utilisateur', utilisateur: '', role: '',
  niveau: 'lecture',
}

export default function DashboardSharePage() {
  const [dashboards, setDashboards] = useState([])
  const [partages, setPartages] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedDashboard, setSelectedDashboard] = useState('')
  const [creating, setCreating] = useState(false)
  // PACT120 — second mécanisme (partage interne nommé), état séparé.
  const [internes, setInternes] = useState([])
  const [membres, setMembres] = useState([])
  const [formInterne, setFormInterne] = useState(PARTAGE_INTERNE_VIDE)
  const [partageInterneEnCours, setPartageInterneEnCours] = useState(false)

  const dashboardTitle = useMemo(() => {
    const map = new Map(dashboards.map((d) => [d.id, d]))
    return (id) => map.get(id)?.titre || `Dashboard #${id}`
  }, [dashboards])

  const nomMembre = useMemo(() => {
    const map = new Map(membres.map((m) => [m.id, nomUtilisateur(m)]))
    return (id) => map.get(id) || `#${id}`
  }, [membres])

  const reload = () => coreApi.dashboardsPartages.list()
    .then((r) => setPartages(r.data?.results ?? r.data ?? []))
    .catch(() => setPartages([]))

  useEffect(() => {
    let active = true
    Promise.all([coreApi.dashboards.list(), coreApi.dashboardsPartages.list()])
      .then(([d, p]) => {
        if (!active) return
        setDashboards(d.data?.results ?? d.data ?? [])
        setPartages(p.data?.results ?? p.data ?? [])
      })
      .catch(() => { if (active) { setDashboards([]); setPartages([]) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const creerLien = () => {
    if (!selectedDashboard) return
    setCreating(true)
    coreApi.dashboardsPartages.create(selectedDashboard)
      .then(() => {
        toast.success('Lien de partage créé.')
        setSelectedDashboard('')
        reload()
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Création du lien impossible.'))
      .finally(() => setCreating(false))
  }

  const revoquer = (partage) => {
    coreApi.dashboardsPartages.revoke(partage.id)
      .then(() => { toast.success('Lien révoqué.'); reload() })
      .catch(() => toast.error('Révocation impossible.'))
  }

  const reloadInternes = () => coreApi.dashboardsPartagesInternes.list()
    .then((r) => setInternes(r.data?.results ?? r.data ?? []))
    .catch(() => setInternes([]))

  useEffect(() => {
    let active = true
    Promise.all([
      coreApi.dashboardsPartagesInternes.list(),
      coreApi.utilisateurs.list(),
    ])
      .then(([i, u]) => {
        if (!active) return
        setInternes(i.data?.results ?? i.data ?? [])
        setMembres(u.data?.results ?? u.data ?? [])
      })
      .catch(() => { if (active) { setInternes([]); setMembres([]) } })
    return () => { active = false }
  }, [])

  const partagerEnInterne = (event) => {
    event.preventDefault()
    const { dashboard, cible, utilisateur, role, niveau } = formInterne
    if (!dashboard || (cible === 'utilisateur' ? !utilisateur : !role)) return
    setPartageInterneEnCours(true)
    // Une seule cible par partage : le serveur contraint l'unicité
    // (dashboard, utilisateur) et (dashboard, rôle) séparément.
    const payload = cible === 'utilisateur'
      ? { dashboard, utilisateur, niveau }
      : { dashboard, role, niveau }
    coreApi.dashboardsPartagesInternes.create(payload)
      .then(() => {
        toast.success('Partage interne ajouté.')
        setFormInterne({ ...PARTAGE_INTERNE_VIDE, dashboard })
        reloadInternes()
      })
      .catch((err) => toast.error(
        err?.response?.data?.detail || 'Partage interne impossible.'))
      .finally(() => setPartageInterneEnCours(false))
  }

  const retirerPartageInterne = (partage) => {
    coreApi.dashboardsPartagesInternes.remove(partage.id)
      .then(() => { toast.success('Partage interne retiré.'); reloadInternes() })
      .catch(() => toast.error('Retrait impossible.'))
  }

  const copier = async (token) => {
    try {
      await navigator.clipboard.writeText(publicUrl(token))
      toast.success('Lien copié.')
    } catch {
      toast.error('Copie impossible — copiez le lien manuellement.')
    }
  }

  const columns = useMemo(() => [
    {
      id: 'dashboard', header: 'Dashboard',
      accessor: (r) => dashboardTitle(r.dashboard),
    },
    {
      id: 'lien', header: 'Lien public',
      accessor: (r) => publicUrl(r.token),
      cell: (v, r) => (
        <div className="flex items-center gap-2">
          <code className="truncate text-xs text-muted-foreground">{publicUrl(r.token)}</code>
          <Button size="sm" variant="ghost" onClick={() => copier(r.token)}>
            <Copy /> Copier
          </Button>
        </div>
      ),
    },
    {
      id: 'statut', header: 'Statut', width: 120,
      accessor: (r) => (r.actif ? 'Actif' : 'Révoqué'),
      cell: (v, r) => <Badge tone={r.actif ? 'success' : 'neutral'}>{r.actif ? 'Actif' : 'Révoqué'}</Badge>,
    },
    {
      id: 'actions', header: '', width: 120, align: 'right',
      accessor: () => '',
      cell: (v, r) => (
        r.actif ? (
          <Button size="sm" variant="ghost" onClick={() => revoquer(r)} data-testid={`revoke-partage-${r.id}`}>
            <Ban /> Révoquer
          </Button>
        ) : null
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- callbacks recréés par rendu
  ], [dashboardTitle])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Partage de tableaux de bord</h1>
        <div className="page-subtitle">
          Liens publics tokenisés, lecture seule, sans login — révocables à tout moment.
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted-foreground">Dashboard</span>
          <Select value={selectedDashboard} onValueChange={setSelectedDashboard}>
            <SelectTrigger className="w-64" aria-label="Choisir un dashboard"><SelectValue placeholder="Choisir un dashboard…" /></SelectTrigger>
            <SelectContent>
              {dashboards.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.titre}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={creerLien} disabled={!selectedDashboard || creating} loading={creating}>
          <Plus /> Créer un lien de partage
        </Button>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : partages.length === 0 ? (
        <EmptyState
          icon={Link2}
          title="Aucun lien de partage"
          description="Créez un lien public pour partager un dashboard en lecture seule."
          className="my-6"
        />
      ) : (
        <DataTable
          data={partages}
          columns={columns}
          getRowId={(row) => row.id}
          searchable={false}
          pageSize={25}
          aria-label="Liens de partage de tableaux de bord"
        />
      )}

      <section className="mt-10" data-testid="partage-interne">
        <h2 className="text-lg font-semibold">Partage interne</h2>
        <p className="mb-4 text-sm text-muted-foreground">
          Donner l’accès à des personnes ou à des rôles précis, en lecture ou en
          édition — sans lien public et sans rendre le dashboard visible à toute
          la société.
        </p>

        <form
          onSubmit={partagerEnInterne}
          className="mb-4 flex flex-wrap items-end gap-3"
        >
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="interne-dashboard">
              Dashboard à partager
            </label>
            <select
              id="interne-dashboard"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={formInterne.dashboard}
              onChange={(e) => setFormInterne({ ...formInterne, dashboard: e.target.value })}
            >
              <option value="">Choisir un dashboard…</option>
              {dashboards.map((d) => (
                <option key={d.id} value={String(d.id)}>{d.titre}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="interne-cible">
              Partager à
            </label>
            <select
              id="interne-cible"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={formInterne.cible}
              onChange={(e) => setFormInterne({
                ...formInterne, cible: e.target.value, utilisateur: '', role: '',
              })}
            >
              <option value="utilisateur">Un utilisateur</option>
              <option value="role">Un rôle</option>
            </select>
          </div>

          {formInterne.cible === 'utilisateur' ? (
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="interne-utilisateur">
                Utilisateur
              </label>
              <select
                id="interne-utilisateur"
                className="h-9 rounded-md border bg-background px-2 text-sm"
                value={formInterne.utilisateur}
                onChange={(e) => setFormInterne({ ...formInterne, utilisateur: e.target.value })}
              >
                <option value="">Choisir un utilisateur…</option>
                {membres.map((m) => (
                  <option key={m.id} value={String(m.id)}>{nomUtilisateur(m)}</option>
                ))}
              </select>
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="interne-role">
                Rôle
              </label>
              <select
                id="interne-role"
                className="h-9 rounded-md border bg-background px-2 text-sm"
                value={formInterne.role}
                onChange={(e) => setFormInterne({ ...formInterne, role: e.target.value })}
              >
                <option value="">Choisir un rôle…</option>
                {ROLES_INTERNES.map(([valeur, libelle]) => (
                  <option key={valeur} value={valeur}>{libelle}</option>
                ))}
              </select>
            </div>
          )}

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="interne-niveau">
              Niveau
            </label>
            <select
              id="interne-niveau"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={formInterne.niveau}
              onChange={(e) => setFormInterne({ ...formInterne, niveau: e.target.value })}
            >
              {NIVEAUX.map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>{libelle}</option>
              ))}
            </select>
          </div>

          <Button type="submit" disabled={partageInterneEnCours} loading={partageInterneEnCours}>
            <Plus /> Partager en interne
          </Button>
        </form>

        {internes.length === 0 ? (
          <EmptyState
            icon={Users}
            title="Aucun partage interne"
            description="Personne n’a encore reçu d’accès nommé à un dashboard."
            className="my-6"
          />
        ) : (
          <table className="w-full text-sm" aria-label="Partages internes de tableaux de bord">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-2">Dashboard</th>
                <th className="py-2">Destinataire</th>
                <th className="py-2">Niveau</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {internes.map((p) => (
                <tr key={p.id} className="border-t" data-testid={`partage-interne-${p.id}`}>
                  <td className="py-2">{dashboardTitle(p.dashboard)}</td>
                  <td className="py-2">
                    {p.utilisateur
                      ? nomMembre(p.utilisateur)
                      : `Rôle : ${LIBELLE_ROLE[p.role] || p.role}`}
                  </td>
                  <td className="py-2">
                    <Badge tone={p.niveau === 'edition' ? 'warning' : 'neutral'}>
                      {LIBELLE_NIVEAU[p.niveau] || p.niveau}
                    </Badge>
                  </td>
                  <td className="py-2 text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => retirerPartageInterne(p)}
                      data-testid={`retirer-partage-interne-${p.id}`}
                    >
                      <Ban /> Retirer
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
