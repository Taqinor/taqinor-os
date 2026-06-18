import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Download, PackageSearch, AlarmClock, AlertTriangle, RotateCcw, Save } from 'lucide-react'
import { fetchEquipements } from '../../features/sav/store/equipementsSlice'
import savApi from '../../api/savApi'
import importApi, { downloadXlsx } from '../../api/importApi'
import {
  EMPTY_EQUIP_FILTERS,
  EQUIP_STATUTS,
  EQUIP_STATUT_LABELS,
  GARANTIE_FILTRES,
  GARANTIE_ETATS,
  filterEquipements,
  sortEquipements,
  garantieLabel,
} from '../../features/sav/equipement'
import {
  TooltipProvider,
  Button,
  StatusPill,
  Card,
  EmptyState,
  Skeleton,
  Input,
  Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  Form, FormSection, FormField, FormActions, useDirtyGuard,
  DataTable,
  toast,
} from '../../ui'

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

// État de garantie → ton StatusPill (la couleur n'est jamais le seul signal :
// le libellé reste explicite). Aligné sur equipement.js / le serializer backend.
const GARANTIE_TONES = {
  sous_garantie: 'success',
  expire_bientot: 'warning',
  hors_garantie: 'danger',
  non_renseignee: 'neutral',
}

function GarantiePill({ eq }) {
  const etat = eq?.garantie_etat ?? 'non_renseignee'
  return <StatusPill tone={GARANTIE_TONES[etat] ?? 'neutral'} label={garantieLabel(eq)} />
}

function EquipementDetail({ equipement, onClose, onSaved }) {
  const initial = useMemo(() => ({
    numero_serie: equipement.numero_serie ?? '',
    date_pose: equipement.date_pose ?? '',
    statut: equipement.statut ?? 'en_service',
    note: equipement.note ?? '',
  }), [equipement])

  const [fields, setFields] = useState(initial)
  const set = (k, v) => setFields((f) => ({ ...f, [k]: v }))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const dirty = useMemo(
    () => Object.keys(initial).some((k) => (fields[k] ?? '') !== (initial[k] ?? '')),
    [fields, initial],
  )
  useDirtyGuard(dirty)

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const nullable = (v) => (v === '' || v === undefined ? null : v)
      await savApi.updateEquipement(equipement.id, {
        numero_serie: nullable(fields.numero_serie),
        date_pose: nullable(fields.date_pose),
        statut: fields.statut,
        note: nullable(fields.note),
      })
      toast.success('Équipement mis à jour')
      onSaved?.()
      onClose()
    } catch (err) {
      setError(JSON.stringify(err.response?.data ?? err.message))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Sheet open onOpenChange={(o) => { if (!o) onClose() }}>
      <SheetContent side="right" className="w-[min(34rem,calc(100%-2rem))] sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Équipement — {equipement.produit_nom ?? ''}</SheetTitle>
          <SheetDescription>
            Numéro de série, pose et statut. La fin de garantie est recalculée
            automatiquement.
          </SheetDescription>
        </SheetHeader>

        <Form onSubmit={(e) => { e.preventDefault(); save() }} className="gap-5">
          <FormSection title="Identité">
            <FormField label="Produit">
              <Input value={equipement.produit_nom ?? '—'} readOnly />
            </FormField>
            <FormField label="Marque">
              <Input value={equipement.produit_marque ?? '—'} readOnly />
            </FormField>
            <FormField label="Chantier">
              <Input value={equipement.installation_reference ?? '—'} readOnly />
            </FormField>
            <FormField label="Client">
              <Input value={equipement.client_nom ?? '—'} readOnly />
            </FormField>
          </FormSection>

          <FormSection title="Suivi">
            <FormField label="Numéro de série" fullWidth>
              <Input value={fields.numero_serie}
                     onChange={(e) => set('numero_serie', e.target.value)} />
            </FormField>
            <FormField label="Date de pose">
              <Input type="date" value={fields.date_pose ?? ''}
                     onChange={(e) => set('date_pose', e.target.value)} />
            </FormField>
            <FormField label="Statut">
              <Select value={fields.statut} onValueChange={(v) => set('statut', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {EQUIP_STATUTS.map((s) => (
                    <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Note" fullWidth>
              <Textarea rows={2} value={fields.note ?? ''}
                        onChange={(e) => set('note', e.target.value)} />
            </FormField>
          </FormSection>

          <FormSection title="Garantie">
            <FormField label="État" fullWidth
                       hint={equipement.date_fin_garantie_production
                         ? `Garantie production jusqu'au ${formatDateFR(equipement.date_fin_garantie_production)}. La date de fin de garantie est recalculée automatiquement à partir de la durée du produit et de la date de pose.`
                         : 'La date de fin de garantie est recalculée automatiquement à partir de la durée du produit et de la date de pose.'}>
              <div><GarantiePill eq={equipement} /></div>
            </FormField>
          </FormSection>

          {error && (
            <div role="alert"
                 className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
              <span className="break-all">{error}</span>
            </div>
          )}

          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
            <Button type="submit" loading={saving}><Save /> Mettre à jour</Button>
          </FormActions>
        </Form>
      </SheetContent>
    </Sheet>
  )
}

export default function EquipementsPage() {
  const dispatch = useDispatch()
  const { items, loading, error } = useSelector((s) => s.equipements)
  const [filters, setFilters] = useState(EMPTY_EQUIP_FILTERS)
  const [selected, setSelected] = useState(null)

  const reload = () => dispatch(fetchEquipements())
  useEffect(() => { reload() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const setF = (k, v) => setFilters((f) => ({ ...f, [k]: v }))

  const produitOptions = useMemo(() => {
    const seen = new Map()
    for (const it of items) if (it.produit && !seen.has(it.produit)) seen.set(it.produit, it.produit_nom)
    return [...seen.entries()].map(([id, nom]) => ({ id, nom: nom ?? `#${id}` }))
  }, [items])

  const marqueOptions = useMemo(
    () => [...new Set(items.map((it) => it.produit_marque).filter(Boolean))].sort(),
    [items])

  const rows = useMemo(
    () => sortEquipements(filterEquipements(items, filters), 'date_fin_garantie', 'asc'),
    [items, filters])

  const expirantBientot = filters.garantie === 'expire_bientot'
  const hasFilters = filters.q || filters.produit || filters.marque || filters.garantie || filters.statut

  const columns = useMemo(() => [
    {
      id: 'numero_serie',
      header: 'Série',
      width: 150,
      accessor: (r) => r.numero_serie ?? '—',
      cell: (v) => <span className="font-medium">{v}</span>,
    },
    { id: 'produit_nom', header: 'Produit', width: 200, accessor: (r) => r.produit_nom ?? '—' },
    { id: 'produit_marque', header: 'Marque', width: 130, accessor: (r) => r.produit_marque ?? '—' },
    { id: 'installation_reference', header: 'Chantier', width: 140, accessor: (r) => r.installation_reference ?? '—' },
    { id: 'client_nom', header: 'Client', width: 160, accessor: (r) => r.client_nom ?? '—' },
    {
      id: 'statut',
      header: 'Statut',
      width: 120,
      searchable: false,
      accessor: (r) => EQUIP_STATUT_LABELS[r.statut] ?? r.statut,
    },
    {
      id: 'date_fin_garantie',
      header: 'Garantie',
      width: 220,
      searchable: false,
      cell: (_v, row) => <GarantiePill eq={row} />,
      exportValue: (row) => garantieLabel(row),
    },
  ], [])

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root flex flex-col gap-5 p-1">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">Parc d'équipements</h1>
            <p className="text-sm text-muted-foreground">
              {rows.length} équipement{rows.length > 1 ? 's' : ''}
            </p>
          </div>
          <Button variant="outline" size="sm"
                  onClick={() => importApi.exportList('equipements', rows.map((r) => r.id))
                    .then((r) => downloadXlsx(r.data, 'equipements.xlsx')).catch(() => {})}>
            <Download /> Exporter Excel
          </Button>
        </header>

        {/* ── Filtres ── */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-[220px] flex-1">
            <Input placeholder="Rechercher (série, produit, chantier, client)…"
                   value={filters.q} onChange={(e) => setF('q', e.target.value)} />
          </div>
          <Select value={filters.produit || '__all'}
                  onValueChange={(v) => setF('produit', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[160px]"><SelectValue placeholder="Tous les produits" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous les produits</SelectItem>
              {produitOptions.map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.marque || '__all'}
                  onValueChange={(v) => setF('marque', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[150px]"><SelectValue placeholder="Toutes les marques" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Toutes les marques</SelectItem>
              {marqueOptions.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.garantie || '__all'}
                  onValueChange={(v) => setF('garantie', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[170px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              {GARANTIE_FILTRES.map((g) => (
                <SelectItem key={g.value || '__all'} value={g.value || '__all'}>{g.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" variant={expirantBientot ? 'default' : 'outline'}
                  onClick={() => setF('garantie', expirantBientot ? '' : 'expire_bientot')}>
            <AlarmClock /> Expirant bientôt
          </Button>
          {hasFilters && (
            <Button size="sm" variant="ghost" onClick={() => setFilters(EMPTY_EQUIP_FILTERS)}>
              <RotateCcw /> Réinitialiser
            </Button>
          )}
        </div>

        {loading ? (
          <Card className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </Card>
        ) : error ? (
          <EmptyState
            icon={AlertTriangle}
            title="Chargement impossible"
            description="Le parc d'équipements n'a pas pu être chargé. Réessayez."
            action={<Button size="sm" variant="outline" onClick={reload}><RotateCcw /> Réessayer</Button>}
          />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={PackageSearch}
            title="Aucun équipement"
            description={hasFilters
              ? 'Aucun équipement ne correspond à vos filtres.'
              : "Aucun équipement. Ajoutez-en depuis la fiche d'un chantier."}
            action={hasFilters
              ? <Button size="sm" variant="outline" onClick={() => setFilters(EMPTY_EQUIP_FILTERS)}><RotateCcw /> Réinitialiser</Button>
              : undefined}
          />
        ) : (
          <DataTable
            data={rows}
            columns={columns}
            getRowId={(row) => row.id}
            searchable={false}
            onRowClick={(row) => setSelected(row)}
            exportName="equipements"
            emptyTitle="Aucun équipement"
            emptyDescription="Aucun équipement ne correspond à votre recherche."
          />
        )}

        {/* Légende garantie */}
        <div className="flex flex-wrap items-center gap-3">
          {Object.entries(GARANTIE_ETATS).map(([k, v]) => (
            <span key={k} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <span aria-hidden="true" className="inline-block size-2.5 rounded-sm"
                    style={{ background: v.color }} />
              {v.label}
            </span>
          ))}
        </div>

        {selected && (
          <EquipementDetail equipement={selected} onClose={() => setSelected(null)}
                            onSaved={reload} />
        )}
      </div>
    </TooltipProvider>
  )
}
