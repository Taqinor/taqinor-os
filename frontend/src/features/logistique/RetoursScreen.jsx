import { useCallback, useEffect, useState } from 'react'
import { Undo2 } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Spinner, EmptyState,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { formatDate } from '../../lib/format'
import api from '../../api/axios'

/* ============================================================================
   WIR111 — Consultation « Retours » (`/logistique/retours`).
   ----------------------------------------------------------------------------
   Étend le module Logistique aux retours jusqu'ici backend-only : retours de
   matériel (depuis un chantier) et retours de livraison. Consultation lecture
   seule (un onglet par nature) ; le cycle de validation reste côté API.
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
  if (rows.length === 0) return <EmptyState icon={Undo2} title={emptyLabel} className="py-6" />
  return <SimpleTable columns={columns} rows={rows} />
}

const statutBadge = (r) => (
  <Badge tone={r.statut === 'valide' ? 'success' : r.statut === 'annule' ? 'neutral' : 'info'}>
    {r.statut_display || r.statut || '—'}
  </Badge>
)

const MATERIEL_COLS = [
  { key: 'installation_reference', label: 'Chantier', render: (r) => r.installation_reference || r.installation || '—' },
  { key: 'statut', label: 'Statut', render: statutBadge },
  { key: 'lignes', label: 'Lignes', render: (r) => (r.lignes?.length ?? 0) },
  { key: 'valide_le', label: 'Validé le', render: (r) => formatDate(r.valide_le) },
  { key: 'date_creation', label: 'Créé le', render: (r) => formatDate(r.date_creation) },
]
const LIVRAISON_COLS = [
  { key: 'livraison_reference', label: 'Livraison', render: (r) => r.livraison_reference || r.livraison || '—' },
  { key: 'motif', label: 'Motif', render: (r) => r.motif || '—' },
  { key: 'statut', label: 'Statut', render: statutBadge },
  { key: 'lignes', label: 'Lignes', render: (r) => (r.lignes?.length ?? 0) },
  { key: 'date_creation', label: 'Créé le', render: (r) => formatDate(r.date_creation) },
]

const TABS = [
  { value: 'materiel', label: 'Retours matériel', fetcher: () => api.get('/installations/retours-materiel/'), columns: MATERIEL_COLS, empty: 'Aucun retour de matériel' },
  { value: 'livraison', label: 'Retours livraison', fetcher: () => api.get('/installations/retours-livraison/'), columns: LIVRAISON_COLS, empty: 'Aucun retour de livraison' },
]

export default function RetoursScreen() {
  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Retours"
        subtitle="Retours de matériel depuis les chantiers et retours de livraison."
      />
      <Tabs defaultValue="materiel" className="flex flex-col gap-4">
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
