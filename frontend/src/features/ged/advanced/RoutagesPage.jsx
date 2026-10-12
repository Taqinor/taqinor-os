import { useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Label, Input, StatusPill, MultiSelect, Tag, toast,
} from '../../../ui'
import gedApi from '../../../api/gedApi'
import {
  errMessage, toutesLesPages, unpage, useChargementGed, actionAvecToast, actionsActivation,
} from './shared.js'
import { ChampCabinet } from './ChampsGed.jsx'
import DialogueFormulaire from './DialogueFormulaire.jsx'

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
  const [showCreate, setShowCreate] = useState(false)

  const { loading, error, load } = useChargementGed(async () => {
    const [r, c, t] = await Promise.all([
      // ADOC31 — toutes les pages, jamais la seule première.
      toutesLesPages(gedApi.getRoutagesDocumentaires),
      toutesLesPages(gedApi.getCabinets),
      toutesLesPages(gedApi.getTags),
    ])
    setRoutages(unpage(r.data))
    setCabinets(unpage(c.data))
    setTags(unpage(t.data))
  }, 'Impossible de charger les routages.')

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

  const toggleActif = (r) => actionAvecToast(
    () => gedApi.updateRoutageDocumentaire(r.id, { actif: !r.actif }),
    r.actif ? 'Routage désactivé.' : 'Routage activé.', load)

  const supprimer = (r) => actionAvecToast(
    () => gedApi.deleteRoutageDocumentaire(r.id), 'Routage supprimé.', load)

  const rowActions = (r) => actionsActivation(r, toggleActif, supprimer)

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
    <DialogueFormulaire titre="Nouveau routage documentaire" onClose={onClose} submit={submit} saving={saving}>
      <div>
        <Label>Source (code de module)</Label>
        <Input aria-label="Source" placeholder="Ex. paie_bulletin, rh_document, sav_piece_jointe"
          value={source} onChange={(e) => setSource(e.target.value)} />
      </div>
      <ChampCabinet label="Cabinet cible" ariaLabel="Choisir un cabinet cible"
        cabinets={cabinets} cabinetId={cabinetId} setCabinetId={setCabinetId} />
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
    </DialogueFormulaire>
  )
}
