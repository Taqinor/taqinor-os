import { useMemo, useState } from 'react'
import { Segmented } from '../../ui'
import { ListShell } from '../../ui/module'
import flotteApi from '../../api/flotteApi'
import { formatNumber } from '../../lib/format'
import { ENERGIES, VEHICULE_STATUTS } from './flotte'
import { VehiculeStatutPill } from './statusPills'
import useFlotteResource from './useFlotteResource'
import VehiculeDetail from './VehiculeDetail'

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

export default function VehiculesList() {
  const [parc, setParc] = useState('vehicules')
  const [statut, setStatut] = useState('')
  const [energie, setEnergie] = useState('')
  const [selected, setSelected] = useState(null)

  const isVeh = parc === 'vehicules'
  const params = useMemo(() => {
    const p = {}
    if (statut) p.statut = statut
    if (isVeh && energie) p.energie = energie
    return p
  }, [statut, energie, isVeh])

  const { data, loading, error } = useFlotteResource(
    isVeh ? flotteApi.vehicules.list : flotteApi.engins.list,
    params,
    [parc],
  )

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

  return (
    <div className="page">
      <ListShell
        title="Véhicules & engins"
        subtitle="Parc roulant de l’entreprise — identité, coûts, conformité."
        filters={filters}
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
    </div>
  )
}
