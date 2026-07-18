import { useEffect, useMemo, useState } from 'react'
import {
  UserPlus, Ban, ScanText, Star, BarChart3, FileSignature, CalendarClock,
} from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Segmented, Badge, toast, Card, Stat,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatDate, formatNumber } from '../../lib/format'
import rhApi from '../../api/rhApi'
import {
  EtapeCandidature, StatutPoste, StatutSanction, StatutEvaluation,
} from './constants.jsx'

/* ============================================================================
   UX26 + XRH17-23 / ZRH7-9 — EPI, recrutement (ATS complet) & évaluations.
   ----------------------------------------------------------------------------
   ATS : ouvertures → candidatures (avec parsing CV XRH23, mise au vivier XRH21,
   comparatif XRH17, promesse d'embauche XRH20, planification d'entretien XRH17),
   vivier (talent pool), statistiques recrutement (XRH22), gabarits d'email
   (XRH19) & modèles d'évaluation (ZRH7). Toutes les transitions passent par les
   @actions serveur ; la société est toujours posée côté serveur.
   ========================================================================== */

const VUES = [
  { value: 'epi', label: 'EPI' },
  { value: 'recrutement', label: 'Recrutement' },
  { value: 'vivier', label: 'Vivier' },
  { value: 'stats', label: 'Statistiques' },
  { value: 'gabarits', label: 'Gabarits' },
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
  const [vivier, setVivier] = useState([])
  const [stats, setStats] = useState(null)
  const [gabarits, setGabarits] = useState([])
  const [modelesEval, setModelesEval] = useState([])
  const [campagnes, setCampagnes] = useState([])
  const [evaluations, setEvaluations] = useState([])
  const [sanctions, setSanctions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Dialogues ATS.
  const [promesseFor, setPromesseFor] = useState(null)
  const [entretienFor, setEntretienFor] = useState(null)
  const [comparatifFor, setComparatifFor] = useState(null)
  // WIR34 — nouveau candidat + nouveau modèle d'évaluation (ZRH7).
  const [candidatOpen, setCandidatOpen] = useState(false)
  const [modeleOpen, setModeleOpen] = useState(false)

  const recharger = () => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([
      rhApi.getEpiCatalogue(),
      rhApi.getDotationsEpi(),
      rhApi.getOuverturesPoste(),
      rhApi.getCandidatures(),
      rhApi.getVivier(),
      rhApi.getRecrutementStatistiques(),
      rhApi.getGabaritsEmailRecrutement(),
      rhApi.getModelesEvaluation(),
      rhApi.getCampagnesEvaluation(),
      rhApi.getEvaluationsEmploye(),
      rhApi.getSanctions(),
    ])
      .then(([ec, dt, op, ca, vv, st, gb, me, cp, ev, sa]) => {
        if (!vivant) return
        setEpiCat(unwrap(ec.data))
        setDotations(unwrap(dt.data))
        setPostes(unwrap(op.data))
        setCandidatures(unwrap(ca.data))
        setVivier(unwrap(vv.data))
        setStats(st.data ?? null)
        setGabarits(unwrap(gb.data))
        setModelesEval(unwrap(me.data))
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

  const parserCv = async (c) => {
    try {
      const res = await rhApi.parserCv(c.id)
      const champs = res?.data?.champs_remplis ?? []
      toast.success(champs.length
        ? `CV analysé — champs pré-remplis : ${champs.join(', ')}.`
        : 'CV analysé — aucun champ vide à compléter.')
      recharger()
    } catch (err) {
      if (err?.response?.status === 503) {
        toast.error(err?.response?.data?.detail ?? 'Analyse CV indisponible (clé OCR non configurée).')
      } else {
        toast.error(err?.response?.data?.detail ?? 'Analyse du CV impossible.')
      }
    }
  }

  const mettreAuVivier = async (c) => {
    const ok = await confirm({
      title: `Mettre ${c.nom} au vivier ?`,
      description: 'Le candidat restera disponible pour de futures ouvertures.',
      confirmLabel: 'Mettre au vivier',
      destructive: false,
    })
    if (!ok) return
    try {
      await rhApi.mettreAuVivier(c.id, {})
      toast.success('Candidat ajouté au vivier.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Mise au vivier impossible.')
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

  const supprimerGabarit = async (g) => {
    const ok = await confirmDelete({
      title: 'Supprimer ce gabarit ?',
      description: `Le gabarit « ${g.sujet || g.etape} » sera supprimé.`,
      confirmLabel: 'Supprimer',
    })
    if (!ok) return
    try {
      await rhApi.deleteGabaritEmailRecrutement(g.id)
      toast.success('Gabarit supprimé.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Suppression impossible.')
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

  const vivierColumns = useMemo(() => [
    { id: 'nom', header: 'Candidat', width: 180, accessor: (c) => c.nom || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'email', header: 'Email', width: 200, accessor: (c) => c.email || '', cell: (v) => v || '—' },
    { id: 'tags', header: 'Tags', width: 220, accessor: (c) => c.tags_vivier || '', cell: (v) => v || '—' },
    { id: 'recu', header: 'Reçu le', width: 120, searchable: false, accessor: (c) => c.date_candidature || c.date_creation || '', cell: (v) => (v ? formatDate(v) : '—') },
  ], [])

  const gabaritColumns = useMemo(() => [
    { id: 'etape', header: 'Étape', width: 150, accessor: (g) => g.etape_display || g.etape || '', cell: (v) => v || '—' },
    { id: 'sujet', header: 'Sujet', width: 260, accessor: (g) => g.sujet || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'actif', header: 'Actif', width: 90, accessor: (g) => (g.actif ? 'oui' : 'non'), cell: (_v, g) => <Badge tone={g.actif ? 'success' : 'neutral'}>{g.actif ? 'Actif' : 'Inactif'}</Badge> },
  ], [])

  const modeleEvalColumns = useMemo(() => [
    { id: 'nom', header: 'Modèle', width: 220, accessor: (m) => m.nom || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'departement', header: 'Département', width: 160, accessor: (m) => m.departement_nom || (m.departement ? String(m.departement) : ''), cell: (v) => v || 'Tous' },
    { id: 'questions', header: 'Questions', width: 110, align: 'right', searchable: false, accessor: (m) => (Array.isArray(m.questions) ? m.questions.length : (m.questions_count ?? '')), cell: (v) => (v === '' ? '—' : v) },
    { id: 'actif', header: 'Actif', width: 90, accessor: (m) => (m.actif ? 'oui' : 'non'), cell: (_v, m) => <Badge tone={m.actif ? 'success' : 'neutral'}>{m.actif ? 'Actif' : 'Inactif'}</Badge> },
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

  const candidatureActions = (c) => {
    const actions = []
    if (c.etape !== 'embauche' && c.etape !== 'rejete') {
      actions.push({ id: 'embaucher', label: 'Embaucher', icon: UserPlus, onClick: () => embaucher(c) })
    }
    actions.push({ id: 'entretien', label: 'Planifier un entretien', icon: CalendarClock, onClick: () => setEntretienFor(c) })
    actions.push({ id: 'promesse', label: 'Promesse d’embauche', icon: FileSignature, onClick: () => setPromesseFor(c) })
    actions.push({ id: 'comparatif', label: 'Comparer les candidats', icon: BarChart3, onClick: () => setComparatifFor(c) })
    actions.push({ id: 'cv', label: 'Analyser le CV', icon: ScanText, onClick: () => parserCv(c) })
    if (!c.vivier) {
      actions.push({ id: 'vivier', label: 'Mettre au vivier', icon: Star, onClick: () => mettreAuVivier(c) })
    }
    return actions
  }
  const evalActions = (e) => (e.statut === 'brouillon'
    ? [{ id: 'valider', label: 'Valider', icon: UserPlus, onClick: () => validerEval(e) }]
    : [])
  const sanctionActions = (s) => (s.statut !== 'annulee'
    ? [{ id: 'annuler', label: 'Annuler', icon: Ban, destructive: true, onClick: () => annulerSanction(s) }]
    : [])
  const gabaritActions = (g) => [
    { id: 'suppr', label: 'Supprimer', icon: Ban, destructive: true, onClick: () => supprimerGabarit(g) },
  ]

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
            actions={<Button onClick={() => setCandidatOpen(true)}><UserPlus size={15} strokeWidth={1.75} aria-hidden="true" />Nouveau candidat</Button>}
            emptyTitle="Aucune candidature" emptyDescription="Aucune candidature reçue." />
        </div>
      )}
      {vue === 'vivier' && (
        <ListShell title="Vivier de talents" columns={vivierColumns} rows={vivier} loading={loading} error={error}
          searchable exportName="vivier" emptyTitle="Vivier vide"
          emptyDescription="Aucun candidat au vivier. Mettez des candidatures au vivier pour les réutiliser." />
      )}
      {vue === 'stats' && <StatsRecrutement stats={stats} loading={loading} />}
      {vue === 'gabarits' && (
        <div className="flex flex-col gap-4">
          <ListShell title="Gabarits d’email (par étape)" columns={gabaritColumns} rows={gabarits} loading={loading} error={error}
            searchable rowActions={gabaritActions} exportName="gabarits-email"
            emptyTitle="Aucun gabarit" emptyDescription="Aucun gabarit d’email de recrutement." />
          <ListShell title="Modèles d’évaluation" columns={modeleEvalColumns} rows={modelesEval} loading={loading} error={error}
            searchable exportName="modeles-evaluation"
            actions={<Button onClick={() => setModeleOpen(true)}><FileSignature size={15} strokeWidth={1.75} aria-hidden="true" />Nouveau modèle</Button>}
            emptyTitle="Aucun modèle" emptyDescription="Aucun modèle d’évaluation réutilisable." />
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

      {promesseFor && (
        <PromesseDialog
          candidature={promesseFor}
          onClose={() => setPromesseFor(null)}
          onSaved={() => { setPromesseFor(null); recharger() }}
        />
      )}
      {entretienFor && (
        <EntretienDialog
          candidature={entretienFor}
          onClose={() => setEntretienFor(null)}
          onSaved={() => { setEntretienFor(null); recharger() }}
        />
      )}
      {comparatifFor && (
        <ComparatifDialog
          candidature={comparatifFor}
          onClose={() => setComparatifFor(null)}
        />
      )}
      {candidatOpen && (
        <CandidatDialog
          ouvertures={postes}
          onClose={() => setCandidatOpen(false)}
          onSaved={() => { setCandidatOpen(false); recharger() }}
        />
      )}
      {modeleOpen && (
        <ModeleEvaluationDialog
          onClose={() => setModeleOpen(false)}
          onSaved={() => { setModeleOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

/* ── XRH22 — Statistiques de recrutement ── */
function StatsRecrutement({ stats, loading }) {
  if (loading) {
    return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_u, i) => <Card key={i} className="h-24 animate-pulse" />)}
    </div>
  }
  if (!stats) {
    return <p className="text-sm text-muted-foreground">Aucune statistique disponible.</p>
  }
  const entonnoir = stats.entonnoir || stats.funnel || {}
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4"><Stat label="Délai d’embauche moyen" value={stats.delai_embauche_moyen != null ? `${stats.delai_embauche_moyen} j` : '—'} icon={CalendarClock} /></Card>
        <Card className="p-4"><Stat label="Candidatures" value={stats.total_candidatures ?? '—'} icon={UserPlus} /></Card>
        <Card className="p-4"><Stat label="Embauches" value={stats.total_embauches ?? '—'} icon={UserPlus} /></Card>
        <Card className="p-4"><Stat label="Ouvertures actives" value={stats.ouvertures_actives ?? '—'} icon={BarChart3} /></Card>
      </div>
      {Object.keys(entonnoir).length > 0 && (
        <Card className="p-4">
          <h3 className="mb-3 text-sm font-medium">Entonnoir par étape</h3>
          <ul className="flex flex-col gap-2">
            {Object.entries(entonnoir).map(([etape, n]) => (
              <li key={etape} className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{etape}</span>
                <Badge tone="info">{n}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

/* ── XRH20 — Créer une promesse d'embauche ── */
function PromesseDialog({ candidature, onClose, onSaved }) {
  const [poste, setPoste] = useState('')
  const [salaire, setSalaire] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)
  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(poste || salaire || dateDebut)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createPromesseEmbauche({
        candidature: candidature.id,
        poste_propose: poste || '',
        salaire_propose: salaire || null,
        date_debut_prevue: dateDebut || null,
      })
      toast.success('Promesse d’embauche créée.')
      onSaved?.()
    } catch (err) {
      setServerError(err?.response?.data?.detail
        || 'Création de la promesse impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Promesse d’embauche — {candidature.nom}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pr-poste">Poste proposé</Label>
            <Input id="pr-poste" autoFocus value={poste} onChange={(e) => setPoste(e.target.value)} placeholder="Ex. Technicien photovoltaïque" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pr-salaire">Salaire proposé (MAD)</Label>
              <Input id="pr-salaire" type="number" step="any" value={salaire} onChange={(e) => setSalaire(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pr-debut">Début prévu</Label>
              <Input id="pr-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
            </div>
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer la promesse'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── XRH17 — Planifier un entretien de recrutement ── */
function EntretienDialog({ candidature, onClose, onSaved }) {
  const [dateHeure, setDateHeure] = useState('')
  const [type, setType] = useState('')
  const [lieu, setLieu] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)
  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(dateHeure || type || lieu)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!dateHeure) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createEntretienRecrutement({
        candidature: candidature.id,
        date_heure: dateHeure,
        type_entretien: type || undefined,
        lieu: lieu || '',
      })
      toast.success('Entretien planifié.')
      onSaved?.()
    } catch (err) {
      setServerError(err?.response?.data?.detail
        || 'Planification de l’entretien impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Planifier un entretien — {candidature.nom}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="en-dt">Date & heure</Label>
            <Input id="en-dt" type="datetime-local" autoFocus value={dateHeure} onChange={(e) => setDateHeure(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="en-type">Type</Label>
              <Input id="en-type" value={type} onChange={(e) => setType(e.target.value)} placeholder="Ex. Technique, RH" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="en-lieu">Lieu</Label>
              <Input id="en-lieu" value={lieu} onChange={(e) => setLieu(e.target.value)} placeholder="Bureau / visio" />
            </div>
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!dateHeure || saving}>{saving ? 'Planification…' : 'Planifier'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── XRH17 — Comparatif des candidats d'une même ouverture ── */
function ComparatifDialog({ candidature, onClose }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let vivant = true
    rhApi.getComparatifCandidats(candidature.id)
      .then((res) => { if (vivant) setRows(unwrap(res.data)) })
      .catch(() => { if (vivant) setError('Comparatif indisponible.') })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [candidature.id])

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Comparatif des candidats</DialogTitle>
        </DialogHeader>
        {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && (
          rows.length === 0
            ? <p className="text-sm text-muted-foreground">Aucun candidat noté pour cette ouverture.</p>
            : (
              <ul className="flex flex-col gap-2">
                {rows.map((r, i) => (
                  <li key={r.id ?? i} className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-sm">
                    <span className="font-medium">{r.nom || `Candidat ${r.id}`}</span>
                    <Badge tone="info">{r.note_moyenne != null ? formatNumber(r.note_moyenne, { decimals: 1 }) : '—'}</Badge>
                  </li>
                ))}
              </ul>
            )
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR34 — Ajouter un candidat manuellement (CV optionnel) ── */
function CandidatDialog({ ouvertures, onClose, onSaved }) {
  const [ouverture, setOuverture] = useState('')
  const [nom, setNom] = useState('')
  const [email, setEmail] = useState('')
  const [telephone, setTelephone] = useState('')
  const [source, setSource] = useState('')
  const [cv, setCv] = useState(null)
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(ouverture || nom || email || telephone || source || cv)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const valide = Boolean(ouverture && nom.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      let payload
      // CV optionnel : multipart uniquement si un fichier est joint.
      if (cv) {
        const fd = new FormData()
        fd.append('ouverture', ouverture)
        fd.append('nom', nom.trim())
        if (email) fd.append('email', email)
        if (telephone) fd.append('telephone', telephone)
        if (source) fd.append('source', source)
        fd.append('cv_fichier', cv)
        payload = fd
      } else {
        payload = { ouverture, nom: nom.trim(), email: email || '', telephone: telephone || '', source: source || '' }
      }
      await rhApi.createCandidature(payload)
      toast.success('Candidature créée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.ouverture || data?.nom
        || 'Création de la candidature impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau candidat</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cd-ouverture">Poste visé</Label>
            <select
              id="cd-ouverture"
              value={ouverture}
              onChange={(e) => setOuverture(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {ouvertures.map((p) => <option key={p.id} value={p.id}>{p.intitule}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cd-nom">Nom du candidat</Label>
            <Input id="cd-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cd-email">Email</Label>
              <Input id="cd-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cd-telephone">Téléphone</Label>
              <Input id="cd-telephone" value={telephone} onChange={(e) => setTelephone(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cd-source">Source (LinkedIn, ANAPEC, cooptation…)</Label>
            <Input id="cd-source" value={source} onChange={(e) => setSource(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cd-cv">CV (optionnel)</Label>
            <input id="cd-cv" type="file" onChange={(e) => setCv(e.target.files?.[0] ?? null)} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>
              {saving ? 'Création…' : 'Créer la candidature'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR34 (ZRH7) — Créer un modèle d'évaluation réutilisable ── */
function ModeleEvaluationDialog({ onClose, onSaved }) {
  const [nom, setNom] = useState('')
  const [questionsTexte, setQuestionsTexte] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(nom || questionsTexte)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const valide = Boolean(nom.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      // Une question par ligne — libellé texte libre, réponse texte, cible
      // employé (le cas le plus courant ; ciblage manager/type via l'API RH
      // reste possible en édition ultérieure).
      const questions = questionsTexte
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean)
        .map((libelle) => ({ libelle, type: 'texte', cible: 'employe' }))
      await rhApi.createModeleEvaluation({ nom: nom.trim(), questions })
      toast.success('Modèle d’évaluation créé.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.nom || 'Création du modèle impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau modèle d’évaluation</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="me-nom">Nom du modèle</Label>
            <Input id="me-nom" autoFocus value={nom} onChange={(e) => setNom(e.target.value)} placeholder="Ex. Entretien annuel — Technicien" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="me-questions">Questions (une par ligne)</Label>
            <Textarea id="me-questions" value={questionsTexte} onChange={(e) => setQuestionsTexte(e.target.value)} rows={5}
              placeholder={'Ex.\nQuels objectifs ont été atteints ?\nQuels points à améliorer ?'} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>
              {saving ? 'Création…' : 'Créer le modèle'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
