import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Copy, Archive, Plus } from 'lucide-react'
import aoApi from '../../api/aoApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'
import { Badge, Button, toast } from '../../ui'
import { ListShell, daysUntil, urgencyLevel, urgencyTone, urgencyLabel } from '../../ui/module'
import { formatDate, formatMAD } from '../../lib/format'
import { StatutAffaire } from './statusAo'

/* ============================================================================
   AOF170 — Liste des affaires AO (`ListShell`).
   ----------------------------------------------------------------------------
   Données via `useResource` + `aoApi` (zéro `useState`/`useEffect` de fetch,
   ARC45). Tri/filtre persistés en URL (`persistToUrl` + `urlKey`, moteur
   DataTable H33 — aucun câblage manuel ici). `dupliquer` (AOF130) et
   `archiver` (ARCHIVAGE LOGIQUE, jamais une suppression dure — l'affaire sort
   simplement des vues par défaut, elle reste retrouvable via la vue
   « Toutes ») appellent toutes deux un service serveur RÉEL, jamais une
   action de façade.

   `capacite_engagement`/`dossier_completude` : champs agrégés PAS ENCORE posés
   par le serializer actuel (`apps/ao/serializers.py` → `AppelOffreSerializer`,
   ODX11) — livrés par la lane `backend/ao` au fil du Groupe AOF. Rendu
   défensif (« — » si absents), jamais un calcul de substitution côté front.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

// H33 — vues sauvegardées : `columnFilters` = `{ [colId]: valeurs[] }`
// (appartenance multi-select, `logic.js::columnFilterPredicate`).
const SAVED_VIEWS = [
  { id: 'toutes', label: 'Toutes' },
  {
    id: 'en_cours',
    label: 'En cours',
    columnFilters: { statut: ['identifie', 'en_preparation', 'depose'] },
  },
  { id: 'gagnees', label: 'Gagnées', columnFilters: { statut: ['gagne'] } },
  {
    id: 'closes',
    label: 'Perdues / abandonnées',
    columnFilters: { statut: ['perdu', 'abandonne'] },
  },
]

export default function AffairesList() {
  const navigate = useNavigate()

  const { data: rows, loading, error, refetch } = useResource(
    () => aoApi.affaires.list(),
    undefined,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les affaires.' },
  )

  // AOF130 — duplication (gabarit d'affaire réutilisable, service réel).
  const dupliquer = async (row) => {
    try {
      const res = await aoApi.affaires.dupliquer(row.id)
      toast.success('Affaire dupliquée.')
      refetch()
      if (res?.data?.id) navigate(`/ao/affaires/${res.data.id}`)
    } catch (e) {
      toast.error(errMsg(e, 'Duplication impossible.'))
    }
  }

  // Archivage LOGIQUE — jamais une suppression dure : réutilise le `update()`
  // générique de la factory (ARC44), aucune action serveur dédiée requise.
  const archiver = async (row) => {
    try {
      await aoApi.affaires.update(row.id, { archive: true })
      toast.success('Affaire archivée.')
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Archivage impossible.'))
    }
  }

  const rowActions = (row) => [
    { id: 'dupliquer', label: 'Dupliquer', icon: Copy, onClick: () => dupliquer(row) },
    { id: 'archiver', label: 'Archiver', icon: Archive, onClick: () => archiver(row) },
  ]

  const columns = useMemo(() => [
    {
      id: 'reference',
      header: 'Référence',
      width: 140,
      accessor: (r) => r.reference || `#${r.id}`,
      cell: (v) => <span className="font-mono text-xs">{v}</span>,
    },
    {
      // AOF170 — la référence de l'ACHETEUR, à côté de la nôtre.
      // `reference` est la référence PLATEFORME (`AO-YYYYMM-0001`, générée par
      // `core.numbering`) ; celle que l'acheteur imprime sur son avis vit dans
      // un champ distinct (`apps/ao/services.creer_appel_offre_depuis_avis` :
      // « les confondre rendrait impossible de retrouver un dossier depuis
      // l'avis publié »). Sans cette colonne, la liste n'affichait AUCUN moyen
      // de retrouver une affaire depuis l'avis — et l'affaire de démonstration
      // `seed_ao_demo` (repérée par sa référence acheteur) était introuvable à
      // l'écran. Colonne cherchable : c'est le premier réflexe de saisie.
      id: 'reference_acheteur',
      header: 'Réf. acheteur',
      width: 200,
      accessor: (r) => r.reference_acheteur || '',
      cell: (v) => (v
        ? <span className="font-mono text-xs">{v}</span>
        : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'objet',
      header: 'Objet',
      width: 240,
      accessor: (r) => r.objet || '',
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'acheteur',
      header: 'Acheteur',
      width: 180,
      accessor: (r) => r.acheteur || '',
      cell: (v) => v || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'type_marche',
      header: 'Type de marché',
      width: 120,
      accessor: (r) => r.type_marche_display || r.type_marche || '',
      cell: (v) => v || '—',
    },
    {
      id: 'lot',
      header: 'Lot',
      width: 110,
      accessor: (r) => r.lot || '',
      cell: (v) => v || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'date_limite',
      header: 'Date limite',
      width: 190,
      align: 'right',
      searchable: false,
      accessor: (r) => r.date_limite || '',
      cell: (v) => {
        if (!v) return <span className="text-muted-foreground">—</span>
        const days = daysUntil(v)
        const level = urgencyLevel(days)
        return (
          <span className="inline-flex items-center justify-end gap-1.5 tabular-nums">
            {formatDate(v)}
            <Badge tone={urgencyTone(level)}>{urgencyLabel(days)}</Badge>
          </span>
        )
      },
    },
    {
      id: 'montant_estime',
      header: 'Montant estimé',
      align: 'right',
      numeric: true,
      width: 150,
      searchable: false,
      accessor: (r) => Number(r.montant_estime ?? 0),
      cell: (v) => <span className="font-medium tabular-nums">{formatMAD(v)}</span>,
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 140,
      searchable: false,
      accessor: (r) => r.statut,
      cell: (v) => <StatutAffaire status={v} />,
    },
    {
      id: 'capacite_engagement',
      header: 'Capacité vs engagement',
      width: 170,
      searchable: false,
      accessor: (r) => r.capacite_engagement_label || '',
      cell: (v) => v || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'dossier_completude',
      header: 'Complétude du dossier',
      align: 'right',
      width: 160,
      searchable: false,
      accessor: (r) => (r.dossier_completude != null ? Number(r.dossier_completude) : null),
      cell: (v) => (v != null
        ? <span className="tabular-nums">{Math.round(v)} %</span>
        : <span className="text-muted-foreground">—</span>),
    },
  ], [])

  return (
    <ListShell
      title="Affaires"
      subtitle="Appels d'offres publics/privés — identifié → en préparation → déposé → gagné/perdu/abandonné."
      // AOF — 194 tâches du groupe avaient été livrées SANS jamais construire
      // l'écran de création (`AffaireForm.jsx`) : la liste n'avait AUCUN moyen
      // d'ouvrir une affaire. `actions` (prop `ListShell`, passe-plat vers
      // `PageHeader`) accepte un nœud — bouton réel, jamais une façade.
      actions={(
        <Button onClick={() => navigate('/ao/affaires/nouveau')}>
          <Plus className="size-4" /> Nouvelle affaire
        </Button>
      )}
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      rowActions={rowActions}
      searchable
      searchPlaceholder="Rechercher référence, objet, acheteur…"
      savedViews={SAVED_VIEWS}
      persistToUrl
      urlKey="ao-affaires"
      exportName="affaires-ao"
      emptyTitle="Aucune affaire"
      emptyDescription="Aucune affaire AO ne correspond à cette vue."
      onRowClick={(r) => navigate(`/ao/affaires/${r.id}`)}
    />
  )
}
