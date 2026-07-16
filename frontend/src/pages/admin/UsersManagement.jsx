import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { UserPlus, Users, Pencil, Trash2, ShieldCheck, UserCheck, UserX } from 'lucide-react'
import api from '../../api/axios'
import rolesApi from '../../api/rolesApi'
import Avatar from '../../components/Avatar'
import {
  Button, Badge,
  Card,
  EmptyState,
  StatusPill,
  DataTable,
  TooltipProvider,
  Form, FormSection, FormField, FormActions,
  Label, Input, Switch,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  FileUpload,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { useConfirmDialog, toast } from '../../ui/confirm'

// Teinte de pastille dérivée du nom de rôle (admin → ambre, responsable →
// violet, sinon vert) — purement visuel, ne change rien à la sémantique RBAC.
const roleTone = (nom) => {
  if (!nom) return 'neutral'
  const n = nom.toLowerCase()
  if (n.includes('admin')) return 'warning'
  if (n.includes('respon')) return 'primary'
  return 'success'
}

// Libellé d'un rôle dans un sélecteur : nom + étiquette Système / Personnalisé.
const roleOptionLabel = (r) =>
  `${r.nom} ${r.est_systeme ? '(Système)' : '(Personnalisé)'}`

// Un rôle « admin » est celui qui octroie roles_gerer (ou nommé Administrateur /
// Directeur). Sert à garder un rôle admin au propriétaire protégé.
const isAdminRole = (r) => {
  if (!r) return false
  if (Array.isArray(r.permissions) && r.permissions.includes('roles_gerer')) return true
  const n = (r.nom || '').toLowerCase()
  return n.includes('admin') || n.includes('directeur')
}

export default function UsersManagement() {
  const currentUsername = useSelector(s => s.auth.user?.username)
  const navigate = useNavigate()
  const { confirm: askConfirm } = useConfirmDialog()
  const [users, setUsers] = useState([])
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  // VX104 — `supervisor` réglable dès la création (auparavant seul
  // EquipeSection.jsx le permettait, après coup — hiérarchie oubliée en
  // silence). '' = aucun superviseur choisi.
  const [form, setForm] = useState({ username: '', email: '', password: '', role: '', supervisor: '', must_change_password: false })
  const [saving, setSaving] = useState(false)
  const [createError, setCreateError] = useState(null)

  // ── Édition d'un employé (rôle, poste, mot de passe, photo, actif) ──
  const [editUser, setEditUser] = useState(null)
  const [editForm, setEditForm] = useState(null)
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState(null)
  const [avatarBusy, setAvatarBusy] = useState(false)

  const openEdit = (u) => {
    setEditError(null)
    setEditUser(u)
    setEditForm({
      email: u.email || '',
      role: u.role || '',
      poste: u.poste || '',
      is_active: u.is_active,
      password: '',
      password2: '',
    })
  }
  const closeEdit = () => { setEditUser(null); setEditForm(null); setEditError(null) }

  const saveEdit = async (e) => {
    e.preventDefault()
    if (editForm.password && editForm.password !== editForm.password2) {
      setEditError('Les deux mots de passe ne correspondent pas.')
      return
    }
    // Garde : le propriétaire protégé doit garder un rôle administrateur.
    if (editUser.is_protected) {
      const chosen = roles.find(r => String(r.id) === String(editForm.role))
      if (!isAdminRole(chosen)) {
        setEditError('Le propriétaire protégé doit conserver un rôle administrateur.')
        return
      }
    }
    setEditSaving(true)
    setEditError(null)
    try {
      const payload = {
        email: editForm.email,
        role: editForm.role || null,
        poste: editForm.poste,
        is_active: editForm.is_active,
      }
      if (editForm.password) payload.password = editForm.password
      await api.patch(`/users/${editUser.id}/`, payload)
      closeEdit()
      toast.success('Utilisateur enregistré.')
      await load()
    } catch (err) {
      setEditError(err.response?.data?.detail
        ?? "Échec de l'enregistrement. Vérifiez les champs.")
    } finally {
      setEditSaving(false)
    }
  }

  const uploadAvatar = async (file) => {
    if (!file) return
    setAvatarBusy(true)
    setEditError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const r = await api.post(`/users/${editUser.id}/avatar/`, fd)
      // Met à jour l'aperçu immédiat + la ligne dans la liste.
      setEditUser(u => ({ ...u, avatar_url: r.data.avatar_url, avatar_key: r.data.avatar_key }))
      setUsers(list => list.map(u => (u.id === editUser.id ? { ...u, avatar_url: r.data.avatar_url } : u)))
    } catch (err) {
      setEditError(err.response?.data?.detail ?? "Échec de l'envoi de la photo.")
    } finally {
      setAvatarBusy(false)
    }
  }

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
    setCreateError(null)
    try {
      // VX104 — `supervisor` n'est envoyé QUE s'il est choisi (le champ FK
      // n'accepte pas une chaîne vide) ; sinon toast de rappel avec lien vers
      // Paramètres → Équipe, où la hiérarchie reste réglable après coup.
      const payload = { ...form, supervisor: form.supervisor ? Number(form.supervisor) : null }
      await api.post('/users/', payload)
      const hadSupervisor = !!form.supervisor
      setForm({
        username: '', email: '', password: '',
        role: roles.find(r => r.nom === 'Utilisateur')?.id || roles[0]?.id || '',
        supervisor: '', must_change_password: false,
      })
      setShowForm(false)
      if (hadSupervisor) {
        toast.success('Utilisateur créé.')
      } else {
        toast.message('Utilisateur créé.', {
          description: 'Pensez à définir son responsable direct.',
          action: {
            label: 'Paramètres → Équipe',
            onClick: () => navigate('/parametres'),
          },
        })
      }
      await load()
    } catch (err) {
      setCreateError('Erreur : ' + (err.response?.data?.username?.[0] ?? err.message))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
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

  // ── Suppression d'un utilisateur (confirmation maison, jamais window.confirm) ──
  const askDelete = async (u) => {
    const ok = await askConfirm({
      title: 'Supprimer cet utilisateur ?',
      description: `Le compte « ${u.username} » sera définitivement supprimé.`,
      confirmLabel: 'Supprimer',
      cancelLabel: 'Annuler',
      destructive: true,
    })
    if (!ok) return
    try {
      await handleDelete(u.id)
      toast.success('Utilisateur supprimé.')
    } catch (err) {
      toast.error(err.response?.data?.detail ?? 'Suppression impossible.')
    }
  }

  // ── Activation / désactivation rapide (et en masse) ──
  const setActive = async (u, active) => {
    try {
      await api.patch(`/users/${u.id}/`, { is_active: active })
      setUsers(list => list.map(x => (x.id === u.id ? { ...x, is_active: active } : x)))
    } catch (err) {
      toast.error(err.response?.data?.detail ?? 'Modification impossible.')
    }
  }

  // ── Colonnes du DataTable (cellule avatar, pastilles de rôle/statut) ──
  const columns = useMemo(() => [
    {
      id: 'username',
      header: 'Utilisateur',
      width: 260,
      hideable: false,
      accessor: (u) => u.username,
      cell: (value, u) => (
        <span className="flex items-center gap-3">
          <Avatar name={u.username} src={u.avatar_url} size={32} />
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="font-medium text-foreground">{value}</span>
            {u.is_protected && (
              <Badge tone="warning">Propriétaire protégé</Badge>
            )}
          </span>
        </span>
      ),
    },
    {
      id: 'poste',
      header: 'Poste',
      width: 160,
      accessor: (u) => u.poste || '',
      cell: (value) => value || '—',
    },
    {
      id: 'email',
      header: 'Email',
      width: 220,
      accessor: (u) => u.email || '',
      cell: (value) => value || '—',
    },
    {
      id: 'role',
      header: 'Rôle',
      width: 170,
      accessor: (u) => u.role_nom || '',
      cell: (value) => (value
        ? <StatusPill label={value} tone={roleTone(value)} />
        : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'is_active',
      header: 'Actif',
      width: 120,
      searchable: false,
      accessor: (u) => (u.is_active ? 'Actif' : 'Inactif'),
      cell: (_value, u) => (u.is_active
        ? <StatusPill label="Actif" tone="success" />
        : <StatusPill label="Inactif" tone="neutral" />),
    },
  ], [])

  // Actions de ligne : Modifier (toujours) + activer/désactiver + Supprimer
  // (selon les gardes propriétaire / dernier admin / soi-même).
  const rowActions = (u) => {
    const isLastAdmin = isAdminUser(u) && adminCount <= 1
    const deleteLocked = u.is_protected || isLastAdmin
    const actions = [
      { id: 'edit', label: 'Modifier', icon: Pencil, onClick: () => openEdit(u) },
    ]
    actions.push(
      u.is_active
        ? { id: 'deactivate', label: 'Désactiver', icon: UserX, onClick: () => setActive(u, false) }
        : { id: 'activate', label: 'Activer', icon: UserCheck, onClick: () => setActive(u, true) },
    )
    if (u.username !== currentUsername && !deleteLocked) {
      actions.push({
        id: 'delete',
        label: 'Supprimer',
        icon: Trash2,
        destructive: true,
        separatorBefore: true,
        onClick: () => askDelete(u),
      })
    }
    return actions
  }

  // Actions groupées (admin) : activer / désactiver une sélection d'un coup.
  const bulkActions = (rows, _keys, clear) => [
    {
      id: 'bulk-activate',
      label: 'Activer',
      icon: UserCheck,
      onClick: async () => {
        for (const u of rows) if (!u.is_active) await setActive(u, true)
        clear?.()
      },
    },
    {
      id: 'bulk-deactivate',
      label: 'Désactiver',
      icon: UserX,
      onClick: async () => {
        // VX235(d) — `bulkActions` ne vérifiait jamais `isLastAdmin` : une
        // désactivation groupée pouvait vider TOUS les admins actifs d'un
        // coup (contrairement à la ligne unique, qui n'a jamais ce garde non
        // plus mais n'agit que sur UN compte à la fois). Ici : compte les
        // admins ACTIFS de toute la société (pas seulement la sélection) et
        // exclut de la désactivation groupée le(s) compte(s) nécessaire(s)
        // pour qu'il en reste au moins un.
        const activeAdmins = users.filter((u) => isAdminUser(u) && u.is_active).length
        let remainingActiveAdmins = activeAdmins
        const skipped = []
        for (const u of rows) {
          if (!u.is_active || u.username === currentUsername || u.is_protected) continue
          if (isAdminUser(u) && remainingActiveAdmins <= 1) {
            skipped.push(u.username)
            continue
          }
          if (isAdminUser(u)) remainingActiveAdmins -= 1
          await setActive(u, false)
        }
        if (skipped.length > 0) {
          toast.info(
            `${skipped.length} compte(s) laissé(s) actif(s) — au moins un `
            + `administrateur doit rester actif : ${skipped.join(', ')}.`)
        }
        clear?.()
      },
    },
  ]

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex flex-col gap-6">
        {/* ── Header ── */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-xl font-semibold tracking-tight">Gestion des utilisateurs</h2>
          {showForm ? (
            <Button variant="outline" onClick={() => { setShowForm(false); setCreateError(null) }}>
              Annuler
            </Button>
          ) : (
            <Button onClick={() => setShowForm(true)}>
              + Nouvel utilisateur
            </Button>
          )}
        </div>

        {/* ── Formulaire de création ── */}
        {showForm && (
          <Card className="p-4 sm:p-5">
            <Form onSubmit={handleCreate} className="gap-4">
              <FormSection title="Nouvel utilisateur">
                <FormField label="Nom d'utilisateur" required htmlFor="new-username">
                  {/* IMPORTANT : champ sans attribut `type` (sélecteur e2e
                      input:not([type]) = nom d'utilisateur). On ne passe pas par
                      le primitif Input qui force type="text". */}
                  <input
                    id="new-username"
                    required
                    autoFocus
                    value={form.username}
                    onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                    className="flex h-[var(--control-h)] w-full rounded-md border border-input bg-card px-[var(--control-px)] text-base text-foreground shadow-ui-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-sm"
                  />
                </FormField>
                <FormField label="Email" htmlFor="new-email">
                  <Input
                    id="new-email"
                    type="email"
                    value={form.email}
                    onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  />
                </FormField>
                <FormField label="Mot de passe" required htmlFor="new-password">
                  <Input
                    id="new-password"
                    type="password"
                    required
                    autoComplete="new-password"
                    value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  />
                </FormField>
                <FormField label="Rôle" htmlFor="new-role">
                  <Select
                    value={form.role ? String(form.role) : undefined}
                    onValueChange={v => setForm(f => ({ ...f, role: Number(v) }))}
                  >
                    <SelectTrigger id="new-role">
                      <SelectValue placeholder="Choisir un rôle…" />
                    </SelectTrigger>
                    <SelectContent>
                      {roles.map(r => (
                        <SelectItem key={r.id} value={String(r.id)}>{roleOptionLabel(r)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormField>
                {/* VX104 — superviseur réglable dès la création (mêmes options
                    que EquipeSection.jsx) : sans lien, la hiérarchie est
                    oubliée en silence (visibilité des dossiers cassée sans
                    erreur). Optionnel — le toast post-création rappelle de le
                    définir si laissé vide. */}
                <FormField label="Superviseur direct (optionnel)" htmlFor="new-supervisor">
                  <Select
                    value={form.supervisor ? String(form.supervisor) : '__none__'}
                    onValueChange={v => setForm(f => ({ ...f, supervisor: v === '__none__' ? '' : v }))}
                  >
                    <SelectTrigger id="new-supervisor">
                      <SelectValue placeholder="— Aucun —" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">— Aucun —</SelectItem>
                      {users.map(u => (
                        <SelectItem key={u.id} value={String(u.id)}>{u.username}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormField>
                {/* FG21 — onboarding : forcer le changement de mot de passe à
                    la première connexion (case décochée par défaut). */}
                <FormField label="Sécurité" htmlFor="new-must-change">
                  <div className="flex items-center gap-2.5">
                    <Switch
                      id="new-must-change"
                      checked={form.must_change_password}
                      onCheckedChange={v => setForm(f => ({ ...f, must_change_password: v }))}
                    />
                    <Label htmlFor="new-must-change" className="text-sm font-normal text-muted-foreground">
                      Demander un changement de mot de passe à la première connexion
                    </Label>
                  </div>
                </FormField>
              </FormSection>
              {createError && (
                <p role="alert" className="text-sm text-destructive">{createError}</p>
              )}
              <FormActions sticky={false}>
                <Button type="button" variant="ghost" onClick={() => { setShowForm(false); setCreateError(null) }}>
                  Annuler
                </Button>
                <Button type="submit" loading={saving}>
                  <UserPlus /> Créer
                </Button>
              </FormActions>
            </Form>
          </Card>
        )}

        {/* ── Liste (DataTable unifié : recherche, tri, cellule avatar,
              pastilles de rôle/statut, actions de ligne + groupées) ── */}
        {error ? (
          <EmptyState
            icon={Users}
            title="Données indisponibles"
            description={error}
            action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>}
          />
        ) : !loading && users.length === 0 ? (
          <EmptyState
            icon={Users}
            title="Aucun utilisateur"
            description="Créez votre premier utilisateur pour démarrer."
            action={<Button size="sm" onClick={() => setShowForm(true)}>+ Nouvel utilisateur</Button>}
          />
        ) : (
          <DataTable
            data={users}
            columns={columns}
            getRowId={(u) => u.id}
            loading={loading && users.length === 0}
            searchable
            searchPlaceholder="Rechercher un utilisateur, poste, email…"
            rowActions={rowActions}
            selectable
            bulkActions={bulkActions}
            exportName="utilisateurs"
            emptyTitle="Aucun utilisateur"
            emptyDescription="Aucun utilisateur ne correspond à cette recherche."
            aria-label="Liste des utilisateurs"
          />
        )}

        {/* ── Édition employé : ResponsiveDialog (modale bureau ↔ Sheet bas
              mobile). La classe `modal` est conservée pour les contrats e2e
              (recherche de la modale + tenue dans le viewport iPhone). ── */}
        <ResponsiveDialog
          open={!!editUser}
          onOpenChange={(o) => { if (!o) closeEdit() }}
          title={editUser ? `Employé — ${editUser.username}` : undefined}
          className="modal max-w-xl"
        >
          {editUser && editForm && (
            <Form onSubmit={saveEdit} className="gap-5">
              {/* Photo */}
              <div className="flex items-center gap-4">
                <Avatar name={editUser.username} src={editUser.avatar_url} size={64} />
                <div className="flex-1">
                  <FileUpload
                    accept="image/png,image/jpeg,image/webp"
                    maxSize={2 * 1024 * 1024}
                    busy={avatarBusy}
                    onFiles={(files) => uploadAvatar(files[0])}
                    hint="PNG, JPEG ou WebP"
                  >
                    <p className="text-sm font-medium text-foreground">
                      {avatarBusy
                        ? 'Envoi…'
                        : (editUser.avatar_url ? 'Remplacer la photo' : 'Ajouter une photo')}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">PNG, JPEG ou WebP — max 2 Mo</p>
                  </FileUpload>
                </div>
              </div>

              <FormSection>
                <FormField label="Nom d'utilisateur" htmlFor="edit-username">
                  <Input id="edit-username" value={editUser.username} disabled />
                </FormField>
                <FormField label="Email" htmlFor="edit-email">
                  <Input
                    id="edit-email"
                    type="email"
                    autoFocus
                    value={editForm.email}
                    onChange={e => setEditForm(f => ({ ...f, email: e.target.value }))}
                  />
                </FormField>
                <FormField label="Poste (intitulé du métier)" htmlFor="edit-poste">
                  <Input
                    id="edit-poste"
                    value={editForm.poste}
                    placeholder="ex: Commerciale, Technicien…"
                    onChange={e => setEditForm(f => ({ ...f, poste: e.target.value }))}
                  />
                </FormField>
                <FormField label="Rôle (permissions)" htmlFor="edit-role">
                  <Select
                    value={editForm.role ? String(editForm.role) : '__none__'}
                    onValueChange={v => setEditForm(f => ({ ...f, role: v === '__none__' ? '' : Number(v) }))}
                  >
                    <SelectTrigger id="edit-role">
                      <SelectValue placeholder="—" />
                    </SelectTrigger>
                    <SelectContent>
                      {/* Propriétaire protégé : pas d'option « Aucun rôle » et
                          seuls les rôles admin sont proposés (il doit garder un
                          accès administrateur). */}
                      {!editUser.is_protected && <SelectItem value="__none__">—</SelectItem>}
                      {(editUser.is_protected ? roles.filter(isAdminRole) : roles).map(r => (
                        <SelectItem key={r.id} value={String(r.id)}>{roleOptionLabel(r)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormField>
              </FormSection>

              {editUser.is_protected && (
                <p className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-warning">
                  <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                  <span>
                    Propriétaire protégé : ce compte doit toujours conserver un
                    rôle administrateur. Le rôle ne peut pas être retiré.
                  </span>
                </p>
              )}

              <label className="flex items-center gap-2.5 text-sm text-foreground">
                <Switch
                  checked={editForm.is_active}
                  onCheckedChange={(v) => setEditForm(f => ({ ...f, is_active: v }))}
                />
                Compte actif
              </label>

              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <p className="flex items-start gap-2 text-xs text-muted-foreground">
                  <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                  <span>
                    Mot de passe : on ne peut pas afficher l'ancien (il est chiffré).
                    Laissez vide pour ne pas le changer, sinon saisissez un nouveau mot de passe.
                  </span>
                </p>
                <div className="mt-3 grid gap-4 sm:grid-cols-2">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="edit-password">Nouveau mot de passe</Label>
                    <Input
                      id="edit-password"
                      type="password"
                      autoComplete="new-password"
                      value={editForm.password}
                      onChange={e => setEditForm(f => ({ ...f, password: e.target.value }))}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="edit-password2">Confirmer</Label>
                    <Input
                      id="edit-password2"
                      type="password"
                      autoComplete="new-password"
                      value={editForm.password2}
                      onChange={e => setEditForm(f => ({ ...f, password2: e.target.value }))}
                    />
                  </div>
                </div>
              </div>

              {editError && (
                <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                  {editError}
                </p>
              )}

              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button type="button" variant="ghost" onClick={closeEdit}>Annuler</Button>
                <Button type="submit" loading={editSaving}>Enregistrer</Button>
              </div>
            </Form>
          )}
        </ResponsiveDialog>
      </div>
    </TooltipProvider>
  )
}
