import { useEffect, useState } from 'react'
import { ListPlus, Plus, Sprout, Pencil } from 'lucide-react'
import api from '../../api/axios'
import {
  Button, Card, Badge, Spinner, EmptyState, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Checkbox, DataTable,
} from '../../ui'

/* ============================================================================
   PACT95 — Types d'entrées ponctuelles de paie.
   ----------------------------------------------------------------------------
   `TypeEntreePonctuelle` (`apps/paie`, `apps/paie/models.py:2086`) est un
   catalogue par société d'entrées ponctuelles hors rubriques récurrentes
   (pourboire, remboursement non imposable…), déjà exposé à
   `/paie/types-entree-ponctuelle/` (+ l'action `seed-standard`) SANS AUCUN
   écran. Un type créé ici est immédiatement sélectionnable comme
   `ElementVariable.type_entree` ailleurs dans l'app — la liste vient du
   serveur, déjà scopée société, jamais refiltrée côté client.
   ========================================================================== */

const listOf = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

const SENS_OPTIONS = [
  { value: 'gain', label: 'Gain' },
  { value: 'retenue', label: 'Retenue' },
]

const TYPE_VIDE = {
  code: '', libelle: '', sens: 'gain', imposable: true, soumis_cnss: true,
  soumis_amo: true, actif: true,
}

export default function TypesEntreePonctuelle() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState(null) // null = création, sinon la ligne éditée

  const load = () =>
    api.get('/paie/types-entree-ponctuelle/')
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement des types d’entrée ponctuelle impossible.'))
      .finally(() => setLoading(false))

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  const seed = async () => {
    setBusy(true)
    try {
      await api.post('/paie/types-entree-ponctuelle/seed-standard/')
      toast.success('Catalogue standard provisionné.')
      await load()
    } catch {
      toast.error('Semis impossible.')
    } finally { setBusy(false) }
  }

  const ouvrirCreation = () => { setEditing(null); setDialogOpen(true) }
  const ouvrirEdition = (row) => { setEditing(row); setDialogOpen(true) }

  const columns = [
    { id: 'code', header: 'Code', width: 120, accessor: (r) => r.code },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    {
      id: 'sens', header: 'Sens', accessor: (r) => r.sens,
      cell: (_v, r) => <Badge tone={r.sens === 'retenue' ? 'danger' : 'success'}>{r.sens}</Badge>,
    },
    { id: 'imposable', header: 'Imposable', accessor: (r) => r.imposable, cell: (_v, r) => (r.imposable ? 'Oui' : 'Non') },
    { id: 'cnss', header: 'CNSS', accessor: (r) => r.soumis_cnss, cell: (_v, r) => (r.soumis_cnss ? 'Oui' : 'Non') },
    { id: 'amo', header: 'AMO', accessor: (r) => r.soumis_amo, cell: (_v, r) => (r.soumis_amo ? 'Oui' : 'Non') },
    {
      id: 'actif', header: 'Statut', accessor: (r) => r.actif,
      cell: (_v, r) => <Badge tone={r.actif ? 'success' : 'neutral'}>{r.actif ? 'Actif' : 'Inactif'}</Badge>,
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Types d’entrées ponctuelles
        </h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Catalogue des entrées ponctuelles hors rubriques récurrentes (pourboire, remboursement non imposable…).
        </p>
      </div>

      <div className="flex flex-wrap justify-end gap-2">
        <Button onClick={seed} loading={busy} variant="outline">
          <Sprout size={16} aria-hidden="true" /> Catalogue standard
        </Button>
        <Button onClick={ouvrirCreation}>
          <Plus size={16} aria-hidden="true" /> Nouveau type
        </Button>
      </div>

      <Card className="p-4 sm:p-5">
        {loading ? (
          <div className="flex items-center gap-2 py-6 text-muted-foreground">
            <Spinner className="size-4" /> Chargement…
          </div>
        ) : rows.length === 0 ? (
          <EmptyState icon={ListPlus} title="Aucun type d’entrée ponctuelle"
            description="Provisionnez le catalogue standard ou créez-en un." />
        ) : (
          <DataTable data={rows} columns={columns} searchable
            exportName="types-entree-ponctuelle"
            rowActions={(r) => [
              { id: 'editer', label: 'Éditer le type', icon: Pencil, onClick: () => ouvrirEdition(r) },
            ]} />
        )}
      </Card>

      {dialogOpen && (
        <TypeDialog
          type={editing}
          onClose={() => setDialogOpen(false)}
          onSaved={() => { setDialogOpen(false); load() }}
        />
      )}
    </div>
  )
}

function TypeDialog({ type, onClose, onSaved }) {
  const isEdit = !!type
  const [code, setCode] = useState(type?.code || '')
  const [libelle, setLibelle] = useState(type?.libelle || '')
  const [sens, setSens] = useState(type?.sens || 'gain')
  const [imposable, setImposable] = useState(type ? Boolean(type.imposable) : true)
  const [soumisCnss, setSoumisCnss] = useState(type ? Boolean(type.soumis_cnss) : true)
  const [soumisAmo, setSoumisAmo] = useState(type ? Boolean(type.soumis_amo) : true)
  const [actif, setActif] = useState(type ? Boolean(type.actif) : true)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!code.trim() || !libelle.trim()) {
      setErr('Le code et le libellé sont requis.')
      return
    }
    setSaving(true)
    setErr(null)
    const data = {
      code: code.trim(), libelle: libelle.trim(), sens,
      imposable, soumis_cnss: soumisCnss, soumis_amo: soumisAmo, actif,
    }
    try {
      if (isEdit) {
        await api.patch(`/paie/types-entree-ponctuelle/${type.id}/`, data)
        toast.success('Type mis à jour.')
      } else {
        await api.post('/paie/types-entree-ponctuelle/', data)
        toast.success('Type créé.')
      }
      onSaved()
    } catch (e2) {
      setErr(e2?.response?.data?.detail || e2?.response?.data?.code?.[0] || 'Enregistrement impossible.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? `Type — ${type.code}` : 'Nouveau type d’entrée ponctuelle'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex gap-3">
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="tep-code" required>Code</Label>
              <Input id="tep-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="ex. POURBOIRE" />
            </div>
            <div className="flex flex-[2] flex-col gap-1.5">
              <Label htmlFor="tep-libelle" required>Libellé</Label>
              <Input id="tep-libelle" value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="ex. Pourboire" />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tep-sens">Sens</Label>
            <Select value={sens} onValueChange={setSens}>
              <SelectTrigger id="tep-sens"><SelectValue /></SelectTrigger>
              <SelectContent>
                {SENS_OPTIONS.map((s) => (
                  <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2">
              <Checkbox checked={imposable} onCheckedChange={(v) => setImposable(Boolean(v))} />
              Imposable (IR)
            </label>
            <label className="flex items-center gap-2">
              <Checkbox checked={soumisCnss} onCheckedChange={(v) => setSoumisCnss(Boolean(v))} />
              Soumis CNSS
            </label>
            <label className="flex items-center gap-2">
              <Checkbox checked={soumisAmo} onCheckedChange={(v) => setSoumisAmo(Boolean(v))} />
              Soumis AMO
            </label>
            {isEdit && (
              <label className="flex items-center gap-2">
                <Checkbox checked={actif} onCheckedChange={(v) => setActif(Boolean(v))} />
                Actif
              </label>
            )}
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Enregistrement…' : (isEdit ? 'Mettre à jour' : 'Créer le type')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
