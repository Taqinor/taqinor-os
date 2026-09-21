import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Star } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import { useDebouncedValue } from '../../../lib/debounce'
import { Badge, Input, Segmented } from '../../../ui'
import { ListShell } from '../../../ui/module'
import { formatNumber } from '../../../lib/format'
import { StatutVariante } from '../statusAo'

/* ============================================================================
   PV59 — La VRAIE liste des calepinages : `VarianteCalepinage`, la seule
   ressource qui existe (`aoApi.variantes`, AOF28 — `/ao/variantes-calepinage/`).
   ----------------------------------------------------------------------------
   `/ao/calepinages` (au pluriel) montrait un `EmptyState` disant « pas de vue
   d'ensemble » depuis le 03/08/2026 : la nav promettait « Calepinages » et
   n'ouvrait jamais rien. Ce n'était pas un mensonge à l'époque — il n'existait
   ni modèle « Calepinage » (le calcul est SANS ÉTAT) ni écran de liste des
   variantes PERSISTÉES. Il existe désormais un écran de liste réel : celui-ci,
   monté sur la MÊME route dans `module.config.jsx`.

   Filtres SERVEUR (`VarianteCalepinageViewSet.get_queryset`,
   `apps/ao/views.py` : `toiture`/`appel_offre`/`role`/`statut`) — jamais un
   filtre client sur une liste tronquée. `role`/`statut` : `Segmented` (jeu de
   valeurs fermé, `VarianteCalepinage.Role`/`Statut`). `appel_offre`/`toiture` :
   identifiants numériques saisis à la main (aucun sélecteur d'affaire/toiture
   n'existe à ce niveau — l'écran n'a pas de contexte d'affaire imposé, tout le
   contraire de `VariantesCompare` qui, LUI, vit DANS une fiche affaire) ;
   anti-rebond (`useDebouncedValue`) pour ne pas recharger à chaque frappe.

   Colonne « Toiture / Affaire » : le sérialiseur (AOF28) ne publie que les
   IDENTIFIANTS (`toiture`, `appel_offre`) — aucune jointure nommée n'existe
   sur cette ressource. `nom` (souvent descriptif : « Bâtiment A — segment 2 »,
   « Plan imposé du 12/08 ») porte le repère PRINCIPAL ; les deux identifiants
   restent en second, comme un numéro de dossier. Le clic sur une ligne ouvre
   l'AFFAIRE (`/ao/affaires/<appel_offre>`) — il n'existe pas de fiche « toiture »
   dédiée à ouvrir.

   « Publiable » : `raisons_de_non_publiabilite` (calculée serveur,
   `VarianteCalepinage.raisons_de_non_publiabilite()`) — liste vide = rien qui
   bloque. Non vide, chaque motif est NOMMÉ dans un `<details>` (« expand ») :
   jamais une pastille rouge muette qui forcerait à rouvrir la variante pour
   savoir pourquoi.
   ========================================================================== */

const ROLE_OPTIONS = [
  { value: '', label: 'Tous les rôles' },
  { value: 'RETENUE', label: 'Retenue' },
  { value: 'ALTERNATIVE', label: 'Alternative' },
  { value: 'SENSIBILITE', label: 'Sensibilité' },
  { value: 'MARCHE', label: 'Marche' },
]

const STATUT_OPTIONS = [
  { value: '', label: 'Tous les statuts' },
  { value: 'brouillon', label: 'Brouillon' },
  { value: 'calculee', label: 'Calculée' },
  { value: 'publiable', label: 'Publiable' },
  { value: 'perime', label: 'Périmée' },
]

function CelluleToitureAffaire({ row }) {
  return (
    <div className="flex flex-col">
      <span className="font-medium">{row.nom || `Variante #${row.id}`}</span>
      <span className="text-xs text-muted-foreground">
        {`Toiture #${row.toiture} · Affaire #${row.appel_offre}`}
      </span>
    </div>
  )
}

function CelluleRetenue({ estRetenue }) {
  return (
    <span
      className="inline-flex items-center"
      data-ao-variante-retenue={estRetenue ? 'true' : 'false'}
      aria-label={estRetenue ? 'Variante retenue' : 'Variante non retenue'}
    >
      <Star
        className={estRetenue ? 'size-4 fill-warning text-warning' : 'size-4 text-muted-foreground'}
        aria-hidden="true"
      />
    </span>
  )
}

function CelluleRaisons({ raisons = [] }) {
  if (!raisons.length) {
    // Distinct du texte du badge STATUT (qui peut lui-même valoir « Publiable » :
    // ``raisons_de_non_publiabilite`` vide n'est pas la MÊME affirmation que
    // ``statut === 'publiable'`` — une variante calculée sans réserve peut
    // rester au statut « Calculée » tant qu'elle n'a pas été explicitement
    // publiée).
    return <Badge tone="success" data-ao-raisons-non-publiabilite="aucune">Aucune réserve</Badge>
  }
  return (
    <details data-ao-raisons-non-publiabilite="">
      <summary className="cursor-pointer text-sm font-medium text-destructive">
        {`${raisons.length} raison${raisons.length > 1 ? 's' : ''}`}
      </summary>
      <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
        {raisons.map((raison) => <li key={raison}>{raison}</li>)}
      </ul>
    </details>
  )
}

export default function VariantesListPage() {
  const navigate = useNavigate()

  const [appelOffreSaisi, setAppelOffreSaisi] = useState('')
  const [toitureSaisie, setToitureSaisie] = useState('')
  const [statut, setStatut] = useState('')
  const [role, setRole] = useState('')
  const appelOffreFiltre = useDebouncedValue(appelOffreSaisi, 300)
  const toitureFiltre = useDebouncedValue(toitureSaisie, 300)

  const params = useMemo(() => {
    const p = {}
    if (appelOffreFiltre.trim()) p.appel_offre = appelOffreFiltre.trim()
    if (toitureFiltre.trim()) p.toiture = toitureFiltre.trim()
    if (statut) p.statut = statut
    if (role) p.role = role
    return p
  }, [appelOffreFiltre, toitureFiltre, statut, role])

  const { data: rows, loading, error } = useResource(
    () => aoApi.variantes.list(params), params,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les calepinages.' },
  )

  const columns = useMemo(() => [
    {
      id: 'toiture_affaire',
      header: 'Toiture / Affaire',
      width: 220,
      accessor: (r) => r.nom || `Variante #${r.id}`,
      cell: (_v, row) => <CelluleToitureAffaire row={row} />,
    },
    {
      id: 'role',
      header: 'Rôle',
      width: 130,
      searchable: false,
      accessor: (r) => r.role_display || r.role || '',
      cell: (v) => v || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 140,
      searchable: false,
      accessor: (r) => r.statut,
      cell: (_v, row) => <StatutVariante status={row.statut} label={row.statut_display} />,
    },
    {
      id: 'modules',
      header: 'Modules',
      align: 'right',
      numeric: true,
      width: 100,
      searchable: false,
      accessor: (r) => Number(r.total_modules ?? 0),
      cell: (v) => <span className="tabular-nums">{formatNumber(v)}</span>,
    },
    {
      id: 'kwc',
      header: 'kWc',
      align: 'right',
      numeric: true,
      width: 100,
      searchable: false,
      accessor: (r) => Number(r.puissance_kwc ?? 0),
      cell: (v) => <span className="tabular-nums">{`${formatNumber(v)} kWc`}</span>,
    },
    {
      id: 'est_retenue',
      header: 'Retenue',
      align: 'center',
      width: 90,
      searchable: false,
      accessor: (r) => (r.est_retenue ? 1 : 0),
      cell: (_v, row) => <CelluleRetenue estRetenue={row.est_retenue} />,
    },
    {
      id: 'raisons_de_non_publiabilite',
      header: 'Publiabilité',
      width: 180,
      searchable: false,
      accessor: (r) => (r.raisons_de_non_publiabilite || []).length,
      cell: (_v, row) => <CelluleRaisons raisons={row.raisons_de_non_publiabilite} />,
    },
  ], [])

  const filters = (
    <div className="flex flex-wrap items-center gap-2">
      <Segmented options={ROLE_OPTIONS} value={role} onChange={setRole} size="sm" aria-label="Filtrer par rôle" />
      <Segmented options={STATUT_OPTIONS} value={statut} onChange={setStatut} size="sm" aria-label="Filtrer par statut" />
      <Input
        value={appelOffreSaisi}
        onChange={(e) => setAppelOffreSaisi(e.target.value)}
        placeholder="Affaire #…"
        inputMode="numeric"
        className="h-9 w-28"
        aria-label="Filtrer par identifiant d’affaire"
      />
      <Input
        value={toitureSaisie}
        onChange={(e) => setToitureSaisie(e.target.value)}
        placeholder="Toiture #…"
        inputMode="numeric"
        className="h-9 w-28"
        aria-label="Filtrer par identifiant de toiture"
      />
    </div>
  )

  return (
    <ListShell
      title="Calepinages"
      subtitle="Toutes les variantes de calepinage (AOF28) — retenues, alternatives, sensibilités."
      filters={filters}
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      searchable
      searchPlaceholder="Rechercher un nom de variante…"
      exportName="variantes-calepinage"
      onRowClick={(r) => navigate(`/ao/affaires/${r.appel_offre}`)}
      emptyTitle="Aucun calepinage"
      emptyDescription="Aucune variante de calepinage ne correspond à ces filtres."
    />
  )
}
