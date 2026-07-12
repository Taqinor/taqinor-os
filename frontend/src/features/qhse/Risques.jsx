import { useMemo, useState } from 'react'
import {
  ShieldAlert, ListChecks, CheckCircle2, QrCode, Plus, Wrench, AlertOctagon,
} from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
import {
  Tabs, TabsList, TabsTrigger, TabsContent, Badge, Dialog, DialogContent,
  DialogTitle, Button, Input, Label, toast,
} from '../../ui'
import { formatDate } from '../../lib/format'
import { QhseResourceList } from './QhseResourceList'
import { useQhseList } from './useQhseList'
import {
  EvalRisqueStatutPill, PermisStatutPill, LotoStatutPill,
  IncidentStatutPill, IncidentTypePill, GravitePill, CnssStatutPill,
} from './qhsePills'

// XQHS16 — création d'un lien de signalement QR public par chantier.
function CreerLienSignalementDialog({ onClose, onCreated }) {
  const [libelle, setLibelle] = useState('')
  const [chantierId, setChantierId] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!libelle.trim()) { toast.error('Le libellé est requis.'); return }
    setSaving(true)
    try {
      await qhseApi.liensSignalement.create({
        libelle: libelle.trim(),
        chantier_id: chantierId ? Number(chantierId) : null,
      })
      toast.success('Lien de signalement créé.')
      onCreated()
      onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>Nouveau lien de signalement QR</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Libellé</Label>
            <Input value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          </div>
          <div>
            <Label>Chantier (id, optionnel)</Label>
            <Input value={chantierId} onChange={(e) => setChantierId(e.target.value)} inputMode="numeric" />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? 'Création…' : 'Créer'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

async function telechargerQr(lien) {
  const pending = downloadBlobInGesture()
  try {
    const res = await qhseApi.liensSignalement.qr(lien.id)
    pending.deliver(new Blob([res.data]), `signalement-qr-${lien.token?.slice(0, 8) || lien.id}.png`)
  } catch {
    toast.error('Génération QR indisponible.')
  }
}

// XQHS1 — checklist des étapes légales AT/MP (loi 18-12), dialog rattaché à
// une déclaration CNSS.
function EtapesDeclarationDialog({ declaration, onClose }) {
  const { rows, loading, reload } = useQhseList(
    () => qhseApi.etapesDeclarationAt.list({ declaration: declaration.id }),
    [declaration.id],
  )

  async function marquerFait(etape) {
    try {
      await qhseApi.etapesDeclarationAt.marquerFait(etape.id)
      toast.success('Étape marquée faite.')
      reload()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Enregistrement impossible.')
    }
  }

  const STATUT_TONE = { a_faire: 'warning', fait: 'success', hors_delai: 'danger' }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogTitle>
          Checklist légale AT/MP — {declaration.numero_declaration || `#${declaration.id}`}
        </DialogTitle>
        <div className="flex flex-col gap-2">
          {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
          {!loading && rows.length === 0 && (
            <p className="text-sm text-muted-foreground">Aucune étape instanciée.</p>
          )}
          <ul className="flex flex-col gap-2">
            {rows.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-2 rounded-md border border-border p-2.5">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium">{e.type_etape_display || e.type_etape}</span>
                  <span className="text-xs text-muted-foreground">
                    Échéance {formatDate(e.echeance)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={STATUT_TONE[e.statut] ?? 'neutral'}>{e.statut_display || e.statut}</Badge>
                  {e.statut === 'a_faire' && (
                    <Button size="sm" variant="outline" onClick={() => marquerFait(e)}>
                      <CheckCircle2 size={14} /> Fait
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <div className="flex justify-end pt-1">
            <Button variant="outline" onClick={onClose}>Fermer</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

/* ============================================================================
   UX32 — Risques, permis & incidents.
   ----------------------------------------------------------------------------
   Onglets :
   • Document unique : évaluations des risques (matrice criticité) + lignes.
   • Permis & consignation : permis de travail + LOTO.
   • Préparation site : inductions sécurité + plans d'urgence + secouristes.
   • Incidents : registre incidents + déclarations CNSS + analyses de cause.
   ========================================================================== */

const critTone = (c) => (c >= 15 ? 'danger' : c >= 8 ? 'warning' : 'info')

export default function Risques() {
  const [tab, setTab] = useState('document-unique')
  const [cnssChecklist, setCnssChecklist] = useState(null)
  const [creatingLien, setCreatingLien] = useState(false)
  const [liensReload, setLiensReload] = useState(0)

  const evalCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 130, accessor: (r) => r.reference },
    { id: 'titre', header: 'Évaluation', accessor: (r) => r.titre },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    {
      id: 'criticite_max', header: 'Criticité max', width: 130, align: 'center',
      accessor: (r) => r.criticite_max ?? 0,
      cell: (v) => <Badge tone={critTone(v)}>{v}</Badge>,
    },
    { id: 'nb_lignes', header: 'Lignes', width: 90, align: 'right', accessor: (r) => r.nb_lignes ?? 0 },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut, cell: (v) => <EvalRisqueStatutPill status={v} />,
    },
  ], [])

  const permisCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 120, accessor: (r) => r.reference },
    { id: 'titre', header: 'Permis', accessor: (r) => r.titre },
    { id: 'type', header: 'Type', width: 160, accessor: (r) => r.type_permis_display || r.type_permis },
    {
      id: 'statut', header: 'Statut', width: 120,
      accessor: (r) => r.statut, cell: (v) => <PermisStatutPill status={v} />,
    },
    {
      id: 'date_fin', header: 'Fin validité', width: 130, align: 'right',
      accessor: (r) => r.date_fin, cell: (v) => formatDate(v),
    },
  ], [])

  const lotoCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 120, accessor: (r) => r.reference },
    { id: 'equipement', header: 'Équipement', accessor: (r) => r.equipement || '—' },
    { id: 'point', header: 'Point de consignation', accessor: (r) => r.point_consignation || '—' },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut, cell: (v) => <LotoStatutPill status={v} />,
    },
  ], [])

  const inductionsCols = useMemo(() => [
    { id: 'personne', header: 'Personne', accessor: (r) => r.personne_nom || '—' },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    {
      id: 'acquittement', header: 'Acquittée', width: 110, align: 'center',
      accessor: (r) => r.acquittement,
      cell: (v) => <Badge tone={v ? 'success' : 'warning'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
    {
      id: 'date_induction', header: 'Le', width: 120, align: 'right',
      accessor: (r) => r.date_induction, cell: (v) => formatDate(v),
    },
  ], [])

  const plansUrgenceCols = useMemo(() => [
    { id: 'titre', header: 'Plan d’urgence', accessor: (r) => r.titre },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    { id: 'point_rassemblement', header: 'Point de rassemblement', accessor: (r) => r.point_rassemblement || '—' },
    { id: 'nb_secouristes', header: 'Secouristes', width: 110, align: 'right', accessor: (r) => r.nb_secouristes ?? 0 },
  ], [])

  const secouristesCols = useMemo(() => [
    { id: 'nom', header: 'Secouriste', accessor: (r) => r.secouriste_nom || r.nom || '—' },
    { id: 'certification', header: 'Certification', accessor: (r) => r.certification || '—' },
    { id: 'telephone', header: 'Téléphone', width: 150, accessor: (r) => r.telephone || '—' },
    {
      id: 'validite', header: 'Validité', width: 120, align: 'right',
      accessor: (r) => r.validite, cell: (v) => formatDate(v),
    },
  ], [])

  const incidentsCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 120, accessor: (r) => r.reference },
    { id: 'titre', header: 'Incident', accessor: (r) => r.titre },
    {
      id: 'type', header: 'Type', width: 150,
      accessor: (r) => r.type_incident, cell: (v) => <IncidentTypePill status={v} />,
    },
    {
      id: 'gravite', header: 'Gravité', width: 120,
      accessor: (r) => r.gravite, cell: (v) => <GravitePill status={v} />,
    },
    {
      id: 'statut', header: 'Statut', width: 120,
      accessor: (r) => r.statut, cell: (v) => <IncidentStatutPill status={v} />,
    },
    {
      id: 'date_incident', header: 'Date', width: 120, align: 'right',
      accessor: (r) => r.date_incident, cell: (v) => formatDate(v),
    },
  ], [])

  const cnssCols = useMemo(() => [
    { id: 'numero', header: 'N° déclaration', accessor: (r) => r.numero_declaration || '—' },
    {
      id: 'date_accident', header: 'Accident', width: 120, align: 'right',
      accessor: (r) => r.date_accident, cell: (v) => formatDate(v),
    },
    {
      id: 'date_limite', header: 'Échéance légale', width: 150, align: 'right',
      accessor: (r) => r.date_limite, cell: (v) => formatDate(v),
    },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut, cell: (v) => <CnssStatutPill status={v} />,
    },
  ], [])

  const analysesCols = useMemo(() => [
    { id: 'incident', header: 'Incident', accessor: (r) => r.incident_reference || r.incident },
    { id: 'methode', header: 'Méthode', width: 180, accessor: (r) => r.methode_display || r.methode },
    { id: 'nb_causes', header: 'Causes', width: 90, align: 'right', accessor: (r) => r.nb_causes ?? 0 },
    { id: 'nb_capa', header: 'CAPA', width: 80, align: 'right', accessor: (r) => r.nb_capa ?? 0 },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut_display || r.statut },
  ], [])

  // XQHS18 — exercices d'urgence (drills) rattachés aux plans d'urgence.
  const exercicesUrgenceCols = useMemo(() => [
    { id: 'plan', header: 'Plan d’urgence', accessor: (r) => r.plan_titre || r.plan },
    { id: 'type', header: 'Type', width: 150, accessor: (r) => r.type_exercice_display || r.type_exercice },
    {
      id: 'date_prevue', header: 'Prévu le', width: 120, align: 'right',
      accessor: (r) => r.date_prevue, cell: (v) => formatDate(v),
    },
    {
      id: 'date_realisee', header: 'Réalisé le', width: 120, align: 'right',
      accessor: (r) => r.date_realisee, cell: (v) => (v ? formatDate(v) : '—'),
    },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut_display || r.statut },
  ], [])

  // XQHS16 — liens de signalement QR public + signalements reçus.
  const liensCols = useMemo(() => [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    {
      id: 'actif', header: 'Actif', width: 90, align: 'center',
      accessor: (r) => r.actif,
      cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
    { id: 'token', header: 'Jeton', width: 130, accessor: (r) => `${(r.token || '').slice(0, 8)}…` },
  ], [])

  const signalementsCols = useMemo(() => [
    {
      id: 'date', header: 'Reçu le', width: 130, align: 'right',
      accessor: (r) => r.date_creation, cell: (v) => formatDate(v),
    },
    { id: 'type', header: 'Type', width: 120, accessor: (r) => r.type_signalement_display || r.type_signalement },
    { id: 'description', header: 'Description', accessor: (r) => r.description },
    {
      id: 'anonyme', header: 'Anonyme', width: 100, align: 'center',
      accessor: (r) => r.anonyme,
      cell: (v) => <Badge tone={v ? 'neutral' : 'info'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
  ], [])

  // XQHS17 — observations sécurité comportementales (BBS).
  const observationsCols = useMemo(() => [
    {
      id: 'date_observation', header: 'Date', width: 120, align: 'right',
      accessor: (r) => r.date_observation, cell: (v) => formatDate(v),
    },
    { id: 'categorie', header: 'Catégorie', width: 130, accessor: (r) => r.categorie_display || r.categorie },
    { id: 'type', header: 'Type', width: 130, accessor: (r) => r.type_observation_display || r.type_observation },
    { id: 'description', header: 'Description', accessor: (r) => r.description },
    { id: 'chantier_id', header: 'Chantier', width: 110, accessor: (r) => r.chantier_id ?? '—' },
    {
      id: 'feedback_donne', header: 'Feedback donné', width: 130, align: 'center',
      accessor: (r) => r.feedback_donne,
      cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2 className="flex items-center gap-2">
          <ShieldAlert size={20} strokeWidth={1.75} aria-hidden="true" />
          Risques, permis & incidents
        </h2>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="document-unique">Document unique</TabsTrigger>
          <TabsTrigger value="permis">Permis & LOTO</TabsTrigger>
          <TabsTrigger value="preparation">Préparation site</TabsTrigger>
          <TabsTrigger value="incidents">Incidents</TabsTrigger>
          <TabsTrigger value="observations">Observations BBS</TabsTrigger>
          <TabsTrigger value="signalement-qr">Signalement QR</TabsTrigger>
        </TabsList>

        <TabsContent value="document-unique" className="mt-4">
          <QhseResourceList
            title="Évaluations des risques (document unique)"
            subtitle="Matrice de criticité gravité × probabilité"
            fetcher={() => qhseApi.evaluationsRisque.list()}
            columns={evalCols}
            exportName="qhse-evaluations-risque"
          />
        </TabsContent>

        <TabsContent value="permis" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Permis de travail"
            subtitle="Hauteur, point chaud, espace confiné…"
            fetcher={() => qhseApi.permisTravail.list()}
            columns={permisCols}
            exportName="qhse-permis-travail"
          />
          <QhseResourceList
            title="Consignations LOTO"
            fetcher={() => qhseApi.consignationsLoto.list()}
            columns={lotoCols}
            exportName="qhse-loto"
          />
        </TabsContent>

        <TabsContent value="preparation" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Inductions sécurité"
            subtitle="Accueils sécurité (internes & sous-traitants)"
            fetcher={() => qhseApi.inductionsSecurite.list()}
            columns={inductionsCols}
            exportName="qhse-inductions"
          />
          <QhseResourceList
            title="Plans d’urgence"
            fetcher={() => qhseApi.plansUrgence.list()}
            columns={plansUrgenceCols}
            exportName="qhse-plans-urgence"
          />
          <QhseResourceList
            title="Secouristes"
            fetcher={() => qhseApi.secouristes.list()}
            columns={secouristesCols}
            exportName="qhse-secouristes"
          />
          <QhseResourceList
            title="Exercices d'urgence (drills)"
            subtitle="Exigence ISO 45001 8.2 — exercices rattachés aux plans d'urgence"
            fetcher={() => qhseApi.exercicesUrgence.list()}
            columns={exercicesUrgenceCols}
            exportName="qhse-exercices-urgence"
          />
        </TabsContent>

        <TabsContent value="incidents" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Registre des incidents HSE"
            subtitle="Accidents, presqu’accidents, incidents"
            fetcher={() => qhseApi.incidents.list()}
            columns={incidentsCols}
            exportName="qhse-incidents"
          />
          <QhseResourceList
            title="Déclarations CNSS"
            subtitle="Accidents du travail — échéance légale"
            fetcher={() => qhseApi.declarationsCnss.list()}
            columns={cnssCols}
            exportName="qhse-cnss"
            rowActions={(r) => [
              {
                id: 'checklist', label: 'Checklist légale AT/MP', icon: ListChecks,
                onClick: () => setCnssChecklist(r),
              },
            ]}
          />
          <QhseResourceList
            title="Analyses d’incident"
            subtitle="Arbre des causes → CAPA"
            fetcher={() => qhseApi.analysesIncident.list()}
            columns={analysesCols}
            exportName="qhse-analyses-incident"
          />
        </TabsContent>

        <TabsContent value="observations" className="mt-4">
          <QhseResourceList
            title="Observations sécurité comportementales (BBS)"
            subtitle="Capture terrain rapide — conversion en un clic vers CAPA/NCR"
            fetcher={() => qhseApi.observationsSecurite.list()}
            columns={observationsCols}
            exportName="qhse-observations-securite"
            rowActions={(r) => [
              {
                id: 'capa', label: 'Convertir en CAPA', icon: Wrench,
                onClick: async () => {
                  try {
                    await qhseApi.observationsSecurite.convertirCapa(r.id, {})
                    toast.success('CAPA créée depuis l’observation.')
                  } catch (err) {
                    toast.error(err?.response?.data?.detail ?? 'Conversion impossible.')
                  }
                },
              },
              {
                id: 'ncr', label: 'Convertir en NCR', icon: AlertOctagon,
                onClick: async () => {
                  try {
                    await qhseApi.observationsSecurite.convertirNcr(r.id, {})
                    toast.success('NCR créée depuis l’observation.')
                  } catch (err) {
                    toast.error(err?.response?.data?.detail ?? 'Conversion impossible.')
                  }
                },
              },
            ]}
          />
        </TabsContent>

        <TabsContent value="signalement-qr" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Liens de signalement QR"
            subtitle="Signalement danger/incident chantier sans compte — imprimer le QR sur site"
            fetcher={() => qhseApi.liensSignalement.list()}
            columns={liensCols}
            exportName="qhse-liens-signalement"
            deps={[liensReload]}
            actions={
              <Button onClick={() => setCreatingLien(true)}>
                <Plus size={16} /> Nouveau lien
              </Button>
            }
            rowActions={(r) => [
              { id: 'qr', label: 'Générer QR', icon: QrCode, onClick: () => telechargerQr(r) },
            ]}
          />
          <QhseResourceList
            title="Signalements reçus"
            subtitle="Danger/incident signalés via QR chantier (lecture interne)"
            fetcher={() => qhseApi.signalementsPublics.list()}
            columns={signalementsCols}
            exportName="qhse-signalements-publics"
          />
        </TabsContent>
      </Tabs>

      {creatingLien && (
        <CreerLienSignalementDialog
          onClose={() => setCreatingLien(false)}
          onCreated={() => setLiensReload((n) => n + 1)}
        />
      )}

      {cnssChecklist && (
        <EtapesDeclarationDialog
          declaration={cnssChecklist}
          onClose={() => setCnssChecklist(null)}
        />
      )}
    </div>
  )
}
