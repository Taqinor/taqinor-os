import { useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Label, Input, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, StatusPill, toast,
} from '../../../ui'
import gedApi from '../../../api/gedApi'
import rolesApi from '../../../api/rolesApi'
import {
  errMessage, toutesLesPages, unpage, resumeCondition, useChargementGed, actionAvecToast, actionsActivation,
} from './shared.js'
import DialogueFormulaire from './DialogueFormulaire.jsx'
import ConditionOperateurValeur from './ConditionOperateurValeur.jsx'

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

function niveauLabel(niveau) {
  return NIVEAUX.find((n) => n.value === niveau)?.label || niveau
}

export default function ReglesAclPage() {
  const [regles, setRegles] = useState([])
  const [roles, setRoles] = useState([])
  const [showCreate, setShowCreate] = useState(false)

  const { loading, error, load } = useChargementGed(async () => {
    const [r, ro] = await Promise.all([
      // ADOC31 — toutes les pages, jamais la seule première.
      toutesLesPages(gedApi.getReglesAclMetadonnee),
      rolesApi.getRoles(),
    ])
    setRegles(unpage(r.data))
    setRoles(unpage(ro.data))
  }, 'Impossible de charger les règles ACL.')

  const columns = useMemo(() => [
    { id: 'nom', header: 'Règle', accessor: (r) => r.nom },
    { id: 'condition', header: 'Condition', accessor: (r) => resumeCondition(r.condition_group, OPERATEURS) },
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

  const toggleActif = (r) => actionAvecToast(
    () => gedApi.updateRegleAclMetadonnee(r.id, { actif: !r.actif }),
    r.actif ? 'Règle désactivée.' : 'Règle activée.', load)

  const supprimer = (r) => actionAvecToast(
    () => gedApi.deleteRegleAclMetadonnee(r.id), 'Règle supprimée.', load)

  const rowActions = (r) => actionsActivation(r, toggleActif, supprimer)

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
    <DialogueFormulaire titre="Nouvelle règle d'accès par métadonnée" onClose={onClose} submit={submit} saving={saving}>
      <div>
        <Label>Nom de la règle</Label>
        <Input aria-label="Nom de la règle" value={nom} onChange={(e) => setNom(e.target.value)} />
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <ConditionOperateurValeur
          champ={champ} setChamp={setChamp} placeholder="Ex. tags, type, custom_data.confidentiel" champClassName="w-56"
          operateurs={OPERATEURS} operateur={operateur} setOperateur={setOperateur}
          valeur={valeur} setValeur={setValeur}
        />
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
    </DialogueFormulaire>
  )
}
