// Onglet « Équipe & rôles » de la page Paramètres : vue « Organisation » de
// TOUTE l'entreprise (Direction, équipes commerciales, équipes terrain, sans
// équipe). Les équipes (Paramètres → Leads / Chantier) définissent le manager
// de leurs membres ; le superviseur direct ne se règle à la main que pour les
// personnes sans équipe et les responsables/chefs d'équipe (qui remontent à la
// direction). Cette hiérarchie pilote la visibilité des enregistrements.
import { useEffect, useState } from 'react'
import api from '../../api/axios'
import { fetchAllPages } from '../../utils/fetchAllPages'
import { Skeleton, EmptyState, CarteContenu, Badge } from '../../ui'
import crmApi from '../../api/crmApi'
import installationsApi from '../../api/installationsApi'
import toutesLesPages from './toutesLesPages'
import { SectionTitle } from './peComponents'

// Comptes « Direction » : rôle Directeur ou Administrateur (role_nom de
// l'API utilisateurs) ou superutilisateur.
const ROLES_DIRECTION = ['directeur', 'administrateur']
const estDirection = (u) => u.is_superuser === true
  || ROLES_DIRECTION.includes(String(u.role_nom || '').trim().toLowerCase())

const selectCls =
  'h-[var(--control-h)] w-full max-w-[220px] rounded-md border border-input '
  + 'bg-card px-[var(--control-px)] text-sm text-foreground shadow-ui-xs '
  + 'transition-colors focus-visible:border-ring focus-visible:outline-none '
  + 'focus-visible:ring-2 focus-visible:ring-ring'

// FG19 — construit l'arbre hiérarchique (org-chart) à partir du champ
// `supervisor` des utilisateurs. Les racines sont les comptes sans superviseur
// (ou dont le superviseur n'est pas dans la liste). Retourne une liste de
// racines, chacune portant ses `children` (récursif), et un compteur
// `subtreeCount` = nombre de personnes que ce nœud « voit » via son sous-arbre
// (lui-même + tout ce qui lui remonte, récursivement). Robuste aux cycles
// éventuels (un nœud n'est visité qu'une fois).
function buildOrgTree(users) {
  const byId = new Map(users.map((u) => [u.id, { ...u, children: [] }]))
  const roots = []
  for (const node of byId.values()) {
    const sup = node.supervisor != null ? byId.get(node.supervisor) : null
    if (sup && sup.id !== node.id) sup.children.push(node)
    else roots.push(node)
  }
  const seen = new Set()
  const countSubtree = (node) => {
    if (seen.has(node.id)) return 0
    seen.add(node.id)
    let n = 1
    for (const c of node.children) n += countSubtree(c)
    node.subtreeCount = n
    return n
  }
  // Compteur calculé sur un `seen` partagé pour neutraliser les cycles.
  for (const r of roots) countSubtree(r)
  // Tri stable des enfants par nom d'utilisateur pour un rendu déterministe.
  const sortRec = (node) => {
    node.children.sort((a, b) => a.username.localeCompare(b.username))
    node.children.forEach(sortRec)
  }
  roots.sort((a, b) => a.username.localeCompare(b.username))
  roots.forEach(sortRec)
  return roots
}

// VX235(b) — défense en profondeur côté UI : ne même pas PROPOSER dans le
// `<select>` un superviseur qui créerait un cycle (le backend le refuse déjà,
// `authentication/serializers.py::validate_supervisor`) — calcule tous les
// descendants de `rootId` (son sous-arbre entier via le champ `supervisor`),
// robuste aux cycles éventuels déjà présents en base (un id n'est jamais
// empilé deux fois).
function descendantIds(users, rootId) {
  const children = new Map()
  for (const u of users) {
    if (u.supervisor != null) {
      if (!children.has(u.supervisor)) children.set(u.supervisor, [])
      children.get(u.supervisor).push(u.id)
    }
  }
  const seen = new Set()
  const stack = [rootId]
  while (stack.length > 0) {
    const id = stack.pop()
    for (const childId of children.get(id) || []) {
      if (!seen.has(childId)) {
        seen.add(childId)
        stack.push(childId)
      }
    }
  }
  return seen
}

// Sélecteur de superviseur direct (hors cycles : VX235(b)).
function SuperviseurSelect({ user, users, savingId, onChange }) {
  const excluded = descendantIds(users, user.id)
  return (
    <select
      className={selectCls}
      aria-label={`Superviseur de ${user.username}`}
      disabled={savingId === user.id}
      value={user.supervisor ?? ''}
      onChange={(e) => onChange(user.id, e.target.value)}
    >
      <option value="">— Aucun —</option>
      {users
        .filter((o) => o.id !== user.id && !excluded.has(o.id)
          && (o.is_active !== false || o.id === user.supervisor))
        .map((o) => (
          <option key={o.id} value={o.id}>{o.username}</option>
        ))}
    </select>
  )
}

// Bloc d'une équipe : responsable/chef (superviseur éditable) + membres
// (manager en lecture seule, défini par l'équipe).
function BlocEquipe({ equipe, chefId, chefLabel, byId, users, savingId, onSupervisor, badge }) {
  const chef = chefId != null ? byId.get(chefId) : null
  const membres = (equipe.membres ?? []).map((id) => byId.get(id)).filter(Boolean)
  return (
    <div className="rounded-lg border border-border p-3" data-testid={`org-equipe-${equipe.id}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-semibold text-foreground">{equipe.nom}</span>
        <Badge tone="neutral">{membres.length} membre(s)</Badge>
        {badge && <Badge tone="info">Reçoit les nouveaux leads</Badge>}
      </div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-xs text-muted-foreground">{chefLabel} :</span>
        {chef ? (
          <>
            <span className="font-medium text-foreground">{chef.username}</span>
            <span className="text-xs text-muted-foreground">{chef.role_nom || '—'}</span>
            <SuperviseurSelect user={chef} users={users} savingId={savingId} onChange={onSupervisor} />
          </>
        ) : (
          <span className="text-xs text-muted-foreground">non défini</span>
        )}
      </div>
      {membres.length === 0 ? (
        <p className="text-xs text-muted-foreground">Aucun membre.</p>
      ) : (
        <ul className="divide-y divide-border/60 text-sm">
          {membres.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center gap-x-2 py-1.5">
              <span className="font-medium text-foreground">{m.username}</span>
              <span className="text-xs text-muted-foreground">{m.role_nom || '—'}</span>
              <span className="ml-auto text-[11px] text-muted-foreground">
                manager : {chef ? chef.username : '—'} · défini par l'équipe {equipe.nom}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function OrgNode({ node, depth }) {
  return (
    <li>
      <div
        className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/40"
        style={{ marginLeft: depth * 18 }}
      >
        {depth > 0 && (
          <span aria-hidden className="text-muted-foreground/60">└</span>
        )}
        <span className="font-medium text-foreground">{node.username}</span>
        <span className="text-xs text-muted-foreground">
          {node.role_nom || '—'}
        </span>
        {node.children.length > 0 && (
          <span className="ml-auto text-[11px] text-muted-foreground" title="Personnes vues via son sous-arbre (lui inclus)">
            voit {node.subtreeCount}
          </span>
        )}
      </div>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((c) => (
            <OrgNode key={c.id} node={c} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  )
}

export default function EquipeSection() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [savingId, setSavingId] = useState(null)
  const [view, setView] = useState('org')
  const [equipesCom, setEquipesCom] = useState([])
  const [equipesTerrain, setEquipesTerrain] = useState([])

  const load = async () => {
    setLoading(true)
    try {
      // APAR40 — TOUTES les pages (plus seulement la première).
      const res = await fetchAllPages(
        (page) => api.get('/users/', { params: { page, page_size: 200 } })
          .then((r) => r?.data))
      setUsers(Array.isArray(res) ? res : (res?.results ?? []))
      // Équipes : un échec n'empêche pas d'afficher les utilisateurs.
      const [com, terrain] = await Promise.all([
        toutesLesPages((params) => crmApi.getEquipes(params)).catch(() => []),
        toutesLesPages((params) => installationsApi.getEquipesTerrain(params)).catch(() => []),
      ])
      setEquipesCom(com)
      setEquipesTerrain(terrain)
      setError(null)
    } catch {
      setError('Impossible de charger l\'équipe.')
    } finally {
      setLoading(false)
    }
  }

  // Chargement initial — le setState a lieu dans le callback async.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial : setState dans le callback async, jamais synchrone (D-ENF22)
  useEffect(() => { load() }, [])

  const setSupervisor = async (userId, value) => {
    setSavingId(userId)
    try {
      const { data } = await api.patch(`/users/${userId}/`, {
        supervisor: value === '' ? null : Number(value),
      })
      setUsers((list) => list.map((u) => (u.id === userId ? data : u)))
      setError(null)
    } catch (err) {
      setError(
        err.response?.data?.supervisor?.[0]
        || err.response?.data?.detail
        || 'Impossible d\'enregistrer le superviseur.',
      )
    } finally {
      setSavingId(null)
    }
  }

  const actifs = users.filter((u) => u.is_active !== false)
  const byId = new Map(users.map((u) => [u.id, u]))
  const comActives = equipesCom.filter((e) => e.actif !== false)
  const terrainActives = equipesTerrain.filter((e) => e.actif !== false)
  const direction = actifs.filter(estDirection)
  // Personnes rattachées à une équipe active (membre, responsable ou chef).
  const enEquipe = new Set()
  for (const e of comActives) {
    (e.membres ?? []).forEach((id) => enEquipe.add(id))
    if (e.responsable != null) enEquipe.add(e.responsable)
  }
  for (const e of terrainActives) {
    (e.membres ?? []).forEach((id) => enEquipe.add(id))
    if (e.chef != null) enEquipe.add(e.chef)
  }
  const sansEquipe = actifs.filter((u) => !estDirection(u) && !enEquipe.has(u.id))

  const orgTree = view === 'tree' ? buildOrgTree(users) : []
  const tabCls = (active) =>
    'rounded-md px-3 py-1 text-xs font-medium transition-colors '
    + (active
      ? 'bg-primary text-primary-foreground'
      : 'bg-muted/60 text-muted-foreground hover:bg-muted')

  return (
    <div className="flex flex-col gap-4">
      <CarteContenu contenu="pt-4 sm:pt-5">
        <div className="flex items-center justify-between gap-2">
          <SectionTitle label="Organisation" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
          <div className="flex shrink-0 gap-1" role="tablist" aria-label="Affichage de l'organisation">
            <button type="button" role="tab" aria-selected={view === 'org'} className={tabCls(view === 'org')} onClick={() => setView('org')}>Organisation</button>
            <button type="button" role="tab" aria-selected={view === 'tree'} className={tabCls(view === 'tree')} onClick={() => setView('tree')}>Organigramme</button>
          </div>
        </div>
        <p className="mb-3.5 text-[12.5px] leading-relaxed text-muted-foreground">
          Vue d'ensemble de <strong>toute l'entreprise</strong> : Direction,
          équipes commerciales, équipes terrain et personnes sans équipe. Le
          manager d'un membre est défini par son équipe (Paramètres → Leads
          pour les commerciaux, Chantier pour le terrain) ; il ne se règle à
          la main que pour les personnes sans équipe et les responsables
          d'équipe. Les comptes Directeur/Administrateur voient tout.
        </p>

        {error && (
          <p role="alert" className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">
            {error}
          </p>
        )}

        {loading ? (
          <div className="space-y-2.5">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : users.length === 0 ? (
          <EmptyState title="Aucun utilisateur" description="Ajoutez des employés dans Administration → Utilisateurs." />
        ) : view === 'tree' ? (
          <div className="text-sm">
            <p className="mb-2 text-[12px] text-muted-foreground">
              Vue lecture seule pour vérifier d'un coup d'œil la portée de
              visibilité (« voit N » = personnes du sous-arbre, lui inclus).
              Modifiez les liens dans la vue Organisation.
            </p>
            <ul>
              {orgTree.map((r) => (
                <OrgNode key={r.id} node={r} depth={0} />
              ))}
            </ul>
          </div>
        ) : (
          <div className="flex flex-col gap-5 text-sm">
            <section aria-label="Direction">
              <h3 className="mb-1.5 text-[13px] font-semibold text-foreground">Direction</h3>
              {direction.length === 0 ? (
                <p className="text-xs text-muted-foreground">Aucun compte Directeur/Administrateur actif.</p>
              ) : (
                <ul className="divide-y divide-border/60 rounded-lg border border-border px-3">
                  {direction.map((u) => (
                    <li key={u.id} className="flex flex-wrap items-center gap-x-2 py-1.5">
                      <span className="font-medium text-foreground">{u.username}</span>
                      <span className="text-xs text-muted-foreground">{u.role_nom || '—'}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section aria-label="Équipes commerciales" className="flex flex-col gap-2">
              <h3 className="text-[13px] font-semibold text-foreground">Équipes commerciales</h3>
              {comActives.length === 0 && (
                <p className="text-xs text-muted-foreground">Aucune équipe commerciale active.</p>
              )}
              {comActives.map((e) => (
                <BlocEquipe key={e.id} equipe={e} chefId={e.responsable} chefLabel="Responsable"
                            byId={byId} users={users} savingId={savingId}
                            onSupervisor={setSupervisor} badge={!!e.recoit_leads} />
              ))}
            </section>

            <section aria-label="Équipes terrain" className="flex flex-col gap-2">
              <h3 className="text-[13px] font-semibold text-foreground">Équipes terrain</h3>
              {terrainActives.length === 0 && (
                <p className="text-xs text-muted-foreground">Aucune équipe terrain active.</p>
              )}
              {terrainActives.map((e) => (
                <BlocEquipe key={e.id} equipe={e} chefId={e.chef} chefLabel="Chef d'équipe"
                            byId={byId} users={users} savingId={savingId}
                            onSupervisor={setSupervisor} badge={false} />
              ))}
            </section>

            <section aria-label="Sans équipe">
              <h3 className="mb-1.5 text-[13px] font-semibold text-foreground">Sans équipe</h3>
              {sansEquipe.length === 0 ? (
                <p className="text-xs text-muted-foreground">Tout le monde est rattaché à une équipe ou à la direction.</p>
              ) : (
                <ul className="divide-y divide-border/60 rounded-lg border border-border px-3">
                  {sansEquipe.map((u) => (
                    <li key={u.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 py-1.5">
                      <span className="font-medium text-foreground">{u.username}</span>
                      <span className="text-xs text-muted-foreground">{u.role_nom || '—'}</span>
                      <span className="ml-auto">
                        <SuperviseurSelect user={u} users={users} savingId={savingId} onChange={setSupervisor} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </CarteContenu>

      <CarteContenu contenu="pt-4 sm:pt-5">
        <p className="text-[12.5px] leading-relaxed text-muted-foreground">
          La gestion des employés se fait dans
          <strong> Administration → Utilisateurs</strong> (menu latéral), et
          les rôles & permissions dans <strong>Administration → Rôles</strong>.
        </p>
      </CarteContenu>
    </div>
  )
}
