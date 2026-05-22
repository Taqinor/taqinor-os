import { useEffect, useState } from 'react'
import rolesApi from '../../api/rolesApi'

const PERMISSION_GROUPS = [
  {
    label: 'Stock',
    codes: [
      { code: 'stock_voir',      label: 'Voir' },
      { code: 'stock_creer',     label: 'Créer' },
      { code: 'stock_modifier',  label: 'Modifier' },
      { code: 'stock_supprimer', label: 'Supprimer' },
      { code: 'stock_mouvement', label: 'Mouvements' },
    ],
  },
  {
    label: 'CRM',
    codes: [
      { code: 'crm_voir',      label: 'Voir' },
      { code: 'crm_creer',     label: 'Créer' },
      { code: 'crm_modifier',  label: 'Modifier' },
      { code: 'crm_supprimer', label: 'Supprimer' },
    ],
  },
  {
    label: 'Ventes',
    codes: [
      { code: 'ventes_voir',      label: 'Voir' },
      { code: 'ventes_creer',     label: 'Créer' },
      { code: 'ventes_modifier',  label: 'Modifier' },
      { code: 'ventes_supprimer', label: 'Supprimer' },
      { code: 'ventes_valider',   label: 'Valider' },
      { code: 'ventes_pdf',       label: 'Générer PDF' },
    ],
  },
  {
    label: 'Paramètres',
    codes: [
      { code: 'parametres_voir',     label: 'Voir' },
      { code: 'parametres_modifier', label: 'Modifier' },
    ],
  },
  {
    label: 'Utilisateurs',
    codes: [
      { code: 'users_voir',  label: 'Voir' },
      { code: 'users_gerer', label: 'Gérer' },
    ],
  },
  {
    label: 'Rôles',
    codes: [
      { code: 'roles_gerer', label: 'Gérer les rôles' },
    ],
  },
  {
    label: 'Reporting',
    codes: [
      { code: 'reporting_voir', label: 'Voir' },
    ],
  },
]

const EMPTY_FORM = { nom: '', permissions: [] }

const S = {
  card: { background: 'white', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden' },
  th: { padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.8rem', color: '#64748b', fontWeight: 600 },
  td: { padding: '0.75rem 1rem', fontSize: '0.875rem' },
  badge: (sys) => ({
    display: 'inline-block',
    background: sys ? '#eff6ff' : '#f0fdf4',
    color: sys ? '#1d4ed8' : '#166534',
    border: `1px solid ${sys ? '#bfdbfe' : '#bbf7d0'}`,
    borderRadius: '999px', padding: '0.15rem 0.55rem', fontSize: '0.72rem', fontWeight: 600,
  }),
  btnPrimary: { background: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', padding: '0.5rem 1rem', cursor: 'pointer', fontWeight: 500, fontSize: '0.875rem' },
  btnDanger: { background: 'transparent', border: '1px solid #fca5a5', color: '#ef4444', borderRadius: '6px', padding: '0.3rem 0.7rem', cursor: 'pointer', fontSize: '0.8rem' },
  btnGhost: { background: 'transparent', border: '1px solid #e2e8f0', color: '#475569', borderRadius: '6px', padding: '0.3rem 0.7rem', cursor: 'pointer', fontSize: '0.8rem' },
  input: { border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.45rem 0.75rem', fontSize: '0.875rem', width: '100%' },
  label: { fontSize: '0.8rem', color: '#64748b', marginBottom: '0.25rem', display: 'block' },
  section: { marginBottom: '0.5rem' },
  groupTitle: { fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.4rem' },
  checkRow: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem 1.2rem', marginBottom: '0.2rem' },
  checkLabel: { display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: '#374151', cursor: 'pointer' },
}

export default function RolesManagement() {
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await rolesApi.getRoles()
      setRoles(data.results ?? data)
    } catch {
      setError('Impossible de charger les rôles.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setShowForm(true)
  }

  const openEdit = (role) => {
    setEditing(role)
    setForm({ nom: role.nom, permissions: [...role.permissions] })
    setShowForm(true)
  }

  const cancel = () => {
    setShowForm(false)
    setEditing(null)
    setForm(EMPTY_FORM)
  }

  const togglePerm = (code) => {
    setForm(f => ({
      ...f,
      permissions: f.permissions.includes(code)
        ? f.permissions.filter(c => c !== code)
        : [...f.permissions, code],
    }))
  }

  const selectAll = (codes) => {
    setForm(f => {
      const set = new Set(f.permissions)
      codes.forEach(c => set.add(c))
      return { ...f, permissions: Array.from(set) }
    })
  }

  const deselectAll = (codes) => {
    setForm(f => ({
      ...f,
      permissions: f.permissions.filter(c => !codes.includes(c)),
    }))
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      if (editing) {
        await rolesApi.patchRole(editing.id, form)
      } else {
        await rolesApi.createRole(form)
      }
      cancel()
      await load()
    } catch (err) {
      const msg = err.response?.data?.nom?.[0]
        || err.response?.data?.permissions?.[0]
        || err.response?.data?.detail
        || err.message
      alert('Erreur : ' + msg)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (role) => {
    if (!confirm(`Supprimer le rôle "${role.nom}" ?`)) return
    try {
      await rolesApi.deleteRole(role.id)
      await load()
    } catch (err) {
      alert(err.response?.data?.detail || 'Impossible de supprimer ce rôle.')
    }
  }

  return (
    <div>
      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600 }}>Gestion des rôles</h2>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: '#64748b' }}>
            Créez des rôles personnalisés avec des permissions précises pour votre entreprise.
          </p>
        </div>
        {!showForm && (
          <button onClick={openCreate} style={S.btnPrimary}>
            + Nouveau rôle
          </button>
        )}
      </div>

      {error && <p style={{ color: '#ef4444', marginBottom: '1rem' }}>{error}</p>}

      {/* ── Form ── */}
      {showForm && (
        <div style={{ ...S.card, padding: '1.5rem', marginBottom: '1.5rem' }}>
          <h3 style={{ margin: '0 0 1.25rem', fontSize: '1rem', fontWeight: 600 }}>
            {editing ? `Modifier : ${editing.nom}` : 'Nouveau rôle'}
          </h3>
          <form onSubmit={handleSave}>
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={S.label}>Nom du rôle *</label>
              <input
                required
                value={form.nom}
                onChange={e => setForm(f => ({ ...f, nom: e.target.value }))}
                placeholder="ex: Comptable, Magasinier..."
                style={{ ...S.input, maxWidth: '320px' }}
              />
            </div>

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ ...S.label, marginBottom: '0.75rem' }}>Permissions</label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '1rem' }}>
                {PERMISSION_GROUPS.map(group => {
                  const allSelected = group.codes.every(p => form.permissions.includes(p.code))
                  return (
                    <div key={group.label} style={{ background: '#f8fafc', borderRadius: '6px', padding: '0.75rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                        <span style={S.groupTitle}>{group.label}</span>
                        <button
                          type="button"
                          onClick={() => allSelected
                            ? deselectAll(group.codes.map(p => p.code))
                            : selectAll(group.codes.map(p => p.code))
                          }
                          style={{ fontSize: '0.7rem', background: 'none', border: 'none', color: '#3b82f6', cursor: 'pointer', padding: 0 }}
                        >
                          {allSelected ? 'Tout décocher' : 'Tout cocher'}
                        </button>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                        {group.codes.map(p => (
                          <label key={p.code} style={S.checkLabel}>
                            <input
                              type="checkbox"
                              checked={form.permissions.includes(p.code)}
                              onChange={() => togglePerm(p.code)}
                              style={{ accentColor: '#3b82f6' }}
                            />
                            {p.label}
                          </label>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button type="submit" disabled={saving} style={{ ...S.btnPrimary, background: '#10b981' }}>
                {saving ? 'Enregistrement...' : (editing ? 'Mettre à jour' : 'Créer le rôle')}
              </button>
              <button type="button" onClick={cancel} style={S.btnGhost}>
                Annuler
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ── Table ── */}
      {loading ? (
        <p style={{ color: '#64748b' }}>Chargement...</p>
      ) : (
        <div style={S.card}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                <th style={S.th}>Nom</th>
                <th style={S.th}>Type</th>
                <th style={S.th}>Permissions</th>
                <th style={S.th}>Utilisateurs</th>
                <th style={{ ...S.th, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {roles.map((r, i) => (
                <tr key={r.id} style={{ borderBottom: i < roles.length - 1 ? '1px solid #f1f5f9' : 'none' }}>
                  <td style={{ ...S.td, fontWeight: 600 }}>{r.nom}</td>
                  <td style={S.td}>
                    <span style={S.badge(r.est_systeme)}>
                      {r.est_systeme ? 'Système' : 'Personnalisé'}
                    </span>
                  </td>
                  <td style={S.td}>
                    <span style={{ color: '#64748b', fontSize: '0.8rem' }}>
                      {r.permissions.length} permission{r.permissions.length !== 1 ? 's' : ''}
                    </span>
                  </td>
                  <td style={{ ...S.td, color: '#64748b' }}>{r.users_count}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                      <button onClick={() => openEdit(r)} style={S.btnGhost}>
                        Modifier
                      </button>
                      {!r.est_systeme && (
                        <button onClick={() => handleDelete(r)} style={S.btnDanger}>
                          Supprimer
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {roles.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
                    Aucun rôle défini.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
