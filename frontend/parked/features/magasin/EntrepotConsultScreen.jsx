import { useCallback, useEffect, useState } from 'react'
import { Boxes } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Spinner, EmptyState,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { formatDate } from '../../lib/format'
import api from '../../api/axios'

/* ============================================================================
   WIR111 — Consultation « Entrepôt » (`/magasin/entrepot`).
   ----------------------------------------------------------------------------
   Étend le module Magasin aux endpoints jusqu'ici backend-only de nature
   entrepôt : catégories de stockage, règles de rangement, règles de réappro,
   séries entrepôt, lots de prélèvement, matériels consignés. Consultation
   lecture seule (un onglet par famille) — le workflow reste côté API. Aucun
   prix d'achat affiché (opérations d'entrepôt uniquement).
   ========================================================================== */

function SimpleTable({ columns, rows }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
            {columns.map((c) => <th key={c.key} className="px-3 py-2 font-medium">{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-border/60 last:border-0">
              {columns.map((c) => (
                <td key={c.key} className="px-3 py-2 align-top">
                  {c.render ? c.render(r) : (r[c.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ResourceTab({ fetcher, columns, emptyLabel }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetcher()
      .then((res) => {
        if (cancelled) return
        const payload = res?.data
        setRows(Array.isArray(payload) ? payload : (payload?.results ?? []))
      })
      .catch((err) => {
        if (cancelled) return
        setError(err?.response?.data?.detail || 'Chargement impossible.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  if (loading) return (
    <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (error) return <EmptyState title="Impossible de charger" description={error} className="py-6" />
  if (rows.length === 0) return <EmptyState icon={Boxes} title={emptyLabel} className="py-6" />
  return <SimpleTable columns={columns} rows={rows} />
}

const bool = (v) => (v ? 'Oui' : 'Non')
const statutBadge = (r) => (
  <Badge tone={r.statut === 'valide' || r.statut === 'retourne' ? 'success'
    : r.statut === 'annule' ? 'neutral' : 'info'}>
    {r.statut_display || r.statut || '—'}
  </Badge>
)

const CATEGORIES_COLS = [
  { key: 'nom', label: 'Nom' },
  { key: 'poids_max_kg', label: 'Poids max (kg)', render: (r) => r.poids_max_kg ?? '—' },
  { key: 'qte_max', label: 'Qté max', render: (r) => r.qte_max ?? '—' },
  { key: 'melange_autorise', label: 'Mélange autorisé', render: (r) => bool(r.melange_autorise) },
]
const RANGEMENT_COLS = [
  { key: 'produit_nom', label: 'Produit', render: (r) => r.produit_nom || '—' },
  { key: 'categorie_produit', label: 'Catégorie produit', render: (r) => r.categorie_produit || '—' },
  { key: 'bin_cible_code', label: 'Casier cible', render: (r) => r.bin_cible_code || '—' },
  { key: 'priorite', label: 'Priorité', render: (r) => r.priorite ?? '—' },
  { key: 'actif', label: 'Actif', render: (r) => bool(r.actif) },
]
const REAPPRO_COLS = [
  { key: 'produit_nom', label: 'Produit', render: (r) => r.produit_nom || '—' },
  { key: 'emplacement_cible_nom', label: 'Cible', render: (r) => r.emplacement_cible_nom || '—' },
  { key: 'emplacement_source_nom', label: 'Source', render: (r) => r.emplacement_source_nom || '—' },
  { key: 'seuil_min', label: 'Seuil min', render: (r) => r.seuil_min ?? '—' },
  { key: 'seuil_max', label: 'Seuil max', render: (r) => r.seuil_max ?? '—' },
  { key: 'active', label: 'Active', render: (r) => bool(r.active) },
]
const SERIES_COLS = [
  { key: 'numero_serie', label: 'N° de série' },
  { key: 'produit_nom', label: 'Produit', render: (r) => r.produit_nom || '—' },
  { key: 'bin_code', label: 'Casier', render: (r) => r.bin_code || '—' },
  { key: 'statut', label: 'Statut', render: statutBadge },
]
const LOTS_COLS = [
  { key: 'reference', label: 'Référence' },
  { key: 'operateur_nom', label: 'Opérateur', render: (r) => r.operateur_nom || '—' },
  { key: 'pick_list_ids', label: 'Prélèvements', render: (r) => (r.pick_list_ids?.length ?? 0) },
  { key: 'statut', label: 'Statut', render: statutBadge },
]
const CONSIGNES_COLS = [
  { key: 'designation', label: 'Désignation' },
  { key: 'type_materiel_display', label: 'Type', render: (r) => r.type_materiel_display || r.type_materiel || '—' },
  { key: 'fournisseur_nom', label: 'Fournisseur', render: (r) => r.fournisseur_nom || '—' },
  { key: 'quantite', label: 'Qté', render: (r) => r.quantite ?? '—' },
  { key: 'statut', label: 'Statut', render: statutBadge },
  { key: 'date_retour', label: 'Retour', render: (r) => formatDate(r.date_retour) },
]

const TABS = [
  { value: 'categories', label: 'Catégories de stockage', fetcher: () => api.get('/installations/categories-stockage/'), columns: CATEGORIES_COLS, empty: 'Aucune catégorie de stockage' },
  { value: 'rangement', label: 'Règles de rangement', fetcher: () => api.get('/installations/regles-rangement/'), columns: RANGEMENT_COLS, empty: 'Aucune règle de rangement' },
  { value: 'reappro', label: 'Règles de réappro', fetcher: () => api.get('/installations/regles-reappro/'), columns: REAPPRO_COLS, empty: 'Aucune règle de réappro' },
  { value: 'series', label: 'Séries entrepôt', fetcher: () => api.get('/installations/series-entrepot/'), columns: SERIES_COLS, empty: 'Aucune série en entrepôt' },
  { value: 'lots', label: 'Lots de prélèvement', fetcher: () => api.get('/installations/lots-prelevement/'), columns: LOTS_COLS, empty: 'Aucun lot de prélèvement' },
  { value: 'consignes', label: 'Matériels consignés', fetcher: () => api.get('/installations/materiels-consignes/'), columns: CONSIGNES_COLS, empty: 'Aucun matériel consigné' },
]

export default function EntrepotConsultScreen() {
  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Entrepôt — référentiel & suivi"
        subtitle="Catégories de stockage, règles de rangement et de réappro, séries, lots de prélèvement et matériels consignés."
      />
      <Tabs defaultValue="categories" className="flex flex-col gap-4">
        <TabsList className="flex flex-wrap">
          {TABS.map((t) => <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>)}
        </TabsList>
        {TABS.map((t) => (
          <TabsContent key={t.value} value={t.value}>
            <ResourceTab fetcher={t.fetcher} columns={t.columns} emptyLabel={t.empty} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
