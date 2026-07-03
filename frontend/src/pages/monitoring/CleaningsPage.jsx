import { useEffect, useMemo, useState } from 'react'
import { Droplets, Plus, Trash2 } from 'lucide-react'
import monitoringApi from '../../api/monitoringApi'
import {
  Badge, Button, Card, CardContent, DataTable, EmptyState, IconButton,
  Input, Label, Spinner, Textarea,
} from '../../ui'
import { useConfirmDialog, toast } from '../../ui/confirm'
import { formatDate, formatPercent } from '../../lib/format'
import MonitoringNav from './MonitoringNav'
import SystemPicker from './SystemPicker'
import useSupervisedSystems from './useSupervisedSystems'

/* WR7 — Journal de nettoyages + évaluation de salissure (FG283).
   Liste et enregistre les nettoyages (bornes pour l'estimation d'encrassement)
   d'un système, et affiche l'évaluation de salissure (chute de PR + reco de
   nettoyage) depuis /monitoring/configs/{id}/soiling/. */

const todayISO = () => new Date().toISOString().slice(0, 10)

export default function CleaningsPage() {
  const { confirmDelete } = useConfirmDialog()
  const { systems, loading: loadingSystems } = useSupervisedSystems()
  const [selectedId, setSelectedId] = useState('')

  const [cleanings, setCleanings] = useState([])
  const [soiling, setSoiling] = useState(null)
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ date: todayISO(), note: '' })
  const [saving, setSaving] = useState(false)

  const selected = useMemo(
    () => systems.find((s) => String(s.id) === String(selectedId)) || null,
    [systems, selectedId])
  const installationId = selected?.installation

  const reload = (cfgId, instId) => {
    if (!cfgId || !instId) return
    monitoringApi.getCleanings({ installation: instId })
      .then((r) => setCleanings(r.data.results ?? r.data ?? []))
      .catch(() => setCleanings([]))
    monitoringApi.getSoiling(cfgId)
      .then((r) => setSoiling(r.data))
      .catch(() => setSoiling(null))
  }

  useEffect(() => {
    if (!selectedId || !installationId) return undefined
    let active = true
    const load = async () => {
      await Promise.resolve()
      if (!active) return
      setLoading(true)
      try {
        const [c, s] = await Promise.all([
          monitoringApi.getCleanings({ installation: installationId }),
          monitoringApi.getSoiling(selectedId),
        ])
        if (active) {
          setCleanings(c.data.results ?? c.data ?? [])
          setSoiling(s.data)
        }
      } catch {
        if (active) { setCleanings([]); setSoiling(null) }
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [selectedId, installationId])

  const addCleaning = (e) => {
    e.preventDefault()
    setSaving(true)
    monitoringApi.addCleaning({
      installation: installationId,
      date: form.date,
      note: form.note,
    })
      .then(() => {
        toast.success('Nettoyage enregistré.')
        setForm({ date: todayISO(), note: '' })
        reload(selectedId, installationId)
      })
      .catch(() => toast.error('Échec de l’enregistrement du nettoyage.'))
      .finally(() => setSaving(false))
  }

  const remove = async (c) => {
    const ok = await confirmDelete({
      title: 'Supprimer ce nettoyage ?',
      description: `Le nettoyage du ${formatDate(c.date)} sera supprimé.`,
    })
    if (!ok) return
    monitoringApi.deleteCleaning(c.id)
      .then(() => {
        toast.success('Nettoyage supprimé.')
        reload(selectedId, installationId)
      })
      .catch(() => toast.error('Suppression impossible.'))
  }

  const columns = useMemo(() => [
    { id: 'date', header: 'Date', width: 160, accessor: (r) => r.date, cell: (v, r) => formatDate(r.date) },
    { id: 'note', header: 'Note', accessor: (r) => r.note ?? '' },
    {
      id: 'actions', header: '', width: 70, align: 'right',
      accessor: () => '',
      cell: (v, r) => (
        <IconButton variant="ghost" label="Supprimer" onClick={() => remove(r)}>
          <Trash2 />
        </IconButton>
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- remove recréé par rendu
  ], [])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Nettoyages</h1>
        <div className="page-subtitle">
          Journal des nettoyages de panneaux et estimation de la perte par salissure.
        </div>
      </div>
      <MonitoringNav />

      <div className="mb-4">
        <SystemPicker
          systems={systems}
          loading={loadingSystems}
          value={selectedId}
          onChange={setSelectedId}
        />
      </div>

      {!loadingSystems && systems.length === 0 ? (
        <EmptyState
          title="Aucun système supervisé"
          description="Configurez la supervision d'un système depuis l'écran Relevés pour suivre ses nettoyages."
          className="my-6"
        />
      ) : !selectedId ? (
        <EmptyState
          title="Choisissez un système"
          description="Sélectionnez un système supervisé pour voir et enregistrer ses nettoyages."
          className="my-6"
        />
      ) : (
        <div className="flex flex-col gap-4">
          {/* Évaluation de salissure */}
          {soiling && !loading && (
            <Card>
              <CardContent className="flex flex-wrap items-center gap-x-8 gap-y-3 p-4" data-testid="soiling-card">
                <div>
                  <div className="text-xs text-muted-foreground">Perte estimée (salissure)</div>
                  <div className="font-medium tabular-nums">
                    {soiling.estimated_soiling_loss_pct != null
                      ? formatPercent(soiling.estimated_soiling_loss_pct, { decimals: 1 })
                      : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Dernier nettoyage</div>
                  <div className="font-medium">
                    {soiling.last_cleaning_date ? formatDate(soiling.last_cleaning_date) : 'jamais'}
                    {soiling.days_since_cleaning != null && ` (${soiling.days_since_cleaning} j)`}
                  </div>
                </div>
                <Badge tone={soiling.recommend_cleaning ? 'warning' : 'success'}>
                  <Droplets className="size-3.5" aria-hidden="true" />
                  {soiling.recommend_cleaning ? 'Nettoyage recommandé' : 'Aucun nettoyage requis'}
                </Badge>
                {soiling.recommend_cleaning && soiling.reasons?.length > 0 && (
                  <span className="text-xs text-muted-foreground">
                    {soiling.reasons.join(' · ')}
                  </span>
                )}
              </CardContent>
            </Card>
          )}

          {/* Saisie d'un nettoyage */}
          <Card>
            <CardContent className="p-4">
              <div className="mb-3 text-sm font-semibold">Enregistrer un nettoyage</div>
              <form onSubmit={addCleaning} noValidate className="flex flex-wrap items-end gap-3">
                <div>
                  <Label htmlFor="c-date">Date</Label>
                  <Input id="c-date" type="date" value={form.date} onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))} required />
                </div>
                <div className="min-w-[16rem] flex-1">
                  <Label htmlFor="c-note">Note</Label>
                  <Textarea id="c-note" rows={1} value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} />
                </div>
                <Button type="submit" loading={saving}><Plus /> Ajouter</Button>
              </form>
            </CardContent>
          </Card>

          {/* Journal */}
          {loading ? (
            <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
          ) : cleanings.length === 0 ? (
            <EmptyState
              title="Aucun nettoyage"
              description="Aucun nettoyage enregistré pour ce système."
              className="my-4"
            />
          ) : (
            <DataTable
              data={cleanings}
              columns={columns}
              getRowId={(row) => row.id}
              searchable={false}
              pageSize={25}
              aria-label="Journal des nettoyages"
            />
          )}
        </div>
      )}
    </div>
  )
}
