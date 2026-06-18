import { useEffect, useState } from 'react'
import { ShieldPlus, ShieldCheck, Pencil, Trash2 } from 'lucide-react'
import rolesApi from '../../api/rolesApi'
import {
  Button, Spinner, Badge,
  Card, CardHeader, CardTitle,
  EmptyState, Skeleton,
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  Form, FormActions,
  Label, Input, Checkbox,
} from '../../ui'

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

export default function RolesManagement() {
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [formError, setFormError] = useState(null)

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

  // Chargement initial — le setState a lieu dans le callback async, pas en sync
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setFormError(null)
    setShowForm(true)
  }

  const openEdit = (role) => {
    setEditing(role)
    setForm({ nom: role.nom, permissions: [...role.permissions] })
    setFormError(null)
    setShowForm(true)
  }

  const cancel = () => {
    setShowForm(false)
    setEditing(null)
    setForm(EMPTY_FORM)
    setFormError(null)
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
    setFormError(null)
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
      setFormError('Erreur : ' + msg)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (role) => {
    try {
      await rolesApi.deleteRole(role.id)
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Impossible de supprimer ce rôle.')
    }
  }

  const th = 'px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground'

  return (
    <div className="flex flex-col gap-6">
      {/* ── Header ── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-semibold tracking-tight">Gestion des rôles</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Créez des rôles personnalisés avec des permissions précises pour votre entreprise.
          </p>
        </div>
        {!showForm && (
          <Button onClick={openCreate}>
            <ShieldPlus /> Nouveau rôle
          </Button>
        )}
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {/* ── Éditeur de rôle ── */}
      {showForm && (
        <Card className="p-4 sm:p-5">
          <CardTitle className="mb-4">
            {editing ? `Modifier : ${editing.nom}` : 'Nouveau rôle'}
          </CardTitle>
          <Form onSubmit={handleSave} className="gap-5">
            <div className="flex flex-col gap-1.5 sm:max-w-xs">
              <Label htmlFor="role-nom" required>Nom du rôle</Label>
              <Input
                id="role-nom"
                required
                value={form.nom}
                placeholder="ex: Comptable, Magasinier…"
                onChange={e => setForm(f => ({ ...f, nom: e.target.value }))}
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label>Permissions</Label>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {PERMISSION_GROUPS.map(group => {
                  const codes = group.codes.map(p => p.code)
                  const allSelected = codes.every(c => form.permissions.includes(c))
                  return (
                    <Card key={group.label} className="bg-muted/30 shadow-none">
                      <CardHeader className="flex-row items-center justify-between p-3">
                        <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {group.label}
                        </CardTitle>
                        <Button
                          type="button"
                          variant="link"
                          size="sm"
                          className="h-auto p-0 text-xs"
                          onClick={() => allSelected ? deselectAll(codes) : selectAll(codes)}
                        >
                          {allSelected ? 'Tout décocher' : 'Tout cocher'}
                        </Button>
                      </CardHeader>
                      <div className="flex flex-col gap-2 p-3 pt-0">
                        {group.codes.map(p => (
                          <label key={p.code} className="flex cursor-pointer items-center gap-2.5 text-sm text-foreground">
                            <Checkbox
                              checked={form.permissions.includes(p.code)}
                              onCheckedChange={() => togglePerm(p.code)}
                            />
                            {p.label}
                          </label>
                        ))}
                      </div>
                    </Card>
                  )
                })}
              </div>
            </div>

            {formError && (
              <p role="alert" className="text-sm text-destructive">{formError}</p>
            )}

            <FormActions sticky={false}>
              <Button type="button" variant="ghost" onClick={cancel}>Annuler</Button>
              <Button type="submit" variant="success" loading={saving}>
                {editing ? 'Mettre à jour' : 'Créer le rôle'}
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
      ) : roles.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title="Aucun rôle défini"
          description="Créez un rôle personnalisé pour attribuer des permissions précises."
          action={<Button size="sm" onClick={openCreate}><ShieldPlus /> Nouveau rôle</Button>}
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className={th}>Nom</th>
                  <th className={th}>Type</th>
                  <th className={th}>Permissions</th>
                  <th className={th}>Utilisateurs</th>
                  <th className={`${th} text-right`}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {roles.map((r) => (
                  <tr key={r.id} className="border-b border-border/60 last:border-b-0 hover:bg-accent/40">
                    <td className="px-4 py-2.5 font-medium text-foreground">{r.nom}</td>
                    <td className="px-4 py-2.5">
                      <Badge tone={r.est_systeme ? 'info' : 'success'}>
                        {r.est_systeme ? 'Système' : 'Personnalisé'}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {r.permissions.length} permission{r.permissions.length !== 1 ? 's' : ''}
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">{r.users_count}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center justify-end gap-2">
                        <Button size="sm" variant="outline" onClick={() => openEdit(r)}>
                          <Pencil /> Modifier
                        </Button>
                        {!r.est_systeme && (
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button size="sm" variant="ghost" className="text-destructive hover:bg-destructive/10">
                                <Trash2 /> Supprimer
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Supprimer ce rôle ?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  Le rôle « {r.nom} » sera définitivement supprimé.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Annuler</AlertDialogCancel>
                                <AlertDialogAction onClick={() => handleDelete(r)}>
                                  Supprimer
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
