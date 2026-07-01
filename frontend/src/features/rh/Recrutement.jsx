import { useEffect, useMemo, useState } from 'react'
import { UserPlus, Ban } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Segmented, Badge, toast } from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'
import {
  EtapeCandidature, StatutPoste, StatutSanction, StatutEvaluation,
} from './constants.jsx'

/* ============================================================================
   UX26 — EPI, recrutement & évaluations.
   ----------------------------------------------------------------------------
   Regroupe sous onglets : Catalogue EPI + dotations, ATS léger (ouvertures de
   poste → candidatures → embauche), campagnes & évaluations, sanctions. Les
   transitions (embaucher / valider / annuler) passent par les @actions serveur.
   ========================================================================== */

const VUES = [
  { value: 'epi', label: 'EPI' },
  { value: 'recrutement', label: 'Recrutement' },
  { value: 'evaluations', label: 'Évaluations' },
  { value: 'sanctions', label: 'Sanctions' },
]

export default function Recrutement() {
  const { confirm, confirmDelete } = useConfirmDialog()
  const [vue, setVue] = useState('epi')

  const [epiCat, setEpiCat] = useState([])
  const [dotations, setDotations] = useState([])
  const [postes, setPostes] = useState([])
  const [candidatures, setCandidatures] = useState([])
  const [campagnes, setCampagnes] = useState([])
  const [evaluations, setEvaluations] = useState([])
  const [sanctions, setSanctions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const recharger = () => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([
      rhApi.getEpiCatalogue(),
      rhApi.getDotationsEpi(),
      rhApi.getOuverturesPoste(),
      rhApi.getCandidatures(),
      rhApi.getCampagnesEvaluation(),
      rhApi.getEvaluationsEmploye(),
      rhApi.getSanctions(),
    ])
      .then(([ec, dt, op, ca, cp, ev, sa]) => {
        if (!vivant) return
        setEpiCat(unwrap(ec.data))
        setDotations(unwrap(dt.data))
        setPostes(unwrap(op.data))
        setCandidatures(unwrap(ca.data))
        setCampagnes(unwrap(cp.data))
        setEvaluations(unwrap(ev.data))
        setSanctions(unwrap(sa.data))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger le module recrutement/EPI.')
        toast.error('Impossible de charger le module recrutement/EPI.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(recharger, [])

  const embaucher = async (c) => {
    const ok = await confirm({
      title: `Embaucher ${c.nom} ?`,
      description: 'Un dossier employé sera créé à partir de cette candidature.',
      confirmLabel: 'Embaucher',
      destructive: false,
    })
    if (!ok) return
    try {
      await rhApi.embaucherCandidat(c.id, {})
      toast.success('Candidat embauché — dossier créé.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Embauche impossible (matricule/contrat requis).')
    }
  }

  const validerEval = async (e) => {
    try {
      await rhApi.validerEvaluation(e.id)
      toast.success('Évaluation validée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Validation impossible.')
    }
  }

  const annulerSanction = async (s) => {
    const ok = await confirmDelete({
      title: 'Annuler cette sanction ?',
      description: 'La sanction sera marquée annulée.',
      confirmLabel: 'Annuler la sanction',
    })
    if (!ok) return
    try {
      await rhApi.annulerSanction(s.id)
      toast.success('Sanction annulée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Annulation impossible.')
    }
  }

  // ── Colonnes par onglet ──
  const epiColumns = useMemo(() => [
    { id: 'designation', header: 'Désignation', width: 220, accessor: (e) => e.designation || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'type', header: 'Type', width: 150, accessor: (e) => e.type_epi_display || e.type_epi || '', cell: (v) => v || '—' },
    { id: 'duree', header: 'Durée de vie', width: 120, align: 'right', searchable: false, accessor: (e) => e.duree_vie_mois ?? '', cell: (v) => (v ? `${v} mois` : '—') },
    { id: 'actif', header: 'Actif', width: 90, accessor: (e) => (e.actif ? 'oui' : 'non'), cell: (_v, e) => <Badge tone={e.actif ? 'success' : 'neutral'}>{e.actif ? 'Actif' : 'Inactif'}</Badge> },
  ], [])

  const dotationColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 170, accessor: (d) => d.employe_nom || String(d.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'epi', header: 'EPI', width: 180, accessor: (d) => d.epi_designation || String(d.epi || ''), cell: (v) => v || '—' },
    { id: 'taille', header: 'Taille', width: 90, accessor: (d) => d.taille || '', cell: (v) => v || '—' },
    { id: 'dotation', header: 'Remis le', width: 120, searchable: false, accessor: (d) => d.date_dotation || '', cell: (v) => formatDate(v) },
    { id: 'etat', header: 'État', width: 120, accessor: (d) => (d.perime ? 'perime' : d.a_controler ? 'controle' : 'ok'), cell: (_v, d) => (d.perime ? <Badge tone="danger">Périmé</Badge> : d.a_controler ? <Badge tone="warning">À contrôler</Badge> : <Badge tone="success">OK</Badge>) },
  ], [])

  const posteColumns = useMemo(() => [
    { id: 'intitule', header: 'Intitulé', width: 220, accessor: (p) => p.intitule || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'nombre', header: 'Postes', width: 90, align: 'right', numeric: true, searchable: false, accessor: (p) => p.nombre_postes ?? 0, cell: (v) => v },
    { id: 'cible', header: 'Cible', width: 120, searchable: false, accessor: (p) => p.date_cible || '', cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'statut', header: 'Statut', width: 120, accessor: (p) => p.statut || '', cell: (_v, p) => <StatutPoste status={p.statut} label={p.statut_display} /> },
  ], [])

  const candidatureColumns = useMemo(() => [
    { id: 'nom', header: 'Candidat', width: 180, accessor: (c) => c.nom || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'ouverture', header: 'Poste', width: 180, accessor: (c) => c.ouverture_intitule || String(c.ouverture || ''), cell: (v) => v || '—' },
    { id: 'email', header: 'Email', width: 200, accessor: (c) => c.email || '', cell: (v) => v || '—' },
    { id: 'etape', header: 'Étape', width: 130, accessor: (c) => c.etape || '', cell: (_v, c) => <EtapeCandidature status={c.etape} label={c.etape_display} /> },
  ], [])

  const evalColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (e) => e.employe_nom || String(e.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'evaluateur', header: 'Évaluateur', width: 160, accessor: (e) => e.evaluateur_nom || String(e.evaluateur || ''), cell: (v) => v || '—' },
    { id: 'entretien', header: 'Entretien', width: 120, searchable: false, accessor: (e) => e.date_entretien || '', cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'note', header: 'Note', width: 90, align: 'right', searchable: false, accessor: (e) => e.note_globale ?? '', cell: (v) => (v ?? '—') },
    { id: 'statut', header: 'Statut', width: 120, accessor: (e) => e.statut || '', cell: (_v, e) => <StatutEvaluation status={e.statut} label={e.statut_display} /> },
  ], [])

  const sanctionColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (s) => s.employe_nom || String(s.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'type', header: 'Type', width: 150, accessor: (s) => s.type_sanction_display || s.type_sanction || '', cell: (v) => v || '—' },
    { id: 'faits', header: 'Faits le', width: 120, searchable: false, accessor: (s) => s.date_faits || '', cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'statut', header: 'Statut', width: 120, accessor: (s) => s.statut || '', cell: (_v, s) => <StatutSanction status={s.statut} label={s.statut_display} /> },
  ], [])

  const candidatureActions = (c) => (c.etape !== 'embauche' && c.etape !== 'rejete'
    ? [{ id: 'embaucher', label: 'Embaucher', icon: UserPlus, onClick: () => embaucher(c) }]
    : [])
  const evalActions = (e) => (e.statut === 'brouillon'
    ? [{ id: 'valider', label: 'Valider', icon: UserPlus, onClick: () => validerEval(e) }]
    : [])
  const sanctionActions = (s) => (s.statut !== 'annulee'
    ? [{ id: 'annuler', label: 'Annuler', icon: Ban, destructive: true, onClick: () => annulerSanction(s) }]
    : [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>EPI, recrutement & évaluations</h2>
      </div>

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue recrutement" />

      {vue === 'epi' && (
        <div className="flex flex-col gap-4">
          <ListShell title="Catalogue EPI" columns={epiColumns} rows={epiCat} loading={loading} error={error}
            searchable exportName="epi-catalogue" emptyTitle="Aucun EPI" emptyDescription="Catalogue EPI vide." />
          <ListShell title="Dotations EPI" columns={dotationColumns} rows={dotations} loading={loading} error={error}
            searchable exportName="dotations-epi" emptyTitle="Aucune dotation" emptyDescription="Aucune dotation enregistrée." />
        </div>
      )}
      {vue === 'recrutement' && (
        <div className="flex flex-col gap-4">
          <ListShell title="Ouvertures de poste" columns={posteColumns} rows={postes} loading={loading} error={error}
            searchable exportName="ouvertures-poste" emptyTitle="Aucune ouverture" emptyDescription="Aucun poste ouvert." />
          <ListShell title="Candidatures" columns={candidatureColumns} rows={candidatures} loading={loading} error={error}
            searchable rowActions={candidatureActions} exportName="candidatures"
            emptyTitle="Aucune candidature" emptyDescription="Aucune candidature reçue." />
        </div>
      )}
      {vue === 'evaluations' && (
        <div className="flex flex-col gap-4">
          <ListShell title="Campagnes d’évaluation"
            columns={[
              { id: 'intitule', header: 'Intitulé', width: 220, accessor: (c) => c.intitule || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
              { id: 'annee', header: 'Année', width: 90, align: 'right', searchable: false, accessor: (c) => c.annee ?? '', cell: (v) => v || '—' },
              { id: 'statut', header: 'Statut', width: 120, accessor: (c) => c.statut_display || c.statut || '', cell: (v) => v || '—' },
            ]}
            rows={campagnes} loading={loading} error={error} searchable exportName="campagnes-evaluation"
            emptyTitle="Aucune campagne" emptyDescription="Aucune campagne d’évaluation." />
          <ListShell title="Évaluations" columns={evalColumns} rows={evaluations} loading={loading} error={error}
            searchable rowActions={evalActions} exportName="evaluations"
            emptyTitle="Aucune évaluation" emptyDescription="Aucune évaluation enregistrée." />
        </div>
      )}
      {vue === 'sanctions' && (
        <ListShell title="Sanctions disciplinaires" columns={sanctionColumns} rows={sanctions} loading={loading} error={error}
          searchable rowActions={sanctionActions} exportName="sanctions"
          emptyTitle="Aucune sanction" emptyDescription="Aucune sanction enregistrée." />
      )}
    </div>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
