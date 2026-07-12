// T13/T14/T15 — Hub « Rapports » : ventes/pipeline, stock, service (chantier +
// SAV). Lecture seule ; chaque rapport est exportable en .xlsx. Données
// agrégées côté serveur, bornées à la société.
// FG91 — onglet « Mes rapports » : CRUD des rapports sauvegardés (SavedReport),
// avec planification email et épinglage tableau de bord.
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, BarChart3, BookmarkPlus, Trash2, Pin, PinOff, Mail } from 'lucide-react'
import api from '../api/axios'
import reportingApi from '../api/reportingApi'
import crmApi from '../api/crmApi'
import { downloadXlsx } from '../api/importApi'
import { downloadBlobInGesture } from '../utils/downloadBlob'
import { formatNumber } from '../lib/format'
import {
  Button, Card, CardHeader, CardTitle, CardDescription, CardContent,
  Tabs, TabsList, TabsTrigger, TabsContent, Skeleton, EmptyState, Input, Spinner,
} from '../ui'
// VX28/VX148 — un seul langage de graphique (kit ui/charts), un seul
// PageHeader, un seul moteur de table de reporting (Table partagé). VX148 —
// un `BarArrondie` au-dessus des tables comparatives les plus consultées (la
// table garde le détail chiffré) + `ChartEmpty` pour un graphe sans donnée.
import { BarArrondie, ChartEmpty } from '../ui/charts'
import { PageHeader } from '../ui/PageHeader'
import { Table as SharedTable } from './reporting/Table'
import { StateBlock } from '../components/StateBlock'

// L9 — types filtrables du Journal d'activité (clés acceptées par ?type=).
const AUDIT_TYPES = [
  { value: 'lead', label: 'Lead' },
  { value: 'devis', label: 'Devis' },
  { value: 'chantier', label: 'Chantier' },
  { value: 'sav', label: 'Ticket SAV' },
  { value: 'parametres', label: 'Paramètres' },
]

// L16 — lien profond par type vers la fiche concernée. Le backend renvoie
// `object_type` (clé de route) + `object_id` quand une cible existe.
const AUDIT_ROUTE = {
  lead: (id) => `/crm/leads?lead=${id}`,
  devis: () => '/ventes/devis',
  chantier: () => '/chantiers',
  ticket: () => '/sav',
}

// Référence du Journal : un lien cliquable vers la fiche si une cible existe,
// sinon le simple libellé textuel.
function auditRef(it) {
  const make = it.object_type && AUDIT_ROUTE[it.object_type]
  if (make && it.object_id) {
    return (
      <Link to={make(it.object_id)} className="text-info hover:underline">
        {it.object_ref}
      </Link>
    )
  }
  return it.object_ref
}

// VX28 — un seul moteur de table de reporting : cet adaptateur mince délègue au
// `Table` PARTAGÉ (pages/reporting/Table.jsx, tokenisé, scrollable PWA) tout en
// gardant l'API historique de ce hub (`headers` + `rows` de tableaux + `footer`
// de tableau) — donc AUCUN site d'appel n'a besoin de changer.
//
// L882 — `footer` (optionnel) : un tableau de cellules de pied « Total » rendu
// dans un <tfoot>, calculé depuis les MÊMES données que les lignes. Masqué
// quand il n'y a aucune ligne.
function Table({ headers, rows, footer }) {
  const columns = headers.map((h, j) => ({
    key: String(j),
    header: h,
    // Les lignes de ce hub sont des TABLEAUX (une cellule par colonne) : on lit
    // la cellule d'indice colonne.
    cell: (row) => row[j],
  }))
  return (
    <SharedTable
      className="mb-2"
      columns={columns}
      rows={rows}
      empty={<span className="text-muted-foreground">Aucune donnée.</span>}
      footer={footer && rows.length > 0 ? (
        <tr className="border-t border-border font-semibold">
          {footer.map((c, j) => (
            <td key={j}
                data-label={typeof headers[j] === 'string' ? headers[j] : undefined}
                className="px-3 py-2 text-foreground">
              {c}
            </td>
          ))}
        </tr>
      ) : null}
    />
  )
}

// Somme d'une colonne numérique depuis les objets-source (pas les lignes déjà
// formatées) — base du pied « Total » L882.
const sumBy = (arr, key) => (arr || []).reduce((s, o) => s + Number(o[key] || 0), 0)

// FG101 — Lien de forage (drill-down) : affiche la valeur + un lien vers la
// liste filtrée.  Peut être utilisé comme cellule de tableau (Row[0]).
function DrillLink({ to, children }) {
  return (
    <Link to={to} className="font-medium text-info hover:underline">
      {children}
    </Link>
  )
}

// Sous-titre interne d'une carte.
function Subhead({ children }) {
  return (
    <h4 className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h4>
  )
}

// Carte de rapport T13/T14/T15 (export Excel via le chemin /reports/<kind>/).
// `params` (période) est transmis à l'export pour qu'il honore le filtre.
function ReportCard({ title, kind, params, children }) {
  const onExport = () => api
    .get(`/reporting/reports/${kind}/`,
      { params: { ...(params || {}), export: 'xlsx' }, responseType: 'blob' })
    .then(r => downloadXlsx(r.data, `rapport-${kind}.xlsx`))
    .catch(() => {})
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <CardTitle>{title}</CardTitle>
        <Button variant="outline" size="sm" onClick={onExport}>
          <Download /> Exporter Excel
        </Button>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

// Carte « insight » avec un bouton d'export personnalisé (chemin différent des
// rapports T13/T14/T15). onExport optionnel : pas de bouton si absent.
// VX172 — `busy` : pending visible pendant l'export (VX49 pose déjà le toast
// d'erreur ; ceci ajoute juste l'état chargement manquant).
// VX189(c) — `className` passthrough (ex. `cv-auto` — content-visibility sur
// une carte liste/texte sous le pli, jamais sur une carte à graphique).
function InsightCard({ title, note, onExport, busy, className, children }) {
  return (
    <Card className={className}>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div className="space-y-1">
          <CardTitle>{title}</CardTitle>
          {note && <CardDescription>{note}</CardDescription>}
        </div>
        {onExport && (
          <Button variant="outline" size="sm" onClick={onExport} disabled={!!busy}>
            {busy ? <Spinner /> : <Download />} Exporter Excel
          </Button>
        )}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

const fmt = (n) => formatNumber(n)

// ── FG91 — Mes rapports sauvegardés ─────────────────────────────────────────
// Labels FR pour les choix server.
const KIND_LABELS = { sales: 'Ventes', stock: 'Stock', service: 'Service' }
const SCHEDULE_LABELS = { none: 'Aucune', daily: 'Quotidien', weekly: 'Hebdomadaire' }

// Formulaire de création/édition d'un rapport sauvegardé.
function SavedReportForm({ initial, onSave, onCancel }) {
  const [name, setName] = useState(initial?.name || '')
  const [kind, setKind] = useState(initial?.target_kind || 'sales')
  const [schedule, setSchedule] = useState(initial?.schedule || 'none')
  const [recipients, setRecipients] = useState(initial?.recipients || '')
  const [pinned, setPinned] = useState(initial?.pinned || false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) { setErr('Le nom est requis.'); return }
    setSaving(true)
    setErr('')
    try {
      await onSave({ name: name.trim(), target_kind: kind, schedule, recipients, pinned })
    } catch {
      setErr("Erreur lors de l'enregistrement.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {err && <p className="text-sm text-destructive">{err}</p>}
      <div>
        <label className="mb-1 block text-xs font-medium text-muted-foreground">Nom *</label>
        <Input value={name} onChange={e => setName(e.target.value)}
               placeholder="Ex : Ventes mensuelles" maxLength={255} />
      </div>
      <div className="flex flex-wrap gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">Type</label>
          <select value={kind} onChange={e => setKind(e.target.value)}
                  className="h-9 rounded-md border border-input bg-card px-2 text-sm">
            {Object.entries(KIND_LABELS).map(([v, l]) =>
              <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">Envoi automatique</label>
          <select value={schedule} onChange={e => setSchedule(e.target.value)}
                  className="h-9 rounded-md border border-input bg-card px-2 text-sm">
            {Object.entries(SCHEDULE_LABELS).map(([v, l]) =>
              <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
      </div>
      {schedule !== 'none' && (
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Destinataires (séparés par virgule)
          </label>
          <Input value={recipients} onChange={e => setRecipients(e.target.value)}
                 placeholder="ex: boss@exemple.com, equipe@exemple.com" />
        </div>
      )}
      <div className="flex items-center gap-2">
        <input id="pinned" type="checkbox" checked={pinned}
               onChange={e => setPinned(e.target.checked)} className="accent-primary" />
        <label htmlFor="pinned" className="text-sm">Épingler sur le tableau de bord</label>
      </div>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? 'Enregistrement…' : 'Enregistrer'}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>
          Annuler
        </Button>
      </div>
    </form>
  )
}

// Onglet « Mes rapports » — liste + CRUD des SavedReport.
function MesRapports() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)  // null = nouveau
  const [deletingId, setDeletingId] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    reportingApi.listSavedReports()
      .then(r => {
        const data = r.data
        setReports(Array.isArray(data) ? data : (data.results || []))
      })
      .catch(() => setReports([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(() => { load() }, [load])

  const handleCreate = async (payload) => {
    await reportingApi.createSavedReport(payload)
    setShowForm(false)
    load()
  }

  const handleUpdate = async (id, payload) => {
    await reportingApi.updateSavedReport(id, payload)
    setEditing(null)
    load()
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Supprimer ce rapport sauvegardé ?')) return
    setDeletingId(id)
    try {
      await reportingApi.deleteSavedReport(id)
      load()
    } finally {
      setDeletingId(null)
    }
  }

  const togglePin = async (r) => {
    await reportingApi.updateSavedReport(r.id, { pinned: !r.pinned })
    load()
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2].map(i => <Skeleton key={i} className="h-20 w-full" />)}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Sauvegardez et planifiez l'envoi automatique de vos rapports par email.
        </p>
        {!showForm && !editing && (
          <Button size="sm" onClick={() => setShowForm(true)}>
            <BookmarkPlus className="mr-1 h-4 w-4" /> Nouveau rapport
          </Button>
        )}
      </div>

      {showForm && !editing && (
        <Card>
          <CardHeader><CardTitle>Nouveau rapport sauvegardé</CardTitle></CardHeader>
          <CardContent>
            <SavedReportForm
              onSave={handleCreate}
              onCancel={() => setShowForm(false)}
            />
          </CardContent>
        </Card>
      )}

      {reports.length === 0 && !showForm && (
        <EmptyState icon={BarChart3} title="Aucun rapport sauvegardé"
                    description="Créez votre premier rapport pour le consulter rapidement." />
      )}

      {reports.map(r => (
        <Card key={r.id}>
          {editing?.id === r.id ? (
            <>
              <CardHeader><CardTitle>Modifier : {r.name}</CardTitle></CardHeader>
              <CardContent>
                <SavedReportForm
                  initial={r}
                  onSave={(payload) => handleUpdate(r.id, payload)}
                  onCancel={() => setEditing(null)}
                />
              </CardContent>
            </>
          ) : (
            <>
              <CardHeader className="flex-row items-start justify-between gap-2">
                <div className="space-y-0.5">
                  <CardTitle className="flex items-center gap-2">
                    {r.pinned && <Pin className="h-4 w-4 text-warning" aria-label="Épinglé" />}
                    {r.name}
                  </CardTitle>
                  <CardDescription>
                    {KIND_LABELS[r.target_kind] || r.target_kind}
                    {' · '}
                    Envoi : {SCHEDULE_LABELS[r.schedule] || r.schedule}
                    {r.schedule !== 'none' && r.recipients && (
                      <span className="ml-1 inline-flex items-center gap-1">
                        <Mail className="h-3 w-3" />
                        {r.recipients.split(/[,;\n]/).filter(Boolean).length} destinataire(s)
                      </span>
                    )}
                    {r.last_sent_at && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        Dernier envoi : {r.last_sent_at.slice(0, 10)}
                      </span>
                    )}
                  </CardDescription>
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button variant="ghost" size="icon" title={r.pinned ? 'Désépingler' : 'Épingler'}
                          onClick={() => togglePin(r)}>
                    {r.pinned
                      ? <PinOff className="h-4 w-4 text-warning" />
                      : <Pin className="h-4 w-4" />}
                  </Button>
                  <Button variant="ghost" size="sm"
                          onClick={() => { setShowForm(false); setEditing(r) }}>
                    Modifier
                  </Button>
                  <Button variant="ghost" size="icon"
                          disabled={deletingId === r.id}
                          onClick={() => handleDelete(r.id)}
                          title="Supprimer">
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </CardHeader>
            </>
          )}
        </Card>
      ))}
    </div>
  )
}

// VX67 — Carte d'erreur FR quand un rapport échoue (réseau / serveur),
// StateBlock apporte un bouton « Réessayer » câblé sur le reload de CETTE
// carte (onRetry), là où l'ancienne carte n'offrait aucun moyen de réessayer
// sans recharger toute la page.
function ErrorCard({ title, message, onRetry }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        <StateBlock error={message || 'Rapport indisponible'} onRetry={onRetry} />
      </CardContent>
    </Card>
  )
}

// Carte « chargement » explicite (libellé FR + squelette) via StateBlock.
function LoadingCard({ title }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        <StateBlock loading loadingText="Chargement…" />
        <Skeleton className="mt-2 h-24 w-full" />
      </CardContent>
    </Card>
  )
}

export function Component() {
  const [sales, setSales] = useState(null)
  const [stock, setStock] = useState(null)
  const [service, setService] = useState(null)
  // ZSAL6 — Rapport d'attribution des leads (par commercial + par source).
  const [attribution, setAttribution] = useState(null)
  const [recurring, setRecurring] = useState(null)
  const [audit, setAudit] = useState(null)
  const [jobCosting, setJobCosting] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [commissions, setCommissions] = useState(null)
  // État par carte : 'loading' | 'ok' | 'error'.
  const [status, setStatus] = useState({})
  // Période optionnelle (?from=&to=) appliquée à ventes/stock/service.
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  // L9 — filtres du Journal d'activité (l'endpoint accepte ?user, ?type,
  // ?since) : pilotent l'affichage ET l'export .xlsx de la carte Journal.
  const [auditUser, setAuditUser] = useState('')
  const [auditType, setAuditType] = useState('')
  const [auditSince, setAuditSince] = useState('')

  const setCardStatus = useCallback((key, value) => {
    setStatus((s) => ({ ...s, [key]: value }))
  }, [])

  // Repasse les cartes period-aware en « chargement » lors d'un changement de
  // période (déclenché par l'utilisateur, hors effet → conforme aux règles).
  const resetPeriodCards = () => {
    setStatus((s) => {
      const next = { ...s }
      delete next.sales
      delete next.stock
      delete next.service
      delete next.attribution
      return next
    })
  }
  const onFrom = (e) => { resetPeriodCards(); setFrom(e.target.value) }
  const onTo = (e) => { resetPeriodCards(); setTo(e.target.value) }
  const onClearPeriod = () => { resetPeriodCards(); setFrom(''); setTo('') }

  // Charge un rapport et trace son état (ok/error) à la résolution. L'état
  // « loading » est implicite : status[key] indéfini → carte « Chargement… »
  // (on ne met pas setState de façon synchrone dans l'effet).
  const load = useCallback((key, promise, setter) => (
    promise
      .then((r) => { setter(r.data); setCardStatus(key, 'ok') })
      .catch(() => { setter(null); setCardStatus(key, 'error') })
  ), [setCardStatus])

  // Les rapports period-aware (ventes/stock/service) se rechargent au filtre.
  useEffect(() => {
    const params = {}
    if (from) params.from = from
    if (to) params.to = to
    load('sales', api.get('/reporting/reports/sales/', { params }), setSales)
    load('stock', api.get('/reporting/reports/stock/', { params }), setStock)
    load('service', api.get('/reporting/reports/service/', { params }), setService)
    // ZSAL6 — même période (?debut=&fin=, noms distincts côté CRM).
    const attrParams = {}
    if (from) attrParams.debut = from
    if (to) attrParams.fin = to
    load('attribution', crmApi.getAttributionLeads(attrParams), setAttribution)
  }, [from, to, load])

  // Les insights (all-time) ne sont chargés qu'une fois.
  useEffect(() => {
    load('recurring', reportingApi.recurringRevenue(), setRecurring)
    // Réservé owner/responsable — un refus (403) est traité comme « erreur ».
    load('jobCosting', reportingApi.jobCosting(), setJobCosting)
    load('analytics', reportingApi.analytics(), setAnalytics)
    // N99 — réservé admin.
    load('commissions', reportingApi.commissions(), setCommissions)
  }, [load])

  // Paramètres de filtre du Journal (envoyés à l'endpoint et à l'export).
  const auditParams = {}
  if (auditUser.trim()) auditParams.user = auditUser.trim()
  if (auditType) auditParams.type = auditType
  if (auditSince) auditParams.since = auditSince

  // Le Journal se recharge quand un filtre change.
  useEffect(() => {
    const p = {}
    if (auditUser.trim()) p.user = auditUser.trim()
    if (auditType) p.type = auditType
    if (auditSince) p.since = auditSince
    load('audit', reportingApi.auditLog(p), setAudit)
  }, [auditUser, auditType, auditSince, load])

  // Remet la carte Journal en « chargement » quand on change un filtre.
  const resetAuditCard = () => setStatus((s) => {
    const next = { ...s }; delete next.audit; return next
  })
  const onAuditUser = (e) => { resetAuditCard(); setAuditUser(e.target.value) }
  const onAuditType = (e) => { resetAuditCard(); setAuditType(e.target.value) }
  const onAuditSince = (e) => { resetAuditCard(); setAuditSince(e.target.value) }
  const onAuditClear = () => {
    resetAuditCard(); setAuditUser(''); setAuditType(''); setAuditSince('')
  }

  // VX172 — geste ouvert AVANT le premier `await` + pending visible par carte
  // (clé = slug) sur les boutons « Exporter Excel » des Insights.
  const [insightExportBusy, setInsightExportBusy] = useState({})
  const exportInsight = (slug, params) => () => {
    const pending = downloadBlobInGesture()
    setInsightExportBusy((b) => ({ ...b, [slug]: true }))
    reportingApi.insightXlsx(slug, params)
      .then(r => pending.deliver(r.data, `${slug}.xlsx`))
      .catch(() => {})
      .finally(() => setInsightExportBusy((b) => ({ ...b, [slug]: false })))
  }

  const periodParams = {}
  if (from) periodParams.from = from
  if (to) periodParams.to = to

  // VX67 — recharge UNE SEULE carte par sa clé (utilisé par le bouton
  // « Réessayer » de StateBlock/ErrorCard). Reprend exactement les mêmes
  // requêtes/params que les effets ci-dessus, sans jamais recharger la page.
  const reloadCard = (key) => {
    setCardStatus(key, undefined)
    if (key === 'sales') {
      const params = {}
      if (from) params.from = from
      if (to) params.to = to
      load('sales', api.get('/reporting/reports/sales/', { params }), setSales)
    } else if (key === 'stock') {
      const params = {}
      if (from) params.from = from
      if (to) params.to = to
      load('stock', api.get('/reporting/reports/stock/', { params }), setStock)
    } else if (key === 'service') {
      const params = {}
      if (from) params.from = from
      if (to) params.to = to
      load('service', api.get('/reporting/reports/service/', { params }), setService)
    } else if (key === 'attribution') {
      const attrParams = {}
      if (from) attrParams.debut = from
      if (to) attrParams.fin = to
      load('attribution', crmApi.getAttributionLeads(attrParams), setAttribution)
    } else if (key === 'recurring') {
      load('recurring', reportingApi.recurringRevenue(), setRecurring)
    } else if (key === 'jobCosting') {
      load('jobCosting', reportingApi.jobCosting(), setJobCosting)
    } else if (key === 'analytics') {
      load('analytics', reportingApi.analytics(), setAnalytics)
    } else if (key === 'commissions') {
      load('commissions', reportingApi.commissions(), setCommissions)
    } else if (key === 'audit') {
      load('audit', reportingApi.auditLog(auditParams), setAudit)
    }
  }

  // Rendu d'une carte period-aware selon son état de chargement.
  const renderReportCard = (key, title, render) => {
    if (status[key] === 'loading' || status[key] === undefined) {
      return <LoadingCard title={title} />
    }
    if (status[key] === 'error') {
      return <ErrorCard title={title} message="Rapport indisponible" onRetry={() => reloadCard(key)} />
    }
    return render()
  }

  return (
    <div className="ui-root page" style={{ maxWidth: 1100 }}>
      {/* VX28 — PageHeader unifié (remplace le `.page-header` + `<h2>` nu). */}
      <PageHeader title="Rapports" icon={BarChart3} />

      <Tabs defaultValue="ventes">
        <TabsList className="flex-wrap">
          <TabsTrigger value="ventes">Ventes &amp; pipeline</TabsTrigger>
          <TabsTrigger value="stock">Stock</TabsTrigger>
          <TabsTrigger value="service">Service</TabsTrigger>
          <TabsTrigger value="insights">Insights</TabsTrigger>
          <TabsTrigger value="mes-rapports">Mes rapports</TabsTrigger>
        </TabsList>

        {/* ── Filtre de période (ventes / stock / service) ── */}
        <div className="my-3 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Du</span>
            <Input type="date" value={from} onChange={onFrom} />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Au</span>
            <Input type="date" value={to} onChange={onTo} />
          </label>
          {(from || to) && (
            <Button variant="outline" size="sm" onClick={onClearPeriod}>
              Effacer la période
            </Button>
          )}
        </div>

        {/* ── Ventes & pipeline ── */}
        <TabsContent value="ventes">
          {renderReportCard('sales', 'Ventes & pipeline', () => (
            <ReportCard title="Ventes & pipeline" kind="sales" params={periodParams}>
              {/* VX148 — entonnoir en graphe AU-DESSUS de la table (qui garde
                  le détail chiffré + les liens de drill-down). */}
              {sales.funnel.length > 0 ? (
                <BarArrondie
                  data={sales.funnel.map((f) => ({ label: f.label, value: f.count }))}
                  layout="vertical"
                  tone="info"
                  name="Leads"
                  height={Math.max(140, sales.funnel.length * 34)}
                  categoryWidth={110}
                  tooltipFormat={(v) => `${fmt(v)} leads`}
                />
              ) : (
                <ChartEmpty title="Aucun lead" />
              )}
              {/* FG101 — funnel : clic sur étape → liste leads filtrée par stage */}
              <Table headers={['Étape', 'Leads']}
                     rows={sales.funnel.map(f => [
                       <DrillLink to={`/crm/leads?stage=${f.stage}`}>{f.label}</DrillLink>,
                       fmt(f.count),
                     ])}
                     footer={['Total', fmt(sumBy(sales.funnel, 'count'))]} />
              {sales.devis_par_statut?.length > 0 && (
                <>
                  <Subhead>Devis par statut</Subhead>
                  <Table headers={['Statut', 'Nombre']}
                         rows={sales.devis_par_statut.map(d => [
                           <DrillLink to={`/ventes/devis?statut=${d.statut}`}>{d.label}</DrillLink>,
                           fmt(d.count),
                         ])}
                         footer={['Total', fmt(sumBy(sales.devis_par_statut, 'count'))]} />
                </>
              )}
              <Subhead>Par responsable</Subhead>
              {/* FG101 — clic sur responsable → liste leads filtrée par owner */}
              <Table headers={['Responsable', 'Leads', 'Gagnés']}
                     rows={sales.par_responsable.map(r => [
                       r.owner__username
                         ? <DrillLink to={`/crm/leads?owner=${encodeURIComponent(r.owner__username)}`}>{r.owner__username}</DrillLink>
                         : '—',
                       fmt(r.count), fmt(r.gagnes),
                     ])}
                     footer={['Total', fmt(sumBy(sales.par_responsable, 'count')), fmt(sumBy(sales.par_responsable, 'gagnes'))]} />
              <Subhead>Pertes par motif</Subhead>
              {/* FG101 — clic sur motif → liste leads perdus filtrée */}
              <Table headers={['Motif', 'Nombre']}
                     rows={sales.perdus_par_motif.map(r => [
                       <DrillLink
                         to={`/crm/leads?perdu=true${r.motif_perte ? `&motif=${encodeURIComponent(r.motif_perte)}` : ''}`}>
                         {r.motif_perte || 'Non précisé'}
                       </DrillLink>,
                       fmt(r.count),
                     ])}
                     footer={['Total', fmt(sumBy(sales.perdus_par_motif, 'count'))]} />
            </ReportCard>
          ))}

          {/* ZSAL6 — Attribution des leads (par commercial + par source). */}
          {renderReportCard('attribution', 'Attribution des leads', () => (
            <InsightCard title="Attribution des leads"
                         note="Répartition des leads par commercial et par canal, croisée avec la conversion et le CA signé.">
              <Subhead>Par commercial</Subhead>
              <Table headers={['Commercial', 'Leads', 'Signés', 'Taux', 'CA signé']}
                     rows={(attribution?.par_commercial ?? []).map((r) => [
                       r.commercial
                         ? <DrillLink to={`/crm/leads?owner=${encodeURIComponent(r.commercial)}`}>{r.commercial}</DrillLink>
                         : 'Non assigné',
                       fmt(r.nb_leads), fmt(r.nb_signes),
                       `${r.taux_conversion_pct ?? 0}%`,
                       `${fmt(r.ca_signe)} DH`,
                     ])}
                     footer={['Total',
                       fmt(sumBy(attribution?.par_commercial ?? [], 'nb_leads')),
                       fmt(sumBy(attribution?.par_commercial ?? [], 'nb_signes')),
                       '', `${fmt(sumBy(attribution?.par_commercial ?? [], 'ca_signe'))} DH`]} />
              <Subhead>Par source</Subhead>
              {/* Pas de lien de drill-down ici : la liste des leads n'a pas
                  de filtre par canal aujourd'hui (contrairement à owner/stage
                  ci-dessus) — on n'invente pas une route qui n'existe pas. */}
              <Table headers={['Canal', 'Leads', 'Signés', 'Taux', 'CA signé']}
                     rows={(attribution?.par_source ?? []).map((r) => [
                       r.canal_label || r.canal,
                       fmt(r.nb_leads), fmt(r.nb_signes),
                       `${r.taux_conversion_pct ?? 0}%`,
                       `${fmt(r.ca_signe)} DH`,
                     ])}
                     footer={['Total',
                       fmt(sumBy(attribution?.par_source ?? [], 'nb_leads')),
                       fmt(sumBy(attribution?.par_source ?? [], 'nb_signes')),
                       '', `${fmt(sumBy(attribution?.par_source ?? [], 'ca_signe'))} DH`]} />
            </InsightCard>
          ))}
        </TabsContent>

        {/* ── Stock ── */}
        <TabsContent value="stock">
          {renderReportCard('stock', 'Stock', () => (
            <ReportCard title="Stock" kind="stock" params={periodParams}>
              <p className="text-sm">
                Valorisation (vente) : <strong className="tabular-nums">{fmt(stock.valorisation_vente)} DH</strong>
                {' · '}achat (interne) : <span className="tabular-nums">{fmt(stock.valorisation_achat)} DH</span>
              </p>
              <Subhead>Par catégorie</Subhead>
              {/* VX148 — valeur vente HT par catégorie, en graphe (la table
                  garde le détail nb articles + total). */}
              {stock.par_categorie.length > 0 ? (
                <BarArrondie
                  data={stock.par_categorie.map((c) => ({ label: c.categorie__nom || '—', value: Number(c.valeur_vente) || 0 }))}
                  layout="vertical"
                  tone="primary"
                  name="Valeur vente HT"
                  height={Math.max(140, stock.par_categorie.length * 34)}
                  categoryWidth={110}
                  tooltipFormat={(v) => `${fmt(v)} DH`}
                />
              ) : (
                <ChartEmpty title="Aucune catégorie" />
              )}
              <Table headers={['Catégorie', 'Articles', 'Valeur vente HT']}
                     rows={stock.par_categorie.map(c => [c.categorie__nom || '—', fmt(c.nb), fmt(c.valeur_vente)])}
                     footer={['Total', fmt(sumBy(stock.par_categorie, 'nb')), fmt(sumBy(stock.par_categorie, 'valeur_vente'))]} />
              <Subhead>Stock bas</Subhead>
              {/* FG101 — clic sur produit → liste stock filtrée par recherche */}
              <Table headers={['Produit', 'SKU', 'Stock', 'Seuil']}
                     rows={stock.bas_stock.map(p => [
                       <DrillLink to={`/stock/produits?search=${encodeURIComponent(p.nom)}`}>{p.nom}</DrillLink>,
                       p.sku || '—',
                       fmt(p.quantite_stock),
                       fmt(p.seuil_alerte),
                     ])} />
            </ReportCard>
          ))}
        </TabsContent>

        {/* ── Service ── */}
        <TabsContent value="service">
          {renderReportCard('service', 'Service (chantiers + SAV)', () => (
            <ReportCard title="Service (chantiers + SAV)" kind="service" params={periodParams}>
              <p className="text-sm">
                Tickets ouverts : <strong className="tabular-nums">{fmt(service.tickets_ouverts)}</strong>
                {' · '}résolus : <span className="tabular-nums">{fmt(service.tickets_resolus)}</span>
                {' · '}garanties expirant ≤90 j : <span className="tabular-nums">{fmt(service.garanties_expirantes_90j)}</span>
              </p>
              <Subhead>Chantiers par statut</Subhead>
              {/* VX148 — répartition en graphe AU-DESSUS de la table (qui
                  garde le lien de drill-down par statut). */}
              {service.chantiers_par_statut.length > 0 ? (
                <BarArrondie
                  data={service.chantiers_par_statut.map((c) => ({ label: c.statut, value: c.count }))}
                  layout="vertical"
                  tone="info"
                  name="Chantiers"
                  height={Math.max(140, service.chantiers_par_statut.length * 34)}
                  categoryWidth={110}
                  tooltipFormat={(v) => `${fmt(v)} chantier(s)`}
                />
              ) : (
                <ChartEmpty title="Aucun chantier" />
              )}
              {/* FG101 — clic sur statut → liste chantiers filtrée */}
              <Table headers={['Statut', 'Nombre']}
                     rows={service.chantiers_par_statut.map(c => [
                       <DrillLink to={`/chantiers?statut=${encodeURIComponent(c.statut)}`}>{c.statut}</DrillLink>,
                       fmt(c.count),
                     ])}
                     footer={['Total', fmt(sumBy(service.chantiers_par_statut, 'count'))]} />
              <Subhead>Activité technicien</Subhead>
              <Table headers={['Technicien', 'Interventions']}
                     rows={service.interventions_par_technicien.map(t => [t.technicien__username || '—', fmt(t.count)])}
                     footer={['Total', fmt(sumBy(service.interventions_par_technicien, 'count'))]} />
            </ReportCard>
          ))}
        </TabsContent>

        {/* ── Insights ── */}
        <TabsContent value="insights">
          <div className="space-y-6">
            <InsightCard title="Revenu récurrent (contrats de maintenance)"
                         onExport={exportInsight('recurring-revenue')}
                         busy={insightExportBusy['recurring-revenue']}>
              {status.recurring === 'error' ? (
                <StateBlock error="Rapport indisponible" onRetry={() => reloadCard('recurring')} />
              ) : recurring ? (
                <>
                  <p className="text-sm">
                    Mensuel équivalent : <strong className="tabular-nums">{fmt(recurring.monthly_total)} DH</strong>
                    {' · '}annuel équivalent : <strong className="tabular-nums">{fmt(recurring.annual_total)} DH</strong>
                    {' · '}contrats actifs : <span className="tabular-nums">{fmt(recurring.active_count)}</span>
                    {' · '}inactifs : <span className="tabular-nums">{fmt(recurring.lapsed_count)}</span>
                  </p>
                  <Subhead>Renouvellements / visites sous 90 jours</Subhead>
                  <Table headers={['Client', 'Périodicité', 'Prochaine visite', 'Mensuel équiv. (DH)']}
                         rows={recurring.upcoming.map(c => [c.client, c.periodicite_label, c.prochaine_visite || '—', fmt(c.monthly_equivalent)])}
                         footer={[`Total (${recurring.upcoming.length})`, '', '', fmt(sumBy(recurring.upcoming, 'monthly_equivalent'))]} />
                </>
              ) : <p className="text-sm text-muted-foreground">Chargement…</p>}
            </InsightCard>

            <InsightCard title="Journal d'activité (qui a fait quoi)"
                         onExport={exportInsight('audit-log', auditParams)}
                         busy={insightExportBusy['audit-log']}>
              {/* L9 — filtres user / type / depuis pilotant l'endpoint et l'export. */}
              <div className="mb-3 flex flex-wrap items-end gap-2">
                <Input value={auditUser} onChange={onAuditUser}
                       placeholder="Utilisateur" aria-label="Filtrer par utilisateur"
                       className="h-9 w-40" />
                <select value={auditType} onChange={onAuditType}
                        aria-label="Filtrer par type"
                        className="h-9 rounded-md border border-input bg-card px-2 text-sm">
                  <option value="">Tous les types</option>
                  {AUDIT_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
                <Input type="date" value={auditSince} onChange={onAuditSince}
                       aria-label="Depuis la date" className="h-9 w-40" />
                {(auditUser || auditType || auditSince) && (
                  <Button variant="ghost" size="sm" onClick={onAuditClear}>
                    Réinitialiser
                  </Button>
                )}
              </div>
              {status.audit === 'error' ? (
                <StateBlock error="Rapport indisponible" onRetry={() => reloadCard('audit')} />
              ) : audit ? (
                <Table headers={['Date', 'Utilisateur', 'Type', 'Référence', 'Action']}
                       rows={audit.items.map(it => [
                         (it.date || '').replace('T', ' ').slice(0, 16),
                         it.user || '—', it.type_label, auditRef(it), it.summary,
                       ])} />
              ) : <p className="text-sm text-muted-foreground">Chargement…</p>}
            </InsightCard>

            <InsightCard title="Coût de revient par chantier"
                         note="(interne — visible owner/responsable)"
                         onExport={jobCosting ? exportInsight('job-costing') : undefined}
                         busy={insightExportBusy['job-costing']}>
              {status.jobCosting === 'error' ? (
                <p className="text-sm text-muted-foreground">Réservé admin / responsable.</p>
              ) : jobCosting ? (
                <>
                  <p className="text-sm">
                    Facturé HT : <strong className="tabular-nums">{fmt(jobCosting.total_invoiced_ht)} DH</strong>
                    {' · '}coût estimé : <span className="tabular-nums">{fmt(jobCosting.total_cost_estimate)} DH</span>
                    {' · '}marge : <strong className="tabular-nums">{fmt(jobCosting.total_margin)} DH</strong>
                  </p>
                  <Table headers={['Chantier', 'Client', 'Facturé HT', 'Coût estimé', 'Marge', 'Marge %']}
                         rows={jobCosting.chantiers.map(c => [
                           c.ref, c.client, fmt(c.invoiced_ht), fmt(c.cost_estimate),
                           fmt(c.margin), `${c.margin_pct} %`,
                         ])}
                         footer={[`Total (${jobCosting.chantiers.length})`, '',
                                  fmt(sumBy(jobCosting.chantiers, 'invoiced_ht')),
                                  fmt(sumBy(jobCosting.chantiers, 'cost_estimate')),
                                  fmt(sumBy(jobCosting.chantiers, 'margin')), '']} />
                </>
              ) : <p className="text-sm text-muted-foreground">Chargement…</p>}
            </InsightCard>

            <InsightCard title="Analytics (délais & kWc installés)"
                         onExport={exportInsight('analytics')}
                         busy={insightExportBusy['analytics']}>
              {status.analytics === 'error' ? (
                <StateBlock error="Rapport indisponible" onRetry={() => reloadCard('analytics')} />
              ) : analytics ? (
                <>
                  <p className="text-sm">
                    Délai moyen lead → signature : <strong className="tabular-nums">{analytics.avg_days_lead_to_signature ?? '—'} j</strong>
                    {' · '}signature → mise en service : <strong className="tabular-nums">{analytics.avg_days_signature_to_commissioning ?? '—'} j</strong>
                  </p>
                  <Subhead>kWc installés par mois</Subhead>
                  {analytics.kwc_by_month.length > 0 ? (
                    <BarArrondie
                      data={analytics.kwc_by_month.map(m => ({ mois: m.mois, kwc: Number(m.kwc) }))}
                      dataKey="kwc"
                      categoryKey="mois"
                      tone="info"
                      name="kWc"
                      height={220}
                      tooltipFormat={(v) => formatNumber(v)}
                    />
                  ) : (
                    <ChartEmpty title="Aucune donnée" />
                  )}
                </>
              ) : <p className="text-sm text-muted-foreground">Chargement…</p>}
            </InsightCard>

            {/* VX189(c) — cv-auto : dernière carte de l'onglet Insights, liste/
                texte (Table), jamais un graphique recharts. */}
            <InsightCard title="Commissions commerciales"
                         note="(interne — visible admin ; configuré dans Paramètres)"
                         onExport={commissions?.enabled
                           ? exportInsight('commissions') : undefined}
                         busy={insightExportBusy.commissions}
                         className="cv-auto">
              {status.commissions === 'error' && (
                <p className="text-sm text-muted-foreground">Réservé admin.</p>
              )}
              {commissions && !commissions.enabled && (
                <p className="text-sm text-muted-foreground">
                  Commissions désactivées. Activez-les dans Paramètres → Devis &amp;
                  Factures → Commission commerciale.
                </p>
              )}
              {commissions && commissions.enabled && (
                <>
                  <p className="text-sm">
                    Total commissions : <strong className="tabular-nums">{fmt(commissions.total)} DH</strong>
                  </p>
                  <Table headers={['Commercial', 'Devis signés',
                                   commissions.base_label, 'Commission (DH)']}
                         rows={commissions.rows.map(r => [
                           r.commercial, fmt(r.count), fmt(r.base), fmt(r.commission),
                         ])}
                         footer={['Total', fmt(sumBy(commissions.rows, 'count')),
                                  fmt(sumBy(commissions.rows, 'base')),
                                  fmt(sumBy(commissions.rows, 'commission'))]} />
                </>
              )}
            </InsightCard>
          </div>
        </TabsContent>

        {/* ── FG91 — Mes rapports sauvegardés ── */}
        <TabsContent value="mes-rapports">
          <MesRapports />
        </TabsContent>
      </Tabs>
    </div>
  )
}
