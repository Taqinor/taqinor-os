import { useEffect, useMemo, useState } from 'react'
import { ShieldPlus, ShieldCheck, Pencil, Trash2, Eye, ChevronDown, Lock } from 'lucide-react'
import api from '../../api/axios'
import rolesApi from '../../api/rolesApi'
import { resilientMutation } from '../../lib/resilientMutation'
import {
  Button, Spinner, Badge,
  Card, CardHeader, CardTitle,
  EmptyState, Skeleton,
  AlertDialog, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  Form, FormActions,
  Label, Input, Checkbox,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { DataTable } from '../../ui/datatable'
// VX132 — anti-scintillement propagé : ce Spinner + Skeleton s'affichaient
// SIMULTANÉMENT (l'anti-pattern que useDelayedLoading existe pour éviter —
// voir InstallationsPage.jsx, déjà migrée).
import { useDelayedLoading } from '../../hooks/useDelayedLoading'

// Grille module × action (Feature D/RBAC). La SOURCE des codes est l'endpoint
// /roles/permissions-disponibles (models.ALL_PERMISSIONS) ; cette table ne sert
// qu'à GROUPER et ÉTIQUETER les codes connus. Tout code renvoyé par le backend
// mais absent d'ici est quand même rendu (groupe « Autres », libellé = code) —
// l'éditeur reste donc synchronisé avec le backend sans tableau en dur.
const PERMISSION_GROUPS = [
  {
    label: 'Stock',
    codes: [
      { code: 'stock_voir',      label: 'Voir' },
      { code: 'stock_creer',     label: 'Créer' },
      { code: 'stock_modifier',  label: 'Modifier' },
      { code: 'stock_supprimer', label: 'Supprimer' },
      { code: 'stock_mouvement', label: 'Mouvements' },
      { code: 'stock_export',    label: 'Exporter' },
    ],
  },
  {
    label: 'CRM (leads & clients)',
    codes: [
      { code: 'crm_voir',      label: 'Voir' },
      { code: 'crm_creer',     label: 'Créer' },
      { code: 'crm_modifier',  label: 'Modifier' },
      { code: 'crm_supprimer', label: 'Supprimer' },
      { code: 'crm_export',    label: 'Exporter' },
      { code: 'crm_reassign',  label: 'Réassigner' },
    ],
  },
  {
    label: 'Ventes (devis/factures/avoirs)',
    codes: [
      { code: 'ventes_voir',      label: 'Voir' },
      { code: 'ventes_creer',     label: 'Créer' },
      { code: 'ventes_modifier',  label: 'Modifier' },
      { code: 'ventes_supprimer', label: 'Supprimer' },
      { code: 'ventes_valider',   label: 'Valider' },
      { code: 'ventes_pdf',       label: 'Générer PDF' },
      { code: 'ventes_export',    label: 'Exporter' },
      { code: 'ventes_reassign',  label: 'Réassigner' },
    ],
  },
  {
    label: 'Chantiers / Installations',
    codes: [
      { code: 'installation_voir',    label: 'Voir' },
      { code: 'installation_gerer',   label: 'Gérer' },
      { code: 'intervention_gerer',   label: 'Interventions' },
      { code: 'installation_export',  label: 'Exporter' },
      { code: 'technicien_assign',    label: 'Assigner techniciens' },
    ],
  },
  {
    label: 'Après-vente (SAV)',
    codes: [
      { code: 'equipement_voir',  label: 'Voir équipements' },
      { code: 'equipement_gerer', label: 'Gérer équipements' },
      { code: 'sav_voir',         label: 'Voir tickets' },
      { code: 'sav_gerer',        label: 'Gérer tickets' },
      { code: 'sav_export',       label: 'Exporter' },
      { code: 'sav_reassign',     label: 'Réassigner' },
    ],
  },
  {
    label: 'Reporting',
    codes: [
      { code: 'reporting_voir',   label: 'Voir' },
      { code: 'reporting_export', label: 'Exporter' },
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
    label: 'Données sensibles',
    codes: [
      { code: 'prix_achat_voir', label: 'Voir prix d\'achat & marges' },
      // FG20 — groupe « Données sensibles » curé : PII client + marge calculée.
      { code: 'client_pii_voir', label: 'Voir les coordonnées client (tél/email/adresse/GPS)' },
      { code: 'marge_voir', label: 'Voir l\'indicateur de marge' },
    ],
  },
  {
    label: 'Journal d\'activité',
    codes: [
      { code: 'journal_activite_voir', label: 'Voir le journal' },
    ],
  },
  {
    label: 'Visibilité des données',
    codes: [
      { code: 'records_scope_equipe', label: 'Limiter à mon équipe' },
      { code: 'records_scope_sous_arbre', label: 'Limiter à mon sous-arbre' },
    ],
  },
]

const EMPTY_FORM = { nom: '', permissions: [] }

// Construit la grille de groupes à partir des codes RÉELS du backend : on garde
// l'ordre/les libellés connus puis on ajoute un groupe « Autres » pour tout code
// inattendu, afin que l'éditeur reste fidèle à ALL_PERMISSIONS.
function buildGroups(availableCodes) {
  if (!availableCodes || availableCodes.length === 0) return PERMISSION_GROUPS
  const available = new Set(availableCodes)
  const seen = new Set()
  const groups = []
  for (const g of PERMISSION_GROUPS) {
    const codes = g.codes.filter(p => available.has(p.code))
    codes.forEach(p => seen.add(p.code))
    if (codes.length) groups.push({ label: g.label, codes })
  }
  const extras = availableCodes.filter(c => !seen.has(c))
  if (extras.length) {
    groups.push({
      label: 'Autres',
      codes: extras.map(c => ({ code: c, label: c })),
    })
  }
  return groups
}

export default function RolesManagement() {
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  // VX132 — rien tant que l'attente reste imperceptible (< 300 ms), puis
  // spinner discret OU squelette, jamais les deux ensemble.
  const { showSpinner, showSkeleton } = useDelayedLoading(loading)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [formError, setFormError] = useState(null)
  // Catalogue de permissions chargé depuis le backend (source de vérité).
  const [availableCodes, setAvailableCodes] = useState([])
  // Ligne « Utilisateurs » dépliée (id du rôle) — tâche RBAC.
  const [expandedUsers, setExpandedUsers] = useState(null)
  // Dialogue de réassignation après une suppression bloquée.
  const [reassign, setReassign] = useState(null) // { role, target }
  // VX152 — dialogue de confirmation de suppression : contrôlé par état
  // (déclenché depuis rowActions du DataTable) au lieu d'un AlertDialogTrigger
  // par ligne (même AlertDialog, même comportement — VX234 le teste).
  const [pendingDelete, setPendingDelete] = useState(null) // role | null

  const groups = useMemo(() => buildGroups(availableCodes), [availableCodes])
  const viewCodes = useMemo(
    () => availableCodes.filter(c => c.endsWith('_voir')),
    [availableCodes],
  )

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [rolesRes, permsRes] = await Promise.all([
        rolesApi.getRoles(),
        rolesApi.getPermissionsDisponibles(),
      ])
      setRoles(rolesRes.data.results ?? rolesRes.data)
      setAvailableCodes(permsRes.data.permissions ?? [])
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

  // Préréglage « Lecture seule » : ne coche que les codes *_voir.
  const applyReadOnly = () => {
    setForm(f => ({ ...f, permissions: [...viewCodes] }))
  }

  // Indicateur « modifié » : true si le formulaire diffère du rôle édité.
  const isDirty = useMemo(() => {
    if (!editing) return form.nom.trim() !== '' || form.permissions.length > 0
    const a = [...editing.permissions].sort()
    const b = [...form.permissions].sort()
    return editing.nom !== form.nom.trim()
      || a.length !== b.length
      || a.some((c, i) => c !== b[i])
  }, [editing, form])

  const handleSave = async (e) => {
    e.preventDefault()
    setFormError(null)
    // Garde côté client : nom obligatoire.
    if (!form.nom.trim()) {
      setFormError('Le nom du rôle est obligatoire.')
      return
    }
    // Garde côté client : au moins une permission.
    if (form.permissions.length === 0) {
      setFormError('Sélectionnez au moins une permission.')
      return
    }
    // Garde côté client : nom dupliqué dans la société (hors rôle édité).
    const dup = roles.some(r =>
      r.id !== editing?.id
      && r.nom.trim().toLowerCase() === form.nom.trim().toLowerCase())
    if (dup) {
      setFormError('Un rôle portant ce nom existe déjà.')
      return
    }
    setSaving(true)
    try {
      const payload = { nom: form.nom.trim(), permissions: form.permissions }
      if (editing) {
        // Le nom des rôles système est verrouillé : on n'envoie que les perms.
        if (editing.est_systeme) {
          await rolesApi.patchRole(editing.id, { permissions: form.permissions })
        } else {
          await rolesApi.patchRole(editing.id, payload)
        }
      } else {
        await rolesApi.createRole(payload)
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
      setPendingDelete(null)
      await load()
    } catch (err) {
      // Suppression bloquée car des utilisateurs y sont assignés → proposer la
      // réassignation dans le même dialogue (perform_destroy → PermissionDenied).
      // ERR101 — On se base sur users_count seul : le sérialiseur de liste peut
      // omettre le tableau `users` imbriqué, mais le dialogue doit quand même
      // s'ouvrir dès qu'il y a au moins un utilisateur.
      setPendingDelete(null)
      if (role.users_count > 0) {
        setReassign({ role, target: '' })
      } else {
        setError(err.response?.data?.detail || 'Impossible de supprimer ce rôle.')
      }
    }
  }

  // Réassigne tous les utilisateurs du rôle bloqué vers `target`, puis supprime.
  // VX117 — allSettled + rapport nominatif : le rôle n'est JAMAIS supprimé
  // tant qu'un utilisateur n'est pas migré, et une relance ne retente QUE les
  // utilisateurs en échec (jamais un re-PATCH des déjà-migrés).
  const handleReassignAndDelete = async () => {
    const { role, target } = reassign
    if (!target) return
    setError(null)
    const { succeeded, failed } = await resilientMutation(role.users || [], (u) =>
      api.patch(`/users/${u.id}/`, { role: Number(target) }))
    if (failed.length > 0) {
      const noms = failed.map(f => f.item.username || `#${f.item.id}`).join(', ')
      setReassign({
        role: { ...role, users: failed.map(f => f.item), users_count: failed.length },
        target,
      })
      setError(
        `${succeeded.length} utilisateur(s) réassigné(s). Échec pour : ${noms}. `
        + 'Rôle non supprimé — corrigez puis réessayez (seuls les échecs seront retentés).')
      return
    }
    try {
      await rolesApi.deleteRole(role.id)
      setReassign(null)
      setError(null)
      await load()
    } catch (err) {
      setError(err.response?.data?.detail
        || 'Utilisateurs réassignés, mais suppression du rôle impossible.')
    }
  }

  // VX152 — la liste des rôles rejoint le moteur DataTable déjà utilisé par
  // UsersManagement (même dossier admin) : recherche/tri/export gratuits, la
  // grille de permissions de l'éditeur au-dessus reste inchangée. La ligne
  // « Utilisateurs » dépliable devient `renderExpanded` (moteur natif).
  const columns = useMemo(() => [
    {
      id: 'nom',
      header: 'Nom',
      accessor: (r) => r.nom,
      cell: (value) => <span className="font-medium text-foreground">{value}</span>,
    },
    {
      id: 'type',
      header: 'Type',
      width: 140,
      accessor: (r) => (r.est_systeme ? 'Système' : 'Personnalisé'),
      cell: (value, r) => (
        <Badge tone={r.est_systeme ? 'info' : 'success'}>{value}</Badge>
      ),
    },
    {
      id: 'permissions',
      header: 'Permissions',
      width: 150,
      accessor: (r) => r.permissions.length,
      cell: (value) => `${value} permission${value !== 1 ? 's' : ''}`,
    },
    {
      id: 'users_count',
      header: 'Utilisateurs',
      width: 160,
      accessor: (r) => r.users_count,
      cell: (value, r) => (value > 0 ? (
        <Button
          size="sm"
          variant="link"
          className="h-auto p-0 text-xs"
          onClick={() => setExpandedUsers(expandedUsers === r.id ? null : r.id)}
        >
          {value} utilisateur{value !== 1 ? 's' : ''}
          <ChevronDown
            className={expandedUsers === r.id ? 'rotate-180 transition' : 'transition'}
          />
        </Button>
      ) : (
        <span className="text-muted-foreground">0</span>
      )),
    },
  ], [expandedUsers])

  const rowActions = (r) => {
    const actions = [
      { id: 'edit', label: 'Modifier', icon: Pencil, onClick: () => openEdit(r) },
    ]
    if (!r.est_systeme) {
      actions.push({
        id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true,
        separatorBefore: true, onClick: () => setPendingDelete(r),
      })
    }
    return actions
  }

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

      {/* VX117 — masqué pendant le dialogue de réassignation : le rapport
          nominatif s'affiche DANS le dialogue (voir plus bas), pas derrière
          l'overlay. */}
      {error && !reassign && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {/* ── Éditeur de rôle ── */}
      {showForm && (
        <Card className="p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <CardTitle>
              {editing ? `Modifier : ${editing.nom}` : 'Nouveau rôle'}
            </CardTitle>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>
                {form.permissions.length} permission{form.permissions.length !== 1 ? 's' : ''}
              </span>
              {isDirty && <Badge tone="warning">Modifié</Badge>}
            </div>
          </div>
          <Form onSubmit={handleSave} className="gap-5">
            <div className="flex flex-col gap-1.5 sm:max-w-xs">
              <Label htmlFor="role-nom" required={!editing?.est_systeme}>Nom du rôle</Label>
              <Input
                id="role-nom"
                autoFocus
                value={form.nom}
                placeholder="ex: Comptable, Magasinier…"
                disabled={!!editing?.est_systeme}
                onChange={e => setForm(f => ({ ...f, nom: e.target.value }))}
              />
              {editing?.est_systeme && (
                <p className="text-xs text-muted-foreground">
                  Nom verrouillé (rôle système) — les permissions restent éditables.
                </p>
              )}
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Label>Permissions</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={applyReadOnly}
                >
                  <Eye /> Lecture seule
                </Button>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {groups.map(group => {
                  const codes = group.codes.map(p => p.code)
                  const allSelected = codes.every(c => form.permissions.includes(c))
                  return (
                    <Card key={group.label} className="bg-muted/30 shadow-none">
                      <CardHeader className="flex-row items-center justify-between gap-2 p-3">
                        <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {group.label}
                        </CardTitle>
                        <Button
                          type="button"
                          variant="link"
                          size="sm"
                          className="h-auto shrink-0 p-0 text-xs"
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
        <>
          {showSpinner && (
            <Card className="p-5">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner /> Chargement…
              </div>
            </Card>
          )}
          {showSkeleton && (
            <Card className="p-5">
              <div className="space-y-3">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
              </div>
            </Card>
          )}
        </>
      ) : error ? (
        <EmptyState
          icon={ShieldCheck}
          title="Rôles indisponibles"
          description={error}
          action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>}
        />
      ) : roles.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title="Aucun rôle défini"
          description="Créez un rôle personnalisé pour attribuer des permissions précises."
          action={<Button size="sm" onClick={openCreate}><ShieldPlus /> Nouveau rôle</Button>}
        />
      ) : (
        <>
          <DataTable
            data={roles}
            columns={columns}
            getRowId={(r) => r.id}
            rowActions={rowActions}
            searchable
            searchPlaceholder="Rechercher un rôle…"
            exportName="roles"
            emptyTitle="Aucun rôle défini"
            emptyDescription="Aucun rôle ne correspond à cette recherche."
            aria-label="Liste des rôles"
            /* VX152 — liste d'administration courte : table unique (recherche/tri
               conservés), sans repli en cartes ni pagination, donc toutes les lignes
               visibles et un seul rendu du DOM (pas de doublon desktop/mobile ni de
               <select> « lignes par page » parasite). */
            pageSize={roles.length}
            hidePagination
            hideMobileCards
          />
          {/* Panneau « Utilisateurs » du rôle déplié (bouton dans la colonne
              Utilisateurs) — reste hors du moteur DataTable : seuls les rôles
              PORTANT des utilisateurs affichent un déclencheur (contrairement
              au chevron toujours-visible du mécanisme natif renderExpanded). */}
          {expandedUsers != null && (() => {
            const r = roles.find(x => x.id === expandedUsers)
            if (!r) return null
            return (
              <Card className="p-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Utilisateurs — {r.nom}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(r.users || []).map(u => (
                    <Badge key={u.id} tone="neutral">{u.username}</Badge>
                  ))}
                  {(r.users?.length ?? 0) === 0 && (
                    <span className="text-xs text-muted-foreground">Aucun détail disponible.</span>
                  )}
                </div>
              </Card>
            )
          })()}
        </>
      )}

      {/* ── Dialogue de suppression (contrôlé par état — VX152, déclenché
          depuis rowActions du DataTable) ── */}
      <AlertDialog open={!!pendingDelete} onOpenChange={(o) => { if (!o) setPendingDelete(null) }}>
        {pendingDelete && (
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Supprimer ce rôle ?</AlertDialogTitle>
              <AlertDialogDescription>
                {pendingDelete.users_count > 0
                  ? `Le rôle « ${pendingDelete.nom} » est porté par ${pendingDelete.users_count} utilisateur(s). `
                    + 'Vous devrez les réassigner avant la suppression.'
                  : `Le rôle « ${pendingDelete.nom} » sera définitivement supprimé.`}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Annuler</AlertDialogCancel>
              <AlertDialogAction onClick={() => handleDelete(pendingDelete)}>
                Supprimer
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        )}
      </AlertDialog>

      {/* ── Dialogue de réassignation (suppression bloquée) ── */}
      <AlertDialog open={!!reassign} onOpenChange={(o) => { if (!o) setReassign(null) }}>
        {reassign && (
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Réassigner avant de supprimer</AlertDialogTitle>
              <AlertDialogDescription>
                Le rôle « {reassign.role.nom} » est assigné à {reassign.role.users_count} utilisateur(s).
                Choisissez un rôle de remplacement pour les réassigner, puis le rôle sera supprimé.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="flex flex-col gap-2">
              <Label htmlFor="reassign-target" className="flex items-center gap-1.5">
                <Lock className="size-3.5" aria-hidden="true" /> Nouveau rôle
              </Label>
              <Select
                value={reassign.target ? String(reassign.target) : undefined}
                onValueChange={v => setReassign(s => ({ ...s, target: Number(v) }))}
              >
                <SelectTrigger id="reassign-target">
                  <SelectValue placeholder="Choisir un rôle…" />
                </SelectTrigger>
                <SelectContent>
                  {/* VX234 — trié par nombre de permissions CROISSANT : un clic
                      hâtif tombe d'abord sur les rôles les moins larges plutôt
                      que sur « Administrateur » en tête de liste alphabétique. */}
                  {roles
                    .filter(r => r.id !== reassign.role.id)
                    .slice()
                    .sort((a, b) => (a.permissions?.length ?? 0) - (b.permissions?.length ?? 0))
                    .map(r => {
                      const wider = (r.permissions?.length ?? 0) > (reassign.role.permissions?.length ?? 0)
                      return (
                        <SelectItem key={r.id} value={String(r.id)}>
                          {r.nom} {r.est_systeme ? '(Système)' : '(Personnalisé)'}
                          {' '}({r.permissions?.length ?? 0} permission{(r.permissions?.length ?? 0) !== 1 ? 's' : ''})
                          {wider ? ' ⚠ plus large' : ''}
                        </SelectItem>
                      )
                    })}
                </SelectContent>
              </Select>
              {reassign.target && (() => {
                const targetRole = roles.find(r => r.id === reassign.target)
                const wider = targetRole
                  && (targetRole.permissions?.length ?? 0) > (reassign.role.permissions?.length ?? 0)
                return wider ? (
                  <Badge tone="warning">⚠ plus large que « {reassign.role.nom} »</Badge>
                ) : null
              })()}
              <p className="text-xs text-muted-foreground">
                Utilisateurs concernés :{' '}
                {(reassign.role.users || []).map(u => u.username).join(', ') || '—'}
              </p>
              {/* VX117 — rapport nominatif visible DANS le dialogue (pas
                  seulement le bandeau de page, masqué par l'overlay). */}
              {error && (
                <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
                  {error}
                </p>
              )}
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel>Annuler</AlertDialogCancel>
              <AlertDialogAction
                disabled={!reassign.target}
                onClick={handleReassignAndDelete}
              >
                Réassigner et supprimer
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        )}
      </AlertDialog>
    </div>
  )
}
