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

export default function EquipeSection() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [savingId, setSavingId] = useState(null)

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

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Hiérarchie d'équipe" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
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
                  {users.map((u) => (
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
                            .filter((o) => o.id !== u.id)
                            .map((o) => (
                              <option key={o.id} value={o.id}>{o.username}</option>
                            ))}
                        </select>
                      </td>
                    </tr>
                  ))}
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
