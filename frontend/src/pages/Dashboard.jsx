import { lazy, Suspense, useEffect, useMemo } from 'react'

const ActivityFeedWidget = lazy(() => import('../components/ActivityFeedWidget'))
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  Package, Users, FileCheck, FileText, AlertTriangle,
  TrendingUp, Activity, ReceiptText, Clock,
} from 'lucide-react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import { fetchProduits } from '../features/stock/store/stockSlice'
import { fetchClients } from '../features/crm/store/crmSlice'
import { fetchDevis, fetchFactures } from '../features/ventes/store/ventesSlice'
import { fetchInstallations } from '../features/installations/store/installationsSlice'
import {
  INSTALLATION_STATUSES, STATUS_LABELS, STATUS_COLORS, canonicalStatus,
} from '../features/installations/statuses'
import {
  Stat, Card, CardHeader, CardTitle, CardDescription, CardContent,
  StatusPill, Badge, Progress, EmptyState, Skeleton, SkeletonText,
} from '../ui'
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

// Style commun de l'infobulle recharts (surface + bordure tokenisées).
const tooltipStyle = {
  borderRadius: 10,
  fontSize: 12,
  border: `1px solid ${TOKEN.grid}`,
  background: TOKEN.surface,
  color: 'var(--popover-foreground)',
  boxShadow: 'var(--shadow-md)',
}

function ChartCard({ title, description, children, isEmpty, emptyLabel }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        {isEmpty ? (
          <p className="py-6 text-center text-sm text-muted-foreground">{emptyLabel}</p>
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
    { label: 'Produits en stock', value: formatNumber(produits.length), icon: Package, hint: 'références actives', to: '/stock' },
    { label: 'Clients', value: formatNumber(clients.length), icon: Users, hint: 'enregistrés', to: '/crm' },
    { label: 'Devis acceptés', value: formatNumber(devisAcceptes.length), icon: FileCheck, hint: `sur ${formatNumber(devis.length)} devis`, to: '/ventes/devis?statut=accepte' },
    { label: 'Factures émises', value: formatNumber(facturesEmises.length), icon: FileText, hint: 'en attente de règlement', to: '/ventes/factures?statut=emise' },
    {
      label: 'Factures en retard',
      value: formatNumber(facturesEnRetard.length),
      icon: AlertTriangle,
      hint: facturesEnRetard.length > 0 ? 'à relancer' : 'aucune',
      to: '/ventes/factures?statut=en_retard',
      delta: facturesEnRetard.length > 0
        ? { value: `${facturesEnRetard.length}`, direction: 'down' }
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
              <Stat
                key={kpi.label}
                label={kpi.label}
                value={kpi.value}
                hint={kpi.hint}
                delta={kpi.delta}
                icon={kpi.icon}
                role="button"
                tabIndex={0}
                className="cursor-pointer transition-colors hover:border-primary/40"
                onClick={() => navigate(kpi.to)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    navigate(kpi.to)
                  }
                }}
              />
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
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={caMensuel} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="caGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={TOKEN.primary} stopOpacity={0.35} />
                      <stop offset="95%" stopColor={TOKEN.primary} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={TOKEN.grid} vertical={false} />
                  <XAxis dataKey="mois" tick={{ fontSize: 11, fill: TOKEN.muted }} tickLine={false} axisLine={false} />
                  <YAxis
                    tick={{ fontSize: 11, fill: TOKEN.muted }}
                    tickLine={false}
                    axisLine={false}
                    width={40}
                    tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : v)}
                  />
                  <Tooltip
                    cursor={{ stroke: TOKEN.grid }}
                    contentStyle={tooltipStyle}
                    formatter={(v) => [`${formatMAD(v, { decimals: 0 })}`, 'CA HT']}
                  />
                  <Area
                    type="monotone"
                    dataKey="ca"
                    stroke={TOKEN.primary}
                    strokeWidth={2}
                    fill="url(#caGrad)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard
              title="Devis par statut"
              description={`${formatNumber(devis.length)} devis au total`}
              isEmpty={devis.length === 0}
              emptyLabel="Aucun devis pour le moment."
            >
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={devisParStatut.filter((s) => s.count > 0)}
                  layout="vertical"
                  margin={{ top: 4, right: 12, bottom: 0, left: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={TOKEN.grid} horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: TOKEN.muted }} tickLine={false} axisLine={false} />
                  <YAxis type="category" dataKey="label" width={78} tick={{ fontSize: 11, fill: TOKEN.muted }} tickLine={false} axisLine={false} />
                  <Tooltip cursor={{ fill: 'var(--muted)' }} contentStyle={tooltipStyle} formatter={(v) => [formatNumber(v), 'Devis']} />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={18}>
                    {devisParStatut.filter((s) => s.count > 0).map((s) => (
                      <Cell key={s.key} fill={s.token} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
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
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={facturesParStatut.filter((s) => s.count > 0)}
                  margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={TOKEN.grid} vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: TOKEN.muted }} tickLine={false} axisLine={false} />
                  <YAxis allowDecimals={false} width={32} tick={{ fontSize: 11, fill: TOKEN.muted }} tickLine={false} axisLine={false} />
                  <Tooltip cursor={{ fill: 'var(--muted)' }} contentStyle={tooltipStyle} formatter={(v) => [formatNumber(v), 'Factures']} />
                  <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={36}>
                    {facturesParStatut.filter((s) => s.count > 0).map((s) => (
                      <Cell key={s.key} fill={s.token} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard
              title="Encours clients (balance âgée)"
              description={`${formatMAD(encoursTotal, { decimals: 0 })} à recouvrer`}
              isEmpty={encoursTotal === 0}
              emptyLabel="Aucun encours client à recouvrer."
            >
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={ageBalance} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={TOKEN.grid} vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: TOKEN.muted }} tickLine={false} axisLine={false} />
                  <YAxis
                    width={40}
                    tick={{ fontSize: 11, fill: TOKEN.muted }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : v)}
                  />
                  <Tooltip cursor={{ fill: 'var(--muted)' }} contentStyle={tooltipStyle} formatter={(v) => [formatMAD(v, { decimals: 0 }), 'Montant dû']} />
                  <Bar dataKey="montant" radius={[6, 6, 0, 0]} barSize={40}>
                    {ageBalance.map((b) => (
                      <Cell key={b.key} fill={b.token} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          {/* Rangée : chantiers par statut (réalisation physique) */}
          <ChartCard
            title="Chantiers par statut"
            description={`${formatNumber(chantiersActifs)} chantier(s) en cours`}
            isEmpty={chantiersActifs === 0}
            emptyLabel="Aucun chantier pour le moment."
          >
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                data={chantiersParStatut.filter((s) => s.count > 0)}
                layout="vertical"
                margin={{ top: 4, right: 12, bottom: 0, left: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={TOKEN.grid} horizontal={false} />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: TOKEN.muted }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="label" width={120} tick={{ fontSize: 11, fill: TOKEN.muted }} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: 'var(--muted)' }} contentStyle={tooltipStyle} formatter={(v) => [formatNumber(v), 'Chantiers']} />
                <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={18}>
                  {chantiersParStatut.filter((s) => s.count > 0).map((s) => (
                    <Cell key={s.key} fill={s.token} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
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
