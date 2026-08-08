// PACT100 — Jalons de chantier (portail). `apps.portail.JalonChantierPortail`
// trace une timeline de jalons par chantier (étude → commande → livraison →
// installation → mise en service → réception), prévue pour être vue par le
// client — mais, même remarque honnête que Documents client (PACT99), ni le
// client ni l'équipe n'ont d'écran aujourd'hui : le partage client reste hors
// périmètre. Cet écran construit le côté ERP : créer les jalons d'un chantier
// et les marquer atteints via l'action serveur (qui pose la date du jour
// SEULEMENT si elle est absente — jamais calculée côté client).
import { useEffect, useState } from 'react'
import { Plus, Check, Milestone } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import installationsApi from '../../../api/installationsApi'
import {
  Button, Card, EmptyState, Skeleton, StatusPill, Input, NumberInput,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Form, FormField, DataTable, toast,
} from '../../../ui'

const formatDate = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR') : '—')

export default function JalonsChantierPortailAdmin() {
  const [rows, setRows] = useState([])
  const [chantiers, setChantiers] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busyId, setBusyId] = useState(null)
  const [form, setForm] = useState({ chantier: '', libelle: '', ordre: '0' })

  const load = () => {
    setLoading(true)
    setLoadError(false)
    return portailApi.admin.jalonsChantier.liste()
      .then((r) => setRows(r.data?.results ?? r.data ?? []))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    installationsApi.getInstallations()
      .then((r) => setChantiers(r.data?.results ?? r.data ?? []))
      .catch(() => {})
  }, [])

  const creer = async () => {
    if (!form.chantier || !form.libelle.trim()) return
    try {
      await portailApi.admin.jalonsChantier.creer({
        chantier_id: form.chantier, libelle: form.libelle.trim(), ordre: Number(form.ordre) || 0,
      })
      setForm({ chantier: '', libelle: '', ordre: '0' })
      toast.success('Jalon créé')
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Création impossible.')
    }
  }

  const marquerAtteint = async (row) => {
    setBusyId(row.id)
    try {
      await portailApi.admin.jalonsChantier.marquerAtteint(row.id)
      toast.success('Jalon marqué atteint')
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Marquage impossible.')
    } finally {
      setBusyId(null)
    }
  }

  const chantierLabel = (c) => `#${c.id} — ${c.client_nom || 'Chantier'}`

  const columns = [
    { id: 'chantier', header: 'Chantier', width: 110, accessor: (r) => (r.chantier_id ? `#${r.chantier_id}` : '—') },
    { id: 'libelle', header: 'Jalon', width: 180, accessor: (r) => r.libelle },
    { id: 'ordre', header: 'Ordre', width: 70, accessor: (r) => r.ordre },
    {
      id: 'atteint', header: 'Statut', width: 120, sortable: false,
      cell: (_v, row) => (
        <StatusPill tone={row.atteint ? 'success' : 'neutral'}
                    label={row.atteint ? 'Atteint' : 'Non atteint'} />
      ),
      exportValue: (row) => (row.atteint ? 'Atteint' : 'Non atteint'),
    },
    { id: 'date_jalon', header: 'Date du jalon', width: 130, accessor: (r) => formatDate(r.date_jalon) },
    {
      id: 'actions', header: '', width: 150, sortable: false, searchable: false, hideable: false,
      cell: (_v, row) => (row.atteint ? null : (
        <Button variant="outline" size="sm" disabled={busyId === row.id}
                onClick={() => marquerAtteint(row)}>
          <Check /> Marquer atteint
        </Button>
      )),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Timeline de jalons d'avancement par chantier (étude, commande,
        livraison, installation, mise en service, réception). « Marquer
        atteint » pose la date du jour côté serveur si elle est absente —
        jamais calculée côté client.
      </p>

      <Card className="p-4">
        <Form onSubmit={(e) => { e.preventDefault(); creer() }}
              className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_2fr_1fr_auto]">
          <FormField label="Chantier">
            <Select value={form.chantier ? String(form.chantier) : '__none'}
                    onValueChange={(v) => setForm((f) => ({ ...f, chantier: v === '__none' ? '' : v }))}>
              <SelectTrigger aria-label="Chantier"><SelectValue placeholder="— Chantier —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Chantier —</SelectItem>
                {chantiers.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{chantierLabel(c)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Jalon">
            <Input aria-label="Jalon" value={form.libelle}
                   onChange={(e) => setForm((f) => ({ ...f, libelle: e.target.value }))} />
          </FormField>
          <FormField label="Ordre">
            <NumberInput aria-label="Ordre" value={form.ordre}
                         onChange={(e) => setForm((f) => ({ ...f, ordre: e.target.value }))} />
          </FormField>
          <Button type="submit" disabled={!form.chantier || !form.libelle.trim()}>
            <Plus /> Créer le jalon
          </Button>
        </Form>
      </Card>

      {loading ? (
        <Card className="space-y-2 p-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </Card>
      ) : loadError ? (
        <EmptyState title="Chargement impossible"
                    description="Les jalons n'ont pas pu être chargés. Réessayez."
                    action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>} />
      ) : rows.length === 0 ? (
        <EmptyState icon={Milestone} title="Aucun jalon"
                    description="Créez le premier jalon d'un chantier ci-dessus." />
      ) : (
        <DataTable data={rows} columns={columns} getRowId={(r) => r.id}
                   searchable={false} exportName="jalons-chantier-portail"
                   emptyTitle="Aucun jalon" />
      )}
    </div>
  )
}
