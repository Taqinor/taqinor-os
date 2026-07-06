// FG83 — Réclamations garantie fournisseur (flux RMA) : trace les échanges
// avec le fournisseur (Huawei / VEICHI / fabricant panneaux) depuis le
// signalement jusqu'à la résolution (remplacement/avoir/réparation/refus).
// Même patron d'écran que ContratsMaintenance (création + édition inline +
// DataTable).
import { useEffect, useMemo, useState } from 'react'
import {
  Plus, Pencil, Check, X, AlertTriangle, ShieldAlert,
} from 'lucide-react'
import savApi from '../../api/savApi'
import {
  TooltipProvider,
  Button,
  Badge,
  StatusPill,
  Card,
  EmptyState,
  Skeleton,
  Input,
  Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Form, FormField,
  DataTable,
  toast,
} from '../../ui'

const STATUTS = [
  { value: 'ouvert', label: 'Ouvert' },
  { value: 'envoye', label: 'Envoyé au fournisseur' },
  { value: 'en_attente', label: 'En attente de retour' },
  { value: 'resolu', label: 'Résolu' },
  { value: 'refuse', label: 'Refusé' },
]
const STATUT_LABELS = Object.fromEntries(STATUTS.map((s) => [s.value, s.label]))
const STATUT_TONES = {
  ouvert: 'neutral', envoye: 'info', en_attente: 'warning',
  resolu: 'success', refuse: 'danger',
}

const RESOLUTIONS = [
  { value: '', label: '—' },
  { value: 'remplacement', label: 'Remplacement' },
  { value: 'avoir', label: 'Avoir' },
  { value: 'reparation', label: 'Réparation' },
  { value: 'refuse', label: 'Refusé' },
]

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

export function WarrantyClaimStatutPill({ claim }) {
  const tone = STATUT_TONES[claim?.statut] ?? 'neutral'
  const label = STATUT_LABELS[claim?.statut] ?? claim?.statut ?? '—'
  return <StatusPill tone={tone} label={label} />
}

export default function WarrantyClaimsPage() {
  const [rows, setRows] = useState([])
  const [equipements, setEquipements] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [statutFiltre, setStatutFiltre] = useState('')

  const [form, setForm] = useState({
    equipement: '', description: '', rma_ref: '', date_signalement: '',
  })
  const [formError, setFormError] = useState(null)
  const [edit, setEdit] = useState(null) // { id, statut, resolution, rma_ref }

  const load = () => {
    setLoading(true)
    setLoadError(false)
    return savApi.getWarrantyClaims(statutFiltre ? { statut: statutFiltre } : {})
      .then((r) => setRows(r.data.results ?? r.data ?? []))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { load() }, [statutFiltre])
  useEffect(() => {
    savApi.getEquipements()
      .then((r) => setEquipements(r.data.results ?? r.data ?? [])).catch(() => {})
  }, [])

  const visibleRows = useMemo(() => rows, [rows])

  const create = async () => {
    if (!form.equipement) {
      setFormError('Équipement requis.')
      return
    }
    setFormError(null)
    try {
      const payload = {
        equipement: form.equipement,
        description: form.description || '',
      }
      if (form.rma_ref) payload.rma_ref = form.rma_ref
      if (form.date_signalement) payload.date_signalement = form.date_signalement
      await savApi.saveWarrantyClaim(null, payload)
      setForm({ equipement: '', description: '', rma_ref: '', date_signalement: '' })
      toast.success('Réclamation garantie créée')
      load()
    } catch (e) {
      setFormError(e?.response?.data?.detail ?? 'Création impossible.')
    }
  }

  const startEdit = (row) => setEdit({
    id: row.id, statut: row.statut, resolution: row.resolution ?? '',
    rma_ref: row.rma_ref ?? '',
  })
  const saveEdit = async () => {
    try {
      const payload = { statut: edit.statut, rma_ref: edit.rma_ref }
      if (edit.resolution) payload.resolution = edit.resolution
      if (edit.statut === 'resolu' || edit.statut === 'refuse') {
        payload.date_resolution = new Date().toISOString().slice(0, 10)
      }
      if (edit.statut === 'envoye') {
        payload.date_envoi_fournisseur = new Date().toISOString().slice(0, 10)
      }
      await savApi.saveWarrantyClaim(edit.id, payload)
      setEdit(null)
      toast.success('Réclamation mise à jour')
      load()
    } catch { toast.error('Mise à jour impossible.') }
  }

  const columns = [
    {
      id: 'equipement', header: 'Équipement', width: 200,
      accessor: (r) => `${r.equipement_produit ?? '—'} — ${r.equipement_serie ?? 'sans série'}`,
    },
    {
      id: 'fournisseur', header: 'Fournisseur', width: 150,
      accessor: (r) => r.fournisseur_nom_cache || '—',
    },
    {
      id: 'rma_ref', header: 'Réf. RMA', width: 130,
      cell: (_v, row) => (edit?.id === row.id ? (
        <Input className="h-8" value={edit.rma_ref}
               onChange={(e) => setEdit((s) => ({ ...s, rma_ref: e.target.value }))} />
      ) : (row.rma_ref || '—')),
      exportValue: (row) => row.rma_ref || '',
    },
    {
      id: 'statut', header: 'Statut', width: 180,
      cell: (_v, row) => (edit?.id === row.id ? (
        <Select value={edit.statut} onValueChange={(v) => setEdit((e) => ({ ...e, statut: v }))}>
          <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
          <SelectContent>
            {STATUTS.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
          </SelectContent>
        </Select>
      ) : <WarrantyClaimStatutPill claim={row} />),
      exportValue: (row) => STATUT_LABELS[row.statut] ?? row.statut,
    },
    {
      id: 'resolution', header: 'Résolution', width: 160,
      cell: (_v, row) => (edit?.id === row.id ? (
        <Select value={edit.resolution || '__none'}
                onValueChange={(v) => setEdit((e) => ({ ...e, resolution: v === '__none' ? '' : v }))}>
          <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__none">—</SelectItem>
            {RESOLUTIONS.filter((r) => r.value).map((r) => (
              <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (row.resolution_display || '—')),
      exportValue: (row) => row.resolution_display || '',
    },
    {
      id: 'date_signalement', header: 'Signalé le', width: 120,
      accessor: (r) => formatDateFR(r.date_signalement),
    },
    {
      id: 'date_resolution', header: 'Résolu le', width: 120,
      accessor: (r) => formatDateFR(r.date_resolution),
    },
    {
      id: 'actions', header: '', width: 150, sortable: false, searchable: false, hideable: false,
      cell: (_v, row) => (edit?.id === row.id ? (
        <span className="flex items-center gap-1.5">
          <Button variant="outline" size="sm" onClick={saveEdit}><Check /> Enregistrer</Button>
          <Button variant="ghost" size="sm" onClick={() => setEdit(null)}><X /></Button>
        </span>
      ) : (
        <Button variant="ghost" size="sm" onClick={() => startEdit(row)} title="Éditer">
          <Pencil /> Éditer
        </Button>
      )),
    },
  ]

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-6xl flex-col gap-5 p-1">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">
              Réclamations garantie fournisseur (RMA)
            </h1>
            <p className="text-sm text-muted-foreground">
              {visibleRows.length} réclamation{visibleRows.length > 1 ? 's' : ''}
            </p>
          </div>
          <Select value={statutFiltre || '__all'}
                  onValueChange={(v) => setStatutFiltre(v === '__all' ? '' : v)}>
            <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous les statuts</SelectItem>
              {STATUTS.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </header>

        {/* ── Création ── */}
        <Card className="p-4">
          <Form onSubmit={(e) => { e.preventDefault(); create() }}
                className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_2fr_1fr_1fr_auto]">
            <FormField label="Équipement">
              <Select value={form.equipement ? String(form.equipement) : '__none'}
                      onValueChange={(v) => setForm((f) => ({ ...f, equipement: v === '__none' ? '' : v }))}>
                <SelectTrigger><SelectValue placeholder="— Équipement —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Équipement —</SelectItem>
                  {equipements.map((e) => (
                    <SelectItem key={e.id} value={String(e.id)}>
                      {(e.produit_nom ?? 'Produit')} — {e.numero_serie ?? 'sans n° série'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Description">
              <Textarea rows={1} value={form.description}
                        onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
            </FormField>
            <FormField label="Réf. RMA" hint="optionnel">
              <Input value={form.rma_ref}
                     onChange={(e) => setForm((f) => ({ ...f, rma_ref: e.target.value }))} />
            </FormField>
            <FormField label="Signalé le" hint="optionnel">
              <Input type="date" value={form.date_signalement}
                     onChange={(e) => setForm((f) => ({ ...f, date_signalement: e.target.value }))} />
            </FormField>
            <Button type="submit"><Plus /> Créer</Button>
          </Form>
          {formError && (
            <div role="alert"
                 className="mt-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">
              <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
              {formError}
            </div>
          )}
        </Card>

        {loading ? (
          <Card className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </Card>
        ) : loadError ? (
          <EmptyState
            icon={AlertTriangle}
            title="Chargement impossible"
            description="Les réclamations n'ont pas pu être chargées. Réessayez."
            action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>}
          />
        ) : visibleRows.length === 0 ? (
          <EmptyState
            icon={ShieldAlert}
            title="Aucune réclamation"
            description="Créez une réclamation garantie fournisseur (RMA) ci-dessus."
          />
        ) : (
          <DataTable
            data={visibleRows}
            columns={columns}
            getRowId={(row) => row.id}
            searchable={false}
            exportName="warranty-claims"
            emptyTitle="Aucune réclamation"
          />
        )}
      </div>
    </TooltipProvider>
  )
}
