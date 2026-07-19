import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileSignature, Plus } from 'lucide-react'
import contratsApi from '../../api/contratsApi'
import {
  Button, Segmented, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input,
} from '../../ui'
import { ListShell } from '../../ui/module'
import { formatMAD, formatDate } from '../../lib/format'
import {
  StatutContrat, StatutConfidentialite, CONTRAT_STATUS, CONTRAT_TYPES,
} from './status'

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

/* ============================================================================
   UX34 — Liste des contrats (cycle de vie CLM).
   ----------------------------------------------------------------------------
   Coquille de liste UX1 : filtres par statut + type, pastilles de statut et de
   confidentialité, montant TTC client-facing (formatMAD — jamais de prix
   d'achat/marge). Le clic ouvre la fiche cycle de vie (UX34 détail).
   ========================================================================== */

const STATUT_FILTERS = [
  { value: 'tous', label: 'Tous' },
  ...Object.entries(CONTRAT_STATUS).map(([value, v]) => ({ value, label: v.label })),
]

const TYPE_FILTERS = [{ value: 'tous', label: 'Tous types' }, ...CONTRAT_TYPES]

export default function ContratsList() {
  const navigate = useNavigate()
  const [contrats, setContrats] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statutFilter, setStatutFilter] = useState('tous')
  const [typeFilter, setTypeFilter] = useState('tous')
  // WIR9 — création directe d'un contrat (chemin garanti même sans aucun
  // ModeleContrat ; l'instanciation depuis un gabarit reste possible via
  // /contrats/modeles, toujours accessible depuis le menu).
  const [creating, setCreating] = useState(false)

  const load = () => {
    setLoading(true)
    setError(null)
    contratsApi
      .getContrats()
      .then((res) => setContrats(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les contrats.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const visible = useMemo(() => contrats.filter((c) => {
    if (statutFilter !== 'tous' && c.statut !== statutFilter) return false
    if (typeFilter !== 'tous' && c.type_contrat !== typeFilter) return false
    return true
  }), [contrats, statutFilter, typeFilter])

  const columns = useMemo(() => [
    {
      id: 'reference',
      header: 'Référence',
      width: 150,
      accessor: (c) => c.reference || `#${c.id}`,
      cell: (v) => <span className="font-mono text-xs">{v}</span>,
    },
    {
      id: 'objet',
      header: 'Objet',
      width: 260,
      accessor: (c) => c.objet || '',
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      // WIR77 — nom du client lié (résolu cross-app côté serveur).
      id: 'client_nom',
      header: 'Client',
      width: 180,
      accessor: (c) => c.client_nom || '',
      cell: (v) => v || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'type',
      header: 'Type',
      width: 130,
      accessor: (c) => c.type_contrat_display || c.type_contrat || '',
      cell: (v) => v || '—',
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 150,
      accessor: (c) => c.statut,
      cell: (v) => <StatutContrat status={v} />,
    },
    {
      id: 'confidentialite',
      header: 'Confidentialité',
      width: 140,
      accessor: (c) => c.confidentialite,
      cell: (v) => <StatutConfidentialite status={v} />,
    },
    {
      id: 'montant',
      header: 'Montant',
      align: 'right',
      numeric: true,
      width: 140,
      searchable: false,
      accessor: (c) => Number(c.montant ?? 0),
      cell: (_v, c) => (c.montant != null
        ? <span className="font-medium tabular-nums">{formatMAD(c.montant)}</span>
        : <span className="text-muted-foreground">—</span>),
      exportValue: (c) => Number(c.montant ?? 0),
    },
    {
      id: 'date_fin',
      header: 'Échéance',
      align: 'right',
      width: 120,
      searchable: false,
      accessor: (c) => c.date_fin || '',
      cell: (v) => (v ? formatDate(v) : <span className="text-muted-foreground">—</span>),
    },
  ], [])

  return (
    <ListShell
      title="Contrats"
      subtitle="Cycle de vie des contrats : brouillon → approbation → signé → actif → suspendu → résilié → expiré."
      actions={(
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => navigate('/contrats/modeles')}>
            Depuis un gabarit
          </Button>
          <Button onClick={() => setCreating(true)}>
            <Plus /> Nouveau contrat
          </Button>
        </div>
      )}
      columns={columns}
      rows={visible}
      loading={loading}
      error={error}
      searchable
      searchPlaceholder="Rechercher référence, objet…"
      exportName="contrats"
      emptyTitle="Aucun contrat"
      emptyDescription="Aucun contrat ne correspond à ces filtres."
      emptyAction={<Button size="sm" onClick={() => setCreating(true)}><Plus className="size-4" /> Nouveau contrat</Button>}
      onRowClick={(c) => navigate(`/contrats/${c.id}`)}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          options={STATUT_FILTERS}
          value={statutFilter}
          onChange={setStatutFilter}
          aria-label="Filtrer par statut"
        />
        <Segmented
          options={TYPE_FILTERS}
          value={typeFilter}
          onChange={setTypeFilter}
          aria-label="Filtrer par type"
        />
        {error && (
          <Button variant="outline" size="sm" onClick={load}>Réessayer</Button>
        )}
      </div>
      {!error && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <FileSignature className="size-3.5" aria-hidden="true" />
          {visible.length} contrat(s) affiché(s)
        </p>
      )}
      {creating && (
        <CreateContratDialog
          onClose={() => setCreating(false)}
          onDone={(id) => {
            setCreating(false)
            if (id) navigate(`/contrats/${id}`)
            else load()
          }}
        />
      )}
    </ListShell>
  )
}

// WIR9 — premier point d'entrée de CRÉATION directe d'un contrat : une
// société neuve sans aucun `ModeleContrat` ne pouvait rien créer (le seul
// bouton menait à `/contrats/modeles`, une bibliothèque de gabarits vide et
// sans formulaire). Seul `objet` est requis côté backend
// (`apps/contrats/models.py::Contrat`) — l'instanciation depuis un gabarit
// reste une alternative pour les sociétés qui en ont un.
function CreateContratDialog({ onClose, onDone }) {
  const [objet, setObjet] = useState('')
  const [typeContrat, setTypeContrat] = useState('vente')
  const [montant, setMontant] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!objet.trim()) { setErr("L'objet du contrat est requis."); return }
    setSaving(true)
    setErr(null)
    const data = { objet: objet.trim(), type_contrat: typeContrat }
    if (montant !== '') data.montant = Number(montant)
    try {
      const res = await contratsApi.createContrat(data)
      toast.success('Contrat créé.')
      onDone(res.data?.id)
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouveau contrat</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ctr-objet" required>Objet</Label>
            <Input
              id="ctr-objet"
              value={objet}
              onChange={(e) => setObjet(e.target.value)}
              placeholder="ex. Maintenance annuelle onduleurs"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ctr-type">Type de contrat</Label>
            <select
              id="ctr-type"
              value={typeContrat}
              onChange={(e) => setTypeContrat(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              {CONTRAT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ctr-montant">Montant (MAD)</Label>
            <Input
              id="ctr-montant"
              type="number"
              step="any"
              value={montant}
              onChange={(e) => setMontant(e.target.value)}
              placeholder="Optionnel"
            />
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer le contrat'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
