import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Plus, Trash2 } from 'lucide-react'
import api from '../../api/axios'
import reportingApi from '../../api/reportingApi'
import {
  Badge, Button, DataTable, EmptyState, IconButton, Input, Label, MultiSelect,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem, Spinner,
  Switch,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { useConfirmDialog, toast } from '../../ui/confirm'

/* ============================================================================
   XPLT6 — CRUD des alertes de seuil sur KPI AGRÉGÉS (`reporting/kpi-alertes/`).
   ----------------------------------------------------------------------------
   Catalogue FERMÉ (miroir de `KpiAlerte.Kpi` côté backend) : DSO, encours
   échu total, valeur de stock totale. Chaque alerte compare le KPI calculé
   au seuil configuré (opérateur >, >=, <, <=) et notifie une fois par
   franchissement (job Beat quotidien, `deja_notifie` géré serveur — lecture
   seule ici). Réservé responsable/admin (reflète `IsResponsableOrAdmin`).
   ========================================================================== */

const KPI_LABELS = {
  dso: 'DSO (délai moyen de recouvrement, jours)',
  encours_echu_total: 'Encours client échu total (MAD)',
  valeur_stock_totale: 'Valeur de stock totale (MAD)',
}
const KPI_OPTIONS = Object.keys(KPI_LABELS)

const OPERATEUR_LABELS = { sup: '>', sup_egal: '≥', inf: '<', inf_egal: '≤' }
const OPERATEUR_OPTIONS = Object.keys(OPERATEUR_LABELS)

const ROLE_OPTIONS = [
  { value: '', label: 'Aucun rôle (utilisateurs précis uniquement)' },
  { value: 'normal', label: 'Normal' },
  { value: 'responsable', label: 'Responsable' },
  { value: 'admin', label: 'Administrateur' },
]

function nouvelleAlerte() {
  return {
    nom: '', kpi: 'dso', operateur: 'sup', seuil: '',
    destinataire_role: '', destinataires_utilisateurs: [], actif: true,
  }
}

export default function KpiAlertesPage() {
  const { confirmDelete } = useConfirmDialog()
  const [alertes, setAlertes] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(nouvelleAlerte)
  const [saving, setSaving] = useState(false)

  const userOptions = useMemo(
    () => users.map((u) => ({ value: u.id, label: u.username })),
    [users],
  )

  const reload = () => reportingApi.listKpiAlertes()
    .then((r) => setAlertes(r.data?.results ?? r.data ?? []))
    .catch(() => setAlertes([]))

  useEffect(() => {
    let active = true
    Promise.all([reportingApi.listKpiAlertes(), api.get('/users/')])
      .then(([a, u]) => {
        if (!active) return
        setAlertes(a.data?.results ?? a.data ?? [])
        setUsers(u.data?.results ?? u.data ?? [])
      })
      .catch(() => { if (active) setAlertes([]) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const openCreate = () => {
    setEditing(null)
    setForm(nouvelleAlerte())
    setDialogOpen(true)
  }

  const openEdit = (alerte) => {
    setEditing(alerte)
    setForm({
      nom: alerte.nom || '',
      kpi: alerte.kpi,
      operateur: alerte.operateur,
      seuil: alerte.seuil ?? '',
      destinataire_role: alerte.destinataire_role || '',
      destinataires_utilisateurs: alerte.destinataires_utilisateurs || [],
      actif: alerte.actif,
    })
    setDialogOpen(true)
  }

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    const payload = { ...form, seuil: form.seuil === '' ? null : form.seuil }
    const req = editing
      ? reportingApi.updateKpiAlerte(editing.id, payload)
      : reportingApi.createKpiAlerte(payload)
    req
      .then(() => {
        toast.success(editing ? 'Alerte mise à jour.' : 'Alerte créée.')
        setDialogOpen(false)
        reload()
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Échec de l’enregistrement.'))
      .finally(() => setSaving(false))
  }

  const remove = async (alerte) => {
    const ok = await confirmDelete({
      title: 'Supprimer cette alerte ?',
      description: `L'alerte « ${alerte.nom || KPI_LABELS[alerte.kpi]} » sera supprimée.`,
    })
    if (!ok) return
    reportingApi.deleteKpiAlerte(alerte.id)
      .then(() => { toast.success('Alerte supprimée.'); reload() })
      .catch(() => toast.error('Suppression impossible.'))
  }

  const columns = useMemo(() => [
    {
      id: 'nom', header: 'Alerte',
      accessor: (r) => r.nom || r.kpi_label || KPI_LABELS[r.kpi],
      cell: (v, r) => (
        <div>
          <div className="font-medium">{r.nom || r.kpi_label || KPI_LABELS[r.kpi]}</div>
          <div className="text-xs text-muted-foreground">{r.kpi_label || KPI_LABELS[r.kpi]}</div>
        </div>
      ),
    },
    {
      id: 'seuil', header: 'Condition', width: 180,
      accessor: (r) => `${r.operateur_label || OPERATEUR_LABELS[r.operateur]} ${r.seuil}`,
    },
    {
      id: 'derniere_valeur', header: 'Dernière valeur', width: 150,
      accessor: (r) => (r.derniere_valeur ?? '—'),
    },
    {
      id: 'actif', header: 'Statut', width: 120,
      accessor: (r) => (r.actif ? 'Active' : 'Inactive'),
      cell: (v, r) => <Badge tone={r.actif ? 'success' : 'neutral'}>{r.actif ? 'Active' : 'Inactive'}</Badge>,
    },
    {
      id: 'actions', header: '', width: 100, align: 'right',
      accessor: () => '',
      cell: (v, r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" onClick={() => openEdit(r)}>Modifier</Button>
          <IconButton variant="ghost" label="Supprimer" onClick={() => remove(r)}>
            <Trash2 />
          </IconButton>
        </div>
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- callbacks recréés par rendu
  ], [])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Alertes KPI</h1>
        <div className="page-subtitle">
          Seuils configurables sur des indicateurs agrégés (DSO, encours échu,
          valeur de stock) — notification au franchissement.
        </div>
      </div>

      <div className="mb-4 flex justify-end">
        <Button onClick={openCreate}><Plus /> Nouvelle alerte</Button>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : alertes.length === 0 ? (
        <EmptyState
          icon={AlertTriangle}
          title="Aucune alerte KPI"
          description="Créez une alerte pour être notifié quand un indicateur agrégé franchit un seuil."
          className="my-6"
        />
      ) : (
        <DataTable
          data={alertes}
          columns={columns}
          getRowId={(row) => row.id}
          searchable={false}
          pageSize={25}
          aria-label="Alertes KPI"
        />
      )}

      <ResponsiveDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        title={editing ? 'Modifier l’alerte KPI' : 'Nouvelle alerte KPI'}
        description="Le KPI est calculé automatiquement (job quotidien) et comparé au seuil."
      >
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <div>
            <Label htmlFor="ka-nom">Nom (optionnel)</Label>
            <Input
              id="ka-nom" value={form.nom}
              autoFocus
              onChange={(e) => setForm((f) => ({ ...f, nom: e.target.value }))}
              placeholder="Ex. DSO trop élevé"
            />
          </div>

          <div>
            <Label htmlFor="ka-kpi">Indicateur</Label>
            <Select value={form.kpi} onValueChange={(v) => setForm((f) => ({ ...f, kpi: v }))}>
              <SelectTrigger id="ka-kpi"><SelectValue /></SelectTrigger>
              <SelectContent>
                {KPI_OPTIONS.map((k) => <SelectItem key={k} value={k}>{KPI_LABELS[k]}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div className="flex gap-3">
            <div className="w-28">
              <Label htmlFor="ka-op">Opérateur</Label>
              <Select value={form.operateur} onValueChange={(v) => setForm((f) => ({ ...f, operateur: v }))}>
                <SelectTrigger id="ka-op"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {OPERATEUR_OPTIONS.map((o) => <SelectItem key={o} value={o}>{OPERATEUR_LABELS[o]}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="flex-1">
              <Label htmlFor="ka-seuil">Seuil</Label>
              <Input
                id="ka-seuil" type="number" step="any" noValidate
                value={form.seuil}
                onChange={(e) => setForm((f) => ({ ...f, seuil: e.target.value }))}
              />
            </div>
          </div>

          <div>
            <Label htmlFor="ka-role">Destinataires — rôle</Label>
            <Select
              value={form.destinataire_role || 'none'}
              onValueChange={(v) => setForm((f) => ({ ...f, destinataire_role: v === 'none' ? '' : v }))}
            >
              <SelectTrigger id="ka-role"><SelectValue /></SelectTrigger>
              <SelectContent>
                {ROLE_OPTIONS.map((r) => (
                  <SelectItem key={r.value || 'none'} value={r.value || 'none'}>{r.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="ka-users">Destinataires — utilisateurs précis</Label>
            <MultiSelect
              id="ka-users"
              options={userOptions}
              value={form.destinataires_utilisateurs}
              onChange={(vals) => setForm((f) => ({ ...f, destinataires_utilisateurs: vals }))}
              placeholder="Choisir des utilisateurs…"
            />
          </div>

          <div className="flex items-center gap-2">
            <Switch
              checked={form.actif}
              onCheckedChange={(v) => setForm((f) => ({ ...f, actif: v }))}
              id="ka-actif"
            />
            <Label htmlFor="ka-actif">Alerte active</Label>
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Annuler</Button>
            <Button type="submit" loading={saving} disabled={!form.seuil}>
              {editing ? 'Enregistrer' : 'Créer'}
            </Button>
          </div>
        </form>
      </ResponsiveDialog>
    </div>
  )
}
