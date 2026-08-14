import { useEffect, useMemo, useState } from 'react'
import { Check, X } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Card, Stat, Segmented, toast } from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatNumber, formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'
import { StatutConge } from './constants.jsx'

/* ============================================================================
   UX23 — Congés & absences.
   ----------------------------------------------------------------------------
   Trois vues : soldes de congés (cartes), demandes (workflow
   valider/refuser côté responsable) et calendrier d'équipe (absences validées
   à venir). Toutes les décisions passent par les @actions serveur — l'acteur
   et la société sont posés côté serveur.
   ========================================================================== */

const VUES = [
  { value: 'demandes', label: 'Demandes' },
  { value: 'soldes', label: 'Soldes' },
  { value: 'calendrier', label: 'Calendrier équipe' },
  // ZRH3 — rapport congés par type et par employé (année civile).
  { value: 'rapport', label: 'Rapport' },
]

export default function Conges() {
  const { confirmDelete } = useConfirmDialog()
  const [vue, setVue] = useState('demandes')

  const [demandes, setDemandes] = useState([])
  const [soldes, setSoldes] = useState([])
  const [calendrier, setCalendrier] = useState([])
  // ZRH3 — rapport annuel {par_type, par_employe}.
  const [rapport, setRapport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const recharger = () => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([
      rhApi.getDemandesConge(),
      rhApi.getSoldesConge(),
      rhApi.getCalendrierConges(),
      rhApi.getRapportConges(),
    ])
      .then(([dRes, sRes, cRes, rRes]) => {
        if (!vivant) return
        setDemandes(unwrap(dRes.data))
        setSoldes(unwrap(sRes.data))
        setCalendrier(unwrap(cRes.data))
        setRapport(rRes.data)
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les congés.')
        toast.error('Impossible de charger les congés.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(recharger, [])

  const valider = async (d) => {
    try {
      await rhApi.validerDemandeConge(d.id)
      toast.success('Demande validée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Validation impossible.')
    }
  }

  const refuser = async (d) => {
    const ok = await confirmDelete({
      title: 'Refuser cette demande de congé ?',
      description: 'Le collaborateur en sera informé.',
      confirmLabel: 'Refuser',
    })
    if (!ok) return
    try {
      await rhApi.refuserDemandeConge(d.id, { motif_refus: 'Refusée par le responsable.' })
      toast.success('Demande refusée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Refus impossible.')
    }
  }

  const demandeColumns = useMemo(() => [
    {
      id: 'employe',
      header: 'Employé',
      width: 180,
      accessor: (d) => d.employe_nom || String(d.employe || ''),
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'type',
      header: 'Type',
      width: 140,
      accessor: (d) => d.type_absence_code || String(d.type_absence || ''),
      cell: (v) => v || '—',
    },
    {
      id: 'periode',
      header: 'Période',
      width: 200,
      searchable: false,
      accessor: (d) => d.date_debut || '',
      cell: (_v, d) => `${formatDate(d.date_debut)} → ${formatDate(d.date_fin)}`,
    },
    {
      id: 'jours',
      header: 'Jours',
      width: 80,
      align: 'right',
      numeric: true,
      searchable: false,
      accessor: (d) => Number(d.jours ?? 0),
      cell: (v) => formatNumber(v, { decimals: 1 }),
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 120,
      accessor: (d) => d.statut || '',
      cell: (_v, d) => <StatutConge status={d.statut} label={d.statut_display} />,
    },
  ], [])

  const rowActions = (d) => {
    if (d.statut !== 'soumise') return []
    return [
      { id: 'valider', label: 'Valider', icon: Check, onClick: () => valider(d) },
      { id: 'refuser', label: 'Refuser', icon: X, destructive: true, onClick: () => refuser(d) },
    ]
  }

  const calendrierColumns = useMemo(() => [
    {
      id: 'employe',
      header: 'Employé',
      width: 180,
      accessor: (d) => d.employe_nom || String(d.employe || ''),
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'type',
      header: 'Type',
      width: 140,
      accessor: (d) => d.type_absence_code || String(d.type_absence || ''),
      cell: (v) => v || '—',
    },
    {
      id: 'periode',
      header: 'Période',
      width: 220,
      searchable: false,
      accessor: (d) => d.date_debut || '',
      cell: (_v, d) => `${formatDate(d.date_debut)} → ${formatDate(d.date_fin)}`,
    },
  ], [])

  // ZRH3 — colonnes du rapport (clés du sélecteur serveur).
  const rapportTypeColumns = [
    { id: 'code', header: 'Type', width: 120, accessor: (r) => r.code || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'libelle', header: 'Libellé', width: 220, accessor: (r) => r.libelle || '', cell: (v) => v || '—' },
    { id: 'jours', header: 'Jours', width: 100, align: 'right', numeric: true, searchable: false, accessor: (r) => Number(r.jours ?? 0), cell: (v) => formatNumber(v, { decimals: 1 }) },
  ]
  const rapportEmployeColumns = [
    { id: 'nom', header: 'Employé', width: 200, accessor: (r) => r.nom || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'jours', header: 'Jours pris', width: 110, align: 'right', numeric: true, searchable: false, accessor: (r) => Number(r.jours ?? 0), cell: (v) => formatNumber(v, { decimals: 1 }) },
    { id: 'solde', header: 'Solde disponible', width: 140, align: 'right', numeric: true, searchable: false, accessor: (r) => Number(r.solde_disponible ?? 0), cell: (v) => formatNumber(v, { decimals: 1 }) },
  ]

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Congés & absences</h2>
      </div>

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue des congés" />

      {vue === 'soldes' ? (
        loading ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : soldes.length === 0 ? (
          <Card className="p-6 text-sm text-muted-foreground">Aucun solde de congé.</Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {soldes.map((s) => (
              <Card key={s.id} className="p-4">
                <p className="mb-2 text-sm font-medium">
                  {s.employe_nom || `Employé ${s.employe}`} · {s.annee}
                </p>
                <Stat
                  label="Disponible"
                  value={`${formatNumber(s.disponible ?? 0, { decimals: 1 })} j`}
                  hint={`${formatNumber(s.acquis ?? 0, { decimals: 1 })} acquis · ${formatNumber(s.pris ?? 0, { decimals: 1 })} pris`}
                />
              </Card>
            ))}
          </div>
        )
      ) : vue === 'rapport' ? (
        <div className="flex flex-col gap-4">
          <ListShell
            title="Congés par type"
            columns={rapportTypeColumns}
            rows={rapport?.par_type ?? []}
            loading={loading}
            error={error}
            searchable
            exportName="rapport-conges-par-type"
            emptyTitle="Aucun congé validé"
            emptyDescription="Aucune demande validée sur l’année."
          />
          <ListShell
            title="Congés par employé"
            columns={rapportEmployeColumns}
            rows={rapport?.par_employe ?? []}
            loading={loading}
            error={error}
            searchable
            exportName="rapport-conges-par-employe"
            emptyTitle="Aucun congé validé"
            emptyDescription="Aucune demande validée sur l’année."
          />
        </div>
      ) : vue === 'calendrier' ? (
        <ListShell
          title="Calendrier d’équipe"
          subtitle="Absences validées à venir"
          columns={calendrierColumns}
          rows={calendrier}
          loading={loading}
          error={error}
          searchable
          exportName="calendrier-conges"
          emptyTitle="Aucune absence"
          emptyDescription="Aucune absence validée à venir."
        />
      ) : (
        <ListShell
          title="Demandes de congé"
          columns={demandeColumns}
          rows={demandes}
          loading={loading}
          error={error}
          searchable
          searchPlaceholder="Rechercher employé, type…"
          exportName="demandes-conge"
          rowActions={rowActions}
          emptyTitle="Aucune demande"
          emptyDescription="Aucune demande de congé enregistrée."
        />
      )}
    </div>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
