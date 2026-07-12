import { lazy, Suspense, useEffect, useMemo, useState } from 'react'

const ActivityFeedWidget = lazy(() => import('../components/ActivityFeedWidget'))
const MesEquipesCard = lazy(() => import('../components/MesEquipesCard'))
// VX86 — carte « Attend votre décision » (boîte d'approbations centralisée),
// chargée paresseusement comme les autres compléments autonomes du Dashboard.
const ApprobationsAttentionCard = lazy(() => import('../components/ApprobationsAttentionCard'))
// VX36 — bannière de prise en main (autonome : se masque si terminé/rejeté),
// visible dès le premier login en haut du Dashboard.
const OnboardingBanner = lazy(() => import('../components/OnboardingBanner'))
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  Package, Users, FileCheck, FileText, AlertTriangle,
  TrendingUp, Activity, ReceiptText, Clock, Wrench, CalendarClock, Phone,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer,
} from 'recharts'
import {
  AreaSansAxe, BarArrondie, KpiSpark, ChartEmpty, ChartTooltip,
  CHART_TOKENS, CHART_GRID_STYLE, CHART_COMPARISON_STYLE, categoricalColor,
  animationDuration, CHART_ANIM_EASING,
} from '../ui/charts'
import { ModuleHero } from '../ui/module/ModuleHero.jsx'
import { fetchProduits } from '../features/stock/store/stockSlice'
import { fetchClients, fetchLeads } from '../features/crm/store/crmSlice'
import { fetchDevis, fetchFactures } from '../features/ventes/store/ventesSlice'
import { fetchInstallations } from '../features/installations/store/installationsSlice'
// VX27 — cockpit du matin par rôle : le SAV réutilise les helpers de statut/SLA
// existants (aucune logique de ticket dupliquée ici) et les tickets déjà en
// store (fetchTickets). Les endpoints existent — on ajoute seulement le fetch.
import { fetchTickets } from '../features/sav/store/ticketsSlice'
import {
  ticketSlaLevel, TICKET_OPEN_STATUSES,
} from '../features/sav/ticketStatuses'
// VX219 — « Mes chiffres » : carte de performance personnelle (tous rôles),
// extraite comme composant réutilisable dans CrmInsightsPanel.jsx.
import { MesChiffresCard } from './crm/leads/CrmInsightsPanel'
import {
  INSTALLATION_STATUSES, STATUS_LABELS, STATUS_COLORS, canonicalStatus,
} from '../features/installations/statuses'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent,
  StatusPill, Badge, Progress, EmptyState, Skeleton, SkeletonText, Segmented,
  ErrorBoundary,
} from '../ui'
import { StateBlock } from '../components/StateBlock'
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

// ── VX27 — Cockpit du matin : layout par rôle + bandeau « aujourd'hui » ───────
// Le Directeur, le Commercial et le Technicien SAV voyaient EXACTEMENT le même
// mur de KPI. On dérive un « profil de cockpit » du role_nom déjà en store
// (aucune source nouvelle) : commercial (ventes) / sav (terrain & support) /
// directeur (macro). Défaut = directeur (vue macro complète, comportement
// historique). Fonctions PURES exportées → testées sans monter le composant.

// Renvoie 'commercial' | 'sav' | 'directeur' d'après le nom de rôle + le palier.
// eslint-disable-next-line react-refresh/only-export-components -- helper cockpit co-localisé
export function cockpitProfile({ roleNom, roleTier } = {}) {
  const n = String(roleNom ?? '').toLowerCase()
  // Les rôles direction/admin gardent la vue macro même si leur libellé
  // contient un autre mot-clé.
  if (roleTier === 'admin' || /directeur|gérant|gerant|patron|fondateur|admin/.test(n)) {
    return 'directeur'
  }
  // SAV AVANT commercial : « après-vente » contient « vente » et serait sinon
  // classé commercial par erreur (VX27 fix).
  if (/sav|technicien|support|après-vente|apres-vente|maintenance|terrain/.test(n)) return 'sav'
  if (/commercial|vente|sales/.test(n)) return 'commercial'
  return 'directeur'
}

// YYYY-MM-DD du jour (local), pour comparer aux dates ISO des enregistrements.
function isoToday(now = new Date()) {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

// Leads « à relancer » : relance planifiée aujourd'hui ou déjà dépassée, lead
// non perdu/archivé. Si `ownerId` est fourni, on scope à « mes » leads (le
// backend restreint déjà la visibilité ; ce filtre affine à l'assigné courant).
// eslint-disable-next-line react-refresh/only-export-components -- helper cockpit co-localisé
export function leadsARelancer(leads, { ownerId, now = new Date() } = {}) {
  const today = isoToday(now)
  return (leads ?? []).filter((l) => {
    if (!l || l.is_archived || l.perdu) return false
    if (ownerId != null && l.owner != null && l.owner !== ownerId) return false
    const r = l.relance_date
    return !!r && String(r).slice(0, 10) <= today
  })
}

// Devis qui expirent bientôt : encore ouverts (brouillon/envoyé), date de
// validité comprise entre aujourd'hui et +N jours (défaut 7).
// eslint-disable-next-line react-refresh/only-export-components -- helper cockpit co-localisé
export function devisQuiExpirent(devis, { days = 7, now = new Date() } = {}) {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const end = new Date(start)
  end.setDate(end.getDate() + days)
  return (devis ?? []).filter((d) => {
    if (!d || !['brouillon', 'envoye'].includes(d.statut)) return false
    if (!d.date_validite) return false
    const v = new Date(`${String(d.date_validite).slice(0, 10)}T00:00:00`)
    if (Number.isNaN(v.getTime())) return false
    return v >= start && v <= end
  })
}

// Tickets SAV « à faire aujourd'hui » côté terrain : ouverts (nouveau/planifié/
// en cours), non annulés. Proxy honnête de la charge du jour sans nouvel
// endpoint (les interventions planifiées vivent dans les tickets ouverts).
// eslint-disable-next-line react-refresh/only-export-components -- helper cockpit co-localisé
export function ticketsAujourdhui(tickets) {
  return (tickets ?? []).filter(
    (t) => t && !t.annule && TICKET_OPEN_STATUSES.includes(t.statut),
  )
}

// Tickets urgents : priorité haute/urgente, ouverts, non annulés.
// eslint-disable-next-line react-refresh/only-export-components -- helper cockpit co-localisé
export function ticketsUrgents(tickets) {
  return (tickets ?? []).filter(
    (t) => t && !t.annule && TICKET_OPEN_STATUSES.includes(t.statut)
      && ['haute', 'urgente'].includes(t.priorite),
  )
}

// Tickets en retard de SLA (réutilise ticketSlaLevel === 'late').
// eslint-disable-next-line react-refresh/only-export-components -- helper cockpit co-localisé
export function ticketsSlaEnRetard(tickets, now = new Date()) {
  return (tickets ?? []).filter((t) => ticketSlaLevel(t, now) === 'late')
}

// VX219 — « Mes chiffres » : devis du MOIS COURANT scopés au vendeur
// (`created_by === userId`, jamais agrégés à l'équipe), même ancrage mensuel
// que caMensuel/devisSpark ci-dessus (`date_creation`). Fonction PURE, testée
// sans monter le composant ni le store (`userId` absent → aucun scope, utile
// en repli si l'utilisateur courant n'est pas encore chargé).
// eslint-disable-next-line react-refresh/only-export-components -- helper cockpit co-localisé
export function mesChiffresDuMois(devis, { userId, now = new Date() } = {}) {
  const y = now.getFullYear()
  const m = now.getMonth()
  const mine = (devis ?? []).filter((d) => {
    if (!d || !d.date_creation) return false
    if (userId != null && d.created_by !== userId) return false
    const dt = new Date(d.date_creation)
    return dt.getFullYear() === y && dt.getMonth() === m
  })
  const emis = mine.filter((d) => ['envoye', 'accepte', 'refuse', 'expire'].includes(d.statut))
  const acceptesList = mine.filter((d) => d.statut === 'accepte')
  const caSigne = acceptesList.reduce((s, d) => s + num(d.total_affiche ?? d.total_ttc), 0)
  return {
    envoyes: emis.length,
    acceptes: acceptesList.length,
    tauxSignature: emis.length > 0 ? Math.round((acceptesList.length / emis.length) * 100) : 0,
    caSigne,
  }
}

// VX219 — leads « chauds » à traiter en priorité : les MIENS, non perdus/
// archivés, triés par score décroissant (score absent → 0), plafonnés à
// `limit`. Réutilise `Lead.score` déjà exposé (ScoreBadge/VX221) — zéro calcul
// dupliqué.
// eslint-disable-next-line react-refresh/only-export-components -- helper cockpit co-localisé
export function leadsChauds(leads, { userId, limit = 3 } = {}) {
  return (leads ?? [])
    .filter((l) => l && !l.perdu && !l.is_archived && (userId == null || l.owner === userId))
    .slice()
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, limit)
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

// VX205 — le graphique (recharts + données calculées) est isolé dans SA
// PROPRE `ErrorBoundary` (déjà construite, `ui/ErrorBoundary.jsx`) : un throw
// dans UNE carte-graphique ne fait plus disparaître tout le Dashboard, seule
// cette carte affiche l'écran de récupération.
function ChartCard({ title, description, children, isEmpty, emptyLabel, loading, actions }) {
  return (
    <Card>
      <CardHeader className={actions ? 'flex-row items-center justify-between gap-3' : undefined}>
        <div>
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        {actions}
      </CardHeader>
      <CardContent>
        {loading ? (
          // Squelette de graphe (K148) — aire fantôme pendant le chargement.
          <Skeleton className="h-44 w-full" />
        ) : isEmpty ? (
          <ChartEmpty description={emptyLabel} />
        ) : (
          <ErrorBoundary>{children}</ErrorBoundary>
        )}
      </CardContent>
    </Card>
  )
}

/* VX27 — Bandeau « aujourd'hui » : rangée compacte de segments cliquables
   (« 3 interventions en cours · 2 relances en retard · 1 devis expire »).
   Ne rend RIEN quand aucun signal (pas de bruit un matin calme). */
const TODAY_TONE = {
  info: 'text-info',
  danger: 'text-destructive',
  warning: 'text-warning',
}
function TodayBanner({ segments, navigate }) {
  if (!segments || segments.length === 0) return null
  return (
    <Card className="mb-4 p-0" data-testid="today-banner">
      <div className="flex flex-wrap items-center gap-x-1 gap-y-2 px-4 py-3">
        <span className="mr-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Aujourd'hui
        </span>
        {segments.map((s, i) => {
          const Icon = s.icon
          return (
            <span key={s.key} className="flex items-center">
              {i > 0 && <span className="mx-1.5 text-border" aria-hidden="true">·</span>}
              <button
                type="button"
                onClick={() => navigate(s.to)}
                className="inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-sm font-medium hover:bg-muted"
              >
                <Icon className={cn('size-4', TODAY_TONE[s.tone] ?? 'text-muted-foreground')} aria-hidden="true" />
                <span>{s.text}</span>
              </button>
            </span>
          )
        })}
      </div>
    </Card>
  )
}

/* VX27 — Carte « liste de priorités » d'une section de tête par rôle : titre +
   compteur, jusqu'à 5 lignes cliquables, état vide honnête. */
// VX249(c) — `mine` : pastille partagée (même token que la cloche de
// notifications/Ma file) — pleine = « assigné à moi/action », contour =
// « information société ». VX27 posait déjà « Mes leads »/« Mes devis »/« Mes
// tickets » (mine) à côté de « SLA en retard » (société) SANS convention
// visuelle commune ; ceci retrofite le même token, jamais un second système.
function PriorityCard({
  title, icon: Icon, tone = 'muted', items, renderItem, emptyLabel, toAll, navigate,
  mine = false,
}) {
  const count = items.length
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2">
            {Icon && <Icon className={cn('size-4', TODAY_TONE[tone] ?? 'text-muted-foreground')} aria-hidden="true" />}
            {title}
            <span
              className={`vx-pastille ${mine ? 'vx-pastille-mine' : 'vx-pastille-company'}`}
              aria-hidden="true"
              title={mine ? 'Vous concerne personnellement' : 'Information société'}
            />
          </span>
          {count > 0 && <Badge tone={tone === 'danger' ? 'destructive' : tone === 'warning' ? 'warning' : 'primary'}>{count}</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {count === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">{emptyLabel}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {items.slice(0, 5).map((it) => renderItem(it))}
            {count > 5 && toAll && (
              <li className="pt-2">
                <button type="button" onClick={() => navigate(toAll)}
                        className="text-xs font-medium text-primary hover:underline">
                  Voir les {count} →
                </button>
              </li>
            )}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export function Component() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { produits, loading: stockLoading, error: stockError } = useSelector((s) => s.stock)
  const { clients, leads, loading: crmLoading, error: crmError } = useSelector((s) => s.crm)
  const { devis, factures, loading: ventesLoading, error: ventesError } = useSelector((s) => s.ventes)
  const { items: installations, loading: instLoading } = useSelector((s) => s.installations)
  // VX27 — tickets SAV (déjà en store via fetchTickets) pour le cockpit terrain.
  const tickets = useSelector((s) => s.tickets.items)
  const user = useSelector((s) => s.auth.user)
  const roleNom = useSelector((s) => s.auth.role_nom)
  const roleTier = useSelector((s) => s.auth.role)
  const profile = cockpitProfile({ roleNom, roleTier })

  // VX41 — comparaison togglable « période précédente » sur le CA mensuel
  // (off par défaut : comportement écran inchangé tant qu'on ne l'active pas).
  const [caCompare, setCaCompare] = useState(false)

  // VX67 — extrait en fonction nommée pour être réutilisable comme `onRetry`
  // du StateBlock d'erreur ci-dessous.
  // VX27 — on ajoute les fetchs frontend qui manquaient (leads + tickets SAV) :
  // le Dashboard ne chargeait ni leads ni tickets alors que les endpoints
  // existent — c'est ce qui empêchait le cockpit commercial/SAV d'exister.
  const reload = () => {
    dispatch(fetchProduits())
    dispatch(fetchClients())
    dispatch(fetchDevis())
    dispatch(fetchFactures())
    dispatch(fetchInstallations())
    dispatch(fetchLeads())
    dispatch(fetchTickets())
  }
  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch])

  const devisAcceptes = devis.filter((d) => d.statut === 'accepte')
  const facturesEnRetard = factures.filter((f) => f.statut === 'en_retard')
  const facturesEmises = factures.filter((f) => f.statut === 'emise')

  // CA mensuel sur 12 mois — calculé depuis les factures payées déjà chargées.
  // VX41 — la fenêtre s'étend à 12 mois (au lieu de 6) pour porter la série
  // « période précédente » : les 6 premiers mois servent de référence décalée
  // aux 6 mois affichés, à partir des MÊMES données déjà en store (zéro appel
  // API supplémentaire).
  const caMensuel12 = useMemo(() => {
    const MOIS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
    const map = {}
    const today = new Date()
    for (let i = 11; i >= 0; i--) {
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

  const caMensuel = useMemo(() => caMensuel12.slice(-6), [caMensuel12])

  // VX41 — Série « période précédente » togglable : les 6 mois qui précèdent
  // directement la fenêtre affichée, alignés position à position (mois N vs
  // mois N-6). Même tableau `caMensuel12` déjà calculé, aucune donnée en plus.
  const caMensuelCompare = useMemo(() => {
    const precedent = caMensuel12.slice(0, 6)
    return caMensuel.map((m, i) => ({
      ...m,
      caPrecedent: precedent[i]?.ca ?? 0,
      moisPrecedent: precedent[i]?.mois,
    }))
  }, [caMensuel12, caMensuel])

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

  // VX27 — signaux « aujourd'hui » (dérivés des données déjà chargées, aucun
  // appel réseau ajouté). Alimentent le bandeau compact ET les sections de tête
  // par rôle. « Mes » leads scopés à l'utilisateur courant quand l'assigné est
  // connu (le backend restreint déjà la visibilité).
  const relancesEnRetard = useMemo(
    () => leadsARelancer(leads, { ownerId: user?.id }),
    [leads, user?.id],
  )
  const devisExpirent = useMemo(() => devisQuiExpirent(devis, { days: 7 }), [devis])
  const interventionsAujourdhui = useMemo(() => ticketsAujourdhui(tickets), [tickets])
  const ticketsUrgentsList = useMemo(() => ticketsUrgents(tickets), [tickets])
  const slaEnRetard = useMemo(() => ticketsSlaEnRetard(tickets), [tickets])

  // VX219 — « Mes chiffres » : dérivé des slices devis/leads déjà chargées,
  // scopé à l'utilisateur courant (jamais l'équipe) — zéro appel réseau ajouté
  // pour ces deux blocs (seule l'atteinte d'objectif, dans la carte elle-même,
  // refait un appel scopé `?owner=`).
  const mesChiffres = useMemo(
    () => mesChiffresDuMois(devis, { userId: user?.id }),
    [devis, user?.id],
  )
  const mesLeadsChauds = useMemo(
    () => leadsChauds(leads, { userId: user?.id, limit: 3 }),
    [leads, user?.id],
  )

  // Bandeau « aujourd'hui » : segments non nuls uniquement, chacun cliquable
  // vers la liste ciblée (aucun cul-de-sac).
  const todaySegments = useMemo(() => {
    const segs = []
    if (interventionsAujourdhui.length > 0) {
      segs.push({
        key: 'interventions',
        icon: Wrench,
        text: `${interventionsAujourdhui.length} intervention${interventionsAujourdhui.length > 1 ? 's' : ''} en cours`,
        to: '/sav/tickets',
        tone: 'info',
      })
    }
    if (relancesEnRetard.length > 0) {
      segs.push({
        key: 'relances',
        icon: Phone,
        text: `${relancesEnRetard.length} relance${relancesEnRetard.length > 1 ? 's' : ''} en retard`,
        to: '/crm/leads',
        tone: 'danger',
      })
    }
    if (devisExpirent.length > 0) {
      segs.push({
        key: 'devis',
        icon: CalendarClock,
        text: `${devisExpirent.length} devis expire${devisExpirent.length > 1 ? 'nt' : ''} ≤ 7 j`,
        to: '/ventes/devis',
        tone: 'warning',
      })
    }
    if (slaEnRetard.length > 0) {
      segs.push({
        key: 'sla',
        icon: Clock,
        text: `${slaEnRetard.length} SLA en retard`,
        to: '/sav/tickets',
        tone: 'danger',
      })
    }
    return segs
  }, [interventionsAujourdhui, relancesEnRetard, devisExpirent, slaEnRetard])

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
      {/* VX15 — ModuleHero remplace le <h2> nu : identité de cockpit (liseré
          gradient brass). Le titre « Tableau de bord » reste un <h2>
          (headingAs="h2") : l'e2e (auth.setup.js) s'appuie dessus, contrat
          heading INCHANGÉ. */}
      <div className="mb-6">
        <ModuleHero
          headingAs="h2"
          title="Tableau de bord"
          subtitle="Vue d'ensemble de votre activité"
        />
      </div>

      {/* VX36 — bannière de prise en main (autonome : se masque si terminé ou
          « ne plus afficher »). En tête, visible au premier login. */}
      <Suspense fallback={null}>
        <OnboardingBanner />
      </Suspense>

      {/* VX27 — bandeau « aujourd'hui » : les signaux du jour, cliquables. Se
          masque de lui-même un matin sans alerte. */}
      {!showLoading && !showError && (
        <TodayBanner segments={todaySegments} navigate={navigate} />
      )}

      {/* VX86 — carte « Attend votre décision » : autonome, se masque elle-même
          si rien n'attend l'utilisateur ; indépendante des sources loading/
          error ci-dessous (approbations n'a rien à voir avec stock/crm/ventes). */}
      <div className="mb-4 sm:mb-5">
        <Suspense fallback={null}>
          <ApprobationsAttentionCard />
        </Suspense>
      </div>

      {showError ? (
        // VX67 — StateBlock unifie l'état d'erreur avec un bouton « Réessayer »
        // (relance les 5 fetch du montage), là où l'ancienne carte d'erreur
        // n'offrait aucun moyen de réessayer sans recharger la page entière.
        <Card>
          <CardContent className="py-8 sm:py-10">
            <StateBlock error={errorMessage} onRetry={reload} />
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
          {/* VX219 — « Mes chiffres » : EN TÊTE, TOUS RÔLES (avant même le
              cockpit par rôle) — le vendeur `normal`, jusqu'ici privé de toute
              vue personnelle (`/reporting`+`/reporting/commercial` gatés
              manager/admin), voit enfin SA propre performance. Ne dé-gate
              RIEN : `/reporting/commercial` reste l'outil manager. */}
          {user?.id != null && (
            <MesChiffresCard
              envoyes={mesChiffres.envoyes}
              acceptes={mesChiffres.acceptes}
              tauxSignature={mesChiffres.tauxSignature}
              caSigne={mesChiffres.caSigne}
              leadsChauds={mesLeadsChauds}
              userId={user.id}
              navigate={navigate}
            />
          )}

          {/* VX27 — SECTION DE TÊTE PAR RÔLE : chaque profil voit d'abord SA
              charge du jour, avant le mur de KPI générique. Commercial → leads à
              relancer + devis qui expirent ; SAV → tickets urgents + SLA en
              retard ; directeur → métrique héros CA promue + macro dessous. */}
          {/* VX205 — carte cockpit isolée : un throw dans CE profil ne fait
              plus disparaître le Dashboard entier (KPI/graphiques dessous
              restent utilisables). */}
          {profile === 'commercial' && (
            <ErrorBoundary>
            <div className="grid grid-cols-1 gap-4 sm:gap-5 lg:grid-cols-2" data-testid="cockpit-commercial">
              <PriorityCard
                title="Mes leads à relancer"
                icon={Phone}
                tone="danger"
                mine
                items={relancesEnRetard}
                emptyLabel="Aucune relance en retard. Beau travail."
                toAll="/crm/leads"
                navigate={navigate}
                renderItem={(l) => (
                  <li key={l.id}>
                    <button type="button" onClick={() => navigate(`/crm/leads?lead=${l.id}`)}
                            className="flex w-full items-center justify-between gap-3 py-2 text-left first:pt-0 hover:underline">
                      <span className="truncate text-sm font-medium text-foreground">
                        {`${l.nom ?? ''} ${l.prenom ?? ''}`.trim() || 'Lead'}
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {l.relance_date ? formatDate(l.relance_date) : ''}
                      </span>
                    </button>
                  </li>
                )}
              />
              <PriorityCard
                title="Mes devis qui expirent ≤ 7 j"
                icon={CalendarClock}
                tone="warning"
                mine
                items={devisExpirent}
                emptyLabel="Aucun devis n'expire dans les 7 jours."
                toAll="/ventes/devis"
                navigate={navigate}
                renderItem={(d) => (
                  <li key={d.id}>
                    <button type="button" onClick={() => navigate(`/ventes/devis?devis=${d.id}`)}
                            className="flex w-full items-center justify-between gap-3 py-2 text-left first:pt-0 hover:underline">
                      <span className="min-w-0 truncate text-sm">
                        <span className="font-medium text-foreground">{d.reference}</span>
                        <span className="text-muted-foreground"> · {d.client_nom || '—'}</span>
                      </span>
                      <span className="shrink-0 text-xs text-warning">
                        {d.date_validite ? formatDate(d.date_validite) : ''}
                      </span>
                    </button>
                  </li>
                )}
              />
            </div>
            </ErrorBoundary>
          )}

          {profile === 'sav' && (
            <ErrorBoundary>
            <div className="grid grid-cols-1 gap-4 sm:gap-5 lg:grid-cols-2" data-testid="cockpit-sav">
              <PriorityCard
                title="Mes tickets urgents"
                icon={AlertTriangle}
                tone="danger"
                mine
                items={ticketsUrgentsList}
                emptyLabel="Aucun ticket urgent ouvert."
                toAll="/sav/tickets"
                navigate={navigate}
                renderItem={(t) => (
                  <li key={t.id}>
                    <button type="button" onClick={() => navigate('/sav/tickets')}
                            className="flex w-full items-center justify-between gap-3 py-2 text-left first:pt-0 hover:underline">
                      <span className="min-w-0 truncate text-sm">
                        <span className="font-medium text-foreground">{t.reference}</span>
                        <span className="text-muted-foreground"> · {t.client_nom || '—'}</span>
                      </span>
                      <Badge tone={t.priorite === 'urgente' ? 'destructive' : 'warning'}>
                        {t.priorite === 'urgente' ? 'Urgente' : 'Haute'}
                      </Badge>
                    </button>
                  </li>
                )}
              />
              <PriorityCard
                title="SLA en retard"
                icon={Clock}
                tone="danger"
                items={slaEnRetard}
                emptyLabel="Aucun ticket au-delà de son SLA."
                toAll="/sav/tickets"
                navigate={navigate}
                renderItem={(t) => (
                  <li key={t.id}>
                    <button type="button" onClick={() => navigate('/sav/tickets')}
                            className="flex w-full items-center justify-between gap-3 py-2 text-left first:pt-0 hover:underline">
                      <span className="min-w-0 truncate text-sm">
                        <span className="font-medium text-foreground">{t.reference}</span>
                        <span className="text-muted-foreground"> · {t.client_nom || '—'}</span>
                      </span>
                      <span className="shrink-0 text-xs font-medium text-destructive">En retard</span>
                    </button>
                  </li>
                )}
              />
            </div>
            </ErrorBoundary>
          )}

          {profile === 'directeur' && caTotal > 0 && (
            <ErrorBoundary>
            <Card className="p-5" data-testid="cockpit-directeur">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Chiffre d'affaires · 6 mois
                  </span>
                  <div className="num mt-1 text-4xl font-semibold leading-none text-foreground">
                    {formatMAD(caTotal, { decimals: 0 })}
                  </div>
                </div>
                <Badge tone="success">
                  {formatPercent(conversion.taux)} de signature
                </Badge>
              </div>
            </Card>
            </ErrorBoundary>
          )}

          {/* Cartes KPI */}
          <ErrorBoundary>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
            {kpis.map((kpi) => (
              <KpiCard key={kpi.label} kpi={kpi} navigate={navigate} />
            ))}
          </div>
          </ErrorBoundary>

          {/* Rangée graphiques : CA mensuel + devis par statut */}
          <div className="grid grid-cols-1 gap-4 sm:gap-5 lg:grid-cols-2">
            <ChartCard
              title="Chiffre d'affaires mensuel"
              description={`Factures payées · ${formatMAD(caTotal, { decimals: 0 })} sur 6 mois`}
              isEmpty={caMensuel.every((m) => m.ca === 0)}
              emptyLabel="Aucune facture payée sur les 6 derniers mois."
              actions={(
                <Segmented
                  size="sm"
                  value={caCompare ? 'compare' : 'simple'}
                  onChange={(v) => setCaCompare(v === 'compare')}
                  options={[
                    { value: 'simple', label: 'CA seul' },
                    { value: 'compare', label: 'Vs période précédente' },
                  ]}
                />
              )}
            >
              {caCompare ? (
                <>
                  {/* VX41 — comparaison « période précédente » : mêmes données
                      déjà chargées, décalées de 6 mois — zéro appel API. Série
                      courante en trait plein (palette CA), précédente en
                      pointillé (CHART_COMPARISON_STYLE). */}
                  <ResponsiveContainer width="100%" height={180}>
                    <AreaChart data={caMensuelCompare} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid {...CHART_GRID_STYLE} />
                      <XAxis
                        dataKey="mois"
                        tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
                        tickLine={false}
                        axisLine={false}
                      />
                      <YAxis hide domain={[0, 'auto']} />
                      <RTooltip
                        cursor={{ stroke: CHART_TOKENS.grid }}
                        content={<ChartTooltip format={(v) => formatMAD(v, { decimals: 0 })} />}
                      />
                      <Area
                        type="monotone"
                        dataKey="ca"
                        name="CA HT (période actuelle)"
                        stroke={categoricalColor(0)}
                        strokeWidth={2}
                        fill={categoricalColor(0)}
                        fillOpacity={0.12}
                        dot={false}
                        isAnimationActive={animationDuration() > 0}
                        animationDuration={animationDuration()}
                        animationEasing={CHART_ANIM_EASING}
                      />
                      <Area
                        type="monotone"
                        dataKey="caPrecedent"
                        name="CA HT (période précédente)"
                        stroke={categoricalColor(1)}
                        dot={false}
                        isAnimationActive={animationDuration() > 0}
                        animationDuration={animationDuration()}
                        animationEasing={CHART_ANIM_EASING}
                        {...CHART_COMPARISON_STYLE}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                  {/* Légende claire (les couleurs recharts natives ne rendent
                      pas le style pointillé) : trait plein = période actuelle,
                      pointillé = période précédente. */}
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                      <span aria-hidden="true" className="inline-block h-0.5 w-3.5 rounded-full" style={{ background: categoricalColor(0) }} />
                      Période actuelle
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <span
                        aria-hidden="true"
                        className="inline-block h-0.5 w-3.5"
                        style={{
                          backgroundImage: `repeating-linear-gradient(90deg, ${categoricalColor(1)} 0 4px, transparent 4px 7px)`,
                        }}
                      />
                      Période précédente
                    </span>
                  </div>
                </>
              ) : (
                <AreaSansAxe
                  data={caMensuel}
                  dataKey="ca"
                  xKey="mois"
                  tone="primary"
                  name="CA HT"
                  height={180}
                  tooltipFormat={(v) => formatMAD(v, { decimals: 0 })}
                />
              )}
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

          {/* ZSAL3 — Tableau de bord « Mes équipes » (autonome : ne rend rien
              si aucune équipe ou si le rôle n'y a pas accès). */}
          <Suspense fallback={null}>
            <MesEquipesCard />
          </Suspense>

          {/* FG8 — Flux d'activités planifiées (records.Activity).
              VX189(c) — cv-auto : section liste/texte sous le pli, jamais un
              graphique recharts (voir index.css). */}
          <Card className="cv-auto">
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

          {/* Alerte factures en retard — VX189(c) cv-auto (liste, sous le pli). */}
          {facturesEnRetard.length > 0 && (
            <Card className="border-destructive/30 bg-destructive/5 cv-auto">
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
