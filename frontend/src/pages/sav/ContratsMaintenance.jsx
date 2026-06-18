// T16 — contrats de maintenance (visites préventives). Liste + vue « à venir »
// (visites dues) + génération à la demande des tickets SAV préventifs (sans
// planificateur, cohérent T7). Création simple (client + périodicité + début).
import { useEffect, useState } from 'react'
import { Download, Cog, Plus, CalendarClock, ClipboardList } from 'lucide-react'
import savApi from '../../api/savApi'
import crmApi from '../../api/crmApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import {
  TooltipProvider,
  Button,
  Badge,
  StatusPill,
  Card,
  EmptyState,
  Skeleton,
  Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Segmented,
  Form, FormField,
  DataTable,
  toast,
} from '../../ui'

const PERIODES = [
  { value: 'mensuel', label: 'Mensuel' },
  { value: 'trimestriel', label: 'Trimestriel' },
  { value: 'semestriel', label: 'Semestriel' },
  { value: 'annuel', label: 'Annuel' },
]
const PERIODE_LABELS = Object.fromEntries(PERIODES.map((p) => [p.value, p.label]))

export function Component() {
  const [rows, setRows] = useState([])
  const [clients, setClients] = useState([])
  const [dueOnly, setDueOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({
    client: '', periodicite: 'annuel', date_debut: '', date_renouvellement: '' })

  const load = () => {
    setLoading(true)
    return savApi.getContrats(dueOnly ? { due: 1 } : {})
      .then((r) => setRows(r.data.results ?? r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [dueOnly]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    crmApi.getClients().then((r) => setClients(r.data.results ?? r.data)).catch(() => {})
  }, [])

  const create = async () => {
    if (!form.client || !form.date_debut) return
    try {
      const payload = { ...form }
      if (!payload.date_renouvellement) delete payload.date_renouvellement
      await savApi.saveContrat(null, payload)
      setForm({
        client: '', periodicite: 'annuel', date_debut: '',
        date_renouvellement: '' })
      toast.success('Contrat ajouté')
      load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Création impossible.') }
  }
  const rapport = async (id) => {
    try {
      const res = await savApi.maintenanceRapportPdf(id)
      openPdfBlob(res.data, `maintenance-contrat-${id}.pdf`)
    } catch { toast.error('Rapport indisponible.') }
  }
  const generer = async () => {
    try {
      const { data } = await savApi.genererVisitesDues()
      toast.success(`${data.tickets_generes} ticket(s) de maintenance généré(s).`)
      load()
    } catch { toast.error('Génération impossible.') }
  }

  const columns = [
    { id: 'client_nom', header: 'Client', width: 200, accessor: (r) => r.client_nom },
    {
      id: 'periodicite', header: 'Périodicité', width: 130,
      accessor: (r) => PERIODE_LABELS[r.periodicite] ?? r.periodicite,
    },
    { id: 'date_debut', header: 'Début', width: 130, accessor: (r) => r.date_debut ?? '—' },
    { id: 'prochaine_visite', header: 'Prochaine visite', width: 150, accessor: (r) => r.prochaine_visite ?? '—' },
    {
      id: 'date_renouvellement', header: 'Renouvellement', width: 170,
      cell: (_v, row) => (
        <span className="flex items-center gap-1.5">
          {row.date_renouvellement || '—'}
          {row.renouvellement_du && <Badge tone="warning">à renouveler</Badge>}
        </span>
      ),
      exportValue: (row) => row.date_renouvellement || '—',
    },
    {
      id: 'statut', header: 'Statut', width: 140, searchable: false,
      cell: (_v, row) => (
        !row.actif ? <StatusPill tone="neutral" label="Inactif" />
          : row.due ? <StatusPill tone="danger" label="Visite due" />
            : <StatusPill tone="success" label="À jour" />
      ),
      exportValue: (row) => (!row.actif ? 'Inactif' : row.due ? 'Visite due' : 'À jour'),
    },
    {
      id: 'actions', header: '', width: 150, sortable: false, searchable: false, hideable: false,
      cell: (_v, row) => (
        <Button variant="outline" size="sm" onClick={() => rapport(row.id)}>
          <Download /> Rapport PDF
        </Button>
      ),
    },
  ]

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-5xl flex-col gap-5 p-1">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">Contrats de maintenance</h1>
            <p className="text-sm text-muted-foreground">
              Visites préventives — {rows.length} contrat{rows.length > 1 ? 's' : ''}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Segmented
              size="sm"
              value={dueOnly ? 'dus' : 'tous'}
              onChange={(v) => setDueOnly(v === 'dus')}
              options={[
                { value: 'tous', label: 'Tous' },
                { value: 'dus', label: 'À venir (dus)' },
              ]}
            />
            <Button variant="outline" size="sm" onClick={generer}>
              <Cog /> Générer les visites dues
            </Button>
          </div>
        </header>

        {/* ── Création ── */}
        <Card className="p-4">
          <Form onSubmit={(e) => { e.preventDefault(); create() }}
                className="grid items-end gap-3 sm:grid-cols-[2fr_1fr_1fr_1fr_auto]">
            <FormField label="Client">
              <Select value={form.client ? String(form.client) : '__none'}
                      onValueChange={(v) => setForm((f) => ({ ...f, client: v === '__none' ? '' : v }))}>
                <SelectTrigger><SelectValue placeholder="— Client —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Client —</SelectItem>
                  {clients.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>{c.nom} {c.prenom || ''}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Périodicité">
              <Select value={form.periodicite}
                      onValueChange={(v) => setForm((f) => ({ ...f, periodicite: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PERIODES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Début">
              <Input type="date" value={form.date_debut}
                     onChange={(e) => setForm((f) => ({ ...f, date_debut: e.target.value }))} />
            </FormField>
            <FormField label="Renouvellement" hint="optionnel">
              <Input type="date" value={form.date_renouvellement}
                     onChange={(e) => setForm((f) => ({ ...f, date_renouvellement: e.target.value }))} />
            </FormField>
            <Button type="submit" disabled={!form.client || !form.date_debut}><Plus /> Ajouter</Button>
          </Form>
        </Card>

        {loading ? (
          <Card className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </Card>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={dueOnly ? CalendarClock : ClipboardList}
            title={dueOnly ? 'Aucune visite due' : 'Aucun contrat'}
            description={dueOnly
              ? 'Aucun contrat n’a de visite due pour le moment.'
              : 'Ajoutez un contrat de maintenance ci-dessus pour planifier les visites préventives.'}
          />
        ) : (
          <DataTable
            data={rows}
            columns={columns}
            getRowId={(row) => row.id}
            searchable={false}
            exportName="contrats-maintenance"
            emptyTitle="Aucun contrat"
          />
        )}
      </div>
    </TooltipProvider>
  )
}
