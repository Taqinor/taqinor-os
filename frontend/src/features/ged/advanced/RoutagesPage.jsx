import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2, CheckCircle2, XCircle } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, StatusPill, MultiSelect, Tag, toast,
} from '../../../ui'
import gedApi from '../../../api/gedApi'
import { errMessage } from './shared.js'

/* ============================================================================
   PACT136 — Routage documentaire automatique (ZGED6).
   ----------------------------------------------------------------------------
   Un `source` (code de module libre, ex. `paie_bulletin`) résout un
   `dossier_cible` — chemin en SEGMENTS séparés par `/`, chaque segment
   pouvant porter des jetons `{{ champ }}` résolus par l'émetteur au moment
   de l'envoi (contexte non disponible ici : l'aperçu montre la STRUCTURE des
   segments — statique ou jeton — jamais une valeur résolue inventée). Sans
   réglage pour une source donnée, le comportement reste strictement
   inchangé (no-op).
   ========================================================================== */

function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

function Segments({ dossierCible }) {
  const segments = (dossierCible || '').split('/').filter(Boolean)
  if (segments.length === 0) return <span className="text-muted-foreground">—</span>
  return (
    <div className="flex flex-wrap items-center gap-1">
      {segments.map((seg, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <span className="text-muted-foreground">/</span>}
          {seg.includes('{{') ? <Tag>{seg}</Tag> : <span>{seg}</span>}
        </span>
      ))}
    </div>
  )
}

export default function RoutagesPage() {
  const [routages, setRoutages] = useState([])
  const [cabinets, setCabinets] = useState([])
  const [tags, setTags] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [r, c, t] = await Promise.all([
        gedApi.getRoutagesDocumentaires(),
        gedApi.getCabinets(),
        gedApi.getTags(),
      ])
      setRoutages(unpage(r.data))
      setCabinets(unpage(c.data))
      setTags(unpage(t.data))
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger les routages.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const columns = useMemo(() => [
    { id: 'source', header: 'Source', accessor: (r) => r.source, width: 160 },
    { id: 'cabinet', header: 'Cabinet cible', accessor: (r) => r.cabinet_cible_nom, width: 160 },
    {
      id: 'dossier', header: 'Dossier cible (segments)',
      accessor: (r) => r.dossier_cible, cell: (v) => <Segments dossierCible={v} />,
    },
    {
      id: 'actif', header: 'État', width: 100,
      accessor: (r) => (r.actif ? 'actif' : 'inactif'),
      cell: (v) => <StatusPill status={v} tone={v === 'actif' ? 'success' : 'neutral'} label={v === 'actif' ? 'Actif' : 'Inactif'} />,
    },
  ], [])

  const toggleActif = async (r) => {
    try {
      await gedApi.updateRoutageDocumentaire(r.id, { actif: !r.actif })
      toast.success(r.actif ? 'Routage désactivé.' : 'Routage activé.')
      load()
    } catch (err) { toast.error(errMessage(err)) }
  }

  const rowActions = (r) => [
    r.actif
      ? { id: 'desactiver', label: 'Désactiver', icon: XCircle, onClick: () => toggleActif(r) }
      : { id: 'activer', label: 'Activer', icon: CheckCircle2, onClick: () => toggleActif(r) },
    {
      id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true,
      onClick: async () => {
        try { await gedApi.deleteRoutageDocumentaire(r.id); toast.success('Routage supprimé.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ]

  return (
    <>
      <ListShell
        title="Routage documentaire"
        subtitle="Centralisation automatique des fichiers d'un autre module vers un dossier GED (sans réglage : aucun effet)."
        actions={<Button onClick={() => setShowCreate(true)}><Plus /> Nouveau routage</Button>}
        columns={columns} rows={routages} loading={loading} error={error}
        rowActions={rowActions} searchable exportName="routages-documentaires"
        emptyTitle="Aucun routage" emptyDescription="Créez un routage pour centraliser les fichiers d'un module."
      />

      {showCreate && (
        <CreateRoutageDialog
          cabinets={cabinets} tags={tags}
          onClose={() => setShowCreate(false)}
          onDone={() => { setShowCreate(false); load() }}
        />
      )}
    </>
  )
}

// ── Dialogue ──────────────────────────────────────────────────────────────

function CreateRoutageDialog({ cabinets, tags, onClose, onDone }) {
  const [source, setSource] = useState('')
  const [cabinetId, setCabinetId] = useState('')
  const [dossierCible, setDossierCible] = useState('')
  const [tagIds, setTagIds] = useState([])
  const [saving, setSaving] = useState(false)

  const tagOptions = useMemo(
    () => tags.map((t) => ({ value: String(t.id), label: t.nom })),
    [tags],
  )

  const submit = async () => {
    if (!source.trim()) { toast.error('Source requise (code de module).'); return }
    if (!cabinetId) { toast.error('Choisissez un cabinet cible.'); return }
    if (!dossierCible.trim()) { toast.error('Dossier cible requis.'); return }
    setSaving(true)
    try {
      await gedApi.createRoutageDocumentaire({
        source: source.trim(),
        cabinet_cible: cabinetId,
        dossier_cible: dossierCible.trim(),
        tags_defaut: tagIds,
      })
      toast.success('Routage créé.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouveau routage documentaire</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Source (code de module)</Label>
            <Input aria-label="Source" placeholder="Ex. paie_bulletin, rh_document, sav_piece_jointe"
              value={source} onChange={(e) => setSource(e.target.value)} />
          </div>
          <div>
            <Label>Cabinet cible</Label>
            <Select value={cabinetId} onValueChange={setCabinetId}>
              <SelectTrigger aria-label="Choisir un cabinet cible"><SelectValue placeholder="Choisir un cabinet…" /></SelectTrigger>
              <SelectContent>
                {cabinets.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Dossier cible</Label>
            <Input aria-label="Dossier cible" placeholder="Ex. Paie/{{ annee }}"
              value={dossierCible} onChange={(e) => setDossierCible(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="routage-tags">Tags par défaut (optionnels)</Label>
            <MultiSelect
              id="routage-tags" options={tagOptions} value={tagIds} onChange={setTagIds}
              placeholder="Choisir des tags…"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
