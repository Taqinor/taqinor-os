import { useCallback, useEffect, useMemo, useState } from 'react'
import { ShoppingCart, RefreshCw } from 'lucide-react'
import scmApi from '../../api/scmApi'
import { formatMAD } from '../../lib/format'
import { Button, Badge, DataTable, EmptyState, Skeleton } from '../../ui'
import { StateBlock } from '../../components/StateBlock'

/* ============================================================================
   NTSCM7 — Tableau de bord réappro consolidé (« remplace/étend » le mini
   panneau FG364 brut de PilotageStock.jsx : ici chaque ligne combine stock
   actuel, prévision de rupture (core.stock_reorder) ET la politique de stock
   NTSCM6 pour un vrai statut à 3 niveaux (OK / à commander / rupture
   imminente), plus le fournisseur le moins cher. Écran INTERNE
   (Responsable/Admin) : le prix d'achat affiché n'est jamais client-facing.
   ========================================================================== */

const STATUT_META = {
  ok: { label: 'OK', tone: 'success' },
  a_commander: { label: 'À commander', tone: 'warning' },
  rupture_imminente: { label: 'Rupture imminente', tone: 'danger' },
}

const STATUT_FILTRES = [
  { value: '', label: 'Tous les statuts' },
  { value: 'rupture_imminente', label: 'Rupture imminente' },
  { value: 'a_commander', label: 'À commander' },
  { value: 'ok', label: 'OK' },
]

const CLASSE_FILTRES = ['', 'A', 'B', 'C']

const fmtDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

export default function ReapproPage() {
  const [lignes, setLignes] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [statutFiltre, setStatutFiltre] = useState('')
  const [classeFiltre, setClasseFiltre] = useState('')
  const [creerBusy, setCreerBusy] = useState(false)
  const [creerMsg, setCreerMsg] = useState(null)
  const [creerErr, setCreerErr] = useState(null)

  const charger = useCallback(() => {
    setLoading(true)
    setLoadError(null)
    const params = {}
    if (statutFiltre) params.statut = statutFiltre
    if (classeFiltre) params.classe_abc = classeFiltre
    return scmApi.tableauBordReappro(params)
      .then((r) => setLignes(r.data ?? []))
      .catch((e) => setLoadError(
        e?.response?.status === 403
          ? 'Réservé aux responsables et administrateurs.'
          : (e?.response?.data?.detail ?? "Le tableau de bord n'a pas pu être chargé.")))
      .finally(() => setLoading(false))
  }, [statutFiltre, classeFiltre])

  useEffect(() => { charger() }, [charger])

  const creerBrouillonsBcf = async () => {
    setCreerBusy(true); setCreerMsg(null); setCreerErr(null)
    try {
      const r = await scmApi.creerBrouillonsBcfReappro({})
      const bons = r.data?.bons_crees ?? []
      setCreerMsg(bons.length > 0
        ? `${bons.length} bon(s) de commande brouillon créé(s) (${bons.reduce((n, b) => n + b.nb_lignes, 0)} ligne(s) au total).`
        : 'Aucune ligne à commander pour le moment.')
      charger()
    } catch (e) {
      setCreerErr(e?.response?.status === 403
        ? 'Réservé aux responsables et administrateurs.'
        : (e?.response?.data?.detail ?? 'La création des bons de commande a échoué.'))
    } finally {
      setCreerBusy(false)
    }
  }

  const columns = useMemo(() => [
    { id: 'produit_nom', header: 'Produit', accessor: (r) => r.produit_nom },
    {
      id: 'classe_abc', header: 'Classe', width: 90,
      accessor: (r) => r.classe_abc || '—',
      cell: (v, r) => r.classe_abc || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'stock_actuel', header: 'Stock actuel', align: 'right', width: 120,
      accessor: (r) => Number(r.stock_actuel) || 0,
      cell: (v, r) => <span className="tabular-nums">{r.stock_actuel}</span>,
    },
    {
      id: 'point_commande', header: 'Point de commande', align: 'right', width: 150,
      accessor: (r) => Number(r.point_commande) || 0,
      cell: (v, r) => <span className="tabular-nums">{r.point_commande}</span>,
    },
    {
      id: 'quantite_suggeree', header: 'Qté suggérée', align: 'right', width: 130,
      accessor: (r) => Number(r.quantite_suggeree) || 0,
      cell: (v, r) => <span className="font-semibold tabular-nums">{r.quantite_suggeree}</span>,
    },
    {
      id: 'rupture_date', header: 'Rupture prévue', width: 130,
      accessor: (r) => r.rupture_date || '',
      cell: (v, r) => fmtDateFR(r.rupture_date),
    },
    {
      id: 'fournisseur_nom', header: 'Fournisseur (− cher)',
      accessor: (r) => r.fournisseur_nom || '',
      cell: (v, r) => r.fournisseur_nom ?? <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'prix_achat_unitaire', header: 'Prix achat (interne)', align: 'right', width: 150,
      accessor: (r) => Number(r.prix_achat_unitaire) || 0,
      cell: (v, r) => (
        <span className="tabular-nums">
          {r.prix_achat_unitaire != null ? formatMAD(r.prix_achat_unitaire) : '—'}
        </span>
      ),
    },
    {
      id: 'statut', header: 'Statut', width: 150,
      accessor: (r) => STATUT_META[r.statut]?.label ?? r.statut,
      cell: (v, r) => {
        const meta = STATUT_META[r.statut] ?? { label: r.statut, tone: 'neutral' }
        return <Badge tone={meta.tone}>{meta.label}</Badge>
      },
    },
  ], [])

  const nbACommander = lignes.filter((l) => l.statut !== 'ok').length

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Tableau de bord réappro</h2>
        <p className="text-sm text-muted-foreground">
          Stock actuel, prévision de rupture et point de commande consolidés
          par politique de stock (classe ABC, stock de sécurité au niveau de
          service). Donnée interne — le prix d&apos;achat n&apos;apparaît
          jamais sur un document client.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          value={statutFiltre}
          onChange={(e) => setStatutFiltre(e.target.value)}
          aria-label="Filtrer par statut"
        >
          {STATUT_FILTRES.map((f) => (
            <option key={f.value || 'tous'} value={f.value}>{f.label}</option>
          ))}
        </select>
        <select
          className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          value={classeFiltre}
          onChange={(e) => setClasseFiltre(e.target.value)}
          aria-label="Filtrer par classe ABC"
        >
          {CLASSE_FILTRES.map((c) => (
            <option key={c || 'toutes'} value={c}>{c ? `Classe ${c}` : 'Toutes les classes'}</option>
          ))}
        </select>
        <Button type="button" variant="outline" size="sm" onClick={charger}>
          <RefreshCw /> Actualiser
        </Button>
        <Button
          type="button" size="sm" loading={creerBusy} onClick={creerBrouillonsBcf}
          disabled={nbACommander === 0}
          title="Groupe les lignes à commander par fournisseur et crée un bon de commande brouillon par fournisseur."
        >
          <ShoppingCart /> Créer les brouillons BCF ({nbACommander})
        </Button>
        {creerMsg && <span className="text-sm text-success" role="status">{creerMsg}</span>}
        {creerErr && <span className="text-sm text-destructive" role="alert">{creerErr}</span>}
      </div>

      {loading ? (
        <Skeleton className="h-64 w-full" />
      ) : loadError ? (
        <StateBlock error={loadError} onRetry={charger} />
      ) : lignes.length === 0 ? (
        <EmptyState
          icon={ShoppingCart}
          title="Aucun produit sous politique de stock"
          description="Recalculez les politiques de stock (classification ABC + stock de sécurité) pour peupler ce tableau de bord."
        />
      ) : (
        <DataTable
          data={lignes}
          columns={columns}
          getRowId={(r) => r.produit_id}
          pageSize={25}
          aria-label="Tableau de bord réappro"
        />
      )}
    </div>
  )
}
