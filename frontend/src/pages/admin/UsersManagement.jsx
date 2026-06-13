import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import api from '../../api/axios'
import rolesApi from '../../api/rolesApi'

export default function UsersManagement() {
  const currentUsername = useSelector(s => s.auth.user?.username)
  const [users, setUsers] = useState([])
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ username: '', email: '', password: '', role: '' })
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [usersRes, rolesRes] = await Promise.all([
        api.get('/users/'),
        rolesApi.getRoles(),
      ])
      setUsers(usersRes.data.results ?? usersRes.data)
      const roleList = rolesRes.data.results ?? rolesRes.data
      setRoles(roleList)
      // Default form role to first role in list
      if (roleList.length > 0 && !form.role) {
        setForm(f => ({ ...f, role: roleList.find(r => r.nom === 'Utilisateur')?.id || roleList[0].id }))
      }
    } catch {
      setError('Impossible de charger les données.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, []) // eslint-disable-line

  const handleCreate = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api.post('/users/', form)
      setForm({ username: '', email: '', password: '', role: roles.find(r => r.nom === 'Utilisateur')?.id || roles[0]?.id || '' })
      setShowForm(false)
      await load()
    } catch (err) {
      alert('Erreur : ' + (err.response?.data?.username?.[0] ?? err.message))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Supprimer cet utilisateur ?')) return
    await api.delete(`/users/${id}/`)
    await load()
  }

  // Un utilisateur est "admin" si superuser, role_legacy admin, ou s'il dispose
  // de la permission roles_gerer (selon les champs déjà fournis par /users/).
  const isAdminUser = (u) => {
    if (u.is_superuser === true) return true
    if (u.role_legacy === 'admin') return true
    const perms = u.permissions || u.role?.permissions || []
    if (Array.isArray(perms) && perms.includes('roles_gerer')) return true
    return false
  }

  const adminCount = users.filter(isAdminUser).length

  const roleColor = (nom) => {
    if (!nom) return { bg: '#f1f5f9', text: '#475569' }
    const n = nom.toLowerCase()
    if (n.includes('admin')) return { bg: '#fef3c7', text: '#92400e' }
    if (n.includes('respon')) return { bg: '#ede9fe', text: '#5b21b6' }
    return { bg: '#f0fdf4', text: '#166534' }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600 }}>Gestion des utilisateurs</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          style={{ background: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', padding: '0.5rem 1rem', cursor: 'pointer', fontWeight: 500 }}
        >
          {showForm ? 'Annuler' : '+ Nouvel utilisateur'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} style={{ background: 'white', padding: '1.25rem', borderRadius: '8px', marginBottom: '1.5rem', border: '1px solid #e2e8f0', display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <label style={{ fontSize: '0.8rem', color: '#64748b' }}>Nom d'utilisateur</label>
            <input required value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
              style={{ border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.45rem 0.75rem', fontSize: '0.875rem' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <label style={{ fontSize: '0.8rem', color: '#64748b' }}>Email</label>
            <input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
              style={{ border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.45rem 0.75rem', fontSize: '0.875rem' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <label style={{ fontSize: '0.8rem', color: '#64748b' }}>Mot de passe</label>
            <input required type="password" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
              style={{ border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.45rem 0.75rem', fontSize: '0.875rem' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <label style={{ fontSize: '0.8rem', color: '#64748b' }}>Rôle</label>
            <select value={form.role} onChange={e => setForm(f => ({ ...f, role: Number(e.target.value) }))}
              style={{ border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.45rem 0.75rem', fontSize: '0.875rem' }}>
              {roles.map(r => (
                <option key={r.id} value={r.id}>{r.nom}</option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={saving}
            style={{ background: '#10b981', color: 'white', border: 'none', borderRadius: '6px', padding: '0.5rem 1rem', cursor: 'pointer', fontWeight: 500 }}>
            {saving ? 'Création...' : 'Créer'}
          </button>
        </form>
      )}

      {loading && <p style={{ color: '#64748b' }}>Chargement...</p>}
      {error && <p style={{ color: '#ef4444' }}>{error}</p>}

      {!loading && !error && (
        <div style={{ background: 'white', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>Utilisateur</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>Email</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>Rôle</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>Actif</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'right', fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u, i) => {
                const c = roleColor(u.role_nom)
                const isLastAdmin = isAdminUser(u) && adminCount <= 1
                const deleteLocked = u.is_protected || isLastAdmin
                const lockTooltip = u.is_protected
                  ? 'Compte propriétaire protégé'
                  : 'Au moins un administrateur doit rester'
                return (
                  <tr key={u.id} style={{ borderBottom: i < users.length - 1 ? '1px solid #f1f5f9' : 'none' }}>
                    <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', fontWeight: 500 }}>
                      {u.username}
                      {u.is_protected && (
                        <span style={{ marginLeft: '0.5rem', background: '#fef3c7', color: '#92400e', padding: '0.15rem 0.5rem', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 600 }}>
                          Propriétaire protégé
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', color: '#64748b' }}>{u.email || '—'}</td>
                    <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem' }}>
                      <span style={{ background: c.bg, color: c.text, padding: '0.2rem 0.6rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 500 }}>
                        {u.role_nom || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem' }}>{u.is_active ? '✅' : '❌'}</td>
                    <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                      {u.username !== currentUsername && (
                        deleteLocked ? (
                          <button disabled title={lockTooltip}
                            style={{ background: 'transparent', border: '1px solid #e2e8f0', color: '#cbd5e1', borderRadius: '6px', padding: '0.3rem 0.7rem', cursor: 'not-allowed', fontSize: '0.8rem' }}>
                            Supprimer
                          </button>
                        ) : (
                          <button onClick={() => handleDelete(u.id)}
                            style={{ background: 'transparent', border: '1px solid #fca5a5', color: '#ef4444', borderRadius: '6px', padding: '0.3rem 0.7rem', cursor: 'pointer', fontSize: '0.8rem' }}>
                            Supprimer
                          </button>
                        )
                      )}
                    </td>
                  </tr>
                )
              })}
              {users.length === 0 && (
                <tr><td colSpan={5} style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>Aucun utilisateur</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
