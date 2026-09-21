import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2, History, CheckCircle2, XCircle } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, StatusPill, toast,
} from '../../../ui'
import { formatDateTime } from '../../../lib/format'
import gedApi from '../../../api/gedApi'
import { errMessage } from './shared.js'

/* ============================================================================
   PACT132 — Règles de dossier : action automatique au dépôt (XGED19).
   ----------------------------------------------------------------------------
   Une règle évalue une condition SIMPLE champ/valeur (v1, `core.rules`, une
   feuille unique) contre les métadonnées d'un document déposé dans son
   dossier, et déclenche une SÉQUENCE d'actions ordonnée si elle matche —
   best-effort côté serveur (une action en échec est journalisée sans jamais
   bloquer l'upload). Le journal des dernières exécutions vient de l'action
   dédiée `regles-dossier/<id>/executions/` (lecture seule).
   ========================================================================== */

const OPERATEURS = [
  { value: 'eq', label: '= égal à' },
  { value: 'ne', label: '≠ différent de' },
  { value: 'gt', label: '> supérieur à' },
  { value: 'gte', label: '≥ supérieur ou égal à' },
  { value: 'lt', label: '< inférieur à' },
  { value: 'lte', label: '≤ inférieur ou égal à' },
  { value: 'in', label: 'dans la liste (valeurs séparées par ,)' },
  { value: 'not_in', label: 'absent de la liste (valeurs séparées par ,)' },
  { value: 'contains', label: 'contient' },
  { value: 'startswith', label: 'commence par' },
  { value: 'exists', label: 'le champ existe' },
]

const TYPES_ACTION = [
  { value: 'tag', label: 'Ajouter un tag' },
  { value: 'deplacer', label: 'Déplacer vers un dossier' },
  { value: 'proprietaire', label: 'Assigner un propriétaire' },
  { value: 'demander_approbation', label: 'Demander une approbation' },
  { value: 'demander_signature', label: 'Demander une signature' },
]

function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

function operateurLabel(op) {
  return OPERATEURS.find((o) => o.value === op)?.label || op
}

function actionLabel(type) {
  return TYPES_ACTION.find((t) => t.value === type)?.label || type
}

function resumeCondition(conditionGroup) {
  const leaf = conditionGroup?.conditions?.[0]
  if (!leaf?.field) return '—'
  if (leaf.operator === 'exists') return `${leaf.field} existe`
  const val = Array.isArray(leaf.value) ? leaf.value.join(', ') : leaf.value
  return `${leaf.field} ${operateurLabel(leaf.operator)} ${val ?? ''}`.trim()
}

export default function ReglesDossierPage() {
  const [regles, setRegles] = useState([])
  const [dossiers, setDossiers] = useState([])
  const [tags, setTags] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [journalFor, setJournalFor] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [r, d, t, u] = await Promise.all([
        gedApi.getReglesDossier(),
        gedApi.getDossiers(),
        gedApi.getTags(),
        gedApi.getUsers(),
      ])
      setRegles(unpage(r.data))
      setDossiers(unpage(d.data))
      setTags(unpage(t.data))
      setUsers(unpage(u.data))
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger les règles de dossier.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const columns = useMemo(() => [
    { id: 'nom', header: 'Règle', accessor: (r) => r.nom },
    { id: 'folder', header: 'Dossier', accessor: (r) => r.folder_nom, width: 160 },
    { id: 'condition', header: 'Condition', accessor: (r) => resumeCondition(r.condition_group) },
    {
      id: 'actions_count', header: 'Actions', width: 90, align: 'right',
      accessor: (r) => r.actions?.length ?? 0,
    },
    { id: 'ordre', header: 'Ordre', width: 80, align: 'right', accessor: (r) => r.ordre },
    {
      id: 'actif', header: 'État', width: 100,
      accessor: (r) => (r.actif ? 'actif' : 'inactif'),
      cell: (v) => <StatusPill status={v} tone={v === 'actif' ? 'success' : 'neutral'} label={v === 'actif' ? 'Active' : 'Inactive'} />,
    },
  ], [])

  const toggleActif = async (r) => {
    try {
      await gedApi.updateRegleDossier(r.id, { actif: !r.actif })
      toast.success(r.actif ? 'Règle désactivée.' : 'Règle activée.')
      load()
    } catch (err) { toast.error(errMessage(err)) }
  }

  const rowActions = (r) => [
    { id: 'journal', label: 'Journal d’exécution', icon: History, onClick: () => setJournalFor(r) },
    r.actif
      ? { id: 'desactiver', label: 'Désactiver', icon: XCircle, onClick: () => toggleActif(r) }
      : { id: 'activer', label: 'Activer', icon: CheckCircle2, onClick: () => toggleActif(r) },
    {
      id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true,
      onClick: async () => {
        try { await gedApi.deleteRegleDossier(r.id); toast.success('Règle supprimée.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ]

  return (
    <>
      <ListShell
        title="Règles de dossier"
        subtitle="Action automatique au dépôt d'un document (condition champ/valeur → séquence d'actions)."
        actions={<Button onClick={() => setShowCreate(true)}><Plus /> Nouvelle règle</Button>}
        columns={columns} rows={regles} loading={loading} error={error}
        rowActions={rowActions} searchable exportName="regles-dossier"
        emptyTitle="Aucune règle de dossier" emptyDescription="Créez une règle pour automatiser le classement au dépôt."
      />

      {showCreate && (
        <CreateRegleDialog
          dossiers={dossiers} tags={tags} users={users}
          onClose={() => setShowCreate(false)}
          onDone={() => { setShowCreate(false); load() }}
        />
      )}
      {journalFor && (
        <JournalDialog regle={journalFor} onClose={() => setJournalFor(null)} />
      )}
    </>
  )
}

// ── Dialogues ─────────────────────────────────────────────────────────────

function CreateRegleDialog({ dossiers, tags, users, onClose, onDone }) {
  const [folderId, setFolderId] = useState('')
  const [nom, setNom] = useState('')
  const [ordre, setOrdre] = useState('0')
  const [champ, setChamp] = useState('')
  const [operateur, setOperateur] = useState('eq')
  const [valeur, setValeur] = useState('')
  const [actions, setActions] = useState([])
  // Formulaire d'ajout d'une action.
  const [typeAction, setTypeAction] = useState('tag')
  const [paramTag, setParamTag] = useState('')
  const [paramFolder, setParamFolder] = useState('')
  const [paramUser, setParamUser] = useState('')
  const [paramNom, setParamNom] = useState('')
  const [paramEmail, setParamEmail] = useState('')
  const [saving, setSaving] = useState(false)

  const ajouterAction = () => {
    let params = {}
    if (typeAction === 'tag') {
      if (!paramTag) { toast.error('Choisissez un tag.'); return }
      params = { tag: paramTag }
    } else if (typeAction === 'deplacer') {
      if (!paramFolder) { toast.error('Choisissez un dossier cible.'); return }
      params = { folder: paramFolder }
    } else if (typeAction === 'proprietaire') {
      if (!paramUser) { toast.error('Choisissez un utilisateur.'); return }
      params = { user: paramUser }
    } else if (typeAction === 'demander_signature') {
      if (!paramNom.trim() || !paramEmail.trim()) { toast.error('Nom et email du signataire requis.'); return }
      params = { signataire_nom: paramNom.trim(), signataire_email: paramEmail.trim() }
    }
    setActions((list) => [...list, { type: typeAction, params }])
    setParamTag(''); setParamFolder(''); setParamUser(''); setParamNom(''); setParamEmail('')
  }

  const retirerAction = (i) => setActions((list) => list.filter((_, idx) => idx !== i))

  const submit = async () => {
    if (!folderId) { toast.error('Choisissez un dossier.'); return }
    if (!nom.trim()) { toast.error('Nom requis.'); return }
    if (!champ.trim()) { toast.error('Le champ de la condition est requis.'); return }
    setSaving(true)
    try {
      const value = ['in', 'not_in'].includes(operateur)
        ? valeur.split(',').map((v) => v.trim()).filter(Boolean)
        : (operateur === 'exists' ? true : valeur)
      await gedApi.createRegleDossier({
        folder: folderId,
        nom: nom.trim(),
        ordre: Number(ordre) || 0,
        condition_group: { op: 'and', conditions: [{ field: champ.trim(), operator: operateur, value }] },
        actions,
      })
      toast.success('Règle créée.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouvelle règle de dossier</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Dossier</Label>
            <Select value={folderId} onValueChange={setFolderId}>
              <SelectTrigger aria-label="Choisir un dossier"><SelectValue placeholder="Choisir un dossier…" /></SelectTrigger>
              <SelectContent>
                {dossiers.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Nom de la règle</Label>
            <Input aria-label="Nom de la règle" value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div>
            <Label>Ordre d'exécution</Label>
            <Input type="number" step="1" value={ordre} onChange={(e) => setOrdre(e.target.value)} />
          </div>

          <p className="text-sm font-medium text-foreground">Condition (déclenche la règle si vraie)</p>
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <Label>Champ</Label>
              <Input aria-label="Champ de la condition" placeholder="Ex. nom, tags, custom_data.type"
                value={champ} onChange={(e) => setChamp(e.target.value)} className="w-48" />
            </div>
            <div>
              <Label>Opérateur</Label>
              <Select value={operateur} onValueChange={setOperateur}>
                <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {OPERATEURS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {operateur !== 'exists' && (
              <div>
                <Label>Valeur</Label>
                <Input aria-label="Valeur de la condition" value={valeur} onChange={(e) => setValeur(e.target.value)} className="w-40" />
              </div>
            )}
          </div>

          <p className="text-sm font-medium text-foreground">Actions (exécutées en séquence)</p>
          {actions.length > 0 && (
            <ul className="flex flex-col gap-1">
              {actions.map((a, i) => (
                <li key={i} className="flex items-center justify-between text-sm">
                  <span>{i + 1}. {actionLabel(a.type)}
                    {a.type === 'tag' && ` — ${tags.find((t) => t.slug === a.params.tag)?.nom || a.params.tag}`}
                    {a.type === 'deplacer' && ` — ${dossiers.find((d) => String(d.id) === String(a.params.folder))?.nom || a.params.folder}`}
                    {a.type === 'proprietaire' && ` — ${users.find((u) => String(u.id) === String(a.params.user))?.username || a.params.user}`}
                    {a.type === 'demander_signature' && ` — ${a.params.signataire_nom}`}
                  </span>
                  <Button variant="ghost" size="icon" type="button" aria-label={`Retirer l'action ${i + 1}`} onClick={() => retirerAction(i)}>
                    <Trash2 />
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <Label>Type d'action</Label>
              <Select value={typeAction} onValueChange={setTypeAction}>
                <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TYPES_ACTION.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {typeAction === 'tag' && (
              <Select value={paramTag} onValueChange={setParamTag}>
                <SelectTrigger aria-label="Choisir un tag" className="w-40"><SelectValue placeholder="Tag…" /></SelectTrigger>
                <SelectContent>
                  {tags.map((t) => <SelectItem key={t.id} value={t.slug}>{t.nom}</SelectItem>)}
                </SelectContent>
              </Select>
            )}
            {typeAction === 'deplacer' && (
              <Select value={paramFolder} onValueChange={setParamFolder}>
                <SelectTrigger aria-label="Choisir un dossier cible" className="w-40"><SelectValue placeholder="Dossier…" /></SelectTrigger>
                <SelectContent>
                  {dossiers.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.nom}</SelectItem>)}
                </SelectContent>
              </Select>
            )}
            {typeAction === 'proprietaire' && (
              <Select value={paramUser} onValueChange={setParamUser}>
                <SelectTrigger aria-label="Choisir un utilisateur" className="w-40"><SelectValue placeholder="Utilisateur…" /></SelectTrigger>
                <SelectContent>
                  {users.map((u) => <SelectItem key={u.id} value={String(u.id)}>{u.username || u.email}</SelectItem>)}
                </SelectContent>
              </Select>
            )}
            {typeAction === 'demander_signature' && (
              <>
                <Input placeholder="Nom du signataire" value={paramNom} className="w-40" onChange={(e) => setParamNom(e.target.value)} />
                <Input placeholder="Email" type="email" value={paramEmail} className="w-44" onChange={(e) => setParamEmail(e.target.value)} />
              </>
            )}
            <Button variant="outline" size="sm" type="button" onClick={ajouterAction}>
              <Plus /> Ajouter l'action
            </Button>
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

function JournalDialog({ regle, onClose }) {
  const [executions, setExecutions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    gedApi.getExecutionsRegleDossier(regle.id)
      .then((res) => setExecutions(unpage(res.data)))
      .catch((err) => setError(errMessage(err, 'Impossible de charger le journal.')))
      .finally(() => setLoading(false))
  }, [regle.id])

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Journal d’exécution — {regle.nom}</DialogTitle></DialogHeader>
        {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && executions.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune exécution pour cette règle.</p>
        )}
        {!loading && executions.length > 0 && (
          <ul className="flex flex-col gap-2">
            {executions.map((e) => (
              <li key={e.id} className="text-sm">
                <span className="font-medium">{e.document_nom || `#${e.document}`}</span>
                {' — '}
                <StatusPill status={e.declenchee ? 'declenchee' : 'non_declenchee'}
                  tone={e.declenchee ? 'success' : 'neutral'}
                  label={e.declenchee ? 'Déclenchée' : 'Non déclenchée'} />
                {' '}
                <span className="text-muted-foreground">{formatDateTime(e.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
