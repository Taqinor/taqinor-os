import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Wallet, TrendingUp, Landmark, Clock, Percent, Users,
  FolderOpen, ReceiptText, FileBarChart2, Scale,
} from 'lucide-react'
import { ModuleDashboard } from '../../../ui/module'
import { BarArrondie } from '../../../ui/charts'
import { toast, Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../../ui'
import { formatMAD, formatNumber, formatPercent } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
// APX35 — les tranches d'ancienneté viennent de la balance âgée DÉJÀ exposée :
// aucun endpoint nouveau, aucun champ serveur ajouté.
import ventesApi from '../../../api/ventesApi'
import api from '../../../api/axios'

// VX115 — les 4 destinations où le comptable externe va chercher son export
// mensuel (index de navigation pur : ZÉRO logique d'export dupliquée ici).
const EXPORT_DESTINATIONS = [
  {
    to: '/ventes/factures',
    label: 'Factures — Export comptable',
    hint: 'Export DGI (Excel + CSV) d’une plage de factures validées',
    icon: ReceiptText,
  },
  {
    to: '/comptabilite/fiscalite',
    label: 'Fiscalité',
    hint: 'Échéances et déclarations fiscales',
    icon: Scale,
  },
  {
    to: '/comptabilite/etats',
    label: 'États CGNC',
    hint: 'Résultat, bilan et journaux comptables',
    icon: FileBarChart2,
  },
  {
    to: '/reporting/balance-agee',
    label: 'Balance âgée',
    hint: 'Créances clients par ancienneté',
    icon: FolderOpen,
  },
]

/* ============================================================================
   UX2 — Cockpit financier (GET /compta/pilotage/cockpit/).
   ----------------------------------------------------------------------------
   Lecture seule. Le selector renvoie : resultat_periode, chiffre_affaires,
   tresorerie, marge_brute(_pct), encours_clients/fournisseurs, dso, dpo,
   top_encours_clients[]. (Le backend n'expose PAS de série mensuelle sur 12
   mois ni de « créances en retard » — on rend donc les KPI réels + un top des
   encours clients, avec liens de drill-down vers les états.)
   ========================================================================== */

// VX232(a) — résolution pure `tiers_id` → nom (extraite pour un test unitaire
// direct, sans dépendre du rendu recharts) ; repli « Tiers #N » si la fiche a
// été supprimée entre-temps ou n'a pas encore été chargée.
// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé, testé isolément
export function resolveTiersLabel(tiersId, tiersById) {
  if (!tiersId) return 'Non affecté'
  return tiersById[tiersId] || `Tiers #${tiersId}`
}

export default function CockpitPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // VX232(a) — résout `tiers_id` en nom réel côté FRONTEND (répertoire unifié
  // `apps/tiers`), chargé une fois : le KPI n°1 affichait « Tiers #42 » brut ;
  // repli « Tiers #N » conservé si la fiche a été supprimée entre-temps.
  const [tiersById, setTiersById] = useState({})

  useEffect(() => {
    // Timeout court et dédié : purement décoratif (repli « Tiers #N » déjà
    // correct), jamais bloquant pour le reste du cockpit.
    api.get('/tiers/tiers/', { params: { page_size: 500 }, timeout: 4000 })
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results || [])
        const map = {}
        list.forEach((t) => {
          map[t.id] = (t.type_tiers === 'entreprise' && t.raison_sociale)
            || `${t.prenom || ''} ${t.nom || ''}`.trim() || t.nom
        })
        setTiersById(map)
      })
      .catch(() => {}) // silencieux : le repli « Tiers #N » suffit.
  }, [])

  const load = useCallback(() => {
    let alive = true
    setLoading(true)
    setError(null)
    comptaApi.cockpit()
      .then((res) => { if (alive) setData(res.data) })
      .catch(() => {
        if (!alive) return
        setError('Impossible de charger le cockpit financier.')
        toast.error('Impossible de charger le cockpit financier.')
      })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  // APX35 — tranches d'ancienneté de la créance client, dérivées de la balance
  // âgée DÉJÀ exposée (`getBalanceAgee`, bornée société côté serveur) : aucun
  // endpoint nouveau, aucun champ serveur ajouté. Un échec est silencieux —
  // la rangée disparaît simplement (jamais un zéro trompeur).
  const [aging, setAging] = useState(null)
  useEffect(() => {
    let alive = true
    ventesApi.getBalanceAgee()
      .then((res) => { if (alive) setAging(Array.isArray(res.data) ? res.data : []) })
      .catch(() => { if (alive) setAging([]) })
    return () => { alive = false }
  }, [])

  const agingBuckets = useMemo(() => {
    const rows = aging || []
    const somme = (k) => rows.reduce((s, r) => s + (Number(r[k]) || 0), 0)
    return [
      { value: '0_30', label: '0–30 j', total: somme('b0_30'), className: 'border-border' },
      { value: '31_60', label: '31–60 j', total: somme('b31_60'), className: 'border-warning/40 bg-warning/10 text-warning' },
      { value: '61_90', label: '61–90 j', total: somme('b61_90'), className: 'border-warning/60 bg-warning/15 text-warning' },
      { value: '90_plus', label: '90+ j', total: somme('b90_plus'), className: 'border-destructive/50 bg-destructive/10 text-destructive' },
    ]
  }, [aging])

  const d = data || {}
  // APX35 — le cockpit était propre mais PLAT : huit KPI de même poids, aucune
  // hiérarchie. La trésorerie nette (champ déjà servi par le selector) devient
  // LE chiffre héros ; les autres restent des `<Stat>` secondaires.
  const stats = [
    {
      label: 'Résultat de la période',
      value: formatMAD(d.resultat_periode),
      hint: "Produits − charges (CPC) de l'exercice en cours",
      icon: TrendingUp,
      to: '/comptabilite/etats',
    },
    {
      label: 'Marge brute',
      value: formatMAD(d.marge_brute),
      hint: `Taux : ${formatPercent(d.marge_brute_pct, { decimals: 1 })}`,
      icon: Percent,
    },
    {
      label: 'Chiffre d’affaires',
      value: formatMAD(d.chiffre_affaires),
      hint: 'Total des produits sur la période',
      icon: Landmark,
    },
    {
      label: 'DSO (encaissement client)',
      value: `${formatNumber(d.dso)} j`,
      hint: `Encours clients : ${formatMAD(d.encours_clients)}`,
      icon: Clock,
      to: '/ventes/relances',
    },
    {
      label: 'DPO (paiement fournisseur)',
      value: `${formatNumber(d.dpo)} j`,
      hint: `Encours fournisseurs : ${formatMAD(d.encours_fournisseurs)}`,
      icon: Clock,
    },
    {
      label: 'Créances clients',
      value: formatMAD(d.encours_clients),
      hint: 'Encours non lettré (compte 3421)',
      icon: Users,
      to: '/reporting/balance-agee',
    },
    {
      label: 'Dettes fournisseurs',
      value: formatMAD(d.encours_fournisseurs),
      hint: 'Encours (compte 4411)',
      icon: Users,
    },
  ]

  // Top des encours clients (bar horizontal) — drill-down implicite vers états.
  const topEncours = (d.top_encours_clients || []).map((row) => ({
    label: resolveTiersLabel(row.tiers_id, tiersById),
    value: Number(row.encours) || 0,
  }))

  const charts = topEncours.length > 0
    ? [{
        title: 'Top encours clients',
        span: 'full',
        node: (
          <BarArrondie
            data={topEncours}
            layout="vertical"
            height={Math.max(160, topEncours.length * 34)}
            tone="info"
            tooltipFormat={(v) => formatMAD(v)}
          />
        ),
      }]
    : []

  return (
    <div className="page">
      <div className="page-header">
        <h2>Cockpit financier</h2>
      </div>

      {/* APX35 — UN chiffre héros (patron Stripe) : la trésorerie nette, en
          échelle display et en data typography `.num`. C'est le chiffre que le
          dirigeant vient chercher ; il ne se noie plus dans huit cartes de
          même poids. */}
      <Link
        to="/comptabilite/tresorerie"
        className="mb-4 block rounded-xl transition-shadow hover:ring-2 hover:ring-ring/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Card className="border-primary/40 bg-primary/[0.06]">
          <CardContent className="pt-5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Trésorerie nette
            </span>
            <div
              className="num text-display font-display font-bold leading-none"
              data-testid="cockpit-hero"
            >
              {loading ? '—' : formatMAD(d.tresorerie)}
            </div>
            <span className="mt-2 block text-sm text-muted-foreground">
              Position consolidée et prévisionnel →
            </span>
          </CardContent>
        </Card>
      </Link>

      {/* APX35 — l'AGING en buckets colorés, cliquables. Les tranches sont
          calculées depuis la balance âgée DÉJÀ exposée (`getBalanceAgee`,
          bornée société côté serveur) : aucun endpoint nouveau, aucun champ
          serveur ajouté. Chaque bucket ouvre la balance âgée pré-filtrée. */}
      {agingBuckets.some((b) => b.total > 0) && (
        <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="cockpit-aging">
          {agingBuckets.map((b) => (
            <Link
              key={b.value}
              to={`/reporting/balance-agee?bucket=${b.value}`}
              className={`rounded-lg border p-3 transition-shadow hover:ring-2 hover:ring-ring/40 ${b.className}`}
              data-testid={`cockpit-aging-${b.value}`}
            >
              <span className="block text-xs font-medium uppercase tracking-wide">{b.label}</span>
              <span className="num mt-1 block text-lg font-semibold leading-none">
                {formatMAD(b.total)}
              </span>
            </Link>
          ))}
        </div>
      )}

      <ModuleDashboard
        stats={stats}
        charts={charts}
        loading={loading}
        error={error}
      />
      {/* VX115 — index de navigation vers les 4 écrans où le comptable externe
          va chercher son export mensuel (aucune logique d'export dupliquée). */}
      <Card>
        <CardHeader>
          <CardTitle>Où trouver mes exports</CardTitle>
          <CardDescription>
            Le handoff mensuel au comptable externe est réparti sur ces écrans.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2">
            {EXPORT_DESTINATIONS.map((dest) => {
              const Icon = dest.icon
              return (
                <Link
                  key={dest.to}
                  to={dest.to}
                  className="flex items-start gap-3 rounded-lg border border-border p-3 transition-shadow hover:ring-2 hover:ring-ring/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Icon className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                  <span className="flex flex-col">
                    <span className="font-medium">{dest.label}</span>
                    <span className="text-sm text-muted-foreground">{dest.hint}</span>
                  </span>
                </Link>
              )
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
