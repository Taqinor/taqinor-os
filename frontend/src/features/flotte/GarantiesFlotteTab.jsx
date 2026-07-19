import { useMemo, useState } from 'react'
import {
  Badge, Button, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import { ListShell } from '../../ui/module'
import flotteApi from '../../api/flotteApi'
import { formatDate, formatNumber } from '../../lib/format'
import useFlotteResource from './useFlotteResource'

/* ============================================================================
   WIR132 / XFLT14 — Écran « Garanties flotte ».
   ----------------------------------------------------------------------------
   Le modèle `GarantieFlotte` a un CRUD backend complet mais aucun écran ne le
   surfaçait (seul un badge « sous_garantie » dérivé apparaissait sur les OR).
   Liste + création d'une garantie constructeur/fournisseur sur un actif ou un
   composant (couverture en durée mois ET/OU km). Le badge de statut lit le
   champ serveur `active` (même couverture que le warning OR) pour rester
   cohérent avec les données.
   ========================================================================== */

// GarantieFlotte.VEHICULE_ENTIER — valeur conventionnelle « actif entier ».
const COMPOSANT_VEHICULE = 'vehicule'

function GarantieFlotteDialog({ actifs = [], onClose, onSaved }) {
  const [actifFlotte, setActifFlotte] = useState('')
  const [composant, setComposant] = useState(COMPOSANT_VEHICULE)
  const [dureeMois, setDureeMois] = useState('')
  const [dureeKm, setDureeKm] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [fournisseur, setFournisseur] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(actifFlotte && dateDebut)
  const dirty = Boolean(
    actifFlotte || dureeMois || dureeKm || dateDebut || fournisseur || notes
    || composant !== COMPOSANT_VEHICULE,
  )
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.garanties.create({
        actif_flotte: Number(actifFlotte),
        composant: composant.trim() || COMPOSANT_VEHICULE,
        duree_mois: dureeMois === '' ? null : Number(dureeMois),
        duree_km: dureeKm === '' ? null : Number(dureeKm),
        date_debut: dateDebut,
        fournisseur,
        notes,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.actif_flotte
        || data?.date_debut
        || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvelle garantie</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gar-actif">Actif (véhicule ou engin)</Label>
            <select
              id="gar-actif"
              value={actifFlotte}
              onChange={(e) => setActifFlotte(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {actifs.map((a) => (
                <option key={a.id} value={a.id}>{a.label || `#${a.id}`}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gar-composant">Composant</Label>
            <Input id="gar-composant" value={composant}
                   onChange={(e) => setComposant(e.target.value)}
                   placeholder="vehicule (actif entier), moteur, boîte…" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="gar-mois">Durée (mois)</Label>
              <Input id="gar-mois" type="number" min="0" step="1" value={dureeMois}
                     onChange={(e) => setDureeMois(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="gar-km">Durée (km)</Label>
              <Input id="gar-km" type="number" min="0" step="1" value={dureeKm}
                     onChange={(e) => setDureeKm(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="gar-debut">Date de début</Label>
              <Input id="gar-debut" type="date" value={dateDebut}
                     onChange={(e) => setDateDebut(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="gar-fournisseur">Fournisseur</Label>
              <Input id="gar-fournisseur" value={fournisseur}
                     onChange={(e) => setFournisseur(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gar-notes">Notes</Label>
            <Textarea id="gar-notes" rows={2} value={notes}
                      onChange={(e) => setNotes(e.target.value)} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function GarantiesFlotteTab({ actifs = [] }) {
  const [showForm, setShowForm] = useState(false)
  const { data, loading, error, reload } = useFlotteResource(flotteApi.garanties.list, {})

  const columns = useMemo(() => [
    {
      id: 'actif_label', header: 'Actif', width: 200,
      accessor: (r) => r.actif_label || `#${r.actif_flotte}`,
    },
    {
      id: 'composant', header: 'Composant', width: 160,
      accessor: (r) => r.composant,
      cell: (v) => (v === COMPOSANT_VEHICULE ? 'Véhicule entier' : (v || '—')),
    },
    {
      id: 'couverture', header: 'Couverture', width: 160, searchable: false,
      accessor: (r) => `${r.duree_mois ?? ''} ${r.duree_km ?? ''}`,
      cell: (_v, r) => (
        <span className="text-sm">
          {r.duree_mois != null ? `${r.duree_mois} mois` : ''}
          {r.duree_mois != null && r.duree_km != null ? ' · ' : ''}
          {r.duree_km != null ? `${formatNumber(r.duree_km)} km` : ''}
          {r.duree_mois == null && r.duree_km == null ? '—' : ''}
        </span>
      ),
    },
    {
      id: 'date_debut', header: 'Début', width: 120,
      accessor: (r) => r.date_debut, cell: (v) => (v ? formatDate(v) : '—'),
    },
    {
      id: 'date_fin', header: 'Fin (durée)', width: 120, searchable: false,
      accessor: (r) => r.date_fin, cell: (v) => (v ? formatDate(v) : '—'),
    },
    {
      id: 'fournisseur', header: 'Fournisseur', width: 150,
      accessor: (r) => r.fournisseur, cell: (v) => v || '—',
    },
    {
      id: 'active', header: 'Statut', width: 130, searchable: false,
      accessor: (r) => (r.active ? 'Sous garantie' : 'Hors garantie'),
      cell: (_v, r) => (r.active
        ? <Badge tone="success">Sous garantie</Badge>
        : <Badge tone="neutral">Hors garantie</Badge>),
    },
  ], [])

  return (
    <>
      <ListShell
        title="Garanties"
        subtitle="Garanties constructeur/fournisseur des actifs (durée mois et/ou km)."
        actions={<Button onClick={() => setShowForm(true)}>Nouvelle garantie</Button>}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        exportName="garanties-flotte"
        emptyTitle="Aucune garantie"
        emptyDescription="Aucune garantie enregistrée sur le parc."
      />
      {showForm && (
        <GarantieFlotteDialog
          actifs={actifs}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload(); toast.success('Garantie enregistrée.') }}
        />
      )}
    </>
  )
}
