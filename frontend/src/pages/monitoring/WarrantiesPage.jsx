import { useEffect, useMemo, useState } from 'react'
import { BadgeCheck, LineChart, Pencil, Plus, Trash2 } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import monitoringApi from '../../api/monitoringApi'
import {
  Badge, Button, Card, CardContent, DataTable, EmptyState, IconButton,
  Input, Label, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Spinner, Textarea,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { useConfirmDialog, toast } from '../../ui/confirm'
import { BarArrondie, ChartEmpty, resolveColor } from '../../ui/charts'
import { formatMAD, formatNumber, formatPercent } from '../../lib/format'
import MonitoringNav from './MonitoringNav'
// VX132 — anti-scintillement propagé (voir InstallationsPage.jsx).
import { useDelayedLoading } from '../../hooks/useDelayedLoading'

/* WR6 — Garanties de production (FG282/FG284) : CRUD des garanties par
   système + statut annuel (réel vs garanti dégradé → manque / compensation)
   + courbe de dégradation superposée (dérive anormale → recours fabricant). */

const EMPTY_FORM = {
  installation: '',
  guaranteed_year1_kwh: '',
  degradation_pct_per_year: '0.5',
  start_year: String(new Date().getFullYear()),
  tolerance_pct: '5',
  compensation_mad_per_kwh: '0',
  note: '',
}

export default function WarrantiesPage() {
  const { confirmDelete } = useConfirmDialog()
  const [warranties, setWarranties] = useState([])
  const [installations, setInstallations] = useState([])
  const [loading, setLoading] = useState(true)

  // Dialogue création / édition.
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState(null) // garantie en cours d'édition
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  // Détail : statut + courbe de la garantie sélectionnée.
  const [selected, setSelected] = useState(null)
  const [status, setStatus] = useState(null)
  const [curve, setCurve] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  // VX132 — rien tant que l'attente reste imperceptible (< 300 ms).
  const { showSpinner: showLoadingSpinner } = useDelayedLoading(loading)
  const { showSpinner: showDetailSpinner } = useDelayedLoading(loadingDetail)

  const nameOf = useMemo(() => {
    const map = new Map(installations.map((i) => [i.id, i]))
    return (id) => {
      const inst = map.get(id)
      return inst
        ? `${inst.reference}${inst.client_nom ? ` — ${inst.client_nom}` : ''}`
        : `Système #${id}`
    }
  }, [installations])

  const reload = () => monitoringApi.getWarranties()
    .then((r) => setWarranties(r.data.results ?? r.data ?? []))
    .catch(() => setWarranties([]))

  useEffect(() => {
    let active = true
    Promise.all([
      monitoringApi.getWarranties(),
      installationsApi.getInstallations({ parc: 1, page: 1 }),
    ])
      .then(([w, i]) => {
        if (!active) return
        setWarranties(w.data.results ?? w.data ?? [])
        setInstallations(i.data.results ?? i.data ?? [])
      })
      .catch(() => {})
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!selected) return undefined
    let active = true
    const load = async () => {
      // setState seulement APRÈS un await (pas de setState synchrone en effet).
      await Promise.resolve()
      if (!active) return
      setLoadingDetail(true)
      try {
        const [s, c] = await Promise.all([
          monitoringApi.getWarrantyStatus(selected.id),
          monitoringApi.getWarrantyCurve(selected.id),
        ])
        if (active) { setStatus(s.data); setCurve(c.data) }
      } catch {
        if (active) { setStatus(null); setCurve(null) }
      } finally {
        if (active) setLoadingDetail(false)
      }
    }
    load()
    return () => { active = false }
  }, [selected])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setDialogOpen(true)
  }

  const openEdit = (w) => {
    setEditing(w)
    setForm({
      installation: String(w.installation),
      guaranteed_year1_kwh: String(w.guaranteed_year1_kwh ?? ''),
      degradation_pct_per_year: String(w.degradation_pct_per_year ?? ''),
      start_year: String(w.start_year ?? ''),
      tolerance_pct: String(w.tolerance_pct ?? ''),
      compensation_mad_per_kwh: String(w.compensation_mad_per_kwh ?? ''),
      note: w.note ?? '',
    })
    setDialogOpen(true)
  }

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    monitoringApi.saveWarranty(editing?.id, {
      installation: form.installation,
      guaranteed_year1_kwh: form.guaranteed_year1_kwh,
      degradation_pct_per_year: form.degradation_pct_per_year,
      start_year: form.start_year,
      tolerance_pct: form.tolerance_pct,
      compensation_mad_per_kwh: form.compensation_mad_per_kwh,
      note: form.note,
    })
      .then(() => {
        toast.success(editing ? 'Garantie mise à jour.' : 'Garantie créée.')
        setDialogOpen(false)
        reload()
      })
      .catch(() => toast.error('Échec de l’enregistrement de la garantie.'))
      .finally(() => setSaving(false))
  }

  const remove = async (w) => {
    const ok = await confirmDelete({
      title: 'Supprimer cette garantie ?',
      description: `La garantie de production de « ${nameOf(w.installation)} » sera supprimée.`,
    })
    if (!ok) return
    monitoringApi.deleteWarranty(w.id)
      .then(() => {
        toast.success('Garantie supprimée.')
        if (selected?.id === w.id) setSelected(null)
        reload()
      })
      .catch(() => toast.error('Suppression impossible.'))
  }

  const columns = useMemo(() => [
    { id: 'installation', header: 'Système', accessor: (r) => nameOf(r.installation) },
    {
      id: 'guaranteed_year1_kwh', header: 'Garanti année 1', width: 150, align: 'right',
      accessor: (r) => Number(r.guaranteed_year1_kwh) || 0,
      cell: (v, r) => `${formatNumber(r.guaranteed_year1_kwh, { decimals: 0 })} kWh`,
    },
    {
      id: 'degradation_pct_per_year', header: 'Dégradation', width: 120, align: 'right',
      accessor: (r) => Number(r.degradation_pct_per_year) || 0,
      cell: (v, r) => `${formatNumber(r.degradation_pct_per_year, { decimals: 2 })} %/an`,
    },
    { id: 'start_year', header: 'Année 1', width: 100, align: 'right', accessor: (r) => r.start_year },
    {
      id: 'tolerance_pct', header: 'Tolérance', width: 110, align: 'right',
      accessor: (r) => Number(r.tolerance_pct) || 0,
      cell: (v, r) => formatPercent(r.tolerance_pct, { decimals: 1 }),
    },
    {
      id: 'actions', header: '', width: 140, align: 'right',
      accessor: () => '',
      cell: (v, r) => (
        <span className="flex items-center justify-end gap-1">
          <IconButton variant="ghost" label="Statut et courbe" onClick={() => setSelected(r)}>
            <LineChart />
          </IconButton>
          <IconButton variant="ghost" label="Modifier" onClick={() => openEdit(r)}>
            <Pencil />
          </IconButton>
          <IconButton variant="ghost" label="Supprimer" onClick={() => remove(r)}>
            <Trash2 />
          </IconButton>
        </span>
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- openEdit/remove recréés à chaque rendu ; colonnes rafraîchies via nameOf/selected
  ], [nameOf, selected])

  const curvePoints = useMemo(() => curve?.points ?? [], [curve])
  const curveChart = useMemo(() => curvePoints
    .filter((p) => p.actual_kwh != null && Number(p.guaranteed_kwh) > 0)
    .map((p) => ({
      label: String(p.year),
      value: Math.round((Number(p.actual_kwh) / Number(p.guaranteed_kwh)) * 1000) / 10,
      color: p.anomalous ? resolveColor('danger') : resolveColor('primary'),
    })), [curvePoints])

  const curveColumns = useMemo(() => [
    { id: 'year', header: 'Année', width: 90, accessor: (r) => r.year },
    {
      id: 'guaranteed_kwh', header: 'Garanti (kWh)', width: 140, align: 'right',
      accessor: (r) => Number(r.guaranteed_kwh) || 0,
      cell: (v, r) => formatNumber(r.guaranteed_kwh, { decimals: 0 }),
    },
    {
      id: 'actual_kwh', header: 'Mesuré (kWh)', width: 140, align: 'right',
      accessor: (r) => (r.actual_kwh == null ? -1 : Number(r.actual_kwh)),
      cell: (v, r) => (r.actual_kwh == null ? '—' : formatNumber(r.actual_kwh, { decimals: 0 })),
    },
    {
      id: 'drift_pct', header: 'Dérive', width: 120, align: 'right',
      accessor: (r) => (r.drift_pct == null ? 0 : Number(r.drift_pct)),
      cell: (v, r) => (r.drift_pct == null
        ? '—'
        : (
          <Badge tone={r.anomalous ? 'danger' : 'neutral'}>
            {formatPercent(r.drift_pct, { decimals: 1 })}
          </Badge>
        )),
    },
  ], [])

  const setField = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Garanties de production</h1>
        <div className="page-subtitle">
          Productible garanti par système, écart annuel et courbe de dégradation.
        </div>
      </div>
      <MonitoringNav />

      <div className="mb-4 flex justify-end">
        <Button onClick={openCreate}><Plus /> Nouvelle garantie</Button>
      </div>

      {loading ? (
        showLoadingSpinner && (
          <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
        )
      ) : warranties.length === 0 ? (
        <EmptyState
          title="Aucune garantie de production"
          description="Créez une garantie pour suivre l'écart entre production réelle et productible garanti."
          className="my-6"
        />
      ) : (
        <DataTable
          data={warranties}
          columns={columns}
          getRowId={(row) => row.id}
          searchable={false}
          pageSize={25}
          aria-label="Garanties de production"
        />
      )}

      {/* ── Détail : statut annuel + courbe de dégradation ── */}
      {selected && (
        <div className="mt-6 flex flex-col gap-4" data-testid="warranty-detail">
          <h2 className="font-display text-base font-semibold tracking-tight">
            {nameOf(selected.installation)}
          </h2>
          {loadingDetail ? (
            showDetailSpinner && (
              <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
            )
          ) : (
            <>
              {status?.has_warranty && (
                <Card>
                  <CardContent className="flex flex-wrap items-center gap-x-8 gap-y-3 p-4">
                    <div>
                      <div className="text-xs text-muted-foreground">Année</div>
                      <div className="font-medium tabular-nums">{status.year}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Garanti</div>
                      <div className="font-medium tabular-nums">{formatNumber(status.guaranteed_kwh, { decimals: 0 })} kWh</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Réel</div>
                      <div className="font-medium tabular-nums">{formatNumber(status.actual_kwh, { decimals: 0 })} kWh</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Manque</div>
                      <div className="font-medium tabular-nums">{formatNumber(status.shortfall_kwh, { decimals: 0 })} kWh</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Compensation due</div>
                      <div className="font-medium tabular-nums">{formatMAD(status.compensation_mad)}</div>
                    </div>
                    <Badge tone={status.within_tolerance ? 'success' : 'danger'}>
                      <BadgeCheck className="size-3.5" aria-hidden="true" />
                      {status.within_tolerance ? 'Dans la tolérance' : 'Hors tolérance'}
                    </Badge>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardContent className="p-4">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-semibold">Courbe de dégradation — mesuré / garanti (%)</span>
                    {curve?.manufacturer_recourse && (
                      <Badge tone="danger">Recours fabricant probable</Badge>
                    )}
                  </div>
                  {curveChart.length > 0
                    ? <BarArrondie data={curveChart} height={200} name="Mesuré / garanti" tooltipFormat={(v) => formatPercent(v, { decimals: 1 })} />
                    : <ChartEmpty description="Aucune année avec production mesurée." />}
                  {curvePoints.length > 0 && (
                    <div className="mt-4">
                      <DataTable
                        data={curvePoints}
                        columns={curveColumns}
                        getRowId={(row) => row.year}
                        searchable={false}
                        pageSize={30}
                        aria-label="Courbe garantie par année"
                      />
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      )}

      {/* ── Dialogue création / édition ── */}
      <ResponsiveDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        title={editing ? 'Modifier la garantie' : 'Nouvelle garantie de production'}
        description="Le garanti de l'année N = année 1 × (1 − dégradation)^(N−1)."
      >
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <div>
            <Label htmlFor="w-installation">Système</Label>
            <Select
              value={form.installation}
              onValueChange={(v) => setForm((f) => ({ ...f, installation: v }))}
              disabled={!!editing}
            >
              <SelectTrigger id="w-installation" aria-label="Système installé">
                <SelectValue placeholder="Choisir un système…" />
              </SelectTrigger>
              <SelectContent>
                {installations.map((i) => (
                  <SelectItem key={i.id} value={String(i.id)}>
                    {i.reference}{i.client_nom ? ` — ${i.client_nom}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="w-year1">Garanti année 1 (kWh)</Label>
              <Input id="w-year1" type="number" step="any" value={form.guaranteed_year1_kwh} onChange={setField('guaranteed_year1_kwh')} />
            </div>
            <div>
              <Label htmlFor="w-degradation">Dégradation (%/an)</Label>
              <Input id="w-degradation" type="number" step="any" value={form.degradation_pct_per_year} onChange={setField('degradation_pct_per_year')} />
            </div>
            <div>
              <Label htmlFor="w-start">Année de référence</Label>
              <Input id="w-start" type="number" step="any" value={form.start_year} onChange={setField('start_year')} />
            </div>
            <div>
              <Label htmlFor="w-tolerance">Tolérance (%)</Label>
              <Input id="w-tolerance" type="number" step="any" value={form.tolerance_pct} onChange={setField('tolerance_pct')} />
            </div>
            <div>
              <Label htmlFor="w-compensation">Compensation (MAD/kWh)</Label>
              <Input id="w-compensation" type="number" step="any" value={form.compensation_mad_per_kwh} onChange={setField('compensation_mad_per_kwh')} />
            </div>
          </div>
          <div>
            <Label htmlFor="w-note">Note</Label>
            <Textarea id="w-note" rows={2} value={form.note} onChange={setField('note')} />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Annuler</Button>
            <Button type="submit" loading={saving} disabled={!form.installation}>
              {editing ? 'Enregistrer' : 'Créer'}
            </Button>
          </div>
        </form>
      </ResponsiveDialog>
    </div>
  )
}
