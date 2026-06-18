import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { UserPlus, Users, Pencil, Trash2, ShieldCheck } from 'lucide-react'
import api from '../../api/axios'
import rolesApi from '../../api/rolesApi'
import Avatar from '../../components/Avatar'
import {
  Button, Spinner, Badge,
  Card,
  EmptyState, Skeleton,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  TooltipProvider, SimpleTooltip,
  Form, FormSection, FormField, FormActions,
  Label, Input, Switch,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  FileUpload,
} from '../../ui'

// Teinte de badge dérivée du nom de rôle (admin → ambre, responsable → violet,
// sinon vert) — purement visuel, ne change rien à la sémantique RBAC.
const roleTone = (nom) => {
  if (!nom) return 'neutral'
  const n = nom.toLowerCase()
  if (n.includes('admin')) return 'warning'
  if (n.includes('respon')) return 'primary'
  return 'success'
}

export default function UsersManagement() {
  const currentUsername = useSelector(s => s.auth.user?.username)
  const [users, setUsers] = useState([])
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ username: '', email: '', password: '', role: '' })
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
      await api.post('/users/', form)
      setForm({ username: '', email: '', password: '', role: roles.find(r => r.nom === 'Utilisateur')?.id || roles[0]?.id || '' })
      setShowForm(false)
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

  const th = 'px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground'

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
                        <SelectItem key={r.id} value={String(r.id)}>{r.nom}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
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

        {/* ── Liste ── */}
        {loading ? (
          <Card className="p-5">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner /> Chargement…
            </div>
            <div className="mt-4 space-y-3">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          </Card>
        ) : error ? (
          <EmptyState
            icon={Users}
            title="Données indisponibles"
            description={error}
            action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>}
          />
        ) : users.length === 0 ? (
          <EmptyState
            icon={Users}
            title="Aucun utilisateur"
            description="Créez votre premier utilisateur pour démarrer."
            action={<Button size="sm" onClick={() => setShowForm(true)}>+ Nouvel utilisateur</Button>}
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className={th} style={{ width: 48 }}></th>
                    <th className={th}>Utilisateur</th>
                    <th className={th}>Poste</th>
                    <th className={th}>Email</th>
                    <th className={th}>Rôle</th>
                    <th className={th}>Actif</th>
                    <th className={`${th} text-right`}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => {
                    const isLastAdmin = isAdminUser(u) && adminCount <= 1
                    const deleteLocked = u.is_protected || isLastAdmin
                    const lockTooltip = u.is_protected
                      ? 'Compte propriétaire protégé'
                      : 'Au moins un administrateur doit rester'
                    return (
                      <tr key={u.id} className="border-b border-border/60 last:border-b-0 hover:bg-accent/40">
                        <td className="px-4 py-2.5">
                          <Avatar name={u.username} src={u.avatar_url} size={32} />
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="font-medium text-foreground">{u.username}</span>
                          {u.is_protected && (
                            <Badge tone="warning" className="ml-2">Propriétaire protégé</Badge>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-muted-foreground">{u.poste || '—'}</td>
                        <td className="px-4 py-2.5 text-muted-foreground">{u.email || '—'}</td>
                        <td className="px-4 py-2.5">
                          {u.role_nom
                            ? <Badge tone={roleTone(u.role_nom)}>{u.role_nom}</Badge>
                            : <span className="text-muted-foreground">—</span>}
                        </td>
                        <td className="px-4 py-2.5">
                          {u.is_active
                            ? <Badge tone="success">Actif</Badge>
                            : <Badge tone="neutral">Inactif</Badge>}
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center justify-end gap-2">
                            <Button size="sm" variant="outline" onClick={() => openEdit(u)}>
                              <Pencil /> Modifier
                            </Button>
                            {u.username !== currentUsername && (
                              deleteLocked ? (
                                <SimpleTooltip label={lockTooltip}>
                                  <span>
                                    <Button size="sm" variant="ghost" disabled>
                                      <Trash2 /> Supprimer
                                    </Button>
                                  </span>
                                </SimpleTooltip>
                              ) : (
                                <AlertDialog>
                                  <AlertDialogTrigger asChild>
                                    <Button size="sm" variant="ghost" className="text-destructive hover:bg-destructive/10">
                                      <Trash2 /> Supprimer
                                    </Button>
                                  </AlertDialogTrigger>
                                  <AlertDialogContent>
                                    <AlertDialogHeader>
                                      <AlertDialogTitle>Supprimer cet utilisateur ?</AlertDialogTitle>
                                      <AlertDialogDescription>
                                        Le compte « {u.username} » sera définitivement supprimé.
                                      </AlertDialogDescription>
                                    </AlertDialogHeader>
                                    <AlertDialogFooter>
                                      <AlertDialogCancel>Annuler</AlertDialogCancel>
                                      <AlertDialogAction onClick={() => handleDelete(u.id)}>
                                        Supprimer
                                      </AlertDialogAction>
                                    </AlertDialogFooter>
                                  </AlertDialogContent>
                                </AlertDialog>
                              )
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* ── Modale d'édition employé ── */}
        <Dialog open={!!editUser} onOpenChange={(o) => { if (!o) closeEdit() }}>
          {editUser && editForm && (
            <DialogContent className="modal max-w-xl">
              <DialogHeader>
                <DialogTitle>Employé — {editUser.username}</DialogTitle>
              </DialogHeader>
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
                        <SelectItem value="__none__">—</SelectItem>
                        {roles.map(r => (
                          <SelectItem key={r.id} value={String(r.id)}>{r.nom}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormField>
                </FormSection>

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

                <DialogFooter>
                  <DialogClose asChild>
                    <Button type="button" variant="ghost">Annuler</Button>
                  </DialogClose>
                  <Button type="submit" loading={editSaving}>Enregistrer</Button>
                </DialogFooter>
              </Form>
            </DialogContent>
          )}
        </Dialog>
      </div>
    </TooltipProvider>
  )
}
