import { useEffect, useMemo, useState } from 'react'
import {
  ClipboardCheck, PackageCheck, Play, Calculator, AlertTriangle, CheckCircle2, PlusCircle,
} from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import {
  Tabs, TabsList, TabsTrigger, TabsContent, Badge, Button, Dialog,
  DialogContent, DialogTitle, Textarea, Label, Input, toast,
} from '../../ui'
import { FieldSelect } from './QhseForm'
import { formatDate } from '../../lib/format'
import { QhseResourceList } from './QhseResourceList'
import {
  AuditStatutPill, PlanChantierStatutPill, ProcedureStatutPill,
} from './qhsePills'
import { peutCloturerNotation } from './qhseStatus'

// XQHS3 — verdicts de contrôle réception (miroir `ControleReception.Verdict`).
const VERDICT_OPTS = [
  { value: 'accepte', label: 'Accepté' },
  { value: 'refuse', label: 'Refusé (lève une NCR)' },
  { value: 'quarantaine', label: 'Quarantaine' },
]

function StatuerControleDialog({ controle, onClose, onDone }) {
  const [verdict, setVerdict] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!verdict) { toast.error('Le verdict est requis.'); return }
    setSaving(true)
    try {
      await qhseApi.controlesReception.statuer(controle.id, { verdict, notes })
      toast.success('Verdict enregistré.')
      onDone()
      onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Statuer le contrôle réception</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Verdict</Label>
            <FieldSelect value={verdict} onValueChange={setVerdict} options={VERDICT_OPTS} />
          </div>
          <div>
            <Label>Notes (optionnel)</Label>
            <Textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function ControleReceptionTab() {
  const [statuing, setStatuing] = useState(null)
  const [reload, setReload] = useState(0)

  const plansCols = useMemo(() => [
    { id: 'nom', header: 'Plan de contrôle', accessor: (r) => r.nom },
    { id: 'produit', header: 'Produit', accessor: (r) => r.produit_nom || r.produit || '—' },
    { id: 'categorie', header: 'Catégorie', accessor: (r) => r.categorie_nom || r.categorie || '—' },
    {
      id: 'nb_points', header: 'Points', width: 90, align: 'right',
      accessor: (r) => r.points?.length ?? r.nb_points ?? 0,
    },
    {
      id: 'actif', header: 'Actif', width: 90, align: 'center',
      accessor: (r) => r.actif,
      cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
  ], [])

  const controlesCols = useMemo(() => [
    { id: 'reception_id', header: 'Réception', width: 110, accessor: (r) => r.reception_id ?? '—' },
    { id: 'plan', header: 'Plan', accessor: (r) => r.plan_nom || r.plan },
    { id: 'controleur', header: 'Contrôleur', accessor: (r) => r.controleur_nom || '—' },
    {
      id: 'verdict', header: 'Verdict', width: 140,
      accessor: (r) => r.verdict,
      cell: (v) => (v == null
        ? <Badge tone="warning">En attente</Badge>
        : (
          <Badge tone={v === 'accepte' ? 'success' : v === 'refuse' ? 'danger' : 'warning'}>
            {{ accepte: 'Accepté', refuse: 'Refusé', quarantaine: 'Quarantaine' }[v] ?? v}
          </Badge>
        )),
    },
    {
      id: 'date_controle', header: 'Contrôlé le', width: 130, align: 'right',
      accessor: (r) => r.date_controle, cell: (v) => formatDate(v),
    },
  ], [])

  return (
    <div className="flex flex-col gap-6">
      <QhseResourceList
        title="Plans de contrôle réception"
        subtitle="Bibliothèque de contrôle qualité fournisseur, par produit/catégorie"
        fetcher={() => qhseApi.plansControleReception.list()}
        columns={plansCols}
        exportName="qhse-plans-controle-reception"
      />
      <QhseResourceList
        title="Contrôles réception"
        subtitle="Un verdict refusé lève automatiquement une NCR (pont XQHS3→XQHS2)"
        fetcher={() => qhseApi.controlesReception.list()}
        columns={controlesCols}
        exportName="qhse-controles-reception"
        deps={[reload]}
        rowActions={(r) => (r.verdict
          ? []
          : [{
              id: 'statuer', label: 'Statuer', icon: PackageCheck,
              onClick: () => setStatuing(r),
            }])}
      />
      {statuing && (
        <StatuerControleDialog
          controle={statuing}
          onClose={() => setStatuing(null)}
          onDone={() => setReload((n) => n + 1)}
        />
      )}
    </div>
  )
}

// ── WIR124 — dialogues d'écriture des onglets ITP/Audits/Procédures/Retours ──
// Le backend (instancier ITP, relevés, grilles/audits + calculerScore/leverNcr,
// procédures create/activer, retours + moyenne) était complet et testé mais les
// 4 onglets restaient lecture seule : ces dialogues câblent les helpers
// `qhseApi` déjà prêts. `company`/`auteur` sont posés côté serveur.

const AUDIT_TYPE_OPTS = [
  { value: 'chantier', label: 'Chantier' },
  { value: 'securite', label: 'Sécurité' },
  { value: 'qualite', label: 'Qualité' },
  { value: 'environnement', label: 'Environnement' },
]
const RETOUR_CANAL_OPTS = [
  { value: 'telephone', label: 'Téléphone' },
  { value: 'email', label: 'Email' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'formulaire', label: 'Formulaire' },
  { value: 'visite', label: 'Visite sur site' },
  { value: 'autre', label: 'Autre' },
]

// Charge des options {value,label} pour un <FieldSelect> depuis un fetcher.
function useSelectOptions(fetcher, mapRow) {
  const [options, setOptions] = useState([])
  useEffect(() => {
    let cancelled = false
    fetcher()
      .then((r) => {
        const rows = r?.data?.results ?? r?.data ?? []
        if (!cancelled) setOptions((Array.isArray(rows) ? rows : []).map(mapRow))
      })
      .catch(() => { if (!cancelled) setOptions([]) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return options
}

function InstancierPlanChantierDialog({ onClose, onDone }) {
  const modeles = useSelectOptions(
    () => qhseApi.plansInspection.list(),
    (m) => ({ value: String(m.id), label: `${m.code || ''} ${m.nom}`.trim() }))
  const [modele, setModele] = useState('')
  const [chantierId, setChantierId] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!modele || !chantierId) { toast.error('Modèle et chantier requis.'); return }
    setSaving(true)
    try {
      await qhseApi.plansChantier.instancier({
        modele: Number(modele), chantier_id: Number(chantierId),
      })
      toast.success('Plan chantier instancié.')
      onDone(); onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Instanciation impossible.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Instancier un plan chantier (ITP)</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Modèle ITP</Label>
            <FieldSelect value={modele} onValueChange={setModele} options={modeles} />
          </div>
          <div>
            <Label>Chantier (id)</Label>
            <Input type="number" value={chantierId} onChange={(e) => setChantierId(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Instanciation…' : 'Instancier'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function GrilleAuditDialog({ onClose, onDone }) {
  const [code, setCode] = useState('')
  const [nom, setNom] = useState('')
  const [typeAudit, setTypeAudit] = useState('chantier')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!code.trim() || !nom.trim()) { toast.error('Code et nom requis.'); return }
    setSaving(true)
    try {
      await qhseApi.grillesAudit.create({
        code: code.trim(), nom: nom.trim(), type_audit: typeAudit, actif: true,
      })
      toast.success("Grille d'audit créée.")
      onDone(); onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Création impossible.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Nouvelle grille d'audit</DialogTitle>
        <div className="flex flex-col gap-3">
          <div><Label>Code</Label><Input value={code} onChange={(e) => setCode(e.target.value)} /></div>
          <div><Label>Nom</Label><Input value={nom} onChange={(e) => setNom(e.target.value)} /></div>
          <div>
            <Label>Type d'audit</Label>
            <FieldSelect value={typeAudit} onValueChange={setTypeAudit} options={AUDIT_TYPE_OPTS} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function AuditDialog({ onClose, onDone }) {
  const grilles = useSelectOptions(
    () => qhseApi.grillesAudit.list(),
    (g) => ({ value: String(g.id), label: `${g.code || ''} ${g.nom}`.trim() }))
  const [grille, setGrille] = useState('')
  const [dateAudit, setDateAudit] = useState('')
  const [chantierId, setChantierId] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!grille) { toast.error('La grille est requise.'); return }
    setSaving(true)
    try {
      const payload = { grille: Number(grille) }
      if (dateAudit) payload.date_audit = dateAudit
      if (chantierId) payload.chantier_id = Number(chantierId)
      await qhseApi.audits.create(payload)
      toast.success('Audit démarré.')
      onDone(); onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Création impossible.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Démarrer un audit</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Grille</Label>
            <FieldSelect value={grille} onValueChange={setGrille} options={grilles} />
          </div>
          <div><Label>Date d'audit</Label><Input type="date" value={dateAudit} onChange={(e) => setDateAudit(e.target.value)} /></div>
          <div><Label>Chantier (id, optionnel)</Label><Input type="number" value={chantierId} onChange={(e) => setChantierId(e.target.value)} /></div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Création…' : 'Démarrer'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function ProcedureQualiteDialog({ onClose, onDone }) {
  const [reference, setReference] = useState('')
  const [titre, setTitre] = useState('')
  const [version, setVersion] = useState('1')
  const [contenu, setContenu] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!reference.trim() || !titre.trim()) { toast.error('Référence et titre requis.'); return }
    setSaving(true)
    try {
      await qhseApi.proceduresQualite.create({
        reference: reference.trim(), titre: titre.trim(),
        version: Number(version) || 1, contenu,
      })
      toast.success('Procédure créée (brouillon).')
      onDone(); onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Création impossible.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Nouvelle procédure qualité</DialogTitle>
        <div className="flex flex-col gap-3">
          <div><Label>Référence</Label><Input aria-label="Référence" value={reference} onChange={(e) => setReference(e.target.value)} /></div>
          <div><Label>Titre</Label><Input aria-label="Titre" value={titre} onChange={(e) => setTitre(e.target.value)} /></div>
          <div><Label>Version</Label><Input aria-label="Version" type="number" value={version} onChange={(e) => setVersion(e.target.value)} /></div>
          <div><Label>Contenu (optionnel)</Label><Textarea rows={3} value={contenu} onChange={(e) => setContenu(e.target.value)} /></div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function RetourClientDialog({ onClose, onDone }) {
  const [chantierId, setChantierId] = useState('')
  const [note, setNote] = useState('5')
  const [canal, setCanal] = useState('telephone')
  const [commentaire, setCommentaire] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    const n = Number(note)
    if (!(n >= 1 && n <= 5)) { toast.error('La note doit être entre 1 et 5.'); return }
    setSaving(true)
    try {
      const payload = { note_satisfaction: n, canal, commentaire }
      if (chantierId) payload.chantier_id = Number(chantierId)
      await qhseApi.retoursClient.create(payload)
      toast.success('Retour client enregistré.')
      onDone(); onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Création impossible.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Nouveau retour client</DialogTitle>
        <div className="flex flex-col gap-3">
          <div><Label>Chantier (id, optionnel)</Label><Input type="number" value={chantierId} onChange={(e) => setChantierId(e.target.value)} /></div>
          <div><Label>Note de satisfaction (1-5)</Label><Input type="number" min="1" max="5" value={note} onChange={(e) => setNote(e.target.value)} /></div>
          <div>
            <Label>Canal</Label>
            <FieldSelect value={canal} onValueChange={setCanal} options={RETOUR_CANAL_OPTS} />
          </div>
          <div><Label>Commentaire</Label><Textarea rows={3} value={commentaire} onChange={(e) => setCommentaire(e.target.value)} /></div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function MoyenneRetoursWidget({ deps = [] }) {
  const [data, setData] = useState(null)
  useEffect(() => {
    let cancelled = false
    qhseApi.retoursClient.moyenne()
      .then((r) => { if (!cancelled) setData(r?.data ?? null) })
      .catch(() => { if (!cancelled) setData(null) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  if (!data) return null
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 text-sm" data-testid="retours-moyenne">
      Note moyenne de satisfaction :{' '}
      <strong>{data.moyenne == null ? '—' : `${Number(data.moyenne).toFixed(1)}/5`}</strong>
      {' '}({data.total ?? 0} retour(s))
    </div>
  )
}

/* ============================================================================
   UX31 — Inspections & audits.
   ----------------------------------------------------------------------------
   Regroupe sous onglets les briques ITP / audit / clôture chantier :
   • ITP : modèles de plans d'inspection → points de contrôle → plans chantier
     (avec gating points d'arrêt) → relevés.
   • Audits : grilles → critères → audits → réponses.
   • Fin de chantier : notations (gate de clôture) + procédures qualité +
     retours client.
   Tous les registres sont en lecture/CRUD simple via `QhseResourceList`.
   ========================================================================== */

const boolCell = (v) =>
  v == null
    ? <span className="text-muted-foreground">—</span>
    : <Badge tone={v ? 'success' : 'danger'}>{v ? 'Oui' : 'Non'}</Badge>

export default function Inspections() {
  const [tab, setTab] = useState('itp')
  // WIR124 — état des dialogues d'écriture + compteurs de rechargement par onglet.
  const [dialog, setDialog] = useState(null) // 'instancier' | 'grille' | 'audit' | 'procedure' | 'retour'
  const [reloadItp, setReloadItp] = useState(0)
  const [reloadAudits, setReloadAudits] = useState(0)
  const [reloadProc, setReloadProc] = useState(0)
  const [reloadRetours, setReloadRetours] = useState(0)
  const [busyAudit, setBusyAudit] = useState(null)
  const [busyProc, setBusyProc] = useState(null)

  const calculerScoreAudit = async (audit) => {
    setBusyAudit(audit.id)
    try {
      await qhseApi.audits.calculerScore(audit.id)
      toast.success('Score recalculé.')
      setReloadAudits((n) => n + 1)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Calcul impossible.')
    } finally { setBusyAudit(null) }
  }
  const leverNcrAudit = async (audit) => {
    setBusyAudit(audit.id)
    try {
      await qhseApi.audits.leverNcr(audit.id)
      toast.success('NCR levée(s) pour les réponses non conformes.')
      setReloadAudits((n) => n + 1)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Levée de NCR impossible.')
    } finally { setBusyAudit(null) }
  }
  const activerProcedure = async (proc) => {
    setBusyProc(proc.id)
    try {
      await qhseApi.proceduresQualite.activer(proc.id)
      toast.success('Procédure mise en vigueur.')
      setReloadProc((n) => n + 1)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Activation impossible.')
    } finally { setBusyProc(null) }
  }

  const plansModelesCols = useMemo(() => [
    { id: 'code', header: 'Code', width: 120, accessor: (r) => r.code },
    { id: 'nom', header: 'Modèle ITP', accessor: (r) => r.nom },
    {
      id: 'actif', header: 'Actif', width: 90, align: 'center',
      accessor: (r) => r.actif, cell: boolCell,
    },
  ], [])

  const plansChantierCols = useMemo(() => [
    { id: 'modele_nom', header: 'Modèle', accessor: (r) => r.modele_nom || r.modele },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut, cell: (v) => <PlanChantierStatutPill status={v} />,
    },
    { id: 'nb_releves', header: 'Relevés', width: 90, align: 'right', accessor: (r) => r.nb_releves ?? 0 },
    {
      id: 'peut_avancer', header: 'Points d’arrêt', width: 150, align: 'center',
      accessor: (r) => r.peut_avancer,
      cell: (v, r) =>
        v
          ? <Badge tone="success">Levés</Badge>
          : <Badge tone="danger">{r.nb_hold_points_bloquants ?? 0} bloquant(s)</Badge>,
    },
  ], [])

  const relevesCols = useMemo(() => [
    { id: 'point', header: 'Point', accessor: (r) => r.point_intitule || r.point },
    { id: 'phase', header: 'Phase', width: 130, accessor: (r) => r.point_phase || '—' },
    { id: 'valeur', header: 'Valeur', width: 120, accessor: (r) => r.valeur || '—' },
    {
      id: 'conforme', header: 'Conforme', width: 110, align: 'center',
      accessor: (r) => r.conforme, cell: boolCell,
    },
    {
      id: 'date_releve', header: 'Relevé le', width: 130, align: 'right',
      accessor: (r) => r.date_releve, cell: (v) => formatDate(v),
    },
  ], [])

  const grillesCols = useMemo(() => [
    { id: 'code', header: 'Code', width: 120, accessor: (r) => r.code },
    { id: 'nom', header: 'Grille d’audit', accessor: (r) => r.nom },
    { id: 'nb_criteres', header: 'Critères', width: 100, align: 'right', accessor: (r) => r.nb_criteres ?? 0 },
    {
      id: 'actif', header: 'Actif', width: 90, align: 'center',
      accessor: (r) => r.actif, cell: boolCell,
    },
  ], [])

  const auditsCols = useMemo(() => [
    { id: 'grille', header: 'Grille', accessor: (r) => r.grille_nom || r.grille },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut, cell: (v) => <AuditStatutPill status={v} />,
    },
    {
      id: 'score', header: 'Score', width: 100, align: 'right',
      accessor: (r) => r.score,
      cell: (v) => (v == null ? '—' : `${v} %`),
    },
    {
      id: 'date_audit', header: 'Date', width: 120, align: 'right',
      accessor: (r) => r.date_audit, cell: (v) => formatDate(v),
    },
  ], [])

  const notationsCols = useMemo(() => [
    { id: 'chantier_id', header: 'Chantier', width: 120, accessor: (r) => r.chantier_id ?? '—' },
    {
      id: 'score', header: 'Score', width: 100, align: 'right',
      accessor: (r) => r.score, cell: (v) => (v == null ? '—' : `${v}`),
    },
    { id: 'seuil', header: 'Seuil', width: 90, align: 'right', accessor: (r) => r.seuil_passage ?? '—' },
    {
      id: 'verdict', header: 'Verdict', width: 120,
      accessor: (r) => r.verdict,
      cell: (v) => (v == null ? '—' : (
        <Badge tone={v === 'passe' ? 'success' : 'danger'}>
          {v === 'passe' ? 'Passe' : 'Échec'}
        </Badge>
      )),
    },
    {
      id: 'peut_cloturer', header: 'Clôture autorisée', width: 160, align: 'center',
      accessor: (r) => peutCloturerNotation(r),
      cell: (v) => (
        <Badge tone={v ? 'success' : 'warning'}>{v ? 'Oui' : 'Non'}</Badge>
      ),
    },
  ], [])

  const proceduresCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 130, accessor: (r) => r.reference },
    { id: 'titre', header: 'Procédure', accessor: (r) => r.titre },
    { id: 'version', header: 'V.', width: 70, align: 'right', accessor: (r) => r.version },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut, cell: (v) => <ProcedureStatutPill status={v} />,
    },
  ], [])

  const retoursCols = useMemo(() => [
    { id: 'chantier_id', header: 'Chantier', width: 120, accessor: (r) => r.chantier_id ?? '—' },
    { id: 'note', header: 'Note /5', width: 100, align: 'right', accessor: (r) => r.note_satisfaction ?? '—' },
    { id: 'canal', header: 'Canal', width: 130, accessor: (r) => r.canal_display || r.canal || '—' },
    {
      id: 'traite', header: 'Traité', width: 90, align: 'center',
      accessor: (r) => r.traite, cell: boolCell,
    },
    {
      id: 'date_retour', header: 'Le', width: 120, align: 'right',
      accessor: (r) => r.date_retour, cell: (v) => formatDate(v),
    },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2 className="flex items-center gap-2">
          <ClipboardCheck size={20} strokeWidth={1.75} aria-hidden="true" />
          Inspections & audits
        </h2>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="itp">Plans d’inspection (ITP)</TabsTrigger>
          <TabsTrigger value="audits">Audits</TabsTrigger>
          <TabsTrigger value="cloture">Fin de chantier</TabsTrigger>
          <TabsTrigger value="controle-reception">Contrôle réception</TabsTrigger>
        </TabsList>

        <TabsContent value="itp" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Modèles de plans d’inspection"
            subtitle="Bibliothèque ITP réutilisable"
            fetcher={() => qhseApi.plansInspection.list()}
            columns={plansModelesCols}
            exportName="qhse-plans-inspection"
          />
          <QhseResourceList
            title="Plans chantier"
            subtitle="ITP instanciés — gating des points d’arrêt"
            fetcher={() => qhseApi.plansChantier.list()}
            columns={plansChantierCols}
            exportName="qhse-plans-chantier"
            deps={[reloadItp]}
            actions={(
              <Button size="sm" onClick={() => setDialog('instancier')}>
                <PlusCircle size={15} aria-hidden="true" /> Instancier un plan
              </Button>
            )}
          />
          <QhseResourceList
            title="Relevés de contrôle"
            fetcher={() => qhseApi.releves.list()}
            columns={relevesCols}
            exportName="qhse-releves"
          />
        </TabsContent>

        <TabsContent value="audits" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Grilles d’audit"
            fetcher={() => qhseApi.grillesAudit.list()}
            columns={grillesCols}
            exportName="qhse-grilles-audit"
            deps={[reloadAudits]}
            actions={(
              <Button size="sm" onClick={() => setDialog('grille')}>
                <PlusCircle size={15} aria-hidden="true" /> Nouvelle grille
              </Button>
            )}
          />
          <QhseResourceList
            title="Audits"
            subtitle="Score pondéré % conforme, levée de NCR"
            fetcher={() => qhseApi.audits.list()}
            columns={auditsCols}
            exportName="qhse-audits"
            deps={[reloadAudits]}
            actions={(
              <Button size="sm" onClick={() => setDialog('audit')}>
                <Play size={15} aria-hidden="true" /> Démarrer un audit
              </Button>
            )}
            rowActions={(r) => [
              {
                id: 'calculer-score', label: 'Calculer le score', icon: Calculator,
                disabled: busyAudit === r.id, onClick: () => calculerScoreAudit(r),
              },
              {
                id: 'lever-ncr', label: 'Lever NCR', icon: AlertTriangle,
                disabled: busyAudit === r.id, onClick: () => leverNcrAudit(r),
              },
            ]}
          />
        </TabsContent>

        <TabsContent value="cloture" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Notations fin de chantier"
            subtitle="Gate advisory de clôture (verdict + seuil de passage)"
            fetcher={() => qhseApi.notationsFinChantier.list()}
            columns={notationsCols}
            exportName="qhse-notations"
          />
          <QhseResourceList
            title="Procédures qualité"
            subtitle="Documents versionnés (brouillon → en vigueur → obsolète)"
            fetcher={() => qhseApi.proceduresQualite.list()}
            columns={proceduresCols}
            exportName="qhse-procedures"
            deps={[reloadProc]}
            actions={(
              <Button size="sm" onClick={() => setDialog('procedure')}>
                <PlusCircle size={15} aria-hidden="true" /> Nouvelle procédure
              </Button>
            )}
            rowActions={(r) => (r.statut === 'brouillon'
              ? [{
                  id: 'activer', label: 'Mettre en vigueur', icon: CheckCircle2,
                  disabled: busyProc === r.id, onClick: () => activerProcedure(r),
                }]
              : [])}
          />
          <MoyenneRetoursWidget deps={[reloadRetours]} />
          <QhseResourceList
            title="Retours client"
            fetcher={() => qhseApi.retoursClient.list()}
            columns={retoursCols}
            exportName="qhse-retours-client"
            deps={[reloadRetours]}
            actions={(
              <Button size="sm" onClick={() => setDialog('retour')}>
                <PlusCircle size={15} aria-hidden="true" /> Nouveau retour
              </Button>
            )}
          />
        </TabsContent>

        <TabsContent value="controle-reception" className="mt-4">
          <ControleReceptionTab />
        </TabsContent>
      </Tabs>

      {/* WIR124 — dialogues d'écriture */}
      {dialog === 'instancier' && (
        <InstancierPlanChantierDialog
          onClose={() => setDialog(null)}
          onDone={() => setReloadItp((n) => n + 1)}
        />
      )}
      {dialog === 'grille' && (
        <GrilleAuditDialog
          onClose={() => setDialog(null)}
          onDone={() => setReloadAudits((n) => n + 1)}
        />
      )}
      {dialog === 'audit' && (
        <AuditDialog
          onClose={() => setDialog(null)}
          onDone={() => setReloadAudits((n) => n + 1)}
        />
      )}
      {dialog === 'procedure' && (
        <ProcedureQualiteDialog
          onClose={() => setDialog(null)}
          onDone={() => setReloadProc((n) => n + 1)}
        />
      )}
      {dialog === 'retour' && (
        <RetourClientDialog
          onClose={() => setDialog(null)}
          onDone={() => setReloadRetours((n) => n + 1)}
        />
      )}
    </div>
  )
}
