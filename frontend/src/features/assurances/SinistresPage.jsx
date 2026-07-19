import { useEffect, useMemo, useState } from 'react'
import { ShieldAlert, Plus } from 'lucide-react'
import assurancesApi from './assurancesApi'
import {
  Badge, Button, Segmented, Label, Input, Textarea,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../ui'
import { ListShell } from '../../ui/module'
import { formatMAD, formatDate } from '../../lib/format'
import { SINISTRE_STATUS, SINISTRE_TYPES } from './status'

/* ============================================================================
   NTASS27 — Écran sinistres transverses + suivi indemnisation.
   ----------------------------------------------------------------------------
   Liste filtrable par statut (declare/en_expertise/indemnise/refuse/clos), avec
   bloc indemnisation (réclamé/franchise/indemnisé/reste à charge) sur la fiche
   sélectionnée et bouton « Marquer contesté » (NTASS16). Montants client-safe.
   ========================================================================== */

const STATUT_FILTERS = [
  { value: 'tous', label: 'Tous' },
  ...Object.entries(SINISTRE_STATUS).map(([value, v]) => ({ value, label: v.label })),
]
const TYPE_LABEL = Object.fromEntries(SINISTRE_TYPES.map((t) => [t.value, t.label]))

export default function SinistresPage() {
  const [sinistres, setSinistres] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statutFilter, setStatutFilter] = useState('tous')
  const [selected, setSelected] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const load = () => {
    setLoading(true)
    setError(null)
    assurancesApi
      .getSinistres()
      .then((res) => setSinistres(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les sinistres.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const visible = useMemo(() => sinistres.filter(
    (s) => statutFilter === 'tous' || s.statut === statutFilter,
  ), [sinistres, statutFilter])

  const marquerConteste = (id) => {
    assurancesApi.marquerSinistreConteste(id).then(load)
  }

  const columns = useMemo(() => [
    {
      id: 'reference',
      header: 'N° dossier',
      width: 140,
      accessor: (s) => s.numero_dossier || '',
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span>,
    },
    {
      id: 'type',
      header: 'Type',
      width: 170,
      accessor: (s) => TYPE_LABEL[s.type_sinistre] || s.type_sinistre || '',
    },
    {
      id: 'survenance',
      header: 'Survenance',
      width: 120,
      accessor: (s) => s.date_survenance || '',
      cell: (v) => (v ? formatDate(v) : '—'),
    },
    {
      id: 'estime',
      header: 'Dégâts estimés',
      align: 'right',
      width: 140,
      accessor: (s) => Number(s.montant_estime_degats ?? 0),
      cell: (_v, s) => (
        <span className="tabular-nums">{formatMAD(s.montant_estime_degats ?? 0)}</span>
      ),
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 130,
      accessor: (s) => s.statut || '',
      cell: (v, s) => {
        const st = SINISTRE_STATUS[v]
        return (
          <span className="flex items-center gap-1">
            {st ? <Badge tone={st.tone}>{st.label}</Badge> : '—'}
            {s.conteste && <Badge tone="red">Contesté</Badge>}
          </span>
        )
      },
    },
  ], [])

  return (
    <ListShell
      title="Sinistres transverses"
      subtitle="Déclarations hors véhicule : dommage, RC, décennale, cyber, vol, incendie… Suivi jusqu'à l'indemnisation."
      actions={(
        <Button onClick={() => setShowCreate(true)}>
          <Plus /> Nouveau sinistre
        </Button>
      )}
      columns={columns}
      rows={visible}
      loading={loading}
      error={error}
      searchable
      searchPlaceholder="Rechercher n° dossier, type…"
      exportName="sinistres-assurance"
      emptyTitle="Aucun sinistre"
      emptyDescription="Aucun sinistre ne correspond à ce filtre."
      onRowClick={(s) => setSelected(s)}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          options={STATUT_FILTERS}
          value={statutFilter}
          onChange={setStatutFilter}
          aria-label="Filtrer par statut"
        />
        {error && (
          <Button variant="outline" size="sm" onClick={load}>Réessayer</Button>
        )}
      </div>
      {selected && (
        <div className="rounded-lg border p-3 text-sm">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-semibold">
              {selected.numero_dossier} — indemnisation
            </span>
            {!selected.conteste && selected.statut === 'refuse' && (
              <Button size="sm" variant="outline" onClick={() => marquerConteste(selected.id)}>
                Marquer contesté
              </Button>
            )}
          </div>
          <IndemnisationBloc sinistreId={selected.id} />
          <IndemnisationForm sinistreId={selected.id} onSaved={load} />
        </div>
      )}
      {!error && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <ShieldAlert className="size-3.5" aria-hidden="true" />
          {visible.length} sinistre(s) affiché(s)
        </p>
      )}
      {showCreate && (
        <SinistreCreateDialog
          onClose={() => setShowCreate(false)}
          onSaved={() => { setShowCreate(false); load() }}
        />
      )}
    </ListShell>
  )
}

function IndemnisationBloc({ sinistreId }) {
  const [data, setData] = useState(null)
  useEffect(() => {
    assurancesApi.getSinistre(sinistreId)
      .then((res) => setData(res.data?.indemnisation ?? null))
      .catch(() => setData(null))
  }, [sinistreId])

  if (!data) {
    return <p className="text-muted-foreground">Aucune indemnisation enregistrée.</p>
  }
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
      <dt className="text-muted-foreground">Réclamé</dt>
      <dd className="tabular-nums text-right">{formatMAD(data.montant_reclame)}</dd>
      <dt className="text-muted-foreground">Franchise</dt>
      <dd className="tabular-nums text-right">{formatMAD(data.franchise_appliquee)}</dd>
      <dt className="text-muted-foreground">Indemnisé</dt>
      <dd className="tabular-nums text-right">{formatMAD(data.montant_indemnise)}</dd>
      <dt className="font-medium">Reste à charge</dt>
      <dd className="font-medium tabular-nums text-right">{formatMAD(data.reste_a_charge)}</dd>
    </dl>
  )
}

/* WIR56 — enregistrement d'une indemnisation depuis l'UI (montant réclamé +
   indemnisé requis ; franchise/date optionnelles). Fait passer le sinistre à
   `indemnise` côté serveur. */
function IndemnisationForm({ sinistreId, onSaved }) {
  const [montantReclame, setMontantReclame] = useState('')
  const [montantIndemnise, setMontantIndemnise] = useState('')
  const [franchise, setFranchise] = useState('')
  const [dateVersement, setDateVersement] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const peut = montantReclame !== '' && montantIndemnise !== ''

  const submit = async (e) => {
    e.preventDefault()
    if (!peut) return
    setSaving(true)
    setError(null)
    try {
      await assurancesApi.enregistrerIndemnisation(sinistreId, {
        montant_reclame: Number(montantReclame),
        montant_indemnise: Number(montantIndemnise),
        franchise_appliquee: franchise === '' ? undefined : Number(franchise),
        date_versement: dateVersement || undefined,
      })
      setMontantReclame('')
      setMontantIndemnise('')
      setFranchise('')
      setDateVersement('')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setError(data?.detail || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="mt-3 flex flex-col gap-2 border-t pt-3" noValidate>
      <p className="text-xs font-semibold text-muted-foreground">Enregistrer une indemnisation</p>
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-1">
          <Label htmlFor="ind-reclame" className="text-xs">Montant réclamé</Label>
          <Input id="ind-reclame" type="number" step="any" value={montantReclame} onChange={(e) => setMontantReclame(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="ind-indemnise" className="text-xs">Montant indemnisé</Label>
          <Input id="ind-indemnise" type="number" step="any" value={montantIndemnise} onChange={(e) => setMontantIndemnise(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="ind-franchise" className="text-xs">Franchise (optionnel)</Label>
          <Input id="ind-franchise" type="number" step="any" value={franchise} onChange={(e) => setFranchise(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="ind-date" className="text-xs">Date de versement</Label>
          <Input id="ind-date" type="date" value={dateVersement} onChange={(e) => setDateVersement(e.target.value)} />
        </div>
      </div>
      {error && <p className="text-xs text-destructive" role="alert">{error}</p>}
      <div>
        <Button type="submit" size="sm" disabled={!peut || saving}>
          {saving ? 'Enregistrement…' : 'Enregistrer l\'indemnisation'}
        </Button>
      </div>
    </form>
  )
}

/* WIR56 — déclaration d'un nouveau sinistre transverse. La police est requise
   (FK) ; la société est posée côté serveur. */
function SinistreCreateDialog({ onClose, onSaved }) {
  const [polices, setPolices] = useState([])
  const [form, setForm] = useState({
    police: '',
    type_sinistre: 'dommage_materiel',
    date_survenance: '',
    nature_sinistre: '',
    montant_estime_degats: '',
    description: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    assurancesApi.getPolices()
      .then((res) => setPolices(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setPolices([]))
  }, [])

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const peut = Boolean(form.police && form.nature_sinistre.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!peut) return
    setSaving(true)
    setError(null)
    try {
      await assurancesApi.createSinistre({
        police: Number(form.police),
        type_sinistre: form.type_sinistre,
        date_survenance: form.date_survenance || null,
        nature_sinistre: form.nature_sinistre.trim(),
        montant_estime_degats: form.montant_estime_degats === '' ? 0 : Number(form.montant_estime_degats),
        description: form.description,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setError(data?.police || data?.detail || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau sinistre</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sin-police">Police concernée</Label>
            <select
              id="sin-police"
              value={form.police}
              onChange={(e) => set('police', e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Sélectionner —</option>
              {polices.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.numero_police} · {p.type_police_display || p.type_police}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="sin-type">Type de sinistre</Label>
              <select
                id="sin-type"
                value={form.type_sinistre}
                onChange={(e) => set('type_sinistre', e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {SINISTRE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="sin-date">Date de survenance</Label>
              <Input id="sin-date" type="date" value={form.date_survenance} onChange={(e) => set('date_survenance', e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sin-nature">Nature du sinistre</Label>
            <Input id="sin-nature" value={form.nature_sinistre} onChange={(e) => set('nature_sinistre', e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sin-montant">Montant estimé des dégâts (MAD)</Label>
            <Input id="sin-montant" type="number" step="any" value={form.montant_estime_degats} onChange={(e) => set('montant_estime_degats', e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sin-desc">Description</Label>
            <Textarea id="sin-desc" value={form.description} onChange={(e) => set('description', e.target.value)} />
          </div>
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={!peut || saving}>
              {saving ? 'Enregistrement…' : 'Déclarer le sinistre'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
