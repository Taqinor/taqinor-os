import { useEffect, useMemo, useState } from 'react'
import { CircleSlash, Plus, Receipt, XOctagon } from 'lucide-react'
import crmApi from '../../api/crmApi'
import monitoringApi from '../../api/monitoringApi'
import {
  Badge, Button, DataTable, EmptyState, IconButton,
  Input, Label, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Spinner, Textarea,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { toast } from '../../ui/confirm'
import { formatMAD, formatDate } from '../../lib/format'
import MonitoringNav from './MonitoringNav'

/* WIR123 — Écran « Abonnements de supervision » : `AbonnementMonitoring`
   (cycle actif/suspendu/résilié) était un modèle backend complet
   (`AbonnementMonitoringViewSet`, FG244/YSUBS3/YSUBS4) sans aucun
   consommateur frontend. Liste + création + facturer/suspendre/résilier
   depuis cet écran, sous Production (comme le reste de la suite monitoring). */

const STATUT_TONE = { actif: 'success', suspendu: 'warning', resilie: 'neutral' }

const EMPTY_FORM = {
  client_id: '',
  installation_id: '',
  periodicite: 'mensuel',
  montant: '',
  date_debut: '',
}

export default function AbonnementsPage() {
  const [abonnements, setAbonnements] = useState([])
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const [resiliation, setResiliation] = useState(null) // abonnement en cours de résiliation
  const [motif, setMotif] = useState('')
  const [busyId, setBusyId] = useState(null)

  const reload = () => monitoringApi.getAbonnements()
    .then((r) => setAbonnements(r.data.results ?? r.data ?? []))
    .catch(() => setAbonnements([]))

  useEffect(() => {
    let active = true
    Promise.all([
      monitoringApi.getAbonnements(),
      crmApi.getClients({ page: 1 }),
    ])
      .then(([a, c]) => {
        if (!active) return
        setAbonnements(a.data.results ?? a.data ?? [])
        setClients(c.data.results ?? c.data ?? [])
      })
      .catch(() => {})
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const clientName = useMemo(() => {
    const map = new Map(clients.map((c) => [String(c.id), c]))
    return (id) => {
      const c = map.get(String(id))
      return c ? (c.nom || c.raison_sociale || `Client #${id}`) : `Client #${id}`
    }
  }, [clients])

  const openCreate = () => {
    setForm(EMPTY_FORM)
    setDialogOpen(true)
  }

  const setField = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    monitoringApi.createAbonnement({
      client_id: form.client_id,
      installation_id: form.installation_id || null,
      periodicite: form.periodicite,
      montant: form.montant,
      date_debut: form.date_debut || undefined,
    })
      .then(() => {
        toast.success('Abonnement créé.')
        setDialogOpen(false)
        reload()
      })
      .catch((err) => toast.error(err?.response?.data?.detail ?? 'Création impossible.'))
      .finally(() => setSaving(false))
  }

  const facturer = (a) => {
    setBusyId(a.id)
    monitoringApi.facturerAbonnement(a.id)
      .then((r) => {
        toast.success(`Facture ${r.data.reference} émise (${formatMAD(r.data.montant_ttc)}).`)
        reload()
      })
      .catch((err) => toast.error(err?.response?.data?.detail ?? 'Facturation impossible.'))
      .finally(() => setBusyId(null))
  }

  const suspendre = (a) => {
    setBusyId(a.id)
    monitoringApi.suspendreAbonnement(a.id)
      .then(() => { toast.success('Abonnement suspendu.'); reload() })
      .catch((err) => toast.error(err?.response?.data?.detail ?? 'Suspension impossible.'))
      .finally(() => setBusyId(null))
  }

  const openResilier = (a) => { setResiliation(a); setMotif('') }

  const confirmerResiliation = () => {
    if (!resiliation) return
    setBusyId(resiliation.id)
    monitoringApi.resilierAbonnement(resiliation.id, motif)
      .then(() => {
        toast.success('Abonnement résilié.')
        setResiliation(null)
        reload()
      })
      .catch((err) => toast.error(err?.response?.data?.detail ?? 'Résiliation impossible.'))
      .finally(() => setBusyId(null))
  }

  const columns = useMemo(() => [
    { id: 'client', header: 'Client', accessor: (r) => clientName(r.client_id) },
    {
      id: 'periodicite', header: 'Périodicité', width: 110,
      accessor: (r) => r.periodicite,
      cell: (v) => (v === 'annuel' ? 'Annuel' : 'Mensuel'),
    },
    {
      id: 'montant', header: 'Montant', width: 130, align: 'right',
      accessor: (r) => Number(r.montant) || 0,
      cell: (v) => formatMAD(v),
    },
    {
      id: 'statut', header: 'Statut', width: 110,
      accessor: (r) => r.statut,
      cell: (v) => <Badge tone={STATUT_TONE[v] ?? 'neutral'}>{v}</Badge>,
    },
    {
      id: 'prochaine_echeance', header: 'Prochaine échéance', width: 150,
      accessor: (r) => r.prochaine_echeance ?? '',
      cell: (v) => (v ? formatDate(v) : '—'),
    },
    {
      id: 'actions', header: '', width: 180, align: 'right',
      accessor: () => '',
      cell: (v, r) => (
        <span className="flex items-center justify-end gap-1">
          {r.statut === 'actif' && (
            <>
              <IconButton
                variant="ghost" label="Facturer la période due" disabled={busyId === r.id}
                onClick={() => facturer(r)}
              >
                <Receipt />
              </IconButton>
              <IconButton
                variant="ghost" label="Suspendre" disabled={busyId === r.id}
                onClick={() => suspendre(r)}
              >
                <CircleSlash />
              </IconButton>
            </>
          )}
          {r.statut !== 'resilie' && (
            <IconButton
              variant="ghost" label="Résilier" disabled={busyId === r.id}
              onClick={() => openResilier(r)}
            >
              <XOctagon />
            </IconButton>
          )}
        </span>
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- facturer/suspendre/openResilier recréés à chaque rendu
  ], [clientName, busyId])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Abonnements de supervision</h1>
        <div className="page-subtitle">
          Revenu récurrent de supervision : périodicité, montant, facturation et résiliation.
        </div>
      </div>
      <MonitoringNav />

      <div className="mb-4 flex justify-end">
        <Button onClick={openCreate}><Plus /> Nouvel abonnement</Button>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : abonnements.length === 0 ? (
        <EmptyState
          title="Aucun abonnement de supervision"
          description="Créez un abonnement pour facturer périodiquement la supervision d'un client."
          className="my-6"
        />
      ) : (
        <DataTable
          data={abonnements}
          columns={columns}
          getRowId={(row) => row.id}
          searchable={false}
          pageSize={25}
          aria-label="Abonnements de supervision"
        />
      )}

      {/* ── Dialogue création ── */}
      <ResponsiveDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        title="Nouvel abonnement de supervision"
      >
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <div>
            <Label htmlFor="ab-client">Client</Label>
            <Select value={form.client_id} onValueChange={(v) => setForm((f) => ({ ...f, client_id: v }))}>
              <SelectTrigger id="ab-client" aria-label="Client"><SelectValue placeholder="Choisir un client…" /></SelectTrigger>
              <SelectContent>
                {clients.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.nom || c.raison_sociale || `Client #${c.id}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="ab-periodicite">Périodicité</Label>
              <Select value={form.periodicite} onValueChange={(v) => setForm((f) => ({ ...f, periodicite: v }))}>
                <SelectTrigger id="ab-periodicite" aria-label="Périodicité"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="mensuel">Mensuel</SelectItem>
                  <SelectItem value="annuel">Annuel</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="ab-montant">Montant par période (MAD)</Label>
              <Input id="ab-montant" type="number" step="any" value={form.montant} onChange={setField('montant')} />
            </div>
            <div>
              <Label htmlFor="ab-debut">Date de début</Label>
              <Input id="ab-debut" type="date" value={form.date_debut} onChange={setField('date_debut')} />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Annuler</Button>
            <Button type="submit" loading={saving} disabled={!form.client_id || !form.montant}>
              Créer
            </Button>
          </div>
        </form>
      </ResponsiveDialog>

      {/* ── Dialogue résiliation (motif) ── */}
      <ResponsiveDialog
        open={!!resiliation}
        onOpenChange={(o) => { if (!o) setResiliation(null) }}
        title="Résilier l'abonnement"
        description="La résiliation est définitive."
      >
        <div className="flex flex-col gap-3">
          <div>
            <Label htmlFor="ab-motif">Motif de résiliation</Label>
            <Textarea id="ab-motif" rows={2} value={motif} onChange={(e) => setMotif(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setResiliation(null)}>Annuler</Button>
            <Button type="button" variant="destructive" loading={busyId === resiliation?.id} onClick={confirmerResiliation}>
              Résilier
            </Button>
          </div>
        </div>
      </ResponsiveDialog>
    </div>
  )
}
