import { useEffect, useMemo, useRef, useState } from 'react'
import { LogOut, Upload, Pencil, MonitorSmartphone, Ban } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Segmented, Button, Badge, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input,
} from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatNumber, formatDate, formatDateTime } from '../../lib/format'
import rhApi from '../../api/rhApi'

/* ============================================================================
   UX24 — Temps & présence.
   ----------------------------------------------------------------------------
   Vues : Pointages (arrivée/départ), Roster (affectations d'équipe), Présences
   chantier, Heures supplémentaires. Le pointage départ passe par l'@action
   serveur (durée calculée côté serveur). Export paie déclenché depuis la barre
   d'actions.
   ========================================================================== */

const VUES = [
  { value: 'pointages', label: 'Pointages' },
  { value: 'roster', label: 'Roster' },
  { value: 'presences', label: 'Présences chantier' },
  { value: 'heures_supp', label: 'Heures supp.' },
  { value: 'devices', label: 'Kiosque' },
]

export default function Temps() {
  const { confirmDelete } = useConfirmDialog()
  const [vue, setVue] = useState('pointages')
  const [pointages, setPointages] = useState([])
  const [roster, setRoster] = useState([])
  const [presences, setPresences] = useState([])
  const [heuresSupp, setHeuresSupp] = useState([])
  const [devices, setDevices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [correctionFor, setCorrectionFor] = useState(null)
  const [nouveauToken, setNouveauToken] = useState(null)
  const fileRef = useRef(null)

  const recharger = () => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([
      rhApi.getPointages(),
      rhApi.getRoster(),
      rhApi.getPresencesChantier(),
      rhApi.getHeuresSupp(),
      rhApi.getDevicesKiosque(),
    ])
      .then(([pRes, rRes, prRes, hRes, dRes]) => {
        if (!vivant) return
        setPointages(unwrap(pRes.data))
        setRoster(unwrap(rRes.data))
        setPresences(unwrap(prRes.data))
        setHeuresSupp(unwrap(hRes.data))
        setDevices(unwrap(dRes.data))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les temps & présences.')
        toast.error('Impossible de charger les temps & présences.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(recharger, [])

  const pointerDepart = async (p) => {
    try {
      await rhApi.pointagerDepart(p.id)
      toast.success('Départ pointé.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Pointage impossible.')
    }
  }

  // XRH13 — import CSV pointeuse externe.
  const importerCsv = async (e) => {
    const file = e.target.files?.[0]
    if (fileRef.current) fileRef.current.value = ''
    if (!file) return
    try {
      const res = await rhApi.importPointageCsv(file)
      const d = res.data || {}
      const crees = d.crees ?? d.imported ?? 0
      const erreurs = Array.isArray(d.erreurs) ? d.erreurs.length : (d.erreurs ?? 0)
      toast.success(`Import terminé : ${crees} pointage(s)${erreurs ? `, ${erreurs} erreur(s)` : ''}.`)
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Import du CSV impossible.')
    }
  }

  // XRH10 — émettre un nouveau device kiosque (token affiché une seule fois).
  const emettreDevice = async () => {
    const label = window.prompt('Nom du device (ex. « Tablette entrée atelier ») ?')
    if (label === null) return
    try {
      const res = await rhApi.emettreDeviceKiosque({ label })
      setNouveauToken({ label: res.data?.label || label, token: res.data?.token })
      recharger()
    } catch {
      toast.error('Émission du device impossible.')
    }
  }

  const revoquerDevice = async (d) => {
    const ok = await confirmDelete({
      title: 'Révoquer ce device ?',
      description: 'Le kiosque associé ne pourra plus pointer.',
      confirmLabel: 'Révoquer',
    })
    if (!ok) return
    try {
      await rhApi.revoquerDeviceKiosque(d.id)
      toast.success('Device révoqué.')
      recharger()
    } catch {
      toast.error('Révocation impossible.')
    }
  }

  const exporterPaie = async () => {
    try {
      const res = await rhApi.exportPaiePointages()
      const n = Array.isArray(res.data) ? res.data.length : (res.data?.results?.length ?? 0)
      toast.success(`Export paie prêt : ${n} ligne(s).`)
    } catch {
      toast.error('Export paie indisponible.')
    }
  }

  const pointageColumns = useMemo(() => [
    {
      id: 'employe',
      header: 'Employé',
      width: 180,
      accessor: (p) => p.employe_nom || String(p.employe || ''),
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'arrivee',
      header: 'Arrivée',
      width: 160,
      searchable: false,
      accessor: (p) => p.heure_arrivee || '',
      cell: (v) => (v ? formatDateTime(v) : '—'),
    },
    {
      id: 'depart',
      header: 'Départ',
      width: 160,
      searchable: false,
      accessor: (p) => p.heure_depart || '',
      cell: (v) => (v ? formatDateTime(v) : '—'),
    },
    {
      id: 'duree',
      header: 'Durée',
      width: 100,
      align: 'right',
      searchable: false,
      accessor: (p) => Number(p.duree_minutes ?? 0),
      cell: (v) => (v ? `${formatNumber(v / 60, { decimals: 1 })} h` : '—'),
    },
    {
      id: 'type',
      header: 'Type',
      width: 110,
      accessor: (p) => p.type_pointage_display || p.type_pointage || '',
      cell: (v) => v || '—',
    },
  ], [])

  const pointageActions = (p) => {
    const actions = []
    if (p.heure_arrivee && !p.heure_depart) {
      actions.push({ id: 'depart', label: 'Pointer le départ', icon: LogOut, onClick: () => pointerDepart(p) })
    }
    // XRH11 — corriger un pointage (motif obligatoire, audit immuable serveur).
    actions.push({ id: 'corriger', label: 'Corriger', icon: Pencil, onClick: () => setCorrectionFor(p) })
    return actions
  }

  const deviceColumns = useMemo(() => [
    { id: 'label', header: 'Device', width: 220, accessor: (d) => d.label || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'cree', header: 'Créé le', width: 140, searchable: false, accessor: (d) => d.date_creation || '', cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'actif', header: 'Actif', width: 100, accessor: (d) => (d.actif ? 'oui' : 'non'), cell: (_v, d) => <Badge tone={d.actif ? 'success' : 'neutral'}>{d.actif ? 'Actif' : 'Révoqué'}</Badge> },
  ], [])

  const deviceActions = (d) => (d.actif
    ? [{ id: 'revoquer', label: 'Révoquer', icon: Ban, destructive: true, onClick: () => revoquerDevice(d) }]
    : [])

  const rosterColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (r) => r.employe_nom || String(r.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'equipe', header: 'Équipe', width: 140, accessor: (r) => r.equipe || '', cell: (v) => v || '—' },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (r) => r.date || '', cell: (v) => formatDate(v) },
    { id: 'creneau', header: 'Créneau', width: 120, accessor: (r) => r.creneau_display || r.creneau || '', cell: (v) => v || '—' },
  ], [])

  const presenceColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (p) => p.employe_nom || String(p.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'chantier', header: 'Chantier', width: 140, accessor: (p) => String(p.installation_id ?? ''), cell: (v) => v || '—' },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (p) => p.date || '', cell: (v) => formatDate(v) },
    { id: 'statut', header: 'Statut', width: 130, accessor: (p) => p.statut_display || p.statut || '', cell: (v) => v || '—' },
  ], [])

  const heuresColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (h) => h.employe_nom || String(h.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (h) => h.date || '', cell: (v) => formatDate(v) },
    { id: 'total_hs', header: 'Total HS', width: 100, align: 'right', numeric: true, searchable: false, accessor: (h) => Number(h.total_hs ?? 0), cell: (v) => `${formatNumber(v, { decimals: 1 })} h` },
    { id: 'hs_25', header: 'HS 25%', width: 90, align: 'right', numeric: true, searchable: false, accessor: (h) => Number(h.hs_25 ?? 0), cell: (v) => formatNumber(v, { decimals: 1 }) },
    { id: 'hs_50', header: 'HS 50%', width: 90, align: 'right', numeric: true, searchable: false, accessor: (h) => Number(h.hs_50 ?? 0), cell: (v) => formatNumber(v, { decimals: 1 }) },
  ], [])

  const pointagesActions = (
    <div className="flex items-center gap-2">
      <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={importerCsv} />
      <Button variant="outline" onClick={() => fileRef.current?.click()}>
        <Upload size={15} strokeWidth={1.75} aria-hidden="true" />
        Importer CSV
      </Button>
      <Button variant="outline" onClick={exporterPaie}>Export paie</Button>
    </div>
  )

  const config = {
    pointages: { title: 'Pointages', columns: pointageColumns, rows: pointages, rowActions: pointageActions, exportName: 'pointages',
      actions: pointagesActions },
    roster: { title: 'Roster', columns: rosterColumns, rows: roster, exportName: 'roster' },
    presences: { title: 'Présences chantier', columns: presenceColumns, rows: presences, exportName: 'presences-chantier' },
    heures_supp: { title: 'Heures supplémentaires', columns: heuresColumns, rows: heuresSupp, exportName: 'heures-supp' },
    devices: { title: 'Devices kiosque', columns: deviceColumns, rows: devices, rowActions: deviceActions, exportName: 'devices-kiosque',
      actions: <Button variant="outline" onClick={emettreDevice}><MonitorSmartphone size={15} strokeWidth={1.75} aria-hidden="true" />Émettre un device</Button> },
  }[vue]

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Temps & présence</h2>
      </div>

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue temps & présence" />

      <ListShell
        title={config.title}
        columns={config.columns}
        rows={config.rows}
        loading={loading}
        error={error}
        searchable
        rowActions={config.rowActions}
        actions={config.actions}
        exportName={config.exportName}
        emptyTitle="Aucune ligne"
        emptyDescription="Aucune donnée pour cette vue."
      />

      {correctionFor && (
        <CorrectionDialog
          pointage={correctionFor}
          onClose={() => setCorrectionFor(null)}
          onSaved={() => { setCorrectionFor(null); recharger() }}
        />
      )}
      {nouveauToken && (
        <TokenDialog data={nouveauToken} onClose={() => setNouveauToken(null)} />
      )}
    </div>
  )
}

/* ── XRH11 — Corriger un pointage (motif obligatoire côté serveur) ── */
function CorrectionDialog({ pointage, onClose, onSaved }) {
  const toLocal = (iso) => {
    if (!iso) return ''
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }
  const [arrivee, setArrivee] = useState(toLocal(pointage.heure_arrivee))
  const [depart, setDepart] = useState(toLocal(pointage.heure_depart))
  const [motif, setMotif] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!motif.trim()) { setServerError('Un motif est obligatoire.'); return }
    setSaving(true)
    setServerError(null)
    try {
      const payload = { motif }
      if (arrivee) payload.heure_arrivee = new Date(arrivee).toISOString()
      if (depart) payload.heure_depart = new Date(depart).toISOString()
      await rhApi.updatePointage(pointage.id, payload)
      toast.success('Pointage corrigé (audit conservé).')
      onSaved?.()
    } catch (err) {
      setServerError(err?.response?.data?.motif || err?.response?.data?.detail
        || 'Correction impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Corriger le pointage — {pointage.employe_nom || `#${pointage.id}`}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="co-arr">Arrivée</Label>
              <Input id="co-arr" type="datetime-local" value={arrivee} onChange={(e) => setArrivee(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="co-dep">Départ</Label>
              <Input id="co-dep" type="datetime-local" value={depart} onChange={(e) => setDepart(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="co-motif">Motif de la correction</Label>
            <Input id="co-motif" value={motif} onChange={(e) => setMotif(e.target.value)} placeholder="Obligatoire — tracé dans l’audit" />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Corriger'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── XRH10 — Token de device affiché UNE seule fois ── */
function TokenDialog({ data, onClose }) {
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Device « {data.label} » émis</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            Copiez ce jeton maintenant : il ne sera plus jamais affiché. Il
            authentifie le kiosque (en-tête X-Kiosque-Token).
          </p>
          <code className="select-all break-all rounded-md border border-border bg-muted px-3 py-2 font-mono text-sm">
            {data.token || '—'}
          </code>
        </div>
        <DialogFooter>
          <Button type="button" onClick={onClose}>J’ai copié le jeton</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
