// N51 — Production : supervision de la production des systèmes installés.
// L'utilisateur choisit un système installé (chantier réceptionné, parc), voit
// ses relevés récents et peut SAISIR un relevé à la main (le fallback quand
// aucun fournisseur de monitoring n'est configuré). La config de supervision
// (fournisseur / activation) est éditable par responsable/admin. Tout no-ope
// proprement tant qu'aucun fournisseur n'est configuré.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Plus, RefreshCw, Search, CheckCircle2, AlertTriangle } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import monitoringApi from '../../api/monitoringApi'
import {
  Button, Badge, Spinner, EmptyState, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Card, CardContent, DataTable, Switch, Label,
} from '../../ui'
import MonitoringNav from './MonitoringNav'

const todayISO = () => new Date().toISOString().slice(0, 10)

export default function ProductionPage() {
  const [systems, setSystems] = useState([])
  const [loadingSystems, setLoadingSystems] = useState(true)
  const [selectedId, setSelectedId] = useState('')
  const [q, setQ] = useState('')

  const [readings, setReadings] = useState([])
  const [loadingReadings, setLoadingReadings] = useState(false)
  const [config, setConfig] = useState(null)
  const [providers, setProviders] = useState([])
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState(null)

  const [form, setForm] = useState({ date: todayISO(), energy_kwh: '', period_days: 30, note: '' })

  // Charge la liste des systèmes installés (parc).
  useEffect(() => {
    installationsApi.getInstallations({ parc: 1, page: 1 })
      .then((r) => {
        const d = r.data
        setSystems(Array.isArray(d) ? d : (d.results ?? []))
      })
      .catch(() => {})
      .finally(() => setLoadingSystems(false))
    monitoringApi.getProviders().then((r) => setProviders(r.data ?? [])).catch(() => {})
  }, [])

  const selected = useMemo(
    () => systems.find((s) => String(s.id) === String(selectedId)) || null,
    [systems, selectedId])

  // ERR100 — Garde anti-réponse périmée : on retient l'installation REQUÊTÉE et
  // on ignore toute réponse tardive si la sélection a changé entre-temps (sinon
  // un relevé chargé pour un ancien système écrase le système courant).
  const currentInstallationRef = useRef(selectedId)
  useEffect(() => { currentInstallationRef.current = selectedId }, [selectedId])

  const reloadReadings = (id) => {
    if (!id) return
    const isStale = () => String(currentInstallationRef.current) !== String(id)
    monitoringApi.getReadings({ installation: id })
      .then((r) => { if (!isStale()) setReadings(r.data.results ?? r.data ?? []) })
      .catch(() => { if (!isStale()) setReadings([]) })
      .finally(() => { if (!isStale()) setLoadingReadings(false) })
    monitoringApi.getConfigForInstallation(id)
      .then((r) => {
        if (isStale()) return
        const rows = r.data.results ?? r.data ?? []
        setConfig(rows[0] ?? { installation: id, provider: 'noop', enabled: false })
      })
      .catch(() => { if (!isStale()) setConfig({ installation: id, provider: 'noop', enabled: false }) })
  }

  useEffect(() => {
    if (!selectedId) return undefined
    let active = true
    const load = async () => {
      // setState seulement APRÈS un await (pas de setState synchrone en effet).
      await Promise.resolve()
      if (!active) return
      setLoadingReadings(true)
      try {
        const r = await monitoringApi.getReadings({ installation: selectedId })
        if (active) setReadings(r.data.results ?? r.data ?? [])
      } catch {
        if (active) setReadings([])
      } finally {
        if (active) setLoadingReadings(false)
      }
      try {
        const r = await monitoringApi.getConfigForInstallation(selectedId)
        if (!active) return
        const rows = r.data.results ?? r.data ?? []
        setConfig(rows[0] ?? { installation: selectedId, provider: 'noop', enabled: false })
      } catch {
        if (active) setConfig({ installation: selectedId, provider: 'noop', enabled: false })
      }
    }
    load()
    return () => { active = false }
  }, [selectedId])

  const filteredSystems = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return systems
    return systems.filter((s) =>
      (s.reference ?? '').toLowerCase().includes(needle)
      || (s.client_nom ?? '').toLowerCase().includes(needle))
  }, [systems, q])

  const addReading = (e) => {
    e.preventDefault()
    setMsg(null)
    monitoringApi.addReading({
      installation: selectedId,
      date: form.date,
      energy_kwh: form.energy_kwh,
      period_days: form.period_days,
      note: form.note,
    })
      .then(() => {
        setForm({ date: todayISO(), energy_kwh: '', period_days: 30, note: '' })
        setMsg({ ok: true, text: 'Relevé enregistré.' })
        reloadReadings(selectedId)
      })
      .catch(() => setMsg({ ok: false, text: 'Échec de l’enregistrement du relevé.' }))
  }

  const saveConfig = (patch) => {
    if (!config) return
    const next = { ...config, ...patch }
    setConfig(next)
    monitoringApi.saveConfig(config.id, {
      installation: selectedId,
      provider: next.provider,
      enabled: next.enabled,
    })
      .then((r) => setConfig(r.data))
      .catch(() => setMsg({ ok: false, text: 'Échec de la sauvegarde de la configuration.' }))
  }

  const syncNow = () => {
    if (!config?.id) return
    setSyncing(true)
    setMsg(null)
    monitoringApi.syncNow(config.id)
      .then((r) => {
        const d = r.data
        setMsg({
          ok: true,
          text: d.imported > 0
            ? `${d.imported} relevé(s) importé(s).`
            : 'Aucun relevé importé (aucun fournisseur configuré).',
        })
        reloadReadings(selectedId)
      })
      .catch(() => setMsg({ ok: false, text: 'Échec de la synchronisation.' }))
      .finally(() => setSyncing(false))
  }

  const columns = useMemo(() => [
    { id: 'date', header: 'Date', width: 130, accessor: (r) => r.date },
    {
      id: 'energy_kwh', header: 'Énergie (kWh)', width: 140, align: 'right',
      accessor: (r) => Number(r.energy_kwh) || 0,
      cell: (v, r) => `${r.energy_kwh} kWh`,
    },
    { id: 'period_days', header: 'Période (j)', width: 110, align: 'right', accessor: (r) => r.period_days },
    {
      id: 'source', header: 'Source', width: 130,
      accessor: (r) => r.source_display ?? r.source,
      cell: (v) => <Badge tone={v === 'Automatique' ? 'primary' : 'neutral'}>{v}</Badge>,
    },
    { id: 'note', header: 'Note', accessor: (r) => r.note ?? '' },
  ], [])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Production</h1>
        <div className="page-subtitle">
          Supervision de la production des systèmes installés (relevés manuels ou automatiques).
        </div>
      </div>
      <MonitoringNav />

      <div className="mb-3 flex flex-wrap items-end gap-2">
        <div className="min-w-[14rem] flex-1">
          <Input
            type="search"
            leading={<Search />}
            placeholder="Rechercher un système (réf, client)…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Rechercher un système installé"
          />
        </div>
        <div className="min-w-[18rem]">
          <Select value={String(selectedId)} onValueChange={setSelectedId}>
            <SelectTrigger aria-label="Choisir un système installé"><SelectValue placeholder="Choisir un système installé…" /></SelectTrigger>
            <SelectContent>
              {filteredSystems.map((s) => (
                <SelectItem key={s.id} value={String(s.id)}>
                  {s.reference}{s.client_nom ? ` — ${s.client_nom}` : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {loadingSystems ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : systems.length === 0 ? (
        <EmptyState
          title="Aucun système installé"
          description="Un chantier rejoint le parc dès qu'il atteint « Réceptionné »."
          className="my-6"
        />
      ) : !selected ? (
        <EmptyState
          title="Choisissez un système"
          description="Sélectionnez un système installé pour voir et saisir sa production."
          className="my-6"
        />
      ) : (
        <div className="flex flex-col gap-4">
          {msg && (
            <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${msg.ok ? 'border-success/40 text-success' : 'border-destructive/40 text-destructive'}`}>
              {msg.ok ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />} {msg.text}
            </div>
          )}

          {/* Configuration de supervision (N50) */}
          <Card>
            <CardContent className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold">Supervision automatique</div>
                  <div className="text-xs text-muted-foreground">
                    Sans fournisseur configuré, la production se saisit à la main.
                  </div>
                </div>
                <Button type="button" size="sm" variant="outline" onClick={syncNow} disabled={syncing || !config?.id}>
                  <RefreshCw className={syncing ? 'animate-spin' : ''} /> Synchroniser maintenant
                </Button>
              </div>
              <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-[14rem]">
                  <Label>Fournisseur</Label>
                  <Select value={config?.provider ?? 'noop'} onValueChange={(v) => saveConfig({ provider: v })}>
                    <SelectTrigger aria-label="Fournisseur de supervision"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {providers.map((p) => (
                        <SelectItem key={p.key} value={p.key}>{p.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <Switch checked={!!config?.enabled} onCheckedChange={(v) => saveConfig({ enabled: v })} />
                  Activée
                </label>
              </div>
            </CardContent>
          </Card>

          {/* Saisie manuelle (N51) */}
          <Card>
            <CardContent className="p-4">
              <div className="mb-3 text-sm font-semibold">Saisir un relevé</div>
              <form onSubmit={addReading} noValidate className="flex flex-wrap items-end gap-3">
                <div>
                  <Label>Date</Label>
                  <Input type="date" value={form.date} onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))} required />
                </div>
                <div>
                  <Label>Énergie (kWh)</Label>
                  <Input type="number" step="any" value={form.energy_kwh}
                         onChange={(e) => setForm((f) => ({ ...f, energy_kwh: e.target.value }))} required />
                </div>
                <div>
                  <Label>Période (jours)</Label>
                  <Input type="number" step="any" value={form.period_days}
                         onChange={(e) => setForm((f) => ({ ...f, period_days: e.target.value }))} />
                </div>
                <div className="min-w-[12rem] flex-1">
                  <Label>Note</Label>
                  <Input value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} />
                </div>
                <Button type="submit"><Plus /> Ajouter</Button>
              </form>
            </CardContent>
          </Card>

          {/* Relevés récents */}
          {loadingReadings ? (
            <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
          ) : readings.length === 0 ? (
            <EmptyState
              title="Aucun relevé"
              description="Aucun relevé de production pour ce système. Saisissez-en un ci-dessus."
              className="my-4"
            />
          ) : (
            <DataTable
              data={readings}
              columns={columns}
              getRowId={(row) => row.id}
              searchable={false}
              pageSize={25}
              aria-label="Relevés de production"
            />
          )}
        </div>
      )}
    </div>
  )
}
