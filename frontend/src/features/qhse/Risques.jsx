import { useMemo, useState } from 'react'
import { ShieldAlert } from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { Tabs, TabsList, TabsTrigger, TabsContent, Badge } from '../../ui'
import { formatDate } from '../../lib/format'
import { QhseResourceList } from './QhseResourceList'
import {
  EvalRisqueStatutPill, PermisStatutPill, LotoStatutPill,
  IncidentStatutPill, IncidentTypePill, GravitePill, CnssStatutPill,
} from './qhsePills'

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
          />
          <QhseResourceList
            title="Analyses d’incident"
            subtitle="Arbre des causes → CAPA"
            fetcher={() => qhseApi.analysesIncident.list()}
            columns={analysesCols}
            exportName="qhse-analyses-incident"
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
