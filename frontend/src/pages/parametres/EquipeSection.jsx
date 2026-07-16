// Onglet « Équipe & rôles » de la page Paramètres (Feature E).
// Éditeur de hiérarchie : un Directeur/Admin assigne à chaque utilisateur son
// superviseur direct. L'« équipe » d'un utilisateur = ceux partageant son
// superviseur (ses pairs) ; pour un responsable, tout son sous-arbre. Cette
// hiérarchie pilote la visibilité des enregistrements (qui voit quoi).
import { useEffect, useState } from 'react'
import api from '../../api/axios'
import { Card, CardContent, Skeleton, EmptyState } from '../../ui'
import { SectionTitle } from './peComponents'

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
  const [view, setView] = useState('table')

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/users/')
      setUsers(data.results ?? data)
      setError(null)
    } catch {
      setError('Impossible de charger l\'équipe.')
    } finally {
      setLoading(false)
    }
  }

  // Chargement initial — le setState a lieu dans le callback async.
  // eslint-disable-next-line react-hooks/set-state-in-effect
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

  const th = 'px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground'

  const orgTree = view === 'tree' ? buildOrgTree(users) : []
  const tabCls = (active) =>
    'rounded-md px-3 py-1 text-xs font-medium transition-colors '
    + (active
      ? 'bg-primary text-primary-foreground'
      : 'bg-muted/60 text-muted-foreground hover:bg-muted')

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <div className="flex items-center justify-between gap-2">
            <SectionTitle label="Hiérarchie d'équipe" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
            <div className="flex shrink-0 gap-1" role="tablist" aria-label="Affichage de la hiérarchie">
              <button type="button" role="tab" aria-selected={view === 'table'} className={tabCls(view === 'table')} onClick={() => setView('table')}>Tableau</button>
              <button type="button" role="tab" aria-selected={view === 'tree'} className={tabCls(view === 'tree')} onClick={() => setView('tree')}>Organigramme</button>
            </div>
          </div>
          <p className="mb-3.5 text-[12.5px] leading-relaxed text-muted-foreground">
            Assignez à chaque personne son <strong>superviseur direct</strong>.
            L'équipe d'un commercial/technicien = ceux qui partagent le même
            superviseur ; un responsable voit en plus tout ce qui lui remonte.
            Cette hiérarchie décide de ce que chacun peut voir (leads, devis,
            chantiers…). Les comptes Directeur/Administrateur voient tout.
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
                Modifiez les liens dans la vue Tableau.
              </p>
              <ul>
                {orgTree.map((r) => (
                  <OrgNode key={r.id} node={r} depth={0} />
                ))}
              </ul>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className={th}>Utilisateur</th>
                    <th className={th}>Rôle</th>
                    <th className={th}>Superviseur direct</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => {
                    // VX235(b) — exclut soi-même ET tout son sous-arbre (un
                    // descendant deviendrait sinon un cycle A→B→C→A).
                    const excluded = descendantIds(users, u.id)
                    return (
                      <tr key={u.id} className="border-b border-border/60 last:border-b-0">
                        <td className="px-4 py-2.5 font-medium text-foreground">{u.username}</td>
                        <td className="px-4 py-2.5 text-muted-foreground">{u.role_nom || '—'}</td>
                        <td className="px-4 py-2.5">
                          <select
                            className={selectCls}
                            aria-label={`Superviseur de ${u.username}`}
                            disabled={savingId === u.id}
                            value={u.supervisor ?? ''}
                            onChange={(e) => setSupervisor(u.id, e.target.value)}
                          >
                            <option value="">— Aucun —</option>
                            {users
                              .filter((o) => o.id !== u.id && !excluded.has(o.id))
                              .map((o) => (
                                <option key={o.id} value={o.id}>{o.username}</option>
                              ))}
                          </select>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <p className="text-[12.5px] leading-relaxed text-muted-foreground">
            La gestion des employés se fait dans
            <strong> Administration → Utilisateurs</strong> (menu latéral), et
            les rôles & permissions dans <strong>Administration → Rôles</strong>.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
