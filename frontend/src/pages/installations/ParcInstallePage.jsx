// N8 — Parc installé : base canonique des systèmes installés (chantiers
// réceptionnés). Liste filtrable (client, ville, marque, tranche de puissance,
// année d'installation, régime/dossier loi 82-21, garantie) + vue « carte » par
// liens GPS. La carte à tuiles interactive est différée (leaflet).
// N10 — un clic ouvre la fiche système (InstallationDetail), le hub par actif.
// J43 — portée sur le système de design (DataTable, Select, Input, Button).
import { useEffect, useMemo, useState, lazy, Suspense } from 'react'
import { Download, Search, FileBarChart } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import importApi, { downloadXlsx } from '../../api/importApi'
import { downloadBlob } from '../../utils/downloadBlob'
// VX186 — `MapView` (leaflet) en `lazy` : `escapeHtml` (fonction pure) reste
// statique, seul le COMPOSANT porte le poids de leaflet — la vue « carte »
// n'est qu'une bascule parmi d'autres, souvent jamais ouverte.
import { escapeHtml } from '../../components/MapView'
import {
  TYPE_LABELS,
  REGIME_8221_LABELS,
  DOSSIER_STATUT_LABELS,
  PARC_GARANTIE_LABELS,
  capacityBand,
  CAPACITY_BANDS,
  installYear,
  parcSummary,
} from '../../features/installations/statuses'
import InstallationDetail from './InstallationDetail'
import {
  Button, Badge, Segmented, Spinner, Skeleton, EmptyState, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  DataTable, StatusPill,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter, Label,
} from '../../ui'

const MapView = lazy(() => import('../../components/MapView'))

// N15 — système sans nomenclature gelée (chantier créé sans devis).
const bomVide = (it) => Array.isArray(it.bom) && it.bom.length === 0

const ALL = '__all__'
const toSel = (v) => (v ? v : ALL)
const fromSel = (v) => (v === ALL ? '' : v)

const bomMarques = (it) =>
  [...new Set((it.bom ?? []).map((l) => l.marque).filter(Boolean))]

// Couleur du marqueur carte selon l'état de garantie agrégé du système.
const GARANTIE_MARKER_COLOR = {
  sous_garantie: '#16a34a',
  expire_bientot: '#f59e0b',
  hors_garantie: '#dc2626',
  non_renseignee: '#64748b',
}

// Rapport de production ESTIMÉE — petit modal (période + surcharges optionnelles)
// qui télécharge le PDF client-facing. Toutes les valeurs sont des estimations :
// rien n'est mesuré. Les hypothèses laissées vides utilisent les défauts serveur.
function RapportEnergieModal({ installation, onClose }) {
  const [form, setForm] = useState({
    nb_mois: '12', production_annuelle_kwh: '', tarif: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const telecharger = () => {
    setBusy(true)
    setError(null)
    const params = {}
    if (form.nb_mois) params.nb_mois = form.nb_mois
    if (form.production_annuelle_kwh) params.production_annuelle_kwh = form.production_annuelle_kwh
    if (form.tarif) params.tarif = form.tarif
    installationsApi
      .rapportEnergie(installation.id, params)
      .then((r) => {
        downloadBlob(r.data, `rapport-production-${installation.reference}.pdf`)
        onClose()
      })
      .catch(() => setError('Génération du rapport impossible. Réessayez.'))
      .finally(() => setBusy(false))
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Rapport de production (estimé)</DialogTitle>
          <DialogDescription>
            Estimation à partir de la puissance nominale du système
            {installation.puissance_installee_kwc
              ? ` (${installation.puissance_installee_kwc} kWc)` : ''}
            {' '}et d'hypothèses d'ensoleillement. Aucune donnée mesurée — les
            résultats sont indicatifs.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rap-mois">Période (nombre de mois)</Label>
            <Input
              id="rap-mois" type="number" min="1" step="any"
              value={form.nb_mois}
              onChange={(e) => set('nb_mois', e.target.value)}
              placeholder="12"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rap-prod">
              Production annuelle (kWh/an) — facultatif
            </Label>
            <Input
              id="rap-prod" type="number" min="0" step="any"
              value={form.production_annuelle_kwh}
              onChange={(e) => set('production_annuelle_kwh', e.target.value)}
              placeholder="Estimée depuis la puissance si vide"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rap-tarif">
              Tarif électricité (MAD/kWh) — facultatif
            </Label>
            <Input
              id="rap-tarif" type="number" min="0" step="any"
              value={form.tarif}
              onChange={(e) => set('tarif', e.target.value)}
              placeholder="Défaut appliqué si vide"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            Annuler
          </Button>
          <Button type="button" onClick={telecharger} disabled={busy}>
            {busy ? <Spinner /> : <Download />} Télécharger le PDF
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function ParcInstallePage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [rapportFor, setRapportFor] = useState(null)
  const [view, setView] = useState('liste')
  const [filters, setFilters] = useState({
    q: '', ville: '', marque: '', band: '', annee: '',
    regime: '', dossier: '', garantie: '',
  })

  // Récupère toutes les pages des systèmes réceptionnés (?parc=1). Toute mise à
  // jour d'état se fait dans des callbacks asynchrones (then/catch), jamais de
  // façon synchrone : l'effet de montage peut donc l'appeler directement.
  const load = () => {
    const all = []
    const fetchPage = (page) =>
      installationsApi.getInstallations({ parc: 1, page }).then((r) => {
        const d = r.data
        if (Array.isArray(d)) { all.push(...d); setItems([...all]); setLoading(false); return }
        all.push(...(d.results ?? []))
        // N11 — progression : on affiche les pages déjà chargées au fil de l'eau.
        setItems([...all])
        if (d.next && page < 50) return fetchPage(page + 1)
        setItems([...all]); setLoading(false)
      })
    fetchPage(1).catch(() => {
      setError('Impossible de charger le parc installé. Réessayez.')
      setLoading(false)
    })
  }
  // Rechargement explicite (retry/refresh) — gestionnaire d'événement : on peut
  // repasser l'écran en chargement et effacer l'erreur de façon synchrone.
  const reload = () => { setLoading(true); setError(null); load() }
  useEffect(() => { load() }, [])

  const setF = (k, v) => setFilters((f) => ({ ...f, [k]: v }))

  const villeOptions = useMemo(
    () => [...new Set(items.map((i) => i.site_ville).filter(Boolean))].sort(), [items])
  const marqueOptions = useMemo(
    () => [...new Set(items.flatMap(bomMarques))].sort(), [items])
  const anneeOptions = useMemo(
    () => [...new Set(items.map(installYear).filter(Boolean))].sort((a, b) => b - a), [items])

  const rows = useMemo(() => {
    const q = filters.q.trim().toLowerCase()
    return items.filter((it) => {
      if (filters.ville && it.site_ville !== filters.ville) return false
      if (filters.marque && !bomMarques(it).includes(filters.marque)) return false
      if (filters.band && capacityBand(it.puissance_installee_kwc) !== filters.band) return false
      if (filters.annee && String(installYear(it)) !== String(filters.annee)) return false
      if (filters.regime && (it.regime_8221 ?? '') !== filters.regime) return false
      if (filters.dossier && (it.dossier_statut ?? '') !== filters.dossier) return false
      if (filters.garantie && (it.parc_garantie_etat ?? '') !== filters.garantie) return false
      if (!q) return true
      return (it.reference ?? '').toLowerCase().includes(q)
        || (it.client_nom ?? '').toLowerCase().includes(q)
        || (it.site_ville ?? '').toLowerCase().includes(q)
    })
  }, [items, filters])

  // N14 — synthèse Parc : total kWc + comptes par type et par tranche, calculés
  // depuis les lignes filtrées (suit ce que l'utilisateur regarde).
  const synthese = useMemo(() => parcSummary(rows), [rows])

  const located = rows.filter((it) => it.gps_lat && it.gps_lng)

  // L4 — marqueurs Leaflet : un par système géolocalisé, coloré selon l'état de
  // garantie agrégé ; cliquer ouvre la fiche système. Toujours filtrés par la
  // société côté serveur (?parc=1 borné au queryset de l'utilisateur).
  const markers = useMemo(() => located.map((it) => {
    const g = PARC_GARANTIE_LABELS[it.parc_garantie_etat]
    // ERR26 — échapper chaque valeur serveur avant de l'injecter dans le HTML.
    const ville = it.site_ville ? ` · ${escapeHtml(it.site_ville)}` : ''
    const kwc = it.puissance_installee_kwc ? ` · ${escapeHtml(it.puissance_installee_kwc)} kWc` : ''
    return {
      id: it.id,
      lat: Number(it.gps_lat),
      lng: Number(it.gps_lng),
      label: it.reference || it.client_nom || 'Système',
      color: GARANTIE_MARKER_COLOR[it.parc_garantie_etat] ?? '#16a34a',
      popupHtml: `<div style="margin-top:4px;color:#475569;font-size:0.8rem">`
        + `${escapeHtml(it.client_nom ?? '')}${ville}${kwc}`
        + (g ? `<br/>${escapeHtml(g.label)}` : '')
        + `</div>`,
    }
  }), [located])

  const columns = useMemo(
    () => [
      {
        id: 'reference', header: 'Référence', width: 180,
        accessor: (r) => r.reference ?? '',
        cell: (v, r) => (
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="font-semibold">{r.reference ?? '—'}</span>
            {bomVide(r) && <StatusPill tone="warning" label="Nomenclature absente" />}
          </span>
        ),
        exportValue: (r) => r.reference ?? '',
      },
      { id: 'client_nom', header: 'Client', width: 170, accessor: (r) => r.client_nom ?? '' },
      { id: 'site_ville', header: 'Ville', width: 130, accessor: (r) => r.site_ville ?? '' },
      {
        id: 'puissance', header: 'Puissance', width: 120, align: 'right',
        accessor: (r) => Number(r.puissance_installee_kwc) || 0,
        cell: (v, r) => (r.puissance_installee_kwc ? `${r.puissance_installee_kwc} kWc` : '—'),
        exportValue: (r) => r.puissance_installee_kwc ?? '',
      },
      {
        id: 'type', header: 'Type', width: 150,
        accessor: (r) => TYPE_LABELS[r.type_installation] ?? '',
        exportValue: (r) => TYPE_LABELS[r.type_installation] ?? '',
      },
      {
        id: 'annee', header: 'Année', width: 90, align: 'right',
        accessor: (r) => installYear(r) ?? 0,
        cell: (v) => v || '—',
        exportValue: (r) => installYear(r) ?? '',
      },
      {
        id: 'garantie', header: 'Garantie', width: 180, searchable: false,
        accessor: (r) => r.parc_garantie_etat ?? '',
        cell: (v, r) => {
          const g = PARC_GARANTIE_LABELS[r.parc_garantie_etat]
          return g
            ? <StatusPill tone={g.tone} label={g.label} />
            : <span className="text-muted-foreground">—</span>
        },
        exportValue: (r) => PARC_GARANTIE_LABELS[r.parc_garantie_etat]?.label ?? '',
      },
      { id: 'technicien_nom', header: 'Installateur', width: 150, accessor: (r) => r.technicien_nom ?? '' },
      {
        id: 'actions', header: '', width: 64, searchable: false, sortable: false,
        exportValue: () => '',
        cell: (v, r) => (
          <Button
            type="button" size="sm" variant="ghost"
            aria-label="Rapport de production (estimé)"
            title="Rapport de production (estimé)"
            onClick={(e) => { e.stopPropagation(); setRapportFor(r) }}
          >
            <FileBarChart />
          </Button>
        ),
      },
    ],
    [],
  )

  // N9 — tri par défaut : année d'installation la plus récente d'abord. Toutes
  // les colonnes du DataTable sont triables (clic sur l'en-tête).
  const savedViews = [
    { id: 'recent', label: 'Récents', sorting: [{ id: 'annee', desc: true }], columnFilters: {}, query: '' },
  ]

  const handleExport = (exportRows) => {
    importApi
      .exportList('chantiers', (exportRows ?? rows).map((r) => r.id))
      .then((r) => downloadXlsx(r.data, 'parc-installe.xlsx'))
      .catch(() => {})
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title flex items-center gap-2">
          Parc installé
          <Badge tone="primary">{rows.length}</Badge>
        </h1>
        <div className="page-subtitle">{rows.length} système(s) installé(s)</div>
        <div className="page-header-actions flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant="outline" onClick={() => handleExport(rows)}>
            <Download /> Exporter Excel
          </Button>
          <Segmented
            size="sm"
            value={view}
            onChange={setView}
            aria-label="Changer de vue"
            options={[
              { value: 'liste', label: 'Liste' },
              { value: 'carte', label: 'Carte' },
            ]}
          />
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="min-w-[14rem] flex-1">
          <Input
            type="search"
            leading={<Search />}
            placeholder="Rechercher (réf, client, ville)…"
            value={filters.q}
            onChange={(e) => setF('q', e.target.value)}
            aria-label="Rechercher un système installé"
          />
        </div>
        <Select value={toSel(filters.ville)} onValueChange={(v) => setF('ville', fromSel(v))}>
          <SelectTrigger className="w-auto min-w-[9rem]" aria-label="Filtrer par ville"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Toutes les villes</SelectItem>
            {villeOptions.map((v) => <SelectItem key={v} value={v}>{v}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={toSel(filters.marque)} onValueChange={(v) => setF('marque', fromSel(v))}>
          <SelectTrigger className="w-auto min-w-[9rem]" aria-label="Filtrer par marque"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Toutes les marques</SelectItem>
            {marqueOptions.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={toSel(filters.band)} onValueChange={(v) => setF('band', fromSel(v))}>
          <SelectTrigger className="w-auto min-w-[9rem]" aria-label="Filtrer par puissance"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Toutes puissances</SelectItem>
            {CAPACITY_BANDS.map((b) => <SelectItem key={b} value={b}>{b}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={toSel(filters.annee)} onValueChange={(v) => setF('annee', fromSel(v))}>
          <SelectTrigger className="w-auto min-w-[8rem]" aria-label="Filtrer par année"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Toutes années</SelectItem>
            {anneeOptions.map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={toSel(filters.regime)} onValueChange={(v) => setF('regime', fromSel(v))}>
          <SelectTrigger className="w-auto min-w-[10rem]" aria-label="Filtrer par régime loi 82-21"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Tous les régimes</SelectItem>
            {Object.entries(REGIME_8221_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={toSel(filters.dossier)} onValueChange={(v) => setF('dossier', fromSel(v))}>
          <SelectTrigger className="w-auto min-w-[10rem]" aria-label="Filtrer par statut de dossier"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Tous les dossiers</SelectItem>
            {Object.entries(DOSSIER_STATUT_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={toSel(filters.garantie)} onValueChange={(v) => setF('garantie', fromSel(v))}>
          <SelectTrigger className="w-auto min-w-[10rem]" aria-label="Filtrer par garantie"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Toutes garanties</SelectItem>
            {Object.entries(PARC_GARANTIE_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* N14 — bande de synthèse : total kWc + comptes par type et tranche. */}
      {!loading && !error && rows.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 font-semibold text-primary">
            {synthese.totalKwc} kWc installés
          </span>
          {Object.entries(synthese.parType).map(([type, count]) => (
            <span key={type}
                  className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 font-medium text-muted-foreground">
              {TYPE_LABELS[type] ?? 'Autre'}
              <span className="tabular-nums font-semibold text-foreground">{count}</span>
            </span>
          ))}
          {CAPACITY_BANDS.filter((b) => synthese.parTranche[b]).map((b) => (
            <span key={b}
                  className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 font-medium text-muted-foreground">
              {b}
              <span className="tabular-nums font-semibold text-foreground">{synthese.parTranche[b]}</span>
            </span>
          ))}
        </div>
      )}

      {error ? (
        <EmptyState
          title="Erreur de chargement"
          description={error}
          action={<Button size="sm" onClick={reload}>Réessayer</Button>}
          className="my-6 border-destructive/40"
        />
      ) : loading && items.length === 0 ? (
        // N11 — squelette de chargement (aucune page encore reçue).
        <div className="flex flex-col gap-2">
          <p className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
          {Array.from({ length: 6 }).map((unused, i) => (
            <Skeleton key={i} className="h-10 w-full rounded-lg" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          title="Aucun système installé"
          description="Un chantier rejoint le parc dès qu'il atteint « Réceptionné »."
          className="my-6"
        />
      ) : view === 'liste' ? (
        <>
          {/* N11 — chargement partiel : pages restantes en cours. */}
          {loading && (
            <p className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
              <Spinner /> Chargement des pages suivantes…
            </p>
          )}
          <DataTable
            data={rows}
            columns={columns}
            getRowId={(row) => row.id}
            searchable={false}
            savedViews={savedViews}
            onRowClick={(row) => setSelected(row)}
            onExport={handleExport}
            exportName="parc-installe"
            pageSize={25}
            emptyTitle="Aucun système installé"
            emptyDescription="Aucun système ne correspond aux filtres."
            aria-label="Parc installé"
          />
        </>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            {located.length} système(s) géolocalisé(s). Cliquez un marqueur pour ouvrir la fiche.
          </p>
          {located.length === 0 ? (
            <EmptyState title="Aucun système géolocalisé" description="Renseignez les coordonnées GPS d'un chantier pour le voir ici." />
          ) : (
            <Suspense fallback={<p className="page-loading"><Spinner /> Chargement de la carte…</p>}>
              <MapView
                markers={markers}
                onMarkerClick={(m) => {
                  const it = located.find((r) => r.id === m.id)
                  if (it) setSelected(it)
                }}
              />
            </Suspense>
          )}
        </div>
      )}

      {selected && (
        <InstallationDetail installation={selected} onClose={() => setSelected(null)}
                            onSaved={() => { reload(); setSelected(null) }} />
      )}

      {rapportFor && (
        <RapportEnergieModal installation={rapportFor} onClose={() => setRapportFor(null)} />
      )}
    </div>
  )
}
