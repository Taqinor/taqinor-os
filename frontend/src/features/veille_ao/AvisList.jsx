import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import veilleAoApi from '../../api/veilleAoApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'
import { Badge } from '../../ui'
import { ListShell, statusPill, daysUntil, urgencyLevel, urgencyTone, urgencyLabel } from '../../ui/module'
import { formatDate, formatMAD } from '../../lib/format'

/* ============================================================================
   VAO33 — La liste des avis (`ListShell`) : la page qu'on ouvre le matin.
   ----------------------------------------------------------------------------
   Données via `useResource` + `veilleAoApi` (zéro `useState`/`useEffect` de
   fetch, ARC45), tri/filtre persistés en URL (`persistToUrl` + `urlKey`,
   moteur DataTable H33). Le bandeau de santé (VAO37, `SanteVeille`) sera monté
   EN HAUT via le slot `children` de `ListShell` par la tâche VAO37 elle-même
   (c'est un bandeau, pas un écran séparé — le module n'a que 3 routes, VAO32) :
   pas de référence en avant ici, `SanteVeille.jsx` n'existe pas encore à ce
   stade de la lane.

   `STATUT_AVIS`/`StatutAvis` sont définis ICI (pas de fichier `statusAvis.js`
   séparé — aucune tâche VAO32-37 n'en déclare un) et RÉ-EXPORTÉS pour
   `AvisDetail.jsx` (VAO34, même dossier) : miroir de `AppelOffre.Statut` côté
   AO (`nouveau → retenu|ignore ; retenu → converti ; tout → expire`, VAO14).
   ========================================================================== */

export const STATUT_AVIS = {
  nouveau: { label: 'Nouveau', tone: 'info' },
  retenu: { label: 'Retenu', tone: 'success' },
  ignore: { label: 'Ignoré', tone: 'neutral' },
  converti: { label: 'Converti', tone: 'success' },
  expire: { label: 'Expiré', tone: 'danger' },
}
export const StatutAvis = statusPill(STATUT_AVIS)

// VAO33 (Done=) — « la pastille compte juste (test) » : logique PURE, testable
// hors React. Compte les avis au statut `nouveau` dont l'horodatage de
// création (`cree_le`, convention déjà en vigueur — cf. `ContratDetail.jsx`
// `v.cree_le`) tombe depuis minuit HIER (jamais un « depuis 24 h » glissant :
// « depuis hier » se lit au jour calendaire, comme `daysUntil`/`urgency.js`).
export function avisNouveauxDepuisHier(rows = [], now = new Date()) {
  const base = now instanceof Date ? now : new Date(now)
  if (Number.isNaN(base.getTime())) return 0
  const hier = new Date(base.getFullYear(), base.getMonth(), base.getDate() - 1)
  return rows.filter((r) => {
    if (r?.statut !== 'nouveau' || !r?.cree_le) return false
    const cree = new Date(r.cree_le)
    return !Number.isNaN(cree.getTime()) && cree >= hier
  }).length
}

// H33 — vues sauvegardées : `columnFilters` = `{ [colId]: valeurs[] }`.
const SAVED_VIEWS = [
  { id: 'toutes', label: 'Toutes' },
  { id: 'nouveaux', label: 'Nouveaux', columnFilters: { statut: ['nouveau'] } },
  { id: 'retenus', label: 'Retenus', columnFilters: { statut: ['retenu', 'converti'] } },
  { id: 'ignores', label: 'Ignorés', columnFilters: { statut: ['ignore'] } },
]

export default function AvisList() {
  const navigate = useNavigate()

  const { data: rows, loading, error } = useResource(
    () => veilleAoApi.avis.list(),
    undefined,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les avis.' },
  )

  const nouveaux = useMemo(() => avisNouveauxDepuisHier(rows), [rows])

  const columns = useMemo(() => [
    {
      id: 'objet',
      header: 'Objet',
      minWidth: 220,
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
      id: 'source',
      header: 'Source',
      width: 140,
      searchable: false,
      accessor: (r) => r.source_libelle || r.source_nom || '',
      cell: (v) => v || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'lieu',
      header: 'Lieu',
      width: 150,
      accessor: (r) => r.lieu || r.region || '',
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
      cell: (v) => (v ? <span className="font-medium tabular-nums">{formatMAD(v)}</span> : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'score',
      header: 'Score',
      align: 'right',
      numeric: true,
      width: 90,
      searchable: false,
      accessor: (r) => Number(r.score ?? 0),
      cell: (v) => <span className="tabular-nums">{v}</span>,
    },
    {
      id: 'mots_cles_declenches',
      header: 'Mots déclencheurs',
      width: 220,
      accessor: (r) => (Array.isArray(r.mots_cles_declenches) ? r.mots_cles_declenches.join(' ') : ''),
      cell: (_v, r) => {
        const mots = Array.isArray(r.mots_cles_declenches) ? r.mots_cles_declenches : []
        if (!mots.length) return <span className="text-muted-foreground">—</span>
        return (
          <span className="flex flex-wrap gap-1">
            {mots.map((m) => <Badge key={m} tone="neutral">{m}</Badge>)}
          </span>
        )
      },
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 220,
      searchable: false,
      accessor: (r) => r.statut,
      cell: (v, r) => (
        <span className="flex flex-col gap-0.5">
          <StatutAvis status={v} />
          {/* VAO10/VAO33 (Done=) — un avis auto-ignoré affiche la règle qui
              l'a filtré, jamais un filtrage muet. */}
          {v === 'ignore' && r.regle_exclusion_motif && (
            <span className="text-xs text-muted-foreground">
              règle : {r.regle_exclusion_motif}
            </span>
          )}
        </span>
      ),
    },
  ], [])

  return (
    <ListShell
      title="Avis"
      subtitle="Veille appels d'offres — le sas où atterrissent tous les avis, quelle que soit la porte."
      actions={nouveaux > 0 ? <Badge tone="info">{nouveaux} nouveau{nouveaux > 1 ? 'x' : ''} depuis hier</Badge> : null}
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      searchable
      searchPlaceholder="Rechercher objet, acheteur, lieu…"
      savedViews={SAVED_VIEWS}
      persistToUrl
      urlKey="veille-ao-avis"
      exportName="avis-veille-ao"
      emptyTitle="Aucun avis"
      emptyDescription="Aucun avis ne correspond à cette vue — la collecte automatique ne couvre pas tout, voir le bandeau de santé ci-dessus."
      onRowClick={(r) => navigate(`/veille-ao/avis/${r.id}`)}
    />
  )
}
