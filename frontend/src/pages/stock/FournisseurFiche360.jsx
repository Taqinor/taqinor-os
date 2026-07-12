import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { useHasPermission, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import {
  BarChart3, FileWarning, PackageCheck, Receipt, Wallet,
  Undo2, ShieldCheck, Tags,
} from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import { telHref } from '../../lib/contactLinks'
import {
  Spinner, Tabs, TabsList, TabsTrigger, TabsContent,
  Card, CardHeader, CardTitle, CardContent, Stat, RelationCounters,
} from '../../ui'

// XPUR25 — Fiche fournisseur 360 : une page à onglets qui rassemble les
// briques déjà existantes (performance FG59, factures/solde AP, retours/avoirs,
// réceptions, documents de conformité XPUR1, accords de prix FG318) derrière
// UN endpoint d'agrégat + les endpoints détaillés déjà câblés ailleurs
// (WR4). Réservé aux rôles porteurs de la lecture stock (donnée d'achat
// INTERNE, jamais client-facing) — même garde que le reste de l'écran
// fournisseur (`FournisseursStock.jsx`).
//
// NOTE IMPORTANTE (voir docs/PLAN.md XPUR25) : l'endpoint d'agrégat
// `fournisseurs/{id}/vue-360/` N'EXISTE PAS ENCORE côté backend (BLOCKED).
// Cette page reste pleinement utilisable : le panneau résumé qui consomme
// l'agrégat affiche un état « indisponible » propre (pas de crash, pas de
// message technique) tant que l'agrégat 404, et les onglets détaillés
// continuent à fonctionner via les vrais endpoints existants.

const fmtMad = (v) => formatMAD(v)

const fmtDate = (v) => {
  if (!v) return '—'
  try { return new Date(v).toLocaleDateString('fr-FR') } catch { return '—' }
}

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

function Indisponible({ message }) {
  return (
    <p data-testid="f360-indisponible" className="text-sm text-muted-foreground">
      {message ?? 'Indisponible pour le moment.'}
    </p>
  )
}

// ── Panneau résumé — consomme l'agrégat vue-360 (BLOCKED côté backend) ──────
// VX159/VX250 — la requête (`stockApi.getFournisseur360`) est REMONTÉE au
// parent (`FournisseurFiche360`) : RelationCounters (tête de page) et ce
// panneau consomment désormais le MÊME appel réseau — jamais un second fetch
// dupliqué du même endpoint.
function ResumePanel({ data, unavailable, loading }) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
        <Spinner /> Chargement…
      </div>
    )
  }
  if (unavailable || !data) {
    return (
      <Indisponible message="Vue d'ensemble indisponible (agrégat non encore construit côté serveur)." />
    )
  }

  return (
    <div className="grid gap-3 sm:grid-cols-4">
      <Stat label="BCF ouverts" value={String(data.bcf_ouverts ?? 0)} />
      <Stat label="BCF en retard" value={String(data.bcf_en_retard ?? 0)} />
      <Stat label="Réceptions attendues" value={String(data.receptions_attendues ?? 0)} />
      <Stat label="Solde dû total" value={fmtMad(data.solde_total_du)} />
      <Stat label="Factures ouvertes" value={String(data.factures_ouvertes ?? 0)} />
      <Stat label="Score performance" value={data.score_performance != null ? String(data.score_performance) : '—'} />
      <Stat label="Retours/avoirs" value={String(data.nb_retours_avoirs ?? 0)} />
      <Stat label="Accords de prix actifs" value={String(data.accords_prix_actifs ?? 0)} />
    </div>
  )
}

// ── Onglet Performance (FG59, déjà câblé ailleurs — WR4) ────────────────────
function OngletPerformance({ fournisseurId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.performanceFournisseur(fournisseurId)
      .then((r) => { if (active) setData(r.data ?? null) })
      .catch((e) => { if (active) setError(frErr(e, 'Performance indisponible.')) })
    return () => { active = false }
  }, [fournisseurId])

  if (error) return <Indisponible message={error} />
  if (!data) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>

  const pct = (v) => (v == null ? '—' : `${v} %`)
  const jours = (v) => (v == null ? '—' : `${v} j`)

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <Stat label="Bons de commande" value={String(data.nb_bons ?? 0)} />
      <Stat label="Délai moyen de livraison" value={jours(data.avg_lead_time_days)} />
      <Stat label="Taux de remplissage" value={pct(data.fill_rate_pct)} />
      <Stat label="Retours" value={String(data.nb_retours ?? 0)} />
      <Stat label="Taux de retour" value={pct(data.return_rate_pct)} />
      <Stat label="Dépenses totales (interne)" value={fmtMad(data.total_achats_ht)} />
    </div>
  )
}

// ── Onglet BCF (ouverts + en retard) ─────────────────────────────────────────
function OngletBcf({ fournisseurId }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.getBonsCommandeFournisseurDe(fournisseurId)
      .then((r) => { if (active) setItems(r.data?.results ?? r.data ?? []) })
      .catch((e) => { if (active) setError(frErr(e, 'Bons de commande indisponibles.')) })
    return () => { active = false }
  }, [fournisseurId])

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  if (items.length === 0) return <Indisponible message="Aucun bon de commande." />

  return (
    <ul className="flex flex-col gap-2">
      {items.map((b) => (
        <li key={b.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
          <span>{b.reference ?? `BCF #${b.id}`}</span>
          <span className="text-muted-foreground">{b.statut ?? '—'}</span>
        </li>
      ))}
    </ul>
  )
}

// ── Onglet Factures / solde ───────────────────────────────────────────────
function OngletFactures({ fournisseurId }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.getFacturesFournisseurDe(fournisseurId)
      .then((r) => { if (active) setItems(r.data?.results ?? r.data ?? []) })
      .catch((e) => { if (active) setError(frErr(e, 'Factures indisponibles.')) })
    return () => { active = false }
  }, [fournisseurId])

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  if (items.length === 0) return <Indisponible message="Aucune facture." />

  const totalDu = items.reduce((s, f) => s + (Number(f.solde_du) || 0), 0)

  return (
    <div className="flex flex-col gap-3">
      <Stat label="Solde dû total (onglet)" value={fmtMad(totalDu)} />
      <ul className="flex flex-col gap-2">
        {items.map((f) => (
          <li key={f.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
            <span>{f.reference ?? `Facture #${f.id}`}</span>
            <span className="text-muted-foreground tabular-nums">{fmtMad(f.solde_du)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ── Onglet Retours / avoirs ───────────────────────────────────────────────
function OngletRetours({ fournisseurId }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.getRetoursFournisseurDe(fournisseurId)
      .then((r) => { if (active) setItems(r.data?.results ?? r.data ?? []) })
      .catch((e) => { if (active) setError(frErr(e, 'Retours indisponibles.')) })
    return () => { active = false }
  }, [fournisseurId])

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  if (items.length === 0) return <Indisponible message="Aucun retour." />

  return (
    <ul className="flex flex-col gap-2">
      {items.map((r) => (
        <li key={r.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
          <span>{r.reference ?? `Retour #${r.id}`}</span>
          <span className="text-muted-foreground">{r.statut ?? '—'}</span>
        </li>
      ))}
    </ul>
  )
}

// ── Onglet Documents de conformité (XPUR1) ──────────────────────────────────
function statutExpiration(dateExpiration) {
  if (!dateExpiration) return { label: 'Sans expiration', tone: 'muted' }
  const d = new Date(dateExpiration)
  const now = new Date()
  const joursRestants = Math.floor((d - now) / (1000 * 60 * 60 * 24))
  if (joursRestants < 0) return { label: 'Expiré', tone: 'destructive' }
  if (joursRestants <= 30) return { label: `Expire dans ${joursRestants} j`, tone: 'warning' }
  return { label: 'Valide', tone: 'success' }
}

function OngletDocuments({ fournisseurId }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.getDocumentsConformiteFournisseur(fournisseurId)
      .then((r) => { if (active) setItems(r.data?.results ?? r.data ?? []) })
      .catch((e) => { if (active) setError(frErr(e, 'Documents indisponibles.')) })
    return () => { active = false }
  }, [fournisseurId])

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  if (items.length === 0) return <Indisponible message="Aucun document de conformité." />

  const toneClass = {
    destructive: 'text-destructive',
    warning: 'text-amber-600',
    success: 'text-emerald-600',
    muted: 'text-muted-foreground',
  }

  return (
    <ul className="flex flex-col gap-2">
      {items.map((d) => {
        const st = statutExpiration(d.date_expiration)
        return (
          <li key={d.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
            <span>{d.type_document ?? `Document #${d.id}`}</span>
            <span className={toneClass[st.tone]}>{st.label} · {fmtDate(d.date_expiration)}</span>
          </li>
        )
      })}
    </ul>
  )
}

// ── Onglet Accords de prix actifs (FG318) ───────────────────────────────────
// Pas de listing global côté backend aujourd'hui (`prix_convenu_fournisseur`
// est une fonction PAR PRODUIT) : tant que l'agrégat 360 n'existe pas, cet
// onglet affiche ce que l'agrégat renvoie déjà (accords_prix — liste), sinon
// un état indisponible propre.
function OngletAccordsPrix({ fournisseurId }) {
  const [data, setData] = useState(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    let active = true
    stockApi.getFournisseur360(fournisseurId)
      .then((r) => { if (active) setData(r.data ?? null) })
      .catch(() => { if (active) setUnavailable(true) })
    return () => { active = false }
  }, [fournisseurId])

  if (unavailable) {
    return (
      <Indisponible message="Accords de prix indisponibles (agrégat non encore construit côté serveur)." />
    )
  }
  const accords = data?.accords_prix ?? []
  if (!data) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  if (accords.length === 0) return <Indisponible message="Aucun accord de prix actif." />

  return (
    <ul className="flex flex-col gap-2">
      {accords.map((a, i) => (
        <li key={a.contrat_id ?? i} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
          <span>Produit #{a.produit_id}</span>
          <span className="text-muted-foreground tabular-nums">
            {a.prix_convenu != null ? fmtMad(a.prix_convenu) : '—'}
          </span>
        </li>
      ))}
    </ul>
  )
}

export default function FournisseurFiche360({
  fournisseurId: fournisseurIdProp, fournisseurNom, fournisseurTelephone,
} = {}) {
  const params = useParams()
  const fournisseurId = fournisseurIdProp ?? params.id
  // ARC47 — gating via le hook partagé. Donnée d'achat INTERNE
  // (prix/solde/performance) : même garde que le reste de l'écran fournisseur —
  // responsable/admin ou droit explicite stock_voir. `hasFinePermissions`
  // (présence de codes ERP, PAS un droit) choisit la branche ; hooks
  // inconditionnels ; sémantique identique à l'origine.
  const hasFinePermissions = useSelector((s) => (s.auth.permissions || []).length > 0)
  const canViewViaPerm = useHasPermission('stock_voir')
  const canViewViaRole = useIsAdminOrResponsable()
  const canView = hasFinePermissions ? canViewViaPerm : canViewViaRole
  // VX108 — tap-to-call : la fiche n'affichait aucun téléphone.
  const tel = telHref(fournisseurTelephone)

  // VX159/VX250 — remonté depuis ResumePanel : RelationCounters (tête de
  // page) ET le panneau résumé consomment le MÊME fetch, jamais un doublon.
  const [resumeData, setResumeData] = useState(null)
  const [resumeUnavailable, setResumeUnavailable] = useState(false)
  const [resumeLoading, setResumeLoading] = useState(true)
  useEffect(() => {
    if (!fournisseurId || !canView) return undefined
    let active = true
    stockApi.getFournisseur360(fournisseurId)
      .then((r) => { if (active) setResumeData(r.data ?? null) })
      .catch(() => { if (active) setResumeUnavailable(true) })
      .finally(() => { if (active) setResumeLoading(false) })
    return () => { active = false }
  }, [fournisseurId, canView])

  const tabs = useMemo(() => ([
    { value: 'performance', label: 'Performance', icon: BarChart3, Comp: OngletPerformance },
    { value: 'bcf', label: 'Bons de commande', icon: PackageCheck, Comp: OngletBcf },
    { value: 'factures', label: 'Factures / solde', icon: Receipt, Comp: OngletFactures },
    { value: 'retours', label: 'Retours / avoirs', icon: Undo2, Comp: OngletRetours },
    { value: 'documents', label: 'Conformité', icon: ShieldCheck, Comp: OngletDocuments },
    { value: 'prix', label: 'Accords de prix', icon: Tags, Comp: OngletAccordsPrix },
  ]), [])

  if (!fournisseurId) {
    return (
      <div className="ui-root px-4 py-5 sm:px-5">
        <Indisponible message="Fournisseur introuvable." />
      </div>
    )
  }

  if (!canView) {
    return (
      <div className="ui-root px-4 py-5 sm:px-5">
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <FileWarning className="mr-1.5 inline size-4" aria-hidden="true" />
          Réservé aux rôles habilités (achats/stock).
        </div>
      </div>
    )
  }

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <header>
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Fiche fournisseur 360{fournisseurNom ? ` — ${fournisseurNom}` : ''}
        </h1>
        <p className="text-sm text-muted-foreground">
          <Wallet className="mr-1 inline size-3.5" aria-hidden="true" />
          Vue d&apos;ensemble achats — donnée interne, jamais client-facing.
        </p>
        {tel && (
          <p className="text-sm">
            <a href={tel} className="link-blue" title="Appeler">☎ {fournisseurTelephone}</a>
          </p>
        )}
        {/* VX159/VX250 — RelationCounters : réutilise `resumeData` (même fetch
            que ResumePanel ci-dessous, jamais un doublon). L'agrégat 360 est
            BLOCKED côté backend (voir note en tête de fichier) : ces
            compteurs restent simplement absents tant qu'il 404 (jamais un
            zéro trompeur). Pas de `to` : BonsCommandeFournisseur.jsx/
            FacturesFournisseur.jsx n'ont pas de filtre par fournisseur (hors
            périmètre de cette tâche) — jamais un lien qui MENT sur un
            pré-filtre qu'il n'applique pas. */}
        {resumeData && (
          <RelationCounters
            className="mt-2"
            counters={[
              { label: 'bons de commande ouverts', count: resumeData.bcf_ouverts ?? 0 },
              { label: 'factures ouvertes', count: resumeData.factures_ouvertes ?? 0 },
              { label: 'retours/avoirs', count: resumeData.nb_retours_avoirs ?? 0 },
            ]}
          />
        )}
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Vue d&apos;ensemble</CardTitle>
        </CardHeader>
        <CardContent>
          <ResumePanel data={resumeData} unavailable={resumeUnavailable} loading={resumeLoading} />
        </CardContent>
      </Card>

      <Tabs defaultValue="performance">
        <TabsList data-testid="f360-tabs-list">
          {tabs.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              <t.icon className="mr-1.5 size-4" aria-hidden="true" />
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabs.map((t) => (
          <TabsContent key={t.value} value={t.value} data-testid={`f360-tab-${t.value}`}>
            <t.Comp fournisseurId={fournisseurId} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
