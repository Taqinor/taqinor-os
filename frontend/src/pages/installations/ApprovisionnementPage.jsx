import { useCallback, useEffect, useState } from 'react'
import { PackageSearch } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Spinner, EmptyState,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { formatMAD, formatDate } from '../../lib/format'
import installationsApi from '../../api/installationsApi'

/* ============================================================================
   WIR110 — Approvisionnement avancé (consultation, `/chantiers/approvisionnement`).
   ----------------------------------------------------------------------------
   Écran de CONSULTATION lecture seule pour les 6 familles d'endpoints FG310-318
   qui n'avaient aucun écran : seuils d'approbation BCF, approbations BCF,
   contrats-cadre, commandes d'appel, contrats de prix fournisseur, réceptions
   non facturées. Un onglet par famille, chargé à la demande. Le workflow
   d'écriture (approuver/lettrer/activer…) reste côté API — cet écran rend
   simplement visible l'existant. Écran interne (Responsable/Directeur) : les
   prix négociés affichés sont INTERNES, jamais du contenu client.
   ========================================================================== */

// Table légère (pas le moteur DataTable) : consultation minimale, colonnes
// déclaratives { key, label, render? }.
function SimpleTable({ columns, rows, rowKey = (r) => r.id }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
            {columns.map((c) => (
              <th key={c.key} className="px-3 py-2 font-medium">{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)} className="border-b border-border/60 last:border-0">
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

// Onglet générique : charge via `fetcher`, montre spinner/erreur/vide/tableau.
function ResourceTab({ fetcher, columns, rowKey, emptyLabel }) {
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
  if (rows.length === 0) {
    return <EmptyState icon={PackageSearch} title={emptyLabel} className="py-6" />
  }
  return <SimpleTable columns={columns} rows={rows} rowKey={rowKey} />
}

const mad = (v) => (v == null ? '—' : formatMAD(v, { decimals: 0 }))
const statutBadge = (r) => (
  <Badge tone={r.statut === 'actif' || r.statut === 'active' ? 'success'
    : r.statut === 'cloture' || r.statut === 'expire' ? 'neutral' : 'info'}>
    {r.statut_display || r.statut || '—'}
  </Badge>
)

const SEUILS_COLS = [
  { key: 'seuil_responsable', label: 'Seuil Responsable (MAD)', render: (r) => mad(r.seuil_responsable) },
  { key: 'actif', label: 'Actif', render: (r) => (r.actif ? 'Oui' : 'Non') },
  { key: 'date_modification', label: 'Modifié le', render: (r) => formatDate(r.date_modification) },
]
const APPROBATIONS_COLS = [
  { key: 'bcf', label: 'BCF', render: (r) => r.bcf ?? '—' },
  { key: 'palier_display', label: 'Palier', render: (r) => r.palier_display || r.palier || '—' },
  { key: 'montant_approuve', label: 'Montant approuvé', render: (r) => mad(r.montant_approuve) },
  { key: 'date_approbation', label: 'Approuvé le', render: (r) => formatDate(r.date_approbation) },
]
const CADRE_COLS = [
  { key: 'reference', label: 'Référence' },
  { key: 'intitule', label: 'Intitulé' },
  { key: 'fournisseur_nom', label: 'Fournisseur', render: (r) => r.fournisseur_nom || '—' },
  { key: 'statut', label: 'Statut', render: statutBadge },
  { key: 'date_fin', label: 'Échéance', render: (r) => formatDate(r.date_fin) },
  { key: 'lignes', label: 'Lignes', render: (r) => (r.lignes?.length ?? 0) },
]
const APPELS_COLS = [
  { key: 'ligne', label: 'Ligne cadre', render: (r) => r.ligne ?? '—' },
  { key: 'quantite', label: 'Quantité', render: (r) => r.quantite ?? '—' },
  { key: 'montant', label: 'Montant', render: (r) => mad(r.montant) },
  { key: 'date_appel', label: "Date d'appel", render: (r) => formatDate(r.date_appel) },
]
const CONTRATS_COLS = [
  { key: 'reference', label: 'Référence' },
  { key: 'intitule', label: 'Intitulé' },
  { key: 'fournisseur_nom', label: 'Fournisseur', render: (r) => r.fournisseur_nom || '—' },
  { key: 'version', label: 'Version', render: (r) => r.version ?? '—' },
  { key: 'statut', label: 'Statut', render: statutBadge },
  { key: 'date_fin', label: 'Fin', render: (r) => formatDate(r.date_fin) },
]
const RECEPTIONS_COLS = [
  { key: 'libelle', label: 'Libellé' },
  { key: 'bon_commande', label: 'Bon de commande', render: (r) => r.bon_commande ?? '—' },
  { key: 'montant_a_provisionner', label: 'À provisionner', render: (r) => mad(r.montant_a_provisionner) },
  { key: 'lettre', label: 'Lettré', render: (r) => (r.lettre ? 'Oui' : 'Non') },
  { key: 'date_reception', label: 'Réceptionné le', render: (r) => formatDate(r.date_reception) },
]

const TABS = [
  { value: 'seuils', label: 'Seuils BCF', fetcher: () => installationsApi.getSeuilsApprobationBcf(), columns: SEUILS_COLS, empty: 'Aucun seuil configuré' },
  { value: 'approbations', label: 'Approbations BCF', fetcher: () => installationsApi.getApprobationsBcf(), columns: APPROBATIONS_COLS, empty: 'Aucune approbation' },
  { value: 'cadre', label: 'Contrats-cadre', fetcher: () => installationsApi.getCommandesCadre(), columns: CADRE_COLS, empty: 'Aucun contrat-cadre' },
  { value: 'appels', label: "Commandes d'appel", fetcher: () => installationsApi.getAppelsCommande(), columns: APPELS_COLS, empty: "Aucune commande d'appel" },
  { value: 'contrats', label: 'Contrats de prix', fetcher: () => installationsApi.getContratsPrixFournisseur(), columns: CONTRATS_COLS, empty: 'Aucun contrat de prix' },
  { value: 'receptions', label: 'Réceptions non facturées', fetcher: () => installationsApi.getReceptionsNonFacturees(), columns: RECEPTIONS_COLS, empty: 'Aucune réception non facturée' },
]

export default function ApprovisionnementPage() {
  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Approvisionnement avancé"
        subtitle="Seuils et approbations BCF, contrats-cadre, commandes d'appel, contrats de prix fournisseur et réceptions non facturées."
      />
      <Tabs defaultValue="seuils" className="flex flex-col gap-4">
        <TabsList className="flex flex-wrap">
          {TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
          ))}
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
