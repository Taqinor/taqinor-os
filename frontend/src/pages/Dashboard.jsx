import { lazy, Suspense, useEffect, useMemo } from 'react'

const ActivityFeedWidget = lazy(() => import('../components/ActivityFeedWidget'))
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  Package, Users, FileCheck, FileText, AlertTriangle,
  TrendingUp, Activity, ReceiptText, Clock,
} from 'lucide-react'
import { AreaSansAxe, BarArrondie, KpiSpark, ChartEmpty } from '../ui/charts'
import { fetchProduits } from '../features/stock/store/stockSlice'
import { fetchClients } from '../features/crm/store/crmSlice'
import { fetchDevis, fetchFactures } from '../features/ventes/store/ventesSlice'
import { fetchInstallations } from '../features/installations/store/installationsSlice'
import {
  INSTALLATION_STATUSES, STATUS_LABELS, STATUS_COLORS, canonicalStatus,
} from '../features/installations/statuses'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent,
  StatusPill, Badge, Progress, EmptyState, Skeleton, SkeletonText,
} from '../ui'
import { cn } from '../lib/cn'
import { formatMAD, formatNumber, formatPercent, formatDate } from '../lib/format'

/* K51 — Tableau de bord restylé sur le système de design (refonte UI).
   Cartes KPI (Stat), graphiques recharts thémés via les tokens sémantiques
   (var(--…)), flux d'activité, états réels chargement/vide/erreur. Toutes les
   sources de données / appels API / sélecteurs Redux sont IDENTIQUES à l'écran
   précédent — aucune donnée d'achat ni de marge n'est exposée. */

// Tons sémantiques (var CSS) — fonctionnent en attributs SVG recharts et
// suivent le thème clair/sombre.
const TOKEN = {
  primary: 'var(--primary)',
  info: 'var(--info)',
  success: 'var(--success)',
  warning: 'var(--warning)',
  danger: 'var(--destructive)',
  muted: 'var(--muted-foreground)',
  grid: 'var(--border)',
  surface: 'var(--popover)',
}

// Devis : libellé + ton de statut (couleurs via tokens, jamais en dur).
const STATUT_DEVIS = [
  { key: 'brouillon', label: 'Brouillon', token: TOKEN.muted },
  { key: 'envoye', label: 'Envoyé', token: TOKEN.info },
  { key: 'accepte', label: 'Accepté', token: TOKEN.success },
  { key: 'refuse', label: 'Refusé', token: TOKEN.danger },
  { key: 'expire', label: 'Expiré', token: TOKEN.warning },
]

// Factures : libellé + ton de statut.
const STATUT_FACTURE = [
  { key: 'brouillon', label: 'Brouillon', token: TOKEN.muted },
  { key: 'emise', label: 'Émise', token: TOKEN.info },
  { key: 'en_retard', label: 'En retard', token: TOKEN.danger },
  { key: 'payee', label: 'Payée', token: TOKEN.success },
  { key: 'annulee', label: 'Annulée', token: TOKEN.muted },
]

// Tranches d'ancienneté des montants dûs (balance âgée).
const AGE_BUCKETS = [
  { key: 'a_venir', label: 'À venir', token: TOKEN.info },
  { key: 'j_0_30', label: '0–30 j', token: TOKEN.warning },
  { key: 'j_31_60', label: '31–60 j', token: TOKEN.warning },
  { key: 'j_60_plus', label: '60+ j', token: TOKEN.danger },
]

const num = (v) => {
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : 0
}

// K148 — Delta tokenisé pour une carte KPI : flèche + SIGNE + couleur (jamais
// la couleur seule). `signDisplay:"exceptZero"` force le « + »/« − » explicite.
// Renvoie un objet `delta` consommé par <Stat>, ou undefined si nul/indéfini.
function makeDelta(value, { decimals = 0, suffix = '' } = {}) {
  if (value == null || !Number.isFinite(value) || value === 0) return undefined
  const body = new Intl.NumberFormat('fr-FR', {
    signDisplay: 'exceptZero',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
  return {
    value: `${body}${suffix}`,
    direction: value > 0 ? 'up' : 'down',
  }
}

// Ton de couleur du delta (flèche + signe + couleur — jamais la couleur seule).
const DELTA_CLASS = {
  success: 'text-success',
  danger: 'text-destructive',
  muted: 'text-muted-foreground',
}

/* K148 — Carte KPI : Libellé → Valeur → Δ → Période + sparkline.
   Le delta combine flèche + signe + couleur (jamais la couleur seule), avec
   `signDisplay:"exceptZero"` (cf. makeDelta). Construite sur <Card> pour porter
   la sparkline sous le delta. */
export function KpiCard({ kpi, navigate }) {
  const Icon = kpi.icon
  const d = kpi.delta
  const deltaTone = d?.tone
    ?? (d?.direction === 'up' ? 'success' : d?.direction === 'down' ? 'danger' : 'muted')
  return (
    <Card
      className="cursor-pointer p-4 transition-colors hover:border-primary/40 sm:p-5"
      role="button"
      tabIndex={0}
      onClick={() => navigate(kpi.to)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          navigate(kpi.to)
        }
      }}
    >
      {/* Libellé */}
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {kpi.label}
        </span>
        {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden="true" />}
      </div>
      {/* Valeur */}
      <div className="mt-2 font-display text-2xl font-semibold tabular-nums leading-none">
        {kpi.value}
      </div>
      {/* Δ + indice */}
      {(kpi.hint || d) && (
        <div className="mt-1.5 flex items-center gap-2 text-xs">
          {d && (
            <span className={cn('font-medium tabular-nums', DELTA_CLASS[deltaTone])}>
              {d.direction === 'up' ? '▲' : d.direction === 'down' ? '▼' : ''} {d.value}
            </span>
          )}
          {kpi.hint && <span className="text-muted-foreground">{kpi.hint}</span>}
        </div>
      )}
      {/* Période */}
      {kpi.period && (
        <div className="mt-1 text-[0.7rem] font-medium uppercase tracking-wide text-muted-foreground">
          {kpi.period}
        </div>
      )}
      {/* Sparkline (série réelle ; masquée si tout à zéro) */}
      {kpi.spark && kpi.spark.some((v) => v > 0) && (
        <div className="mt-2 -mx-1">
          <KpiSpark data={kpi.spark} tone={kpi.sparkTone} height={36} />
        </div>
      )}
    </Card>
  )
}

function ChartCard({ title, description, children, isEmpty, emptyLabel, loading }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        {loading ? (
          // Squelette de graphe (K148) — aire fantôme pendant le chargement.
          <Skeleton className="h-44 w-full" />
        ) : isEmpty ? (
          <ChartEmpty description={emptyLabel} />
        ) : (
          children
        )}
      </CardContent>
    </Card>
  )
}

export function Component() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { produits, loading: stockLoading, error: stockError } = useSelector((s) => s.stock)
  const { clients, loading: crmLoading, error: crmError } = useSelector((s) => s.crm)
  const { devis, factures, loading: ventesLoading, error: ventesError } = useSelector((s) => s.ventes)
  const { items: installations, loading: instLoading } = useSelector((s) => s.installations)

  useEffect(() => {
    dispatch(fetchProduits())
    dispatch(fetchClients())
    dispatch(fetchDevis())
    dispatch(fetchFactures())
    dispatch(fetchInstallations())
  }, [dispatch])

  const devisAcceptes = devis.filter((d) => d.statut === 'accepte')
  const facturesEnRetard = factures.filter((f) => f.statut === 'en_retard')
  const facturesEmises = factures.filter((f) => f.statut === 'emise')

  // CA mensuel sur 6 mois — calculé depuis les factures payées déjà chargées.
  const caMensuel = useMemo(() => {
    const MOIS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
    const map = {}
    const today = new Date()
    for (let i = 5; i >= 0; i--) {
      const d = new Date(today.getFullYear(), today.getMonth() - i, 1)
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
      map[key] = { mois: `${MOIS[d.getMonth()]} ${d.getFullYear()}`, ca: 0 }
    }
    factures
      .filter((f) => f.statut === 'payee' && f.date_emission)
      .forEach((f) => {
        const key = f.date_emission.slice(0, 7)
        if (map[key]) map[key].ca += num(f.total_ht)
      })
    return Object.values(map)
  }, [factures])

  const caTotal = useMemo(() => caMensuel.reduce((s, m) => s + m.ca, 0), [caMensuel])

  // Sparklines KPI : comptes mensuels RÉELS sur 6 mois, dérivés des dates des
  // enregistrements déjà chargés (aucun appel API en plus). `monthlyCount`
  // renvoie [{ ca: n }] (clé 'ca' = série KpiSpark) + le delta mois/mois.
  const monthlyCount = useMemo(() => (records, dateField) => {
    const map = {}
    const today = new Date()
    for (let i = 5; i >= 0; i--) {
      const d = new Date(today.getFullYear(), today.getMonth() - i, 1)
      map[`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`] = 0
    }
    records.forEach((r) => {
      const v = r?.[dateField]
      if (!v) return
      const key = String(v).slice(0, 7)
      if (key in map) map[key] += 1
    })
    return Object.values(map)
  }, [])

  const devisSpark = useMemo(
    () => monthlyCount(devisAcceptes, 'date_creation'),
    [monthlyCount, devisAcceptes],
  )
  const facturesSpark = useMemo(
    () => monthlyCount(facturesEmises, 'date_emission'),
    [monthlyCount, facturesEmises],
  )

  // Delta mois/mois (dernier mois vs précédent) d'une série de comptes.
  const momDelta = (series) => {
    if (series.length < 2) return null
    return series[series.length - 1] - series[series.length - 2]
  }

  // Répartition des devis par statut (compte par catégorie connue).
  const devisParStatut = useMemo(
    () =>
      STATUT_DEVIS.map((s) => ({
        ...s,
        count: devis.filter((d) => d.statut === s.key).length,
      })),
    [devis],
  )

  // Répartition des factures par statut.
  const facturesParStatut = useMemo(
    () =>
      STATUT_FACTURE.map((s) => ({
        ...s,
        count: factures.filter((f) => f.statut === s.key).length,
      })),
    [factures],
  )

  // Répartition des chantiers par statut (entonnoir canonique, hors annulés).
  // Reflète la nouvelle portée de visibilité : la liste vient de l'API déjà
  // restreinte à ce que l'utilisateur a le droit de voir.
  const chantiersParStatut = useMemo(() => {
    const actifs = (installations ?? []).filter((it) => !it.annule)
    return INSTALLATION_STATUSES.map((key) => ({
      key,
      label: STATUS_LABELS[key] ?? key,
      token: STATUS_COLORS[key] ?? TOKEN.muted,
      count: actifs.filter((it) => canonicalStatus(it.statut) === key).length,
    }))
  }, [installations])

  const chantiersActifs = useMemo(
    () => (installations ?? []).filter((it) => !it.annule).length,
    [installations],
  )

  // Conversion devis → signé : envoyés vs. acceptés (taux de signature).
  const conversion = useMemo(() => {
    const emis = devis.filter((d) =>
      ['envoye', 'accepte', 'refuse', 'expire'].includes(d.statut),
    ).length
    const signes = devis.filter((d) => d.statut === 'accepte').length
    const taux = emis > 0 ? Math.round((signes / emis) * 100) : 0
    return { emis, signes, taux }
  }, [devis])

  // Encours clients : montant dû agrégé par tranche d'ancienneté (balance âgée).
  const ageBalance = useMemo(() => {
    const today = new Date()
    const buckets = Object.fromEntries(AGE_BUCKETS.map((b) => [b.key, 0]))
    factures
      .filter((f) => ['emise', 'en_retard'].includes(f.statut))
      .forEach((f) => {
        const du = f.montant_du != null ? num(f.montant_du) : num(f.total_ttc)
        if (du <= 0) return
        let key = 'a_venir'
        if (f.date_echeance) {
          const diff = Math.floor((today - new Date(f.date_echeance)) / 86400000)
          if (diff <= 0) key = 'a_venir'
          else if (diff <= 30) key = 'j_0_30'
          else if (diff <= 60) key = 'j_31_60'
          else key = 'j_60_plus'
        }
        buckets[key] += du
      })
    return AGE_BUCKETS.map((b) => ({ ...b, montant: buckets[b.key] }))
  }, [factures])

  const encoursTotal = useMemo(() => ageBalance.reduce((s, b) => s + b.montant, 0), [ageBalance])

  // Flux d'activité : derniers devis créés + factures émises, triés par date.
  const activite = useMemo(() => {
    const items = []
    devis.forEach((d) => {
      if (!d.date_creation) return
      items.push({
        id: `d-${d.id}`,
        type: 'devis',
        date: d.date_creation,
        reference: d.reference,
        client: d.client_nom,
        statut: d.statut,
        montant: d.total_affiche ?? d.total_ttc,
      })
    })
    factures.forEach((f) => {
      if (!f.date_emission) return
      items.push({
        id: `f-${f.id}`,
        type: 'facture',
        date: f.date_emission,
        reference: f.reference,
        client: f.client_nom,
        statut: f.statut,
        montant: f.total_ttc,
      })
    })
    return items.sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 8)
  }, [devis, factures])

  // Chaque KPI pointe vers la liste correspondante : un compteur n'est plus
  // un cul-de-sac, il ouvre les enregistrements (la facture en retard ouvre la
  // liste factures, sur l'onglet « En retard » côté liste).
  const kpis = [
    { label: 'Produits en stock', value: formatNumber(produits.length), icon: Package, hint: 'références actives', period: 'Total', to: '/stock' },
    { label: 'Clients', value: formatNumber(clients.length), icon: Users, hint: 'enregistrés', period: 'Total', to: '/crm' },
    {
      label: 'Devis acceptés',
      value: formatNumber(devisAcceptes.length),
      icon: FileCheck,
      hint: `sur ${formatNumber(devis.length)} devis`,
      period: '6 derniers mois',
      to: '/ventes/devis?statut=accepte',
      spark: devisSpark,
      sparkTone: 'success',
      delta: makeDelta(momDelta(devisSpark)),
    },
    {
      label: 'Factures émises',
      value: formatNumber(facturesEmises.length),
      icon: FileText,
      hint: 'en attente de règlement',
      period: '6 derniers mois',
      to: '/ventes/factures?statut=emise',
      spark: facturesSpark,
      sparkTone: 'info',
      delta: makeDelta(momDelta(facturesSpark)),
    },
    {
      label: 'Factures en retard',
      value: formatNumber(facturesEnRetard.length),
      icon: AlertTriangle,
      hint: facturesEnRetard.length > 0 ? 'à relancer' : 'aucune',
      period: 'En cours',
      to: '/ventes/factures?statut=en_retard',
      // En retard : une hausse est NÉGATIVE → on inverse le ton du delta.
      delta: facturesEnRetard.length > 0
        ? { value: new Intl.NumberFormat('fr-FR', { signDisplay: 'always' }).format(facturesEnRetard.length), direction: 'down' }
        : undefined,
    },
  ]

  // États globaux : on s'appuie sur les drapeaux loading/error déjà exposés par
  // les slices (aucun nouvel appel API). Loading uniquement tant qu'aucune
  // donnée n'est encore arrivée ; erreur uniquement si tout est vide.
  const anyLoading = stockLoading || crmLoading || ventesLoading || instLoading
  const hasAnyData = produits.length || clients.length || devis.length
    || factures.length || (installations?.length ?? 0)
  const firstError = ventesError || crmError || stockError
  const showLoading = anyLoading && !hasAnyData
  const showError = !anyLoading && !hasAnyData && !!firstError
  const errorMessage =
    typeof firstError === 'string'
      ? firstError
      : firstError?.detail || firstError?.message || 'Veuillez réessayer.'

  return (
    <div className="ui-root min-h-full p-4 sm:p-6">
      {/* En-tête — le titre « Tableau de bord » reste un <h2> (heading) :
          l'e2e (auth.setup.js) s'appuie dessus, ne pas modifier. */}
      <header className="mb-6">
        <h2 className="font-display text-xl font-bold tracking-tight text-foreground">
          Tableau de bord
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">Vue d'ensemble de votre activité</p>
      </header>

      {showError ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center sm:pt-12">
            <span className="flex size-11 items-center justify-center rounded-full bg-destructive/12 text-destructive">
              <AlertTriangle className="size-5" aria-hidden="true" />
            </span>
            <p className="font-display text-base font-semibold text-foreground">
              Impossible de charger le tableau de bord
            </p>
            <p className="max-w-sm text-sm text-muted-foreground">{errorMessage}</p>
          </CardContent>
        </Card>
      ) : showLoading ? (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
            {Array.from({ length: 5 }).map((unused, i) => (
              <Card key={i} className="p-4 sm:p-5">
                <Skeleton className="size-4" />
                <Skeleton className="mt-3 h-7 w-1/2" />
                <Skeleton className="mt-2 h-3 w-2/3" />
              </Card>
            ))}
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {Array.from({ length: 2 }).map((unused, i) => (
              <Card key={i}>
                <CardHeader>
                  <Skeleton className="h-4 w-40" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-40 w-full" />
                </CardContent>
              </Card>
            ))}
          </div>
          <Card>
            <CardHeader>
              <Skeleton className="h-4 w-32" />
            </CardHeader>
            <CardContent>
              <SkeletonText lines={5} />
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="flex flex-col gap-4 sm:gap-5">
          {/* Cartes KPI */}
          <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
            {kpis.map((kpi) => (
              <KpiCard key={kpi.label} kpi={kpi} navigate={navigate} />
            ))}
          </div>

          {/* Rangée graphiques : CA mensuel + devis par statut */}
          <div className="grid grid-cols-1 gap-4 sm:gap-5 lg:grid-cols-2">
            <ChartCard
              title="Chiffre d'affaires mensuel"
              description={`Factures payées · ${formatMAD(caTotal, { decimals: 0 })} sur 6 mois`}
              isEmpty={caMensuel.every((m) => m.ca === 0)}
              emptyLabel="Aucune facture payée sur les 6 derniers mois."
            >
              <AreaSansAxe
                data={caMensuel}
                dataKey="ca"
                xKey="mois"
                tone="primary"
                name="CA HT"
                height={180}
                tooltipFormat={(v) => formatMAD(v, { decimals: 0 })}
              />
            </ChartCard>

            <ChartCard
              title="Devis par statut"
              description={`${formatNumber(devis.length)} devis au total`}
              isEmpty={devis.length === 0}
              emptyLabel="Aucun devis pour le moment."
            >
              <BarArrondie
                data={devisParStatut.filter((s) => s.count > 0)}
                dataKey="count"
                categoryKey="label"
                colorKey="token"
                layout="vertical"
                name="Devis"
                height={180}
                barSize={18}
                categoryWidth={78}
                tooltipFormat={(v) => formatNumber(v)}
              />
            </ChartCard>
          </div>

          {/* Rangée graphiques : factures par statut + balance âgée */}
          <div className="grid grid-cols-1 gap-4 sm:gap-5 lg:grid-cols-2">
            <ChartCard
              title="Factures par statut"
              description={`${formatNumber(factures.length)} factures au total`}
              isEmpty={factures.length === 0}
              emptyLabel="Aucune facture pour le moment."
            >
              <BarArrondie
                data={facturesParStatut.filter((s) => s.count > 0)}
                dataKey="count"
                categoryKey="label"
                colorKey="token"
                name="Factures"
                height={180}
                barSize={36}
                tooltipFormat={(v) => formatNumber(v)}
              />
            </ChartCard>

            <ChartCard
              title="Encours clients (balance âgée)"
              description={`${formatMAD(encoursTotal, { decimals: 0 })} à recouvrer`}
              isEmpty={encoursTotal === 0}
              emptyLabel="Aucun encours client à recouvrer."
            >
              <BarArrondie
                data={ageBalance}
                dataKey="montant"
                categoryKey="label"
                colorKey="token"
                name="Montant dû"
                height={180}
                barSize={40}
                tooltipFormat={(v) => formatMAD(v, { decimals: 0 })}
              />
            </ChartCard>
          </div>

          {/* Rangée : chantiers par statut (réalisation physique) */}
          <ChartCard
            title="Chantiers par statut"
            description={`${formatNumber(chantiersActifs)} chantier(s) en cours`}
            isEmpty={chantiersActifs === 0}
            emptyLabel="Aucun chantier pour le moment."
          >
            <BarArrondie
              data={chantiersParStatut.filter((s) => s.count > 0)}
              dataKey="count"
              categoryKey="label"
              colorKey="token"
              layout="vertical"
              name="Chantiers"
              height={200}
              barSize={18}
              categoryWidth={120}
              tooltipFormat={(v) => formatNumber(v)}
            />
          </ChartCard>

          {/* Rangée : conversion devis→signé + flux d'activité */}
          <div className="grid grid-cols-1 gap-4 sm:gap-5 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="size-4 text-muted-foreground" aria-hidden="true" />
                  Conversion devis → signé
                </CardTitle>
                <CardDescription>Taux de signature des devis émis</CardDescription>
              </CardHeader>
              <CardContent>
                {conversion.emis === 0 ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">
                    Aucun devis émis à analyser.
                  </p>
                ) : (
                  <div className="flex flex-col gap-4">
                    <div className="flex items-end justify-between">
                      <span className="font-display text-3xl font-semibold tabular-nums leading-none text-foreground">
                        {formatPercent(conversion.taux)}
                      </span>
                      <Badge tone="success">
                        {formatNumber(conversion.signes)} signé{conversion.signes > 1 ? 's' : ''}
                      </Badge>
                    </div>
                    <Progress value={conversion.taux} tone="success" />
                    <p className="text-xs text-muted-foreground">
                      {formatNumber(conversion.signes)} signés sur {formatNumber(conversion.emis)} devis émis
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="size-4 text-muted-foreground" aria-hidden="true" />
                  Activité récente
                </CardTitle>
                <CardDescription>Derniers devis et factures</CardDescription>
              </CardHeader>
              <CardContent>
                {activite.length === 0 ? (
                  <EmptyState
                    icon={Activity}
                    title="Aucune activité"
                    description="Vos derniers devis et factures apparaîtront ici."
                    className="border-0 px-0 py-8"
                  />
                ) : (
                  <ul className="flex flex-col divide-y divide-border">
                    {activite.map((a) => {
                      const Icon = a.type === 'devis' ? FileText : ReceiptText
                      return (
                        <li key={a.id} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
                          <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                            <Icon className="size-4" aria-hidden="true" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-foreground">
                              {a.type === 'devis' ? 'Devis' : 'Facture'} {a.reference ?? '—'}
                            </p>
                            <p className="truncate text-xs text-muted-foreground">
                              {a.client || 'Client non renseigné'} · {formatDate(a.date)}
                            </p>
                          </div>
                          <div className="flex shrink-0 flex-col items-end gap-1">
                            <span className="text-sm font-medium tabular-nums text-foreground">
                              {a.montant != null ? formatMAD(a.montant, { decimals: 0 }) : '—'}
                            </span>
                            {a.statut && <StatusPill status={a.statut} label={a.statut} />}
                          </div>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          {/* FG8 — Flux d'activités planifiées (records.Activity) */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="size-4 text-muted-foreground" aria-hidden="true" />
                Mes activités planifiées
              </CardTitle>
              <CardDescription>Activités ouvertes qui vous sont assignées</CardDescription>
            </CardHeader>
            <CardContent>
              <Suspense fallback={<p className="text-sm text-muted-foreground">Chargement…</p>}>
                <ActivityFeedWidget limit={5} />
              </Suspense>
            </CardContent>
          </Card>

          {/* Alerte factures en retard */}
          {facturesEnRetard.length > 0 && (
            <Card className="border-destructive/30 bg-destructive/5">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-destructive">
                  <Clock className="size-4" aria-hidden="true" />
                  Factures en retard ({formatNumber(facturesEnRetard.length)})
                </CardTitle>
                <CardDescription>Factures dont l'échéance est dépassée — à relancer.</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col gap-1.5">
                  {facturesEnRetard.map((f) => (
                    <li key={f.id} className="flex items-center justify-between gap-3 text-sm">
                      <span className="truncate text-foreground">
                        <span className="font-medium">{f.reference}</span>
                        <span className="text-muted-foreground"> · {f.client_nom || '—'}</span>
                      </span>
                      <span className="shrink-0 tabular-nums font-medium text-destructive">
                        {f.total_ttc != null ? formatMAD(f.total_ttc, { decimals: 0 }) : '—'}
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
