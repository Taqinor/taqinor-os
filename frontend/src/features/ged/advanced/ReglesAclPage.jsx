import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2, CheckCircle2, XCircle } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, StatusPill, toast,
} from '../../../ui'
import gedApi from '../../../api/gedApi'
import rolesApi from '../../../api/rolesApi'
import { errMessage } from './shared.js'

/* ============================================================================
   PACT133 — Règles d'accès par métadonnée (XGED21, couche dynamique).
   ----------------------------------------------------------------------------
   Une règle accorde un niveau d'accès à un RÔLE (jamais un utilisateur nommé)
   si une condition simple champ/valeur matche les métadonnées d'un document
   (tags/type/custom_data) — recalculée à CHAQUE LECTURE (`selectors.
   acl_effective`), aucune ligne matérialisée. Sujet d'accès documentaire :
   le dépôt le documente lui-même comme « en attente d'arbitrage du fondateur »
   — cette tâche EST cet arbitrage.
   ========================================================================== */

const OPERATEURS = [
  { value: 'eq', label: '= égal à' },
  { value: 'ne', label: '≠ différent de' },
  { value: 'in', label: 'dans la liste (valeurs séparées par ,)' },
  { value: 'not_in', label: 'absent de la liste (valeurs séparées par ,)' },
  { value: 'contains', label: 'contient' },
  { value: 'startswith', label: 'commence par' },
  { value: 'exists', label: 'le champ existe' },
]

const NIVEAUX = [
  { value: 'lecture', label: 'Lecture' },
  { value: 'ecriture', label: 'Écriture' },
  { value: 'gestion', label: 'Gestion' },
]

function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

function operateurLabel(op) {
  return OPERATEURS.find((o) => o.value === op)?.label || op
}

function niveauLabel(niveau) {
  return NIVEAUX.find((n) => n.value === niveau)?.label || niveau
}

function resumeCondition(conditionGroup) {
  const leaf = conditionGroup?.conditions?.[0]
  if (!leaf?.field) return '—'
  if (leaf.operator === 'exists') return `${leaf.field} existe`
  const val = Array.isArray(leaf.value) ? leaf.value.join(', ') : leaf.value
  return `${leaf.field} ${operateurLabel(leaf.operator)} ${val ?? ''}`.trim()
}

export default function ReglesAclPage() {
  const [regles, setRegles] = useState([])
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [r, ro] = await Promise.all([
        gedApi.getReglesAclMetadonnee(),
        rolesApi.getRoles(),
      ])
      setRegles(unpage(r.data))
      setRoles(unpage(ro.data))
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger les règles ACL.'))
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
    { id: 'condition', header: 'Condition', accessor: (r) => resumeCondition(r.condition_group) },
    { id: 'role', header: 'Rôle cible', accessor: (r) => r.role_nom, width: 160 },
    {
      id: 'niveau', header: 'Niveau', width: 110,
      accessor: (r) => r.niveau, cell: (v) => niveauLabel(v),
    },
    { id: 'priorite', header: 'Priorité', width: 90, align: 'right', accessor: (r) => r.priorite },
    {
      id: 'actif', header: 'État', width: 100,
      accessor: (r) => (r.actif ? 'actif' : 'inactif'),
      cell: (v) => <StatusPill status={v} tone={v === 'actif' ? 'success' : 'neutral'} label={v === 'actif' ? 'Active' : 'Inactive'} />,
    },
  ], [])

  const toggleActif = async (r) => {
    try {
      await gedApi.updateRegleAclMetadonnee(r.id, { actif: !r.actif })
      toast.success(r.actif ? 'Règle désactivée.' : 'Règle activée.')
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
        try { await gedApi.deleteRegleAclMetadonnee(r.id); toast.success('Règle supprimée.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ]

  return (
    <>
      <ListShell
        title="Règles d'accès par métadonnée"
        subtitle="Accès automatique par rôle selon une condition sur les tags/type/données du document (recalculé à chaque lecture)."
        actions={<Button onClick={() => setShowCreate(true)}><Plus /> Nouvelle règle</Button>}
        columns={columns} rows={regles} loading={loading} error={error}
        rowActions={rowActions} searchable exportName="regles-acl-metadonnee"
        emptyTitle="Aucune règle ACL par métadonnée" emptyDescription="Créez une règle pour accorder un accès automatique par rôle."
      />

      {showCreate && (
        <CreateRegleAclDialog
          roles={roles}
          onClose={() => setShowCreate(false)}
          onDone={() => { setShowCreate(false); load() }}
        />
      )}
    </>
  )
}

// ── Dialogue ──────────────────────────────────────────────────────────────

function CreateRegleAclDialog({ roles, onClose, onDone }) {
  const [nom, setNom] = useState('')
  const [champ, setChamp] = useState('')
  const [operateur, setOperateur] = useState('eq')
  const [valeur, setValeur] = useState('')
  const [roleId, setRoleId] = useState('')
  const [niveau, setNiveau] = useState('lecture')
  const [priorite, setPriorite] = useState('0')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!nom.trim()) { toast.error('Nom requis.'); return }
    if (!champ.trim()) { toast.error('Le champ de la condition est requis.'); return }
    if (!roleId) { toast.error('Choisissez un rôle cible.'); return }
    setSaving(true)
    try {
      const value = ['in', 'not_in'].includes(operateur)
        ? valeur.split(',').map((v) => v.trim()).filter(Boolean)
        : (operateur === 'exists' ? true : valeur)
      await gedApi.createRegleAclMetadonnee({
        nom: nom.trim(),
        condition_group: { op: 'and', conditions: [{ field: champ.trim(), operator: operateur, value }] },
        role: roleId,
        niveau,
        priorite: Number(priorite) || 0,
      })
      toast.success('Règle créée.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouvelle règle d'accès par métadonnée</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Nom de la règle</Label>
            <Input aria-label="Nom de la règle" value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <Label>Champ</Label>
              <Input aria-label="Champ de la condition" placeholder="Ex. tags, type, custom_data.confidentiel"
                value={champ} onChange={(e) => setChamp(e.target.value)} className="w-56" />
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
          <div>
            <Label>Rôle cible</Label>
            <Select value={roleId} onValueChange={setRoleId}>
              <SelectTrigger aria-label="Choisir un rôle cible"><SelectValue placeholder="Choisir un rôle…" /></SelectTrigger>
              <SelectContent>
                {roles.map((r) => <SelectItem key={r.id} value={String(r.id)}>{r.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Niveau d'accès</Label>
            <Select value={niveau} onValueChange={setNiveau}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {NIVEAUX.map((n) => <SelectItem key={n.value} value={n.value}>{n.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Priorité</Label>
            <Input type="number" step="1" value={priorite} onChange={(e) => setPriorite(e.target.value)} />
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
