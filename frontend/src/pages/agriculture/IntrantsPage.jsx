import { useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import {
  Badge, Button, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, Label, Input, toast, confirmLeaveIfDirty,
} from '../../ui'
import { ListShell } from '../../ui/module'
import agricultureApi from '../../api/agricultureApi'
import stockApi from '../../api/stockApi'
import useAgricultureResource from '../../features/agriculture/useAgricultureResource'
import EtapeCampagneForm from '../../components/agriculture/EtapeCampagneForm'

/* ============================================================================
   NTAGR8 — Écran « Intrants » (`/agriculture/intrants`).
   ----------------------------------------------------------------------------
   Catalogue des intrants (dose/DAR) + application d'un traitement sur une
   campagne choisie, avec alerte DAR en direct (`EtapeCampagneForm`).

   WIR141 — `IntrantAgricole` (attributs agronomiques sur `stock.Produit`)
   n'avait aucune UI de création : dialogue « Nouvel intrant » (produit du
   catalogue stock + catégorie/dose/DAR/matière active/n° AMM).
   ========================================================================== */

const CATEGORIE_LABEL = { semence: 'Semence', engrais: 'Engrais', phyto: 'Phytosanitaire' }
const CATEGORIE_OPTIONS = [
  ['semence', 'Semence'], ['engrais', 'Engrais'], ['phyto', 'Phytosanitaire'],
]

// WIR141 — Création d'un intrant agronomique (aucune UI jusqu'ici).
function IntrantDialog({ produits, onClose, onSaved }) {
  const [produitId, setProduitId] = useState('')
  const [categorie, setCategorie] = useState('phyto')
  const [dose, setDose] = useState('')
  const [dar, setDar] = useState('')
  const [matiereActive, setMatiereActive] = useState('')
  const [numeroAmm, setNumeroAmm] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(produitId || dose || dar || matiereActive || numeroAmm)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const peutEnregistrer = Boolean(produitId && categorie)

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await agricultureApi.intrants.create({
        produit_id: produitId,
        categorie,
        dose_reference_par_ha: dose === '' ? null : dose,
        delai_avant_recolte_jours: dar === '' ? null : dar,
        matiere_active: matiereActive,
        numero_amm: numeroAmm,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.non_field_errors?.[0] || data?.produit_id || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvel intrant</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="int-produit">Produit (catalogue stock)</Label>
            <select
              id="int-produit" autoFocus value={produitId}
              onChange={(e) => setProduitId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {(produits || []).map((p) => (
                <option key={p.id} value={p.id}>{p.nom}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="int-categorie">Catégorie</Label>
            <select
              id="int-categorie" value={categorie}
              onChange={(e) => setCategorie(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              {CATEGORIE_OPTIONS.map(([v, label]) => (
                <option key={v} value={v}>{label}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="int-dose">Dose / ha (option.)</Label>
              <Input id="int-dose" type="number" step="any" value={dose} onChange={(e) => setDose(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="int-dar">DAR (jours, option.)</Label>
              <Input id="int-dar" type="number" step="any" value={dar} onChange={(e) => setDar(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="int-matiere">Matière active (option.)</Label>
            <Input id="int-matiere" value={matiereActive} onChange={(e) => setMatiereActive(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="int-amm">N° AMM (option.)</Label>
            <Input id="int-amm" value={numeroAmm} onChange={(e) => setNumeroAmm(e.target.value)} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Créer l’intrant'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function IntrantsPage() {
  const { data: intrants, loading, error, reload } = useAgricultureResource(
    agricultureApi.intrants.list, {})
  const { data: campagnes } = useAgricultureResource(agricultureApi.campagnes.list, {})
  const { data: produits } = useAgricultureResource(stockApi.getProduits, {})
  const [campagneId, setCampagneId] = useState('')
  const [showTraitement, setShowTraitement] = useState(false)
  const [showIntrantForm, setShowIntrantForm] = useState(false)

  const campagne = useMemo(
    () => (campagnes || []).find((c) => String(c.id) === String(campagneId)) || null,
    [campagnes, campagneId],
  )

  const columns = useMemo(() => [
    {
      id: 'produit', header: 'Produit', width: 200,
      accessor: (r) => r.produit_nom, cell: (v) => v || '—',
    },
    {
      id: 'categorie', header: 'Catégorie', width: 130,
      accessor: (r) => r.categorie_display || r.categorie, cell: (v) => v || '—',
    },
    {
      id: 'dose', header: 'Dose / ha', align: 'right', numeric: true, width: 110,
      accessor: (r) => r.dose_reference_par_ha, cell: (v) => (v != null ? v : '—'),
    },
    {
      id: 'dar', header: 'DAR', align: 'right', numeric: true, width: 90,
      accessor: (r) => r.delai_avant_recolte_jours,
      cell: (v) => (v != null ? <Badge tone="warning">{v} j</Badge> : '—'),
    },
    {
      id: 'amm', header: 'N° AMM', width: 120,
      accessor: (r) => r.numero_amm, cell: (v) => v || '—',
    },
  ], [])

  const actions = (
    <div className="flex items-center gap-2">
      <select
        aria-label="Campagne"
        value={campagneId}
        onChange={(e) => setCampagneId(e.target.value)}
        className="h-9 rounded-md border border-border bg-card px-3 text-sm"
      >
        <option value="">— Choisir une campagne —</option>
        {(campagnes || []).map((c) => (
          <option key={c.id} value={c.id}>{c.culture} — #{c.id}</option>
        ))}
      </select>
      <Button onClick={() => setShowTraitement(true)} disabled={!campagne}>
        <Plus /> Ajouter un traitement
      </Button>
      <Button variant="outline" onClick={() => setShowIntrantForm(true)}>
        <Plus /> Nouvel intrant
      </Button>
    </div>
  )

  return (
    <div className="page flex flex-col gap-4">
      <ListShell
        title="Intrants"
        subtitle="Catalogue agronomique (semences, engrais, phytosanitaires) lié au stock."
        actions={actions}
        columns={columns}
        rows={intrants}
        loading={loading}
        error={error}
        exportName="intrants"
        emptyTitle="Aucun intrant"
        emptyDescription="Aucun intrant agricole enregistré pour l’instant."
      >
        {!campagne && (
          <p className="text-xs text-muted-foreground">
            Choisissez une campagne pour appliquer un traitement.
          </p>
        )}
      </ListShell>

      {showTraitement && campagne && (
        <EtapeCampagneForm
          campagne={campagne}
          intrants={(intrants || []).filter((i) => i.categorie === 'phyto')}
          onClose={() => setShowTraitement(false)}
          onSaved={() => {
            setShowTraitement(false)
            toast.success('Traitement enregistré.')
          }}
        />
      )}

      {showIntrantForm && (
        <IntrantDialog
          produits={produits}
          onClose={() => setShowIntrantForm(false)}
          onSaved={() => {
            setShowIntrantForm(false)
            reload()
            toast.success('Intrant créé.')
          }}
        />
      )}
    </div>
  )
}
