import { useMemo, useState } from 'react'
import { ClipboardCheck, PackageCheck } from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import {
  Tabs, TabsList, TabsTrigger, TabsContent, Badge, Button, Dialog,
  DialogContent, DialogTitle, Textarea, Label, toast,
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
          />
          <QhseResourceList
            title="Audits"
            subtitle="Score pondéré % conforme, levée de NCR"
            fetcher={() => qhseApi.audits.list()}
            columns={auditsCols}
            exportName="qhse-audits"
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
          />
          <QhseResourceList
            title="Retours client"
            fetcher={() => qhseApi.retoursClient.list()}
            columns={retoursCols}
            exportName="qhse-retours-client"
          />
        </TabsContent>

        <TabsContent value="controle-reception" className="mt-4">
          <ControleReceptionTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
