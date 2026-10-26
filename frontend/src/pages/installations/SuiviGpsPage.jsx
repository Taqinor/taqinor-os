import { useCallback, useEffect, useMemo, useRef, useState, lazy, Suspense } from 'react'
import {
  MapPin, ShieldCheck, TriangleAlert, PlusCircle, Ban, Check, History,
  LogIn, LogOut,
} from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Button, Spinner,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDate } from '../../lib/format'
// VX186 — `MapView` (leaflet) en `lazy` : `escapeHtml` (fonction pure) reste
// importée normalement pour construire les popups.
import { escapeHtml } from '../../components/MapView'
import installationsApi from '../../api/installationsApi'
import fetchAllPages, { lireToutesLesPages } from '../../utils/fetchAllPages'
import crmApi from '../../api/crmApi'
import { useFilteredList } from '../../features/installations/chargementListe'
import ListShell from '../../features/installations/ListeEtat'

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

function formatDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return formatDate(value)
  return `${formatDate(value)} ${d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`
}

// ── Consentements ───────────────────────────────────────────────────────────
function ConsentementsTab({ techniciens }) {
  const { rows, loading, error, reload } = useFilteredList(installationsApi.getGpsConsentements)
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
        Le suivi de position n&apos;est possible qu&apos;avec un consentement
        actif ET l&apos;accord du technicien, donné une fois dans « Ma journée »
        après lecture de la notice (loi 09-08). Il est ensuite automatique
        pendant les interventions en route / sur site, avec un bandeau visible
        — jamais de suivi caché.
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
            {/* Revue chantier 26/10/2026 — l'accusé de réception de la notice
                vient du TECHNICIEN lui-même (« Ma journée ») ; tant qu'il
                manque, aucune position n'est relevée. */}
            {r.is_active && (r.accepte_le
              ? <Badge tone="success">Accord donné le {formatDateTime(r.accepte_le)}</Badge>
              : <Badge tone="warning">En attente d&apos;accord du technicien</Badge>)}
            <span className="text-sm text-muted-foreground">
              Notice {r.notice_version || 'v1'} · récépissé CNDP {r.recepisse_cndp || 'non encore déclaré'}
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
  const [noticeVersion, setNoticeVersion] = useState('v1')
  const [recepisse, setRecepisse] = useState('')
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
        notice_version: noticeVersion, recepisse_cndp: recepisse.trim(),
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
        <label className="form-label" htmlFor="gps-notice-version">
          Version de la notice d&apos;information
        </label>
        <select id="gps-notice-version" className="form-control" value={noticeVersion}
          onChange={(e) => setNoticeVersion(e.target.value)}>
          <option value="v1">v1 — notice en vigueur</option>
        </select>
        <label className="form-label" htmlFor="gps-recepisse">
          N° de récépissé de la déclaration CNDP (vide = « non encore déclaré »)
        </label>
        <input id="gps-recepisse" type="text" className="form-control" value={recepisse}
          maxLength={60} onChange={(e) => setRecepisse(e.target.value)} />
        <p className="text-sm text-muted-foreground">
          Le technicien devra ensuite lire la notice et donner son accord dans
          « Ma journée » : aucune position n&apos;est relevée avant.
        </p>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={confirme}
            onChange={(e) => setConfirme(e.target.checked)} />
          <span>
            Je confirme que ce technicien a été informé et a donné son accord
            explicite au suivi de sa position pendant ses interventions, et
            qu&apos;il peut en demander le retrait à un responsable.
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
// Revue chantier 26/10/2026 — la carte se rafraîchit toute seule (30 s), dit
// l'âge de chaque position (« il y a 3 min ») et n'affiche que les positions
// de moins de 15 min (filtre SERVEUR `max_age_min`, défaut 15) ; un
// technicien + une date dessinent le tracé de sa journée.
const RAFRAICHISSEMENT_MS = 30 * 1000
const AGE_MAX_MIN = 15

function ageRelatif(iso, maintenant) {
  if (!iso || !maintenant) return ''
  const minutes = Math.max(0, Math.round((maintenant - new Date(iso).getTime()) / 60000))
  if (minutes < 1) return "à l'instant"
  if (minutes < 60) return `il y a ${minutes} min`
  return `il y a ${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')}`
}

function popupPosition(p, maintenant) {
  // ERR26 — échapper chaque valeur serveur avant de l'injecter dans le HTML.
  return '<div style="margin-top:4px;color:#475569;font-size:0.8rem">'
    + `Relevé ${escapeHtml(formatDateTime(p.captured_at))}`
    + (maintenant ? ` (${escapeHtml(ageRelatif(p.captured_at, maintenant))})` : '')
    + (p.distance_site_km != null
      ? `<br/>${escapeHtml(String(p.distance_site_km))} km du site` : '')
    + (p.hors_perimetre ? '<br/>Hors périmètre' : '')
    + '</div>'
}

function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function CarteLiveTab({ techniciens }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // Horodatage du dernier chargement : sert à calculer l'âge (jamais
  // `Date.now()` pendant le rendu).
  const [maintenant, setMaintenant] = useState(null)
  const [technicien, setTechnicien] = useState('')
  const [jour, setJour] = useState(todayIso)
  const [trace, setTrace] = useState([])

  // Rafraîchissement silencieux : la carte n'est jamais démontée entre deux
  // relevés (pas de « chargement » toutes les 30 s).
  const dejaChargeRef = useRef(false)
  useEffect(() => {
    let vivant = true
    // carte-live/ n'est PAS paginé (pagination_class=None sur l'@action) :
    // lecture directe, jamais ?page= (garde check_frontend_query_params).
    const charger = () => installationsApi.getCarteLivePositions({ max_age_min: 15 })
      .then((r) => {
        const lignes = Array.isArray(r.data) ? r.data : (r.data?.results ?? [])
        if (!vivant) return
        dejaChargeRef.current = true
        setRows(lignes)
        setMaintenant(Date.now())
        setError(null)
      })
      // Un raté de rafraîchissement garde la dernière carte (pas d'écran
      // d'erreur toutes les 30 s sur un réseau capricieux).
      .catch(() => { if (vivant && !dejaChargeRef.current) setError('Chargement impossible.') })
      .finally(() => { if (vivant) setLoading(false) })
    charger()
    const id = setInterval(charger, RAFRAICHISSEMENT_MS)
    return () => { vivant = false; clearInterval(id) }
  }, [])

  useEffect(() => {
    if (!technicien || !jour) return undefined
    let vivant = true
    installationsApi.getPositionsTechniciens({ technicien, date: jour })
      .then((r) => {
        if (!vivant) return
        setTrace(Array.isArray(r?.data) ? r.data : (r?.data?.results ?? []))
      })
      .catch(() => { if (vivant) setTrace([]) })
    return () => { vivant = false }
  }, [technicien, jour])

  const located = useMemo(
    () => rows.filter((p) => p.lat != null && p.lng != null), [rows])
  const traceAffichee = useMemo(() => (technicien ? trace : []), [technicien, trace])

  const markers = useMemo(() => {
    const live = located.map((p) => ({
      id: p.id,
      lat: Number(p.lat),
      lng: Number(p.lng),
      label: `${p.technicien_nom || `#${p.technicien}`} · ${ageRelatif(p.captured_at, maintenant)}`,
      color: p.hors_perimetre ? MARKER_HORS : MARKER_OK,
      popupHtml: popupPosition(p, maintenant),
    }))
    if (traceAffichee.length === 0) return live
    const premier = traceAffichee[0]
    const dernier = traceAffichee[traceAffichee.length - 1]
    return live.concat([
      { id: `debut-${premier.id}`, lat: Number(premier.lat), lng: Number(premier.lng),
        label: `Début ${formatDateTime(premier.captured_at)}`, color: '#2563eb',
        popupHtml: popupPosition(premier, null) },
      { id: `fin-${dernier.id}`, lat: Number(dernier.lat), lng: Number(dernier.lng),
        label: `Dernier relevé ${formatDateTime(dernier.captured_at)}`, color: '#2563eb',
        popupHtml: popupPosition(dernier, null) },
    ])
  }, [located, maintenant, traceAffichee])

  const path = useMemo(
    () => traceAffichee.map((p) => [Number(p.lat), Number(p.lng)]), [traceAffichee])

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Dernière position par technicien, rafraîchie toutes les 30 s
        ({located.length} affiché(s)). Les positions de plus de {AGE_MAX_MIN} min
        sont masquées : un technicien hors intervention n&apos;est pas suivi.
        Marqueur rouge = hors du périmètre du site de l&apos;intervention.
      </p>
      <div className="flex flex-wrap gap-3">
        <select value={technicien} onChange={(e) => setTechnicien(e.target.value)}
          aria-label="Tracé du technicien"
          className="h-9 rounded-md border border-border bg-card px-3 text-sm">
          <option value="">— Tracé d&apos;un technicien —</option>
          {techniciens.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
        </select>
        <input type="date" value={jour} onChange={(e) => setJour(e.target.value)}
          aria-label="Jour du tracé"
          className="h-9 rounded-md border border-border bg-card px-3 text-sm" />
        {technicien && (
          <span className="self-center text-sm text-muted-foreground" data-testid="trace-compte">
            {traceAffichee.length} relevé(s) ce jour-là
          </span>
        )}
      </div>
      {located.length > 0 && (
        <ul className="flex flex-wrap gap-2 text-sm" data-testid="carte-live-ages">
          {located.map((p) => (
            <li key={p.id}>
              <Badge tone={p.hors_perimetre ? 'danger' : 'success'}>
                {p.technicien_nom || `#${p.technicien}`} · {ageRelatif(p.captured_at, maintenant)}
              </Badge>
            </li>
          ))}
        </ul>
      )}
      <ListShell loading={loading} error={error} icon={MapPin}
        empty={`Aucune position de moins de ${AGE_MAX_MIN} min`}>
        {(located.length > 0 || traceAffichee.length > 0) && (
          <Suspense fallback={<p className="page-loading"><Spinner /> Chargement de la carte…</p>}>
            <MapView markers={markers} path={path.length > 1 ? path : null} />
          </Suspense>
        )}
      </ListShell>
    </div>
  )
}

// ── Alertes de géofence ─────────────────────────────────────────────────────
// Filtre serveur `type_franchissement=sortie` (NTMOB9/GeofenceAlertViewSet) :
// seules les SORTIES sont actionnables (« À traiter » / Acquitter) — les
// ENTRÉES sont informatives et vivent dans l'onglet Historique de présence,
// jamais dans cette file d'attente.
function AlertesTab() {
  const { rows, loading, error, reload } = useFilteredList(
    (p) => installationsApi.getGeofenceAlertes({ ...p, type_franchissement: 'sortie' }),
  )

  const [filtre, setFiltre] = useState('ouvertes')

  const acquitter = async (id) => {
    await installationsApi.acquitterGeofenceAlerte(id).catch(() => {})
    reload()
  }

  // Revue chantier 26/10/2026 — ouvertes d'abord (une seule par
  // intervention jusqu'à une ré-entrée), acquittées consultables.
  const visibles = rows.filter((a) => (
    filtre === 'toutes' ? true : filtre === 'ouvertes' ? !a.acquittee : a.acquittee))
  const nbOuvertes = rows.filter((a) => !a.acquittee).length

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Une alerte est levée quand, pendant une intervention SUR SITE, la
        position du technicien sort du rayon du chantier (une seule alerte
        ouverte jusqu&apos;à son retour ; le responsable est notifié).
      </p>
      <select value={filtre} onChange={(e) => setFiltre(e.target.value)}
        aria-label="Filtre des alertes"
        className="h-9 w-fit rounded-md border border-border bg-card px-3 text-sm">
        <option value="ouvertes">Ouvertes ({nbOuvertes})</option>
        <option value="acquittees">Acquittées</option>
        <option value="toutes">Toutes</option>
      </select>
      <ListShell loading={loading} error={error} icon={TriangleAlert}
        empty={filtre === 'ouvertes' ? 'Aucune alerte ouverte' : 'Aucune alerte de géofence'}>
        {visibles.length > 0 && visibles.map((a) => (
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
            <a className="text-sm text-primary underline"
              href={`/interventions?id=${a.intervention}`}>
              Voir l&apos;intervention #{a.intervention}
            </a>
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

// ── Historique de présence (NTMOB9) ─────────────────────────────────────────
// Entrée/sortie de périmètre PAR CHANTIER : `GeofenceAlert.type_franchissement`
// (NTMOB9) est un champ RÉEL journalisé côté serveur à chaque franchissement
// détecté par `gps_tracking_service.enregistrer_position` — jamais une
// dérivation côté écran à partir des positions brutes. Le serveur filtre déjà
// par `chantier` et `type_franchissement` (`GeofenceAlertViewSet.get_queryset`) ;
// l'écran ne fait que transmettre les filtres choisis. « Chantier » =
// `installations.Installation` (`chantiers/`), déjà le sens du mot dans tout
// le reste de l'app (`InterventionSerializer.installation_reference`).
const TYPE_FRANCHISSEMENT = [
  { value: 'tous', label: 'Tous types' },
  { value: 'entree', label: 'Entrées' },
  { value: 'sortie', label: 'Sorties' },
]

// Revue chantier 26/10/2026 — temps passé sur site, par intervention du jour,
// calculé SERVEUR (`interventions/<id>/presence/`, contrat
// intervention_presence.json) ; la source du début est toujours dite.
const SOURCE_DEBUT = {
  positions: 'positions GPS',
  alertes: 'franchissements (positions purgées)',
  pointage: 'pointage manuel',
}
const PRESENCE_MAX_INTERVENTIONS = 50

function heure(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

function dureeLisible(minutes) {
  if (minutes == null) return '—'
  const h = Math.floor(minutes / 60)
  return h ? `${h} h ${String(minutes % 60).padStart(2, '0')}` : `${minutes} min`
}

function PresenceDuJour() {
  const [jour, setJour] = useState(todayIso)
  const [lignes, setLignes] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!jour) return undefined
    let vivant = true
    lireToutesLesPages((p) => installationsApi.getInterventions({ date_prevue: jour, ...p }))
      .then((lignes) => {
        const intervs = lignes.slice(0, PRESENCE_MAX_INTERVENTIONS)
        return Promise.all(intervs.map((iv) => installationsApi.getPresenceIntervention(iv.id)
          .then((p) => ({ interv: iv, presence: p.data }))
          .catch(() => ({ interv: iv, presence: null }))))
      })
      .then((res) => { if (vivant) { setLignes(res); setError(null) } })
      .catch(() => { if (vivant) setError('Chargement impossible.') })
    return () => { vivant = false }
  }, [jour])

  return (
    <div className="flex flex-col gap-2" data-testid="presence-du-jour">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-semibold">Temps sur site du jour</h3>
        <input type="date" value={jour} onChange={(e) => setJour(e.target.value)}
          aria-label="Jour de présence"
          className="h-9 rounded-md border border-border bg-card px-3 text-sm" />
      </div>
      <ListShell loading={lignes === null && !error} error={error} icon={History}
        empty="Aucune intervention ce jour-là">
        {lignes?.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="p-2">Intervention</th>
                  <th className="p-2">Technicien</th>
                  <th className="p-2">Arrivée</th>
                  <th className="p-2" title="Dernière position relevée dans le rayon du chantier">Dernier relevé sur site</th>
                  <th className="p-2">Sur site</th>
                  <th className="p-2">Source</th>
                </tr>
              </thead>
              <tbody>
                {lignes.map(({ interv, presence }) => (
                  <tr key={interv.id} className="border-t border-border"
                    data-testid={`presence-interv-${interv.id}`}>
                    <td className="p-2">{interv.installation_reference || `#${interv.id}`}</td>
                    <td className="p-2">{interv.technicien_nom || '—'}</td>
                    <td className="p-2">{heure(presence?.premiere_entree)}</td>
                    <td className="p-2">{heure(presence?.derniere_sortie)}</td>
                    <td className="p-2">{dureeLisible(presence?.duree_sur_site_min)}</td>
                    <td className="p-2 text-muted-foreground">
                      {presence ? (SOURCE_DEBUT[presence.source_debut] || 'aucun relevé') : 'indisponible'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ListShell>
    </div>
  )
}

function HistoriquePresenceTab() {
  const [chantiers, setChantiers] = useState([])
  const [chantierId, setChantierId] = useState('')
  const [typeFiltre, setTypeFiltre] = useState('tous')
  const [evenements, setEvenements] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchAllPages((page, { page_size: pageSize } = {}) =>
      installationsApi.getInstallations({ page, page_size: pageSize }).then((r) => r.data))
      .catch(() => [])
      .then((rows) => setChantiers(Array.isArray(rows) ? rows : (rows?.results ?? [])))
  }, [])

  // Enveloppé dans `useCallback` (même patron que `useFilteredList` ci-dessus dans
  // ce fichier) : l'effet se contente d'APPELER la fonction, aucun
  // `setState` synchrone dans le corps de l'effet lui-même.
  const chargerEvenements = useCallback(() => {
    if (!chantierId) return
    setLoading(true)
    setError(null)
    installationsApi.getGeofenceAlertes({
      chantier: chantierId,
      page_size: 200,
      ...(typeFiltre !== 'tous' ? { type_franchissement: typeFiltre } : {}),
    })
      .then((r) => setEvenements(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement impossible.'))
      .finally(() => setLoading(false))
  }, [chantierId, typeFiltre])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au chantier/type choisi (même patron que `useFilteredList` ci-dessus) (D-ENF22)
  useEffect(() => { chargerEvenements() }, [chargerEvenements])

  return (
    <div className="flex flex-col gap-3">
      <PresenceDuJour />
      <p className="text-sm text-muted-foreground">
        Entrées/sorties de périmètre par chantier, journalisées par le serveur
        à chaque franchissement détecté (NTMOB9).
      </p>
      <div className="flex flex-wrap gap-3">
        <select
          value={chantierId}
          onChange={(e) => setChantierId(e.target.value)}
          aria-label="Chantier"
          className="h-9 rounded-md border border-border bg-card px-3 text-sm"
        >
          <option value="">— Choisir un chantier —</option>
          {chantiers.map((c) => (
            <option key={c.id} value={c.id}>{c.reference || `Chantier #${c.id}`}</option>
          ))}
        </select>
        <select
          value={typeFiltre}
          onChange={(e) => setTypeFiltre(e.target.value)}
          aria-label="Type de franchissement"
          className="h-9 rounded-md border border-border bg-card px-3 text-sm"
        >
          {TYPE_FRANCHISSEMENT.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>
      <ListShell loading={loading} error={error} icon={History}
        empty={chantierId ? 'Aucun évènement pour ce chantier' : 'Choisissez un chantier'}>
        {!!chantierId && evenements.length > 0 && evenements.map((e) => (
          <div key={e.id} data-testid={`presence-${e.id}-${e.type_franchissement}`}
            className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3">
            <span className="font-medium text-sm">{e.technicien_nom || `#${e.technicien}`}</span>
            <Badge tone={e.type_franchissement === 'entree' ? 'success' : 'neutral'}>
              {e.type_franchissement === 'entree'
                ? <><LogIn className="size-3.5" aria-hidden="true" /> Entrée</>
                : <><LogOut className="size-3.5" aria-hidden="true" /> Sortie</>}
            </Badge>
            <span className="text-sm text-muted-foreground">{formatDateTime(e.created_at)}</span>
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
          <TabsTrigger value="historique">Historique de présence</TabsTrigger>
        </TabsList>
        <TabsContent value="consentements">
          <ConsentementsTab techniciens={techniciens} />
        </TabsContent>
        <TabsContent value="carte">
          <CarteLiveTab techniciens={techniciens} />
        </TabsContent>
        <TabsContent value="alertes">
          <AlertesTab />
        </TabsContent>
        <TabsContent value="historique">
          <HistoriquePresenceTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
