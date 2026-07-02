import { useEffect, useMemo, useState } from 'react'
import { LibraryBig } from 'lucide-react'
import contratsApi from '../../api/contratsApi'
import { Card, Badge, Tabs, TabsList, TabsTrigger, TabsContent, toast } from '../../ui'
import { ListShell } from '../../ui/module'
import { formatDate } from '../../lib/format'

/* ============================================================================
   UX35 — Modèles, clauses & versions.
   ----------------------------------------------------------------------------
   Trois onglets : bibliothèque de gabarits (modeles), bibliothèque de clauses
   réutilisables (clauses), et versions IMMUABLES figées (versions — lecture
   seule, diff par nature). Avenants/résiliations sont montrés sur la fiche
   contrat (UX34) ; ici on adresse la bibliothèque partagée.
   ========================================================================== */

const listData = (res) => (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))

export default function ModelesPage() {
  const [modeles, setModeles] = useState([])
  const [clauses, setClauses] = useState([])
  const [versions, setVersions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    setLoading(true)
    Promise.all([
      contratsApi.getModeles().then((r) => setModeles(listData(r))),
      contratsApi.getClauses().then((r) => setClauses(listData(r))),
      contratsApi.getVersions().then((r) => setVersions(listData(r))),
    ])
      .catch(() => setError('Impossible de charger la bibliothèque.'))
      .finally(() => setLoading(false))
  }, [])

  const modeleCols = useMemo(() => [
    { id: 'nom', header: 'Modèle', width: 220, accessor: (m) => m.nom, cell: (v) => <span className="font-medium">{v}</span> },
    { id: 'categorie', header: 'Catégorie', width: 160, accessor: (m) => m.categorie || '' },
    { id: 'type', header: 'Type par défaut', width: 150, accessor: (m) => m.type_contrat_defaut_display || m.type_contrat_defaut || '' },
    { id: 'clauses', header: 'Clauses', width: 90, align: 'right', searchable: false, accessor: (m) => (m.clauses?.length ?? 0) },
    { id: 'actif', header: 'Actif', width: 90, accessor: (m) => (m.actif ? 'Actif' : 'Inactif'), cell: (v) => <Badge tone={v === 'Actif' ? 'success' : 'neutral'}>{v}</Badge> },
  ], [])

  const clauseCols = useMemo(() => [
    { id: 'titre', header: 'Clause', width: 240, accessor: (c) => c.titre, cell: (v) => <span className="font-medium">{v}</span> },
    { id: 'type', header: 'Type', width: 150, accessor: (c) => c.type_clause_display || c.type_clause || '' },
    { id: 'categorie', header: 'Catégorie', width: 150, accessor: (c) => c.categorie || '' },
    { id: 'actif', header: 'Actif', width: 90, accessor: (c) => (c.actif ? 'Actif' : 'Inactif'), cell: (v) => <Badge tone={v === 'Actif' ? 'success' : 'neutral'}>{v}</Badge> },
  ], [])

  const versionCols = useMemo(() => [
    { id: 'contrat', header: 'Contrat', width: 120, align: 'right', searchable: false, accessor: (v) => v.contrat, cell: (val) => <span className="font-mono text-xs">#{val}</span> },
    { id: 'version', header: 'Version', width: 100, accessor: (v) => `v${v.version}`, cell: (val) => <span className="font-mono">{val}</span> },
    { id: 'motif', header: 'Motif', width: 240, accessor: (v) => v.motif || '' },
    { id: 'auteur', header: 'Auteur', width: 140, accessor: (v) => v.cree_par_username || '' },
    { id: 'cree_le', header: 'Figée le', width: 160, align: 'right', searchable: false, accessor: (v) => v.cree_le || '', cell: (val) => (val ? formatDate(val) : '—') },
  ], [])

  const wrap = (title, subtitle, columns, rows, name, empty) => (
    <ListShell
      title={title}
      subtitle={subtitle}
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      searchable
      exportName={name}
      emptyTitle="Vide"
      emptyDescription={empty}
      onRowClick={() => toast.message('Édition de la bibliothèque à venir.')}
    />
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <LibraryBig className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">Modèles &amp; clauses</h1>
      </div>
      <Tabs defaultValue="modeles">
        <TabsList>
          <TabsTrigger value="modeles">Modèles ({modeles.length})</TabsTrigger>
          <TabsTrigger value="clauses">Clauses ({clauses.length})</TabsTrigger>
          <TabsTrigger value="versions">Versions ({versions.length})</TabsTrigger>
        </TabsList>
        <TabsContent value="modeles">
          {wrap('Gabarits de contrat', 'Instanciez un contrat pré-rempli depuis un gabarit.', modeleCols, modeles, 'modeles-contrat', 'Aucun modèle de contrat.')}
        </TabsContent>
        <TabsContent value="clauses">
          {wrap('Bibliothèque de clauses', 'Clauses réutilisables, rattachables aux gabarits et résolues sur chaque contrat.', clauseCols, clauses, 'clauses-contrat', 'Aucune clause.')}
        </TabsContent>
        <TabsContent value="versions">
          <Card className="mb-3 border-info/40 bg-info/5 p-3 text-sm text-muted-foreground">
            Les versions sont des instantanés IMMUABLES du rendu d’un contrat — jamais modifiées ni supprimées une fois figées.
          </Card>
          {wrap('Versions figées', 'Historique immuable des rendus de contrat (CONTRAT18).', versionCols, versions, 'versions-contrat', 'Aucune version figée.')}
        </TabsContent>
      </Tabs>
    </div>
  )
}
