// N8 — Parc installé : base canonique des systèmes installés (chantiers
// réceptionnés). Liste filtrable (client, ville, marque, tranche de puissance,
// année d'installation) + vue « carte » par liens GPS. La carte à tuiles
// interactive est différée (nécessiterait une nouvelle dépendance, leaflet).
// N10 — un clic ouvre la fiche système (InstallationDetail), le hub par actif.
// J43 — portée sur le système de design (DataTable, Select, Input, Button).
import { useEffect, useMemo, useState } from 'react'
import { Download, Search, ExternalLink } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import importApi, { downloadXlsx } from '../../api/importApi'
import { TYPE_LABELS } from '../../features/installations/statuses'
import InstallationDetail from './InstallationDetail'
import {
  Button, Badge, Segmented, Spinner, EmptyState, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  DataTable, StatusPill,
} from '../../ui'

// N15 — système sans nomenclature gelée (chantier créé sans devis).
const bomVide = (it) => Array.isArray(it.bom) && it.bom.length === 0

const ALL = '__all__'
const toSel = (v) => (v ? v : ALL)
const fromSel = (v) => (v === ALL ? '' : v)

const installYear = (it) => {
  const iso = it.date_reception || it.date_mise_en_service
  if (!iso) return null
  const y = parseInt(String(iso).slice(0, 4), 10)
  return Number.isNaN(y) ? null : y
}

const capacityBand = (kwc) => {
  const v = Number(kwc) || 0
  if (v <= 0) return null
  if (v < 3) return '< 3 kWc'
  if (v < 10) return '3–10 kWc'
  if (v < 50) return '10–50 kWc'
  return '≥ 50 kWc'
}

const bomMarques = (it) =>
  [...new Set((it.bom ?? []).map((l) => l.marque).filter(Boolean))]

export default function ParcInstallePage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [view, setView] = useState('liste')
  const [filters, setFilters] = useState({ q: '', ville: '', marque: '', band: '', annee: '' })

  const reload = () => {
    // Récupère toutes les pages des systèmes réceptionnés (?parc=1).
    const all = []
    const fetchPage = (page) =>
      installationsApi.getInstallations({ parc: 1, page }).then((r) => {
        const d = r.data
        if (Array.isArray(d)) { all.push(...d); setItems([...all]); setLoading(false); return }
        all.push(...(d.results ?? []))
        if (d.next && page < 50) return fetchPage(page + 1)
        setItems([...all]); setLoading(false)
      })
    fetchPage(1).catch(() => setLoading(false))
  }
  useEffect(() => { reload() }, [])

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
      if (!q) return true
      return (it.reference ?? '').toLowerCase().includes(q)
        || (it.client_nom ?? '').toLowerCase().includes(q)
        || (it.site_ville ?? '').toLowerCase().includes(q)
    })
  }, [items, filters])

  const located = rows.filter((it) => it.gps_lat && it.gps_lng)

  const columns = useMemo(
    () => [
      {
        id: 'reference', header: 'Référence', width: 180,
        cell: (v, r) => (
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="font-semibold">{v}</span>
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
        accessor: (r) => installYear(r) ?? '',
        cell: (v) => v || '—',
      },
      { id: 'technicien_nom', header: 'Installateur', width: 150, accessor: (r) => r.technicien_nom ?? '' },
    ],
    [],
  )

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
            {['< 3 kWc', '3–10 kWc', '10–50 kWc', '≥ 50 kWc'].map((b) => <SelectItem key={b} value={b}>{b}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={toSel(filters.annee)} onValueChange={(v) => setF('annee', fromSel(v))}>
          <SelectTrigger className="w-auto min-w-[8rem]" aria-label="Filtrer par année"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Toutes années</SelectItem>
            {anneeOptions.map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : rows.length === 0 ? (
        <EmptyState
          title="Aucun système installé"
          description="Un chantier rejoint le parc dès qu'il atteint « Réceptionné »."
          className="my-6"
        />
      ) : view === 'liste' ? (
        <DataTable
          data={rows}
          columns={columns}
          getRowId={(row) => row.id}
          searchable={false}
          onRowClick={(row) => setSelected(row)}
          onExport={handleExport}
          exportName="parc-installe"
          pageSize={25}
          emptyTitle="Aucun système installé"
          emptyDescription="Aucun système ne correspond aux filtres."
          aria-label="Parc installé"
        />
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            {located.length} système(s) géolocalisé(s). Cliquez « Ouvrir sur la carte »
            pour visualiser un site (la carte à tuiles intégrée sera ajoutée ultérieurement).
          </p>
          {located.length === 0 ? (
            <EmptyState title="Aucun système géolocalisé" description="Renseignez les coordonnées GPS d'un chantier pour le voir ici." />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-border bg-card">
              <table className="w-full border-collapse text-sm">
                <thead className="bg-muted/60">
                  <tr>
                    {['Référence', 'Client', 'Ville', 'GPS', ''].map((h, i) => (
                      <th key={i} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {located.map((it) => (
                    <tr key={it.id} className="border-t border-border">
                      <td className="px-3 py-2">
                        <Button size="sm" variant="outline" onClick={() => setSelected(it)}>{it.reference}</Button>
                      </td>
                      <td className="px-3 py-2">{it.client_nom ?? '—'}</td>
                      <td className="px-3 py-2">{it.site_ville ?? '—'}</td>
                      <td className="px-3 py-2 tabular-nums">{it.gps_lat}, {it.gps_lng}</td>
                      <td className="px-3 py-2">
                        <Button asChild size="sm" variant="outline">
                          <a target="_blank" rel="noopener"
                             href={`https://www.openstreetmap.org/?mlat=${it.gps_lat}&mlon=${it.gps_lng}#map=17/${it.gps_lat}/${it.gps_lng}`}>
                            <ExternalLink /> Ouvrir sur la carte
                          </a>
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {selected && (
        <InstallationDetail installation={selected} onClose={() => setSelected(null)}
                            onSaved={() => { reload(); setSelected(null) }} />
      )}
    </div>
  )
}
