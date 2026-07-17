// NTUX23 — Rapport imprimable « configuration des vues actives » : écran
// /parametres/vues (Directeur/Admin) listant TOUTES les `SavedView` (NTUX1)
// de la company, au-delà du filtre perso/équipe normal (`toutes-company/`,
// 403 côté serveur pour tout autre rôle) — audit de gouvernance des vues
// d'équipe avant un contrôle qualité ou un onboarding de nouveau commercial.
// Export .xlsx via le moteur PARTAGÉ backend (apps.records.xlsx), jamais le
// moteur `quote_engine` (rule #4, hors périmètre).
import { useEffect, useRef, useState } from 'react'
import { Download, LayoutList, Upload } from 'lucide-react'
import uxviewsApi from '../../api/uxviewsApi'
import { DataTable, Button, Spinner, EmptyState, Badge } from '../../ui'
import { downloadBlob, stampedFilename } from '../../utils/downloadBlob'
import { toast } from '../../ui/confirm'

const COLUMNS = [
  { id: 'ecran', header: 'Écran' },
  { id: 'nom', header: 'Nom' },
  { id: 'owner_nom', header: 'Propriétaire' },
  {
    id: 'visibilite',
    header: 'Visibilité',
    accessor: (r) => (r.visibilite === 'EQUIPE' ? "Partagée à l'équipe" : 'Personnelle'),
    cell: (v, r) => (
      <Badge tone={r.visibilite === 'EQUIPE' ? 'info' : 'neutral'}>
        {r.visibilite === 'EQUIPE' ? "Partagée à l'équipe" : 'Personnelle'}
      </Badge>
    ),
  },
  {
    id: 'role_nom',
    header: 'Rôle par défaut',
    accessor: (r) => (r.est_defaut_role ? r.role_nom : null),
    cell: (v) => v || '—',
  },
  {
    id: 'updated_at',
    header: 'Dernière modification',
    accessor: (r) => r.updated_at,
    cell: (v) => (v ? new Date(v).toLocaleDateString('fr-FR') : '—'),
  },
]

export default function VuesConfigurationPage() {
  const [views, setViews] = useState([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  // NTUX34 — import CSV/XLSX de vues sauvegardées entre environnements
  // (staging → prod, ou d'une company sœur) : jamais tout-ou-rien, les
  // lignes valides sont importées même si d'autres échouent (rapportées ici).
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState(null)
  const fileRef = useRef(null)

  const load = (active = { current: true }) => {
    setLoading(true)
    return uxviewsApi.listAllSavedViews()
      .then((res) => {
        if (!active.current) return
        setViews(Array.isArray(res.data?.results) ? res.data.results : (res.data || []))
      })
      .catch(() => { if (active.current) setViews([]) })
      .finally(() => { if (active.current) setLoading(false) })
  }

  useEffect(() => {
    const active = { current: true }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
    load(active)
    return () => { active.current = false }
  }, [])

  const handleExport = () => {
    setExporting(true)
    uxviewsApi.exportSavedViewsXlsx()
      .then((res) => downloadBlob(res.data, stampedFilename('vues-sauvegardees', 'xlsx')))
      .catch(() => toast.error('Export impossible.'))
      .finally(() => setExporting(false))
  }

  const handleImport = (file) => {
    if (!file) return
    setImporting(true)
    setImportResult(null)
    uxviewsApi.importSavedViews(file)
      .then((res) => {
        setImportResult(res.data)
        if (res.data.created?.length) {
          toast.success(`${res.data.created.length} vue(s) importée(s).`)
          load()
        }
        if (res.data.erreurs?.length) {
          toast.error(`${res.data.erreurs.length} ligne(s) rejetée(s), voir le détail.`)
        }
      })
      .catch(() => toast.error('Import impossible.'))
      .finally(() => {
        setImporting(false)
        if (fileRef.current) fileRef.current.value = ''
      })
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Configuration des vues actives</h1>
        <div className="page-subtitle">
          Audit de gouvernance des vues sauvegardées (NTUX1/NTUX2) — toutes
          les vues personnelles et d'équipe de votre société, avant un
          contrôle qualité ou un onboarding de nouveau commercial.
        </div>
      </div>

      <div className="mb-4 flex flex-wrap justify-end gap-2">
        <input
          ref={fileRef} type="file" accept=".csv,.xlsx" className="hidden"
          onChange={(e) => handleImport(e.target.files?.[0])}
        />
        <Button variant="outline" onClick={() => fileRef.current?.click()} loading={importing}>
          <Upload /> Importer des vues
        </Button>
        <Button variant="outline" onClick={handleExport} loading={exporting}>
          <Download /> Exporter (XLSX)
        </Button>
      </div>

      {importResult && importResult.erreurs?.length > 0 && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm" data-testid="vc-import-erreurs">
          <p className="font-medium text-destructive">
            {importResult.erreurs.length} ligne(s) rejetée(s) :
          </p>
          <ul className="ml-4 list-disc">
            {importResult.erreurs.map((e) => (
              <li key={e.ligne}>Ligne {e.ligne} — {e.message}</li>
            ))}
          </ul>
        </div>
      )}

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </p>
      ) : views.length === 0 ? (
        <EmptyState
          icon={LayoutList}
          title="Aucune vue enregistrée"
          description="Aucune vue sauvegardée n'existe encore pour cette société."
          className="my-6"
        />
      ) : (
        <DataTable
          data={views}
          columns={COLUMNS}
          getRowId={(row) => row.id}
          pageSize={25}
          aria-label="Vues sauvegardées de la société"
        />
      )}
    </div>
  )
}
