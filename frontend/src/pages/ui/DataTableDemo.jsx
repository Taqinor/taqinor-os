import { useMemo, useState } from 'react'
import {
  Eye, Pencil, Trash2, Phone, UserPlus, ArrowRightLeft, Download, Send,
} from 'lucide-react'
import { formatMAD, formatDate, formatPhoneMA } from '../../lib/format'
import {
  DataTable, EditableCell, Badge, StatusPill, toast, Button, Card,
} from '../../ui'
import { highlightSegments } from '../../ui/datatable'

/* ============================================================================
   H31/H32/H33 — Vitrine du moteur DataTable avec données d'exemple (leads).
   Exerce : tri multi-colonnes, recherche + surlignage, sélection + barre
   d'actions groupées configurable, actions de ligne + overflow, édition en
   place (toast + undo), pagination « X–Y sur N », sous-totaux TVA, vues
   sauvegardées, colonne gelée, virtualisation (619 lignes) et persistance URL.
   ========================================================================== */

const PRENOMS = ['Reda', 'Meryem', 'Karim', 'Sara', 'Youssef', 'Imane', 'Hamza', 'Nadia', 'Omar', 'Salma']
const NOMS = ['Kasri', 'Benani', 'El Amrani', 'Tazi', 'Bennis', 'Fassi', 'Alaoui', 'Idrissi', 'Cherkaoui', 'Berrada']
const VILLES = ['Rabat', 'Casablanca', 'Marrakech', 'Fès', 'Tanger', 'Agadir', 'Oujda', 'Tétouan']
const CANAUX = ['Meta', 'Google', 'Référence', 'Salon', 'Direct']
const STATUTS = [
  { v: 'signe', label: 'Signé', pill: 'accepte' },
  { v: 'envoye', label: 'Devis envoyé', pill: 'envoye' },
  { v: 'relance', label: 'À relancer', pill: 'en_cours' },
  { v: 'perdu', label: 'Perdu', pill: 'perdu' },
]

/** Génère N leads pseudo-aléatoires déterministes (seed simple). */
function makeLeads(n) {
  const rows = []
  let seed = 7
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff
    return seed / 0x7fffffff
  }
  for (let i = 0; i < n; i++) {
    const prenom = PRENOMS[Math.floor(rnd() * PRENOMS.length)]
    const nom = NOMS[Math.floor(rnd() * NOMS.length)]
    const statut = STATUTS[Math.floor(rnd() * STATUTS.length)]
    const montant = Math.round((3000 + rnd() * 180000) / 100) * 100
    const day = 1 + Math.floor(rnd() * 27)
    rows.push({
      id: i + 1,
      nom: `${prenom} ${nom}`,
      ville: VILLES[Math.floor(rnd() * VILLES.length)],
      tel: `06${String(Math.floor(10000000 + rnd() * 89999999))}`,
      canal: CANAUX[Math.floor(rnd() * CANAUX.length)],
      statut: statut.v,
      montant,
      date: `2026-06-${String(day).padStart(2, '0')}`,
    })
  }
  return rows
}

function statutMeta(v) {
  return STATUTS.find((s) => s.v === v) ?? STATUTS[0]
}

export function DataTableDemo() {
  // Petit jeu éditable (montants modifiables → toast + undo).
  const [leads, setLeads] = useState(() => makeLeads(28))
  // Grand jeu pour la virtualisation (619 lignes, comme l'import réel).
  const big = useMemo(() => makeLeads(619), [])

  function updateMontant(id, value, previous) {
    setLeads((prev) => prev.map((l) => (l.id === id ? { ...l, montant: Number(value) } : l)))
    toast.success('Montant mis à jour', {
      action: {
        label: 'Annuler',
        onClick: () =>
          setLeads((prev) => prev.map((l) => (l.id === id ? { ...l, montant: previous } : l))),
      },
    })
  }

  const columns = useMemo(
    () => [
      {
        id: 'nom',
        header: 'Client',
        pinned: 'left', // colonne gelée
        width: 180,
        hideable: false,
        cell: (value, row, { query }) => (
          <span className="flex flex-col">
            <HighlightedName value={value} query={query} />
            <span className="text-xs text-muted-foreground">{formatPhoneMA(row.tel)}</span>
          </span>
        ),
        exportValue: (row) => row.nom,
      },
      { id: 'ville', header: 'Ville', width: 120 },
      {
        id: 'canal',
        header: 'Canal',
        width: 120,
        cell: (value) => <Badge tone="info">{value}</Badge>,
      },
      {
        id: 'statut',
        header: 'Statut',
        width: 150,
        searchable: false,
        cell: (value) => {
          const m = statutMeta(value)
          return <StatusPill status={m.pill} label={m.label} />
        },
        exportValue: (row) => statutMeta(row.statut).label,
      },
      {
        id: 'montant',
        header: 'Montant TTC',
        align: 'right',
        numeric: true,
        width: 160,
        searchable: false,
        // Édition en place avec validation + sauvegarde + undo (H32).
        cell: (value, row) => (
          <EditableCell
            value={value}
            row={row}
            align="right"
            inputType="number"
            format={(v) => formatMAD(v)}
            validate={(v) => {
              const n = Number(v)
              if (!Number.isFinite(n) || n < 0) return 'Montant invalide'
              return null
            }}
            onSave={(v, r) => updateMontant(r.id, v, value)}
          />
        ),
        exportValue: (row) => row.montant,
        summaryFormat: (n) => formatMAD(n),
        summaryRender: (n) => <span className="text-foreground">{formatMAD(n)}</span>,
      },
      {
        id: 'date',
        header: 'Créé le',
        align: 'right',
        width: 120,
        searchable: false,
        cell: (value) => <span className="text-muted-foreground">{formatDate(value)}</span>,
        exportValue: (row) => formatDate(row.date),
      },
    ],
    [],
  )

  // Actions de ligne (≤3 inline + overflow) — H32.
  const rowActions = (row) => [
    { id: 'view', label: 'Aperçu', icon: Eye, onClick: () => toast(`Aperçu — ${row.nom}`) },
    { id: 'edit', label: 'Modifier', icon: Pencil, onClick: () => toast(`Modifier — ${row.nom}`) },
    { id: 'call', label: 'Appeler', icon: Phone, onClick: () => toast(`Appel — ${formatPhoneMA(row.tel)}`) },
    { id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true, separatorBefore: true, onClick: () => toast.error(`Supprimé — ${row.nom}`) },
  ]

  // Barre d'actions groupées CONFIGURABLE (slots passés, pas codés en dur) — H32.
  const bulkActions = (selectedRows, selectedKeys, clear) => [
    { id: 'assign', label: 'Assigner', icon: UserPlus, onClick: () => { toast(`Assigner ${selectedKeys.length} lead(s)`); clear() } },
    { id: 'stage', label: 'Changer statut', icon: ArrowRightLeft, onClick: () => { toast(`Statut · ${selectedKeys.length}`); clear() } },
    { id: 'export', label: 'Exporter', icon: Download, onClick: () => toast(`Export de ${selectedKeys.length} ligne(s)`) },
    { id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true, onClick: () => { toast.error(`Suppression de ${selectedKeys.length}`); clear() } },
  ]

  // Vues sauvegardées (onglets configurables) — H33.
  const savedViews = [
    { id: 'toutes', label: 'Toutes', sorting: [], columnFilters: {}, query: '' },
    { id: 'a-relancer', label: 'À relancer', columnFilters: { statut: 'relance' }, sorting: [{ id: 'date', desc: false }] },
    { id: 'signes', label: 'Signés', columnFilters: { statut: 'signe' }, sorting: [{ id: 'montant', desc: true }] },
    { id: 'gros', label: 'Gros montants', sorting: [{ id: 'montant', desc: true }], columnFilters: {} },
  ]

  return (
    <div className="flex flex-col gap-8">
      {/* Tableau principal : tout le moteur, persistance URL activée. */}
      <DataTable
        data={leads}
        columns={columns}
        getRowId={(row) => row.id}
        selectable
        searchable
        searchPlaceholder="Rechercher un client, une ville…"
        rowActions={rowActions}
        bulkActions={bulkActions}
        savedViews={savedViews}
        onRowClick={(row) => toast(`Ligne — ${row.nom}`)}
        renderExpanded={(row) => (
          <div className="grid gap-2 text-sm sm:grid-cols-3">
            <Field label="Ville" value={row.ville} />
            <Field label="Canal" value={row.canal} />
            <Field label="Téléphone" value={formatPhoneMA(row.tel)} />
            <Field label="Montant TTC" value={formatMAD(row.montant)} />
            <Field label="Statut" value={statutMeta(row.statut).label} />
            <Field label="Créé le" value={formatDate(row.date)} />
          </div>
        )}
        summary={{ montant: 'sum' }}
        summaryLabel="Total TTC"
        exportName="leads"
        persistToUrl
        urlKey="leads"
        emptyTitle="Aucun lead"
        emptyDescription="Aucun client ne correspond à votre recherche."
      />

      {/* Tableau virtualisé : 619 lignes (windowing maison, sans dépendance). */}
      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="font-display text-base font-semibold">Liste virtualisée — 619 lignes</h3>
            <p className="text-sm text-muted-foreground">
              Fenêtrage léger fait maison ; défilement fluide, première colonne gelée.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => toast('Astuce : faites défiler la zone')}>
            <Send /> Démo
          </Button>
        </div>
        <DataTable
          data={big}
          columns={columns.filter((c) => c.id !== 'montant').concat({
            id: 'montant', header: 'Montant TTC', align: 'right', numeric: true, width: 160,
            cell: (v) => formatMAD(v), exportValue: (r) => r.montant,
          })}
          getRowId={(row) => row.id}
          virtualize
          rowHeight={44}
          maxBodyHeight={420}
          pageSize={619}
          pageSizeOptions={[619]}
          searchable
          exportName="leads-619"
          emptyTitle="Aucun lead"
        />
      </Card>
    </div>
  )
}

function Field({ label, value }) {
  return (
    <div className="rounded-lg border border-border bg-card p-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  )
}

/* Réutilise le surlignage du moteur pour le nom (via la prop query du cell). */
function HighlightedName({ value, query }) {
  if (!query) return <span className="font-medium">{value}</span>
  return (
    <span className="font-medium">
      {highlightSegments(value, query).map((seg, i) =>
        seg.match ? (
          <mark key={i} className="rounded-sm bg-warning/30 text-foreground">{seg.text}</mark>
        ) : (
          <span key={i}>{seg.text}</span>
        ),
      )}
    </span>
  )
}

export default DataTableDemo
