import { useCallback, useEffect, useMemo, useState, lazy, Suspense } from 'react'
import { MapPin, ShieldCheck, TriangleAlert, PlusCircle, Ban, Check } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Button, Spinner, EmptyState,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDate } from '../../lib/format'
// VX186 — `MapView` (leaflet) en `lazy` : `escapeHtml` (fonction pure) reste
// importée normalement pour construire les popups.
import { escapeHtml } from '../../components/MapView'
import installationsApi from '../../api/installationsApi'
import crmApi from '../../api/crmApi'

/* ============================================================================
   WIR113 — Suivi GPS terrain (XFSM23). `/planification/suivi-gps`.
   ----------------------------------------------------------------------------
   DÉCISION DE PÉRIMÈTRE (2026-07-18, tracée dans `docs/module-map.md`) :
   WEB-FIRST. Il n'existe aucune application mobile séparée dans ce dépôt — le
   terrain travaille déjà depuis ce frontend responsive (« Ma journée », le
   check-in F6 utilisant l'API `geolocation` du navigateur). Les 3 familles
   d'endpoints XFSM23 (`gps-consentements/`, `positions-techniciens/`,
   `geofence-alertes/`) n'avaient donc aucun écran : c'est cette page.

   Règle non négociable portée par l'écran : le consentement est EXPLICITE et
   RÉVOCABLE. Aucun suivi silencieux — le serveur refuse (403) tout `ping` de
   position sans consentement actif, et cet écran est l'endroit où le
   consentement se crée, se lit et se révoque.
   ========================================================================== */

const MapView = lazy(() => import('../../components/MapView'))

// Marqueur vert = dans le périmètre du site, rouge = hors périmètre.
const MARKER_OK = '#16a34a'
const MARKER_HORS = '#dc2626'

function useList(fetcher) {
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
        const p = res?.data
        setRows(Array.isArray(p) ? p : (p?.results ?? []))
      })
      .catch((err) => { if (!cancelled) setError(err?.response?.data?.detail || 'Chargement impossible.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])
  return { rows, loading, error, reload: load }
}

function ListShell({ loading, error, empty, icon, children }) {
  if (loading) return (
    <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (error) return <EmptyState title="Impossible de charger" description={error} className="py-6" />
  // `children` vaut `false` quand la liste est vide (`rows.length > 0 && …`) :
  // on teste la valeur, pas seulement null/undefined, sinon l'état vide ne
  // s'afficherait jamais.
  if (!children) return <EmptyState icon={icon} title={empty} className="py-6" />
  return children
}

function formatDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return formatDate(value)
  return `${formatDate(value)} ${d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`
}

// ── Consentements ───────────────────────────────────────────────────────────
function ConsentementsTab({ techniciens }) {
  const { rows, loading, error, reload } = useList(installationsApi.getGpsConsentements)
  const [showCreate, setShowCreate] = useState(false)

  const revoquer = async (id) => {
    const reason = window.prompt('Motif de la révocation (optionnel) :')
    if (reason === null) return
    await installationsApi.revoquerGpsConsentement(id, reason).catch(() => {})
    reload()
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Le suivi de position n'est possible qu'avec un consentement actif du
        technicien. Sans consentement, le serveur refuse toute remontée de
        position — jamais de suivi silencieux.
      </p>
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Enregistrer un consentement
        </Button>
      </div>
      <ListShell loading={loading} error={error} icon={ShieldCheck}
        empty="Aucun consentement enregistré">
        {rows.length > 0 && rows.map((r) => (
          <div key={r.id}
            className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3"
            data-testid={`consentement-${r.id}`}>
            <span className="font-medium text-sm">{r.technicien_nom || `#${r.technicien}`}</span>
            <Badge tone={r.is_active ? 'success' : 'neutral'}>
              {r.is_active ? 'Actif' : 'Révoqué'}
            </Badge>
            <span className="text-sm text-muted-foreground">
              Recueilli le {formatDateTime(r.consent_recorded_at)}
            </span>
            {r.consent_ref && <Badge tone="info">{r.consent_ref}</Badge>}
            {!r.is_active && r.revoked_reason && (
              <span className="text-sm text-muted-foreground">Motif : {r.revoked_reason}</span>
            )}
            {r.is_active && (
              <Button size="sm" variant="outline" className="ml-auto"
                onClick={() => revoquer(r.id)}>
                <Ban className="size-4" aria-hidden="true" /> Révoquer
              </Button>
            )}
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <ConsentementDialog techniciens={techniciens}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

function ConsentementDialog({ techniciens, onClose, onCreated }) {
  const [technicien, setTechnicien] = useState('')
  const [consentRef, setConsentRef] = useState('')
  const [confirme, setConfirme] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const create = async () => {
    if (!technicien) { setError('Technicien requis.'); return }
    if (!confirme) {
      setError('Confirmez que le technicien a donné son accord explicite.')
      return
    }
    setBusy(true); setError(null)
    try {
      await installationsApi.createGpsConsentement({
        technicien: Number(technicien), consent_ref: consentRef || '',
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Enregistrement impossible.')
    } finally { setBusy(false) }
  }

  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Consentement de suivi GPS</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="gps-tech">Technicien</label>
        <select id="gps-tech" className="form-control" value={technicien}
          onChange={(e) => setTechnicien(e.target.value)} autoFocus>
          <option value="">— Choisir —</option>
          {techniciens.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
        </select>
        <label className="form-label" htmlFor="gps-ref">
          Référence du consentement signé (optionnel)
        </label>
        <input id="gps-ref" type="text" className="form-control" value={consentRef}
          onChange={(e) => setConsentRef(e.target.value)} />
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={confirme}
            onChange={(e) => setConfirme(e.target.checked)} />
          <span>
            Je confirme que ce technicien a donné son accord explicite au suivi
            de sa position pendant ses interventions, et qu'il peut le retirer à
            tout moment.
          </span>
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Enregistrement…' : 'Enregistrer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

// ── Carte live ──────────────────────────────────────────────────────────────
function CarteLiveTab() {
  const { rows, loading, error } = useList(installationsApi.getCarteLivePositions)

  const located = useMemo(
    () => rows.filter((p) => p.lat != null && p.lng != null), [rows])

  const markers = useMemo(() => located.map((p) => ({
    id: p.id,
    lat: Number(p.lat),
    lng: Number(p.lng),
    label: p.technicien_nom || `#${p.technicien}`,
    color: p.hors_perimetre ? MARKER_HORS : MARKER_OK,
    // ERR26 — échapper chaque valeur serveur avant de l'injecter dans le HTML.
    popupHtml: '<div style="margin-top:4px;color:#475569;font-size:0.8rem">'
      + `Relevé ${escapeHtml(formatDateTime(p.captured_at))}`
      + (p.distance_site_km != null
        ? `<br/>${escapeHtml(String(p.distance_site_km))} km du site` : '')
      + (p.hors_perimetre ? '<br/>Hors périmètre' : '')
      + '</div>',
  })), [located])

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Dernière position connue par technicien consentant ({located.length} affiché(s)).
        Marqueur rouge = hors du périmètre du site de l'intervention.
      </p>
      <ListShell loading={loading} error={error} icon={MapPin}
        empty="Aucune position remontée">
        {located.length > 0 && (
          <Suspense fallback={<p className="page-loading"><Spinner /> Chargement de la carte…</p>}>
            <MapView markers={markers} />
          </Suspense>
        )}
      </ListShell>
    </div>
  )
}

// ── Alertes de géofence ─────────────────────────────────────────────────────
function AlertesTab() {
  const { rows, loading, error, reload } = useList(installationsApi.getGeofenceAlertes)

  const acquitter = async (id) => {
    await installationsApi.acquitterGeofenceAlerte(id).catch(() => {})
    reload()
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Une alerte est levée quand la position remontée s'éloigne du site de
        l'intervention au-delà du rayon attendu.
      </p>
      <ListShell loading={loading} error={error} icon={TriangleAlert}
        empty="Aucune alerte de géofence">
        {rows.length > 0 && rows.map((a) => (
          <div key={a.id}
            className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3"
            data-testid={`alerte-${a.id}`}>
            <span className="font-medium text-sm">{a.technicien_nom || `#${a.technicien}`}</span>
            <Badge tone={a.acquittee ? 'neutral' : 'danger'}>
              {a.acquittee ? 'Acquittée' : 'À traiter'}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {a.distance_site_km} km (rayon attendu {a.rayon_attendu_km} km)
            </span>
            <span className="text-sm text-muted-foreground">
              {formatDateTime(a.created_at)}
            </span>
            {!a.acquittee && (
              <Button size="sm" variant="outline" className="ml-auto"
                onClick={() => acquitter(a.id)}>
                <Check className="size-4" aria-hidden="true" /> Acquitter
              </Button>
            )}
          </div>
        ))}
      </ListShell>
    </div>
  )
}

export default function SuiviGpsPage() {
  const [techniciens, setTechniciens] = useState([])

  useEffect(() => {
    let alive = true
    crmApi.getAssignableUsers()
      .catch(() => ({ data: [] }))
      .then((u) => {
        if (!alive) return
        setTechniciens(u.data?.results ?? u.data ?? [])
      })
    return () => { alive = false }
  }, [])

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Suivi GPS terrain"
        subtitle="Consentement explicite des techniciens, carte des dernières positions et alertes de géofence."
      />
      <Tabs defaultValue="consentements" className="flex flex-col gap-4">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="consentements">Consentements</TabsTrigger>
          <TabsTrigger value="carte">Carte live</TabsTrigger>
          <TabsTrigger value="alertes">Alertes géofence</TabsTrigger>
        </TabsList>
        <TabsContent value="consentements">
          <ConsentementsTab techniciens={techniciens} />
        </TabsContent>
        <TabsContent value="carte">
          <CarteLiveTab />
        </TabsContent>
        <TabsContent value="alertes">
          <AlertesTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
