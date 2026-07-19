import { useMemo, useState } from 'react'
import {
  Segmented, Button, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, confirmLeaveIfDirty,
} from '../../ui'
import { ListShell } from '../../ui/module'
import flotteApi from '../../api/flotteApi'
import { formatNumber } from '../../lib/format'
import { ENERGIES, VEHICULE_STATUTS, TYPE_ENGINS, optionsFrom } from './flotte'
import { VehiculeStatutPill } from './statusPills'
import useFlotteResource from './useFlotteResource'
import VehiculeDetail from './VehiculeDetail'
import VehiculeCreateDialog from './VehiculeCreateDialog'

/* ============================================================================
   UX16 — Véhicules & engins (`/flotte/vehicules`).
   ----------------------------------------------------------------------------
   Liste filtrable (statut, énergie) des véhicules ; clic → panneau détail à
   onglets (identité, TCO, éco-conduite, amortissement, TSAV). Les engins
   roulants partagent l'écran via un basculeur « Véhicules / Engins ». Aucun
   prix d'achat rendu ; `valeur` est une valeur d'immobilisation interne.
   ========================================================================== */

const STATUT_FILTERS = [
  { value: '', label: 'Tous statuts' },
  { value: 'actif', label: 'Actifs' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'reforme', label: 'Réformés' },
]

const ENERGIE_FILTERS = [
  { value: '', label: 'Toutes énergies' },
  { value: 'diesel', label: 'Diesel' },
  { value: 'essence', label: 'Essence' },
  { value: 'electrique', label: 'Électrique' },
  { value: 'hybride', label: 'Hybride' },
]

const PARC = [
  { value: 'vehicules', label: 'Véhicules' },
  { value: 'engins', label: 'Engins' },
]

// WIR40 — dialogue de création d'un engin roulant (symétrique du « Nouveau
// véhicule » de `VehiculeCreateDialog.jsx`, câblé sur le CRUD `engins/`
// existant). Local à cet écran : les engins n'ont pas de fiche détail ni de
// pré-remplissage catalogue comme les véhicules.
function EnginCreateDialog({ onClose, onSaved }) {
  const [nom, setNom] = useState('')
  const [typeEngin, setTypeEngin] = useState('nacelle')
  const [marque, setMarque] = useState('')
  const [modele, setModele] = useState('')
  const [compteurHeures, setCompteurHeures] = useState('')
  const [valeur, setValeur] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(nom.trim())
  const dirty = Boolean(nom || marque || modele || compteurHeures || valeur || typeEngin !== 'nacelle')
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.engins.create({
        nom: nom.trim(),
        type_engin: typeEngin,
        marque,
        modele,
        compteur_heures: compteurHeures === '' ? undefined : Number(compteurHeures),
        valeur: valeur === '' ? undefined : Number(valeur),
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.nom
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
          <DialogTitle>Nouvel engin</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="engin-nom">Désignation</Label>
            <Input id="engin-nom" autoFocus value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="engin-type">Type d’engin</Label>
              <select
                id="engin-type"
                value={typeEngin}
                onChange={(e) => setTypeEngin(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {optionsFrom(TYPE_ENGINS).map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="engin-compteur">Compteur d’heures</Label>
              <Input id="engin-compteur" type="number" step="any" value={compteurHeures} onChange={(e) => setCompteurHeures(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="engin-marque">Marque</Label>
              <Input id="engin-marque" value={marque} onChange={(e) => setMarque(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="engin-modele">Modèle</Label>
              <Input id="engin-modele" value={modele} onChange={(e) => setModele(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="engin-valeur">Valeur (MAD)</Label>
            <Input id="engin-valeur" type="number" step="any" value={valeur} onChange={(e) => setValeur(e.target.value)} />
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

export default function VehiculesList() {
  const [parc, setParc] = useState('vehicules')
  const [statut, setStatut] = useState('')
  const [energie, setEnergie] = useState('')
  const [selected, setSelected] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const isVeh = parc === 'vehicules'
  const params = useMemo(() => {
    const p = {}
    if (statut) p.statut = statut
    if (isVeh && energie) p.energie = energie
    return p
  }, [statut, energie, isVeh])

  const { data, loading, error, reload } = useFlotteResource(
    isVeh ? flotteApi.vehicules.list : flotteApi.engins.list,
    params,
    [parc],
  )
  // XFLT12 — catalogue de modèles, pour le pré-remplissage à la création.
  const { data: modeles } = useFlotteResource(flotteApi.modelesVehicule.list, {})

  const vehiculeColumns = useMemo(() => [
    {
      id: 'immatriculation',
      header: 'Immatriculation',
      width: 160,
      accessor: (r) => r.immatriculation,
      cell: (v) => <span className="font-mono font-medium">{v || '—'}</span>,
    },
    {
      id: 'marque',
      header: 'Véhicule',
      width: 200,
      accessor: (r) => [r.marque, r.modele].filter(Boolean).join(' '),
      cell: (v) => v || '—',
    },
    {
      id: 'energie',
      header: 'Énergie',
      width: 120,
      accessor: (r) => r.energie_display || ENERGIES[r.energie] || r.energie,
      cell: (v) => v || '—',
    },
    {
      id: 'kilometrage',
      header: 'Kilométrage',
      align: 'right',
      numeric: true,
      width: 130,
      accessor: (r) => Number(r.kilometrage ?? 0),
      cell: (v) => (v ? `${formatNumber(v)} km` : '—'),
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 140,
      accessor: (r) => r.statut,
      cell: (v) => <VehiculeStatutPill status={v} />,
    },
  ], [])

  const enginColumns = useMemo(() => [
    { id: 'nom', header: 'Engin', width: 220, accessor: (r) => r.nom, cell: (v) => v || '—' },
    {
      id: 'type_engin',
      header: 'Type',
      width: 160,
      accessor: (r) => r.type_engin_display || r.type_engin,
      cell: (v) => v || '—',
    },
    {
      id: 'marque',
      header: 'Marque / modèle',
      width: 200,
      accessor: (r) => [r.marque, r.modele].filter(Boolean).join(' '),
      cell: (v) => v || '—',
    },
    {
      id: 'compteur_heures',
      header: 'Compteur (h)',
      align: 'right',
      numeric: true,
      width: 130,
      accessor: (r) => Number(r.compteur_heures ?? 0),
      cell: (v) => (v ? `${formatNumber(v)} h` : '—'),
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 140,
      accessor: (r) => r.statut,
      cell: (v) => <VehiculeStatutPill status={v} />,
    },
  ], [])

  const filters = (
    <div className="flex flex-wrap items-center gap-2">
      <Segmented options={PARC} value={parc} onChange={setParc} aria-label="Type de parc" />
      <Segmented options={STATUT_FILTERS} value={statut} onChange={setStatut} aria-label="Filtrer par statut" />
      {isVeh && (
        <Segmented
          options={ENERGIE_FILTERS}
          value={energie}
          onChange={setEnergie}
          aria-label="Filtrer par énergie"
        />
      )}
    </div>
  )

  const actions = isVeh
    ? <Button onClick={() => setShowCreate(true)}>Nouveau véhicule</Button>
    : <Button onClick={() => setShowCreate(true)}>Nouvel engin</Button>

  return (
    <div className="page">
      <ListShell
        title="Véhicules & engins"
        subtitle="Parc roulant de l’entreprise — identité, coûts, conformité."
        filters={filters}
        actions={actions}
        columns={isVeh ? vehiculeColumns : enginColumns}
        rows={data}
        loading={loading}
        error={error}
        searchable
        searchPlaceholder={isVeh ? 'Rechercher immat., marque, modèle…' : 'Rechercher nom, marque…'}
        exportName={isVeh ? 'vehicules' : 'engins'}
        onRowClick={isVeh ? setSelected : undefined}
        emptyTitle="Aucun élément"
        emptyDescription="Aucun élément du parc ne correspond à ces filtres."
      />

      {selected && (
        <VehiculeDetail
          vehicule={selected}
          onClose={() => setSelected(null)}
        />
      )}

      {showCreate && isVeh && (
        <VehiculeCreateDialog
          modeles={modeles}
          onClose={() => setShowCreate(false)}
          onSaved={() => { setShowCreate(false); reload(); toast.success('Véhicule créé.') }}
        />
      )}

      {showCreate && !isVeh && (
        <EnginCreateDialog
          onClose={() => setShowCreate(false)}
          onSaved={() => { setShowCreate(false); reload(); toast.success('Engin créé.') }}
        />
      )}
    </div>
  )
}
