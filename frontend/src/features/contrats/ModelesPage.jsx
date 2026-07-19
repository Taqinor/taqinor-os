import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LibraryBig, Plus } from 'lucide-react'
import contratsApi from '../../api/contratsApi'
import {
  Card, Badge, Tabs, TabsList, TabsTrigger, TabsContent, toast,
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea,
} from '../../ui'
import { ListShell } from '../../ui/module'
import { formatDate } from '../../lib/format'
import { CONTRAT_TYPES } from './status'

/* ============================================================================
   UX35 — Modèles, clauses & versions.
   ----------------------------------------------------------------------------
   Trois onglets : bibliothèque de gabarits (modeles), bibliothèque de clauses
   réutilisables (clauses), et versions IMMUABLES figées (versions — lecture
   seule, diff par nature). Avenants/résiliations sont montrés sur la fiche
   contrat (UX34) ; ici on adresse la bibliothèque partagée.
   WIR9 — création directe d'un `ModeleContrat`/`Clause` : jusqu'ici seule
   l'action « instancier un gabarit existant » était câblée ; une société
   neuve, avec 0 modèle, ne pouvait RIEN créer (le clic sur une ligne
   affichait juste « Édition de la bibliothèque à venir. »).
   ========================================================================== */

const listData = (res) => (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

// Reflet exact de `Clause.TypeClause` (apps/contrats/models.py) — jamais une
// liste réinventée côté front.
const TYPE_CLAUSE = [
  { value: 'generale', label: 'Générale' },
  { value: 'technique', label: 'Technique' },
  { value: 'financiere', label: 'Financière' },
  { value: 'juridique', label: 'Juridique' },
  { value: 'resiliation', label: 'Résiliation' },
  { value: 'garantie', label: 'Garantie' },
  { value: 'confidentialite', label: 'Confidentialité' },
  { value: 'autre', label: 'Autre' },
]

export default function ModelesPage() {
  const navigate = useNavigate()
  const [modeles, setModeles] = useState([])
  const [clauses, setClauses] = useState([])
  const [versions, setVersions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // WIR9 — dialogues de création directe (bibliothèque partagée).
  const [creatingModele, setCreatingModele] = useState(false)
  const [creatingClause, setCreatingClause] = useState(false)

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

  // CONTRAT7 — instancier un contrat pré-rempli depuis un gabarit puis ouvrir
  // sa fiche cycle de vie (aucun autre chemin de création n'existait).
  const instancier = async (modele) => {
    try {
      const r = await contratsApi.instancierModele(modele.id)
      const id = r.data?.id
      toast.success('Contrat créé depuis le gabarit.')
      if (id) navigate(`/contrats/${id}`)
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Instanciation impossible.')
    }
  }

  const wrap = (title, subtitle, columns, rows, name, empty, onRowClick, actions) => (
    <ListShell
      title={title}
      subtitle={subtitle}
      actions={actions}
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      searchable
      exportName={name}
      emptyTitle="Vide"
      emptyDescription={empty}
      onRowClick={onRowClick || (() => toast.message('Édition de la bibliothèque à venir.'))}
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
          {wrap(
            'Gabarits de contrat',
            'Cliquez un gabarit pour créer un contrat pré-rempli.',
            modeleCols, modeles, 'modeles-contrat', 'Aucun modèle de contrat.', instancier,
            <Button size="sm" onClick={() => setCreatingModele(true)}><Plus className="size-4" /> Nouveau modèle</Button>,
          )}
        </TabsContent>
        <TabsContent value="clauses">
          {wrap(
            'Bibliothèque de clauses',
            'Clauses réutilisables, rattachables aux gabarits et résolues sur chaque contrat.',
            clauseCols, clauses, 'clauses-contrat', 'Aucune clause.', undefined,
            <Button size="sm" onClick={() => setCreatingClause(true)}><Plus className="size-4" /> Nouvelle clause</Button>,
          )}
        </TabsContent>
        <TabsContent value="versions">
          <Card className="mb-3 border-info/40 bg-info/5 p-3 text-sm text-muted-foreground">
            Les versions sont des instantanés IMMUABLES du rendu d’un contrat — jamais modifiées ni supprimées une fois figées.
          </Card>
          {wrap('Versions figées', 'Historique immuable des rendus de contrat (CONTRAT18).', versionCols, versions, 'versions-contrat', 'Aucune version figée.')}
        </TabsContent>
      </Tabs>

      {creatingModele && (
        <CreateModeleDialog
          onClose={() => setCreatingModele(false)}
          onCreated={(m) => { setModeles((cur) => [...cur, m]); setCreatingModele(false) }}
        />
      )}
      {creatingClause && (
        <CreateClauseDialog
          onClose={() => setCreatingClause(false)}
          onCreated={(c) => { setClauses((cur) => [...cur, c]); setCreatingClause(false) }}
        />
      )}
    </div>
  )
}

// WIR9 — création directe d'un gabarit de contrat (`ModeleContrat`) : seul
// `nom` est requis côté backend. Sans ce formulaire, une société neuve (0
// modèle) n'avait AUCUN moyen d'alimenter la bibliothèque depuis l'UI.
function CreateModeleDialog({ onClose, onCreated }) {
  const [nom, setNom] = useState('')
  const [categorie, setCategorie] = useState('')
  const [typeContratDefaut, setTypeContratDefaut] = useState('vente')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!nom.trim()) { setErr('Le nom du modèle est requis.'); return }
    setSaving(true)
    setErr(null)
    try {
      const data = { nom: nom.trim(), type_contrat_defaut: typeContratDefaut }
      if (categorie.trim()) data.categorie = categorie.trim()
      const res = await contratsApi.createModele(data)
      toast.success('Modèle créé.')
      onCreated(res.data)
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouveau modèle de contrat</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="mdl-nom" required>Nom du modèle</Label>
            <Input id="mdl-nom" value={nom} onChange={(e) => setNom(e.target.value)} placeholder="ex. O&M Standard" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="mdl-categorie">Catégorie</Label>
            <Input id="mdl-categorie" value={categorie} onChange={(e) => setCategorie(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="mdl-type">Type de contrat par défaut</Label>
            <select
              id="mdl-type"
              value={typeContratDefaut}
              onChange={(e) => setTypeContratDefaut(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              {CONTRAT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer le modèle'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// WIR9 — création directe d'une clause réutilisable. `titre` et `corps` sont
// requis côté backend (`apps/contrats/models.py::Clause`).
function CreateClauseDialog({ onClose, onCreated }) {
  const [titre, setTitre] = useState('')
  const [typeClause, setTypeClause] = useState('generale')
  const [categorie, setCategorie] = useState('')
  const [corps, setCorps] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!titre.trim() || !corps.trim()) {
      setErr('Le titre et le corps de la clause sont requis.')
      return
    }
    setSaving(true)
    setErr(null)
    try {
      const data = { titre: titre.trim(), type_clause: typeClause, corps: corps.trim() }
      if (categorie.trim()) data.categorie = categorie.trim()
      const res = await contratsApi.createClause(data)
      toast.success('Clause créée.')
      onCreated(res.data)
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouvelle clause</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cls-titre" required>Titre</Label>
            <Input id="cls-titre" value={titre} onChange={(e) => setTitre(e.target.value)} placeholder="ex. Confidentialité générale" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cls-type">Type de clause</Label>
            <select
              id="cls-type"
              value={typeClause}
              onChange={(e) => setTypeClause(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              {TYPE_CLAUSE.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cls-categorie">Catégorie</Label>
            <Input id="cls-categorie" value={categorie} onChange={(e) => setCategorie(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cls-corps" required>Corps de la clause</Label>
            <Textarea id="cls-corps" rows={4} value={corps} onChange={(e) => setCorps(e.target.value)} placeholder="Texte de la clause…" />
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer la clause'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
