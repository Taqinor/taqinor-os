// F22 — « Ma journée » : l'écran unique du technicien sur le terrain. Affiche
// les interventions du jour qui lui sont assignées, dans l'ordre, chacune
// s'ouvrant directement sur son flux préparation → capture sur site →
// complétion (les mêmes panneaux F5–F19 que le volet détail). Pensé
// thumb-reachable et 100 % en français. La portée « seulement les miennes » est
// garantie côté serveur par le rôle Technicien (scope_queryset) ; aucun prix
// d'achat ni marge n'est exposé.
//
// VX42 — Terrain un-tap : deux boutons directs (téléphone, navigation) sur
// chaque carte — l'action la plus fréquente d'un technicien garé était à
// 3 taps (ouvrir la fiche → onglet Trajet → bouton). Rail d'onglets
// icône+libellé (au lieu des 9 icônes seules) avec bandeau « Prochaine
// action ». FAB « Photo rapide » posé au pouce.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  CalendarDays, MapPin, ChevronRight, ClipboardList, Navigation, Camera,
  Tag, ListChecks, Mic, ShieldCheck, Wrench, AlertOctagon, CloudRain, Phone,
  PenLine,
} from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Spinner, EmptyState, Badge, StatusPill, StatusAccentCard,
  Sheet, SheetContent, SheetHeader, SheetTitle,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  toast, FloatingActionButton,
} from '../../ui'
import { useIsMobile } from '../../ui/ResponsiveDialog'
import { usePullToRefresh } from '../../ui/usePullToRefresh'
import {
  PreparationPanel, TrajetPanel, PhotosPanel,
} from '../../features/installations/InterventionFieldExecution'
import {
  SerialsPanel, ConsommationPanel, MemosPanel, ReservesPanel,
  ToolReturnPanel, SafetyPanel, CompteRenduButton, CodePanel,
} from '../../features/installations/InterventionCapturePanels'
import { SignatureClientPanel } from '../../features/installations/SignatureClientPanel'
import {
  interventionStatusLabel, INTERVENTION_TYPES,
  INTERVENTION_STATUSES, INTERVENTION_STATUS_LABELS,
} from '../../features/installations/statuses'
import { formatDate } from '../../lib/format'

// VX105 — clés de persistance de session (survit à un backgrounding suivi d'un
// rechargement — appel entrant en chantier) : fiche ouverte + onglet visité.
const SS_ACTIVE = 'mj.activeId'
const SS_TAB = 'mj.tab'

const TYPE_LABELS = Object.fromEntries(
  INTERVENTION_TYPES.map((t) => [t.value, t.label]))
const typeLabel = (k) => TYPE_LABELS[k] ?? k ?? '—'

// VX149 — accent par TYPE d'intervention (pose/raccordement/mise en
// service/contrôle/dépannage) — un axe différent du statut (déjà porté par
// StatusPill) : chaque ligne se différencie visuellement au premier coup
// d'œil, même style d'accent que le kanban (`ui/StatusAccentCard`).
const TYPE_ACCENT = {
  pose: '#3b82f6',
  raccordement: '#a855f7',
  mise_en_service: '#16a34a',
  controle: '#0ea5e9',
  depannage: '#f59e0b',
}
const typeAccent = (k) => TYPE_ACCENT[k] ?? '#64748b'

function todayISO() {
  const d = new Date()
  const tz = d.getTimezoneOffset() * 60000
  return new Date(d - tz).toISOString().slice(0, 10)
}

// VX42 — Lien tel: nettoyé (chiffres et + initial), même convention que
// LeadCard.jsx/ListView.jsx.
function telHref(phone) {
  const s = String(phone ?? '').trim()
  if (!s) return null
  const cleaned = s.replace(/[^\d+]/g, '')
  return cleaned ? `tel:${cleaned}` : null
}

// VX42 — Navigation maps UNIVERSELLE : geo: sur Android (ouvre le choix
// d'appli installée), repli Google Maps web partout ailleurs (iOS Safari, etc.
// — aucune dépendance à une appli installée). Priorité aux coordonnées GPS du
// chantier (plus précises), repli sur la ville.
function mapsHref(interv) {
  const lat = interv.gps_lat, lng = interv.gps_lng
  if (lat != null && lng != null) {
    return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`
  }
  if (interv.site_ville) {
    return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(interv.site_ville)}`
  }
  return null
}

export default function MaJourneePage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [active, setActive] = useState(null)
  // VX42 — le FAB « Photo rapide » ouvre la fiche directement sur l'onglet
  // Photos ; sinon la fiche s'ouvre normalement sur la préparation.
  const [initialTab, setInitialTab] = useState('prep')
  const today = useMemo(() => todayISO(), [])
  // VX105 — ne restaure la fiche persistée qu'UNE fois (pas à chaque
  // pull-to-refresh, sinon la fiche se rouvrirait après fermeture).
  const restoredRef = useRef(false)

  // VX105 — ouvrir/fermer la fiche en persistant l'état de session.
  const openInterv = useCallback((interv, tab = 'prep') => {
    setInitialTab(tab); setActive(interv)
    try {
      sessionStorage.setItem(SS_ACTIVE, String(interv.id))
      sessionStorage.setItem(SS_TAB, tab)
    } catch { /* stockage indisponible */ }
  }, [])
  const closeInterv = useCallback(() => {
    setActive(null)
    try { sessionStorage.removeItem(SS_ACTIVE) } catch { /* */ }
  }, [])

  // VX88 — « Ma tournée » (FG73) : les interventions du jour du technicien
  // ordonnées géographiquement (plus proche voisin), déjà scopées à lui côté
  // serveur, avec un lien Itinéraire (`itineraire_url`) prêt par arrêt. On
  // remplace `getInterventions({date_prevue})` (ordre priorité-puis-insertion,
  // sans sens géographique) par cet endpoint déjà construit et testé.
  const load = useCallback(() => installationsApi
    .getMaTournee(today)
    .then((r) => {
      // Réponse : { date, stops: [ {...intervention, itineraire_url} ] }.
      const stops = r.data?.stops ?? []
      setRows(stops)
      // VX105 — restauration one-shot de la fiche/onglet persistés (au retour
      // après un backgrounding qui a rechargé la page).
      if (!restoredRef.current) {
        restoredRef.current = true
        try {
          const savedId = sessionStorage.getItem(SS_ACTIVE)
          if (savedId) {
            const found = stops.find((s) => String(s.id) === savedId)
            if (found) {
              setInitialTab(sessionStorage.getItem(SS_TAB) || 'prep')
              setActive(found)
            }
          }
        } catch { /* stockage indisponible */ }
      }
    })
    .catch(() => setRows([]))
    .finally(() => setLoading(false)), [today])
  useEffect(() => { load() }, [load])

  // VX43 — sheet terrain alignée sur le bottom-sheet mobile (au lieu de
  // side="right", un tiroir latéral peu naturel au pouce sur un écran de
  // technicien) ; desktop garde le tiroir latéral existant.
  const isMobile = useIsMobile()

  // VX43 — pull-to-refresh maison : `overscroll-behavior: contain` a coupé le
  // rubber-band natif sans rien remettre à sa place. Relance le fetch existant
  // (`load`), sans changer son contrat.
  const { containerProps, pullDistance, refreshing } = usePullToRefresh(load)

  return (
    <div
      className="mx-auto flex max-w-2xl flex-col gap-3 overflow-y-auto p-3 sm:p-4"
      {...containerProps}
    >
      {(pullDistance > 0 || refreshing) && (
        <div
          className="flex items-center justify-center gap-2 text-xs text-muted-foreground"
          style={{ height: `${Math.max(pullDistance, refreshing ? 32 : 0)}px`, overflow: 'hidden', transition: refreshing ? 'height 150ms ease' : 'none' }}
          role="status"
        >
          {refreshing ? <Spinner className="size-4" /> : null}
          {refreshing ? 'Actualisation…' : 'Tirer pour actualiser'}
        </div>
      )}
      <header className="flex items-center gap-2">
        <CalendarDays className="size-5 text-primary" aria-hidden="true" />
        <h1 className="text-lg font-semibold">Ma journée</h1>
        <span className="text-sm text-muted-foreground">{formatDate(today, { long: true })}</span>
      </header>

      {loading ? (
        <p className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Chargement de vos interventions…
        </p>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="Aucune intervention aujourd'hui"
          description="Vos interventions du jour apparaîtront ici." />
      ) : (
        <ol className="flex flex-col gap-2">
          {rows.map((interv, i) => {
            const tel = telHref(interv.contact_site_telephone)
            // VX88 — un seul lien maps : l'itinéraire optimisé de « Ma tournée »
            // (`itineraire_url`, GPS du chantier) prime ; repli sur mapsHref
            // (GPS/ville) quand la tournée n'a pas pu le calculer.
            const maps = interv.itineraire_url || mapsHref(interv)
            return (
              <li key={interv.id}>
                <StatusAccentCard
                  variant="compact"
                  accent={typeAccent(interv.type_intervention)}
                  className="overflow-hidden !p-0">
                  <button type="button" onClick={() => openInterv(interv, 'prep')}
                    className="flex w-full items-center gap-3 p-3 text-left active:bg-accent">
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium">{interv.client_nom || interv.installation_reference || '—'}</span>
                        <StatusPill status={interv.statut} label={interventionStatusLabel(interv.statut)} dot={false} />
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12px] text-muted-foreground">
                        <span>{typeLabel(interv.type_intervention)}</span>
                        {interv.site_ville && (
                          <span className="flex items-center gap-1"><MapPin className="size-3.5" aria-hidden="true" />{interv.site_ville}</span>)}
                        {interv.photos_obligatoires_manquantes > 0 && (
                          <span className="flex items-center gap-1 text-destructive">
                            <AlertOctagon className="size-3.5" aria-hidden="true" />
                            {interv.photos_obligatoires_manquantes} photo(s) requise(s)
                          </span>)}
                        {/* XFSM21 — risque météo J+3 (pluie/vent) sur une pose planifiée. */}
                        {interv.meteo_risque && (
                          <span className="flex items-center gap-1 text-warning">
                            <CloudRain className="size-3.5" aria-hidden="true" />
                            Météo à risque
                          </span>)}
                      </div>
                    </div>
                    <ChevronRight className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                  </button>
                  {/* VX42 — un-tap terrain : appeler / naviguer SANS ouvrir la
                      fiche. Masqués individuellement si la donnée manque
                      (aucun numéro de contact site, ni GPS/ville). */}
                  {(tel || maps) && (
                    <div className="flex border-t border-border">
                      {tel && (
                        <a href={tel}
                          className="flex min-h-11 flex-1 items-center justify-center gap-1.5 py-2.5 text-[13px] font-medium text-primary active:bg-accent"
                          aria-label={`Appeler le contact sur site pour ${interv.client_nom || interv.installation_reference || 'cette intervention'}`}>
                          <Phone className="size-4" aria-hidden="true" /> Appeler
                        </a>
                      )}
                      {tel && maps && <span className="my-2 w-px bg-border" aria-hidden="true" />}
                      {maps && (
                        <a href={maps} target="_blank" rel="noopener noreferrer"
                          className="flex min-h-11 flex-1 items-center justify-center gap-1.5 py-2.5 text-[13px] font-medium text-primary active:bg-accent"
                          aria-label={`Ouvrir l'itinéraire vers ${interv.site_ville || 'le chantier'}`}>
                          <Navigation className="size-4" aria-hidden="true" /> Itinéraire
                        </a>
                      )}
                    </div>
                  )}
                </StatusAccentCard>
              </li>
            )
          })}
        </ol>
      )}

      {/* ERR103 — dériver la fiche de l'état VIVANT (rows), pas du snapshot
          capturé au tap : les changements de statut/photos faits dans la fiche
          se reflètent sans avoir à la rouvrir. */}
      <InterventionFlowSheet
        key={active ? `${active.id}:${initialTab}` : 'none'}
        interv={active ? (rows.find((r) => r.id === active.id) ?? active) : null}
        initialTab={initialTab}
        isMobile={isMobile}
        onClose={closeInterv}
        onChanged={load} />

      {/* VX42 — FAB « Photo rapide » : ouvre directement la première
          intervention du jour sur l'onglet Photos (le pouce vit dans le
          tiers bas de l'écran). Masqué s'il n'y a aucune intervention. */}
      {rows.length > 0 && (
        <FloatingActionButton
          label="Photo rapide"
          icon={<Camera className="size-5" aria-hidden="true" />}
          onClick={() => openInterv(rows[0], 'photos')} />
      )}
    </div>
  )
}

// VX42 — rail d'onglets : icône + libellé court (au lieu de l'icône seule),
// défilable horizontalement plutôt que replié en grille serrée.
const FLOW_TABS = [
  { value: 'prep', label: 'Prépa', Icon: ClipboardList },
  { value: 'trajet', label: 'Trajet', Icon: Navigation },
  { value: 'safety', label: 'Sécurité', Icon: ShieldCheck },
  { value: 'photos', label: 'Photos', Icon: Camera },
  { value: 'serials', label: 'N° série', Icon: Tag },
  { value: 'conso', label: 'Conso', Icon: ListChecks },
  { value: 'memos', label: 'Mémos', Icon: Mic },
  { value: 'reserves', label: 'Réserves', Icon: AlertOctagon },
  { value: 'signature', label: 'Signature', Icon: PenLine },
  { value: 'outils', label: 'Outils', Icon: Wrench },
]

// VX42 — bandeau « Prochaine action » (pattern ch6-next-action de
// ChantierGateTimeline) : une phrase FR qui dit au technicien où aller
// ensuite dans le flux, dérivée du statut PROPRE de l'intervention (F3).
const NEXT_ACTION = {
  a_preparer: { tab: 'prep', text: 'terminer la liste de préparation.' },
  prete: { tab: 'trajet', text: 'enregistrer le départ dépôt.' },
  en_route: { tab: 'trajet', text: 'faire le check-in à l’arrivée sur site.' },
  sur_site: { tab: 'photos', text: 'compléter les photos obligatoires.' },
  terminee: { tab: 'outils', text: 'confirmer le retour d’outillage.' },
}

function InterventionFlowSheet({ interv, initialTab, isMobile, onClose, onChanged }) {
  // Le tab initial est fixé au montage ; le parent remonte le composant
  // (via `key={id:initialTab}`) quand l'intervention ou l'onglet visé change,
  // ce qui ré-initialise `tab` sans effet-setState (règle no-setstate-in-effect).
  const [tab, setTab] = useState(initialTab || 'prep')
  const [busy, setBusy] = useState(false)
  // VX105 — changer d'onglet persiste le choix (repris au retour après un
  // rechargement provoqué par un backgrounding).
  const changeTab = (t) => {
    setTab(t)
    try { sessionStorage.setItem(SS_TAB, t) } catch { /* stockage indisponible */ }
  }
  // VX105 — changement de statut depuis la fiche terrain. La garde serveur
  // (`transition_block_reason`) n'est JAMAIS dupliquée côté client : on affiche
  // le message 400 renvoyé tel quel.
  const changeStatut = async (statut) => {
    if (!interv || statut === interv.statut) return
    setBusy(true)
    try {
      await installationsApi.updateIntervention(interv.id, { statut })
      toast.success('Statut mis à jour.')
      onChanged?.()
    } catch (err) {
      const data = err?.response?.data
      toast.error(
        data?.transition_block_reason
        ?? data?.detail
        ?? (typeof data?.statut === 'string' ? data.statut : null)
        ?? 'Changement de statut impossible.')
    } finally { setBusy(false) }
  }
  if (!interv) return null

  const next = NEXT_ACTION[interv.statut]

  // VX43 — bottom-sheet sous 768px (glisser-vers-le-bas-pour-fermer inclus
  // nativement par Sheet.jsx pour side="bottom") ; tiroir latéral inchangé
  // sur desktop.
  return (
    <Sheet open={!!interv} onOpenChange={(o) => { if (!o) onClose() }}>
      <SheetContent
        side={isMobile ? 'bottom' : 'right'}
        className={isMobile ? 'max-h-[85vh] w-full overflow-y-auto p-0' : 'w-full max-w-md overflow-y-auto p-0'}
      >
        <SheetHeader className="border-b border-border p-4">
          <SheetTitle className="flex items-center gap-2">
            {interv.client_nom || interv.installation_reference}
          </SheetTitle>
          <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
            <Badge>{typeLabel(interv.type_intervention)}</Badge>
            <StatusPill status={interv.statut} label={interventionStatusLabel(interv.statut)} dot={false} />
            {interv.site_ville && <span>{interv.site_ville}</span>}
          </div>
          {/* VX105 — changer le statut depuis « Ma journée » : un technicien
              qui finit peut marquer « Terminée » sans passer par l'écran
              bureau. La garde de transition reste côté serveur. */}
          <div className="flex flex-col gap-1 pt-1">
            <span className="text-[12px] text-muted-foreground">Statut</span>
            <Select value={interv.statut} onValueChange={changeStatut} disabled={busy}>
              <SelectTrigger aria-label="Statut de l'intervention" className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INTERVENTION_STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>{INTERVENTION_STATUS_LABELS[s]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="pt-1"><CompteRenduButton intervention={interv} /></div>
        </SheetHeader>

        {/* VX42 — bandeau « Prochaine action » : masqué si le statut n'a pas
            de suite mappée (ex. « validée », fin du flux). */}
        {next && (
          <div className="flex items-center justify-between gap-2 border-b border-info/30 bg-info/10 px-4 py-2 text-[13px]"
            data-testid="mj-next-action">
            <span><strong className="text-info">Prochaine action&nbsp;:</strong> {next.text}</span>
            <button type="button" onClick={() => changeTab(next.tab)}
              className="shrink-0 font-medium text-info underline-offset-2 active:underline">
              Y aller
            </button>
          </div>
        )}

        {/* VX105 — `forceMount` : chaque panneau se monte UNE fois et reste
            monté (masqué quand inactif par Radix), au lieu de se
            remonter-refetcher à chaque re-visite d'onglet — une app
            backgroundée (appel entrant) ne perd plus la saisie en cours. */}
        <Tabs value={tab} onValueChange={changeTab} className="p-3">
          <TabsList className="flex w-full gap-1 overflow-x-auto" data-testid="mj-tab-rail">
            {FLOW_TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value} className="shrink-0 flex-col gap-0.5 px-2.5 py-1.5 text-[11px] leading-tight">
                <t.Icon className="size-4" aria-hidden="true" />
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="prep" forceMount hidden={tab !== 'prep'}><PreparationPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="trajet" forceMount hidden={tab !== 'trajet'}><TrajetPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="safety" forceMount hidden={tab !== 'safety'}><SafetyPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="photos" forceMount hidden={tab !== 'photos'}><PhotosPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="serials" forceMount hidden={tab !== 'serials'}><SerialsPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="conso" forceMount hidden={tab !== 'conso'}><ConsommationPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="memos" forceMount hidden={tab !== 'memos'}><MemosPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="reserves" forceMount hidden={tab !== 'reserves'}><ReservesPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="signature" forceMount hidden={tab !== 'signature'}><SignatureClientPanel intervention={interv} onChanged={onChanged} /></TabsContent>
          <TabsContent value="outils" forceMount hidden={tab !== 'outils'}>
            <ToolReturnPanel intervention={interv} onChanged={onChanged} />
            <CodePanel intervention={interv} />
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  )
}
