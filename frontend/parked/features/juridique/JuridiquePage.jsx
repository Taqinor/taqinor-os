import { useEffect, useMemo, useState } from 'react'
import { Scale, Eye } from 'lucide-react'
import { ListShell, ModuleDashboard } from '../../ui/module'
import { Badge } from '../../ui'
import { formatMAD, formatDate } from '../../lib/format'
import juridiqueApi from '../../api/juridiqueApi'
import {
  StatutDossierPill, ConfidentialitePill, NATURE_MAP, PROCEDURE_MAP,
} from './juridiqueStatus'
import DossierDetailPage from './DossierDetailPage'

/* ============================================================================
   NTJUR — Registre des dossiers juridiques (hôte du module).
   ----------------------------------------------------------------------------
   Écran d'entrée du module : cockpit (ModuleDashboard) + registre des dossiers,
   et ouverture du DÉTAIL (NTJUR22) à la sélection. C'est lui qui rend l'écran
   de détail ATTEIGNABLE depuis le menu — sans quoi le détail serait du code
   mort qui se croit vivant (garde ``check_ecrans_atteignables``).

   Rien n'est calculé ici : les totaux viennent de l'agrégat serveur (déjà
   filtré par confidentialité), la liste vient du queryset serveur (les
   dossiers ``confidentiel`` en sont absents pour un rôle non autorisé).
   ========================================================================== */

export default function JuridiquePage() {
  const [dossiers, setDossiers] = useState([])
  const [cockpit, setCockpit] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)
  const [selection, setSelection] = useState(null)

  const charger = () => {
    setLoading(true)
    setErreur(null)
    Promise.all([juridiqueApi.list(), juridiqueApi.tableauBord()])
      .then(([liste, bord]) => {
        setDossiers(Array.isArray(liste.data)
          ? liste.data : (liste.data?.results ?? []))
        setCockpit(bord.data)
      })
      .catch(() => setErreur('Impossible de charger les dossiers juridiques.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    charger()
  }, [])

  const stats = useMemo(() => {
    if (!cockpit) return []
    return [
      {
        label: 'Dossiers suivis',
        value: cockpit.nombre_dossiers ?? 0,
        hint: `${cockpit.echeances_prescription_30j ?? 0} prescription(s) < 30 j`,
        icon: Scale,
      },
      {
        label: 'Montant en jeu',
        value: formatMAD(cockpit.montant_en_jeu_total),
        hint: 'Dossiers non clos',
      },
      {
        label: 'Budget consommé',
        value: formatMAD(cockpit.total_consomme),
        hint: `${formatMAD(cockpit.total_engage)} engagé(s)`,
      },
      {
        label: 'Provisions',
        value: cockpit.provisions_comptabilisees ?? 0,
        hint: `${cockpit.provisions_proposees ?? 0} proposée(s)`,
      },
    ]
  }, [cockpit])

  const columns = useMemo(() => [
    {
      id: 'reference',
      header: 'Référence',
      width: 140,
      accessor: (d) => d.reference || '',
      cell: (value) => (value
        ? <span className="font-mono text-xs">{value}</span>
        : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'titre',
      header: 'Titre',
      width: 240,
      accessor: (d) => d.titre,
      cell: (value) => <span className="font-medium">{value || '—'}</span>,
    },
    {
      id: 'nature',
      header: 'Nature',
      width: 130,
      accessor: (d) => NATURE_MAP[d.nature] || d.nature || '',
      cell: (value) => <Badge tone="neutral">{value || '—'}</Badge>,
    },
    {
      id: 'procedure',
      header: 'Procédure',
      width: 130,
      accessor: (d) => PROCEDURE_MAP[d.type_procedure] || d.type_procedure || '',
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 160,
      accessor: (d) => d.statut,
      cell: (value) => <StatutDossierPill status={value} />,
    },
    {
      id: 'confidentialite',
      header: 'Confidentialité',
      width: 140,
      accessor: (d) => d.confidentialite,
      cell: (value) => <ConfidentialitePill status={value} />,
    },
    {
      id: 'montant',
      header: 'Montant en jeu',
      width: 150,
      align: 'right',
      numeric: true,
      searchable: false,
      accessor: (d) => Number(d.montant_en_jeu ?? 0),
      cell: (_v, d) => {
        const m = Number(d.montant_en_jeu ?? 0)
        return m
          ? <span className="font-medium">{formatMAD(m)}</span>
          : <span className="text-muted-foreground">—</span>
      },
    },
    {
      id: 'ouverture',
      header: 'Ouvert le',
      width: 120,
      align: 'right',
      searchable: false,
      accessor: (d) => d.date_ouverture || '',
      cell: (value) => (
        <span className="text-muted-foreground">
          {value ? formatDate(value) : '—'}
        </span>
      ),
    },
  ], [])

  const rowActions = (d) => [
    { id: 'view', label: 'Ouvrir', icon: Eye, onClick: () => setSelection(d) },
  ]

  if (selection) {
    return (
      <DossierDetailPage
        dossierId={selection.id}
        onBack={() => setSelection(null)}
        onChanged={charger}
      />
    )
  }

  return (
    <div className="page flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="inline-flex items-center gap-2 font-display text-xl font-semibold tracking-tight">
          <Scale className="size-5" aria-hidden="true" />
          Affaires juridiques
        </h1>
      </div>

      <ModuleDashboard stats={stats} loading={loading && !cockpit} error={erreur} />

      <ListShell
        title="Registre des dossiers"
        columns={columns}
        rows={dossiers}
        loading={loading}
        error={erreur}
        onRowClick={setSelection}
        rowActions={rowActions}
        searchable
        searchPlaceholder="Rechercher (référence, titre, partie adverse)…"
        exportName="juridique-dossiers"
        emptyTitle="Aucun dossier juridique"
        emptyDescription="Aucun dossier n'est enregistré pour votre société."
      />
    </div>
  )
}
