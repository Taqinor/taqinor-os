import { useEffect, useMemo, useState } from 'react'
import {
  UserPlus, Ban, ScanText, Star, BarChart3, FileSignature, CalendarClock, Users,
  ShieldCheck, PenLine, Undo2, History, Send, Check, X, Lock, Briefcase,
  MessageSquare,
} from 'lucide-react'
import ChatterTimeline from '../../components/ChatterTimeline'
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

   WIR194 — les dotations EPI n'étaient QUE lues : ni remise, ni restitution,
   ni émargement, alors que les quatre routes serveur existent
   (`/rh/dotations-epi/` POST, `.../restituer/`, `.../emarger/`,
   `.../emargements/`). L'onglet EPI porte désormais « Nouvelle dotation » et
   trois actions de ligne (Restituer, Émarger, Historique) : l'émargement est
   la PREUVE de remise exigible en contrôle CNSS / accident du travail, il ne
   pouvait pas rester injouable. Aucun bloc d'échéances ici — il vit déjà au
   Cockpit RH, le dupliquer serait un second endroit à maintenir.

   WIR131 — l'action « Feedback 360° » (par ligne d'évaluation) invite des
   répondants (`createRetourFeedback360`) et affiche la synthèse agrégée
   (`getSyntheseFeedback360`) — les deux wrappers étaient définis dans
   rhApi.js sans aucun appelant. L'invitation reste gérée par le RH/manager
   ici ; le répondant remplit/soumet ensuite SON PROPRE retour depuis le
   portail self-service (`mes-feedback360`, hors scope de cette tâche).
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
  // WIR194 — employés du référentiel : cible d'une nouvelle dotation EPI.
  const [employes, setEmployes] = useState([])
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
  // XRH15 — ouverture dont on consulte les candidats internes.
  const [internesFor, setInternesFor] = useState(null)
  // WIR34 — nouveau candidat + nouveau modèle d'évaluation (ZRH7).
  const [candidatOpen, setCandidatOpen] = useState(false)
  const [modeleOpen, setModeleOpen] = useState(false)
  // WIR131 — invitations feedback 360° d'une évaluation.
  const [feedbackFor, setFeedbackFor] = useState(null)
  // WIR240 — panneau « Activité » d'une candidature (chatter + notation).
  const [activiteFor, setActiviteFor] = useState(null)
  // WIR196 — création d'une ouverture de poste + refus motivé.
  const [ouvertureOpen, setOuvertureOpen] = useState(false)
  const [refusFor, setRefusFor] = useState(null)
  // WIR194 — écriture des dotations EPI.
  const [dotationOpen, setDotationOpen] = useState(false)
  const [emargerFor, setEmargerFor] = useState(null)
  const [emargementsFor, setEmargementsFor] = useState(null)

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
      // WIR194 — référentiel employés (cible d'une dotation EPI).
      rhApi.getEmployes(),
    ])
      .then(([ec, dt, op, ca, vv, st, gb, me, cp, ev, sa, em]) => {
        if (!vivant) return
        setEpiCat(unwrap(ec.data))
        setDotations(unwrap(dt.data))
        setEmployes(unwrap(em?.data))
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

  /* WIR196 — cycle d'approbation d'une ouverture de poste (YHIRE14). Le
     serveur arbitre TOUT : transition légale et séparation des tâches
     (approbateur ≠ demandeur). Son 400 { detail } — « Vous ne pouvez pas
     approuver votre propre demande », par exemple — est affiché TEL QUEL,
     jamais remplacé par un message générique qui masquerait la vraie règle. */
  const soumettreOuverture = async (o) => {
    try {
      await rhApi.soumettreOuverturePoste(o.id)
      toast.success('Ouverture soumise à approbation.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Soumission impossible.')
    }
  }

  const approuverOuverture = async (o) => {
    try {
      await rhApi.approuverOuverturePoste(o.id)
      toast.success('Ouverture approuvée — poste ouvert.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Approbation impossible.')
    }
  }

  // WIR196 — clôture d'une campagne d'évaluation (idempotente côté serveur).
  const cloturerCampagne = async (c) => {
    try {
      await rhApi.cloturerCampagneEvaluation(c.id)
      toast.success('Campagne clôturée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Clôture impossible.')
    }
  }

  // WIR194 — restitution d'une dotation EPI (YHIRE13). Le serveur refuse une
  // dotation déjà restituée avec un 400 { detail } : on l'affiche TEL QUEL,
  // jamais reformulé.
  const restituerDotation = async (d) => {
    const ok = await confirm({
      title: 'Restituer cet EPI ?',
      description: 'La dotation sera marquée restituée ; le stock est réintégré si l’EPI est lié à un produit.',
      confirmLabel: 'Restituer',
      destructive: false,
    })
    if (!ok) return
    try {
      await rhApi.restituerDotationEpi(d.id)
      toast.success('EPI restitué.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Restitution impossible.')
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
    // WIR194 — l'accusé de remise (FG180) est la preuve exigible en contrôle :
    // il doit être VISIBLE sur la ligne, pas seulement stocké.
    { id: 'accuse', header: 'Accusé', width: 110, accessor: (d) => (d.accuse_remise ? 'oui' : 'non'), cell: (_v, d) => (d.accuse_remise ? <Badge tone="success">Émargé</Badge> : <Badge tone="warning">Non émargé</Badge>) },
    { id: 'restituee', header: 'Restituée', width: 110, accessor: (d) => (d.restituee ? 'oui' : 'non'), cell: (_v, d) => (d.restituee ? <Badge tone="neutral">Restituée</Badge> : <Badge tone="info">En service</Badge>) },
  ], [])

  // WIR194 — actions de ligne d'une dotation EPI. « Restituer » disparaît une
  // fois la dotation restituée (le serveur répondrait 400) ; « Émarger » et
  // « Historique » restent toujours disponibles (ré-émargement possible).
  const dotationActions = (d) => [
    ...(d.restituee
      ? []
      : [{ id: 'restituer', label: 'Restituer', icon: Undo2, onClick: () => restituerDotation(d) }]),
    { id: 'emarger', label: 'Émarger', icon: PenLine, onClick: () => setEmargerFor(d) },
    { id: 'emargements', label: 'Historique', icon: History, onClick: () => setEmargementsFor(d) },
  ]

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
    // WIR240 — chatter de la candidature : les transitions d'étape étaient
    // journalisées côté serveur sans jamais être lisibles, et aucune note ne
    // pouvait être écrite. Le panneau porte aussi la grille de notation
    // d'entretien, sans laquelle la colonne Note et le comparatif restaient
    // vides quoi qu'on fasse.
    actions.push({ id: 'activite', label: 'Activité', icon: MessageSquare, onClick: () => setActiviteFor(c) })
    actions.push({ id: 'entretien', label: 'Planifier un entretien', icon: CalendarClock, onClick: () => setEntretienFor(c) })
    actions.push({ id: 'promesse', label: 'Promesse d’embauche', icon: FileSignature, onClick: () => setPromesseFor(c) })
    actions.push({ id: 'comparatif', label: 'Comparer les candidats', icon: BarChart3, onClick: () => setComparatifFor(c) })
    actions.push({ id: 'cv', label: 'Analyser le CV', icon: ScanText, onClick: () => parserCv(c) })
    if (!c.vivier) {
      actions.push({ id: 'vivier', label: 'Mettre au vivier', icon: Star, onClick: () => mettreAuVivier(c) })
    }
    return actions
  }
  // XRH15 — candidats INTERNES d'une ouverture : classement des employés par
  // couverture du profil requis du `poste_ref` (mobilité interne avant
  // sourcing externe). Sans `poste_ref`, l'action n'a pas de cible.
  // WIR196 — les actions du cycle YHIRE14 sont CONDITIONNÉES au statut : une
  // ouverture ne pouvait pas quitter l'état brouillon, le workflow était
  // injouable. « Candidats internes » reste conditionnée au poste_ref.
  const ouvertureActions = (o) => {
    const actions = []
    if (o.statut === 'brouillon') {
      actions.push({ id: 'soumettre', label: 'Soumettre à approbation', icon: Send, onClick: () => soumettreOuverture(o) })
    }
    if (o.statut === 'en_approbation') {
      actions.push({ id: 'approuver', label: 'Approuver', icon: Check, onClick: () => approuverOuverture(o) })
      actions.push({ id: 'refuser', label: 'Refuser', icon: X, destructive: true, onClick: () => setRefusFor(o) })
    }
    if (o.poste_ref) {
      actions.push({
        id: 'candidats-internes',
        label: 'Candidats internes',
        icon: Users,
        onClick: () => setInternesFor(o),
      })
    }
    return actions
  }
  // WIR196 — clôture d'une campagne d'évaluation encore ouverte.
  const campagneActions = (c) => (c.statut === 'cloturee'
    ? []
    : [{ id: 'cloturer', label: 'Clôturer', icon: Lock, onClick: () => cloturerCampagne(c) }])
  const evalActions = (e) => [
    ...(e.statut === 'brouillon'
      ? [{ id: 'valider', label: 'Valider', icon: UserPlus, onClick: () => validerEval(e) }]
      : []),
    // WIR131 — ouvre les invitations feedback 360° pour CETTE évaluation.
    { id: 'feedback360', label: 'Feedback 360°', icon: Users, onClick: () => setFeedbackFor(e) },
  ]
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
            searchable rowActions={dotationActions} exportName="dotations-epi"
            actions={<Button onClick={() => setDotationOpen(true)}><ShieldCheck size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle dotation</Button>}
            emptyTitle="Aucune dotation" emptyDescription="Aucune dotation enregistrée." />
        </div>
      )}
      {vue === 'recrutement' && (
        <div className="flex flex-col gap-4">
          <ListShell title="Ouvertures de poste" columns={posteColumns} rows={postes} loading={loading} error={error}
            searchable rowActions={ouvertureActions} exportName="ouvertures-poste"
            actions={<Button onClick={() => setOuvertureOpen(true)}><Briefcase size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle ouverture</Button>}
            emptyTitle="Aucune ouverture" emptyDescription="Aucun poste ouvert." />
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
      {/* PACT20 — `postes` alimente la tuile « Ouvertures actives » : la donnée
          vient du serveur (`getOuverturesPoste`), pas d'un calcul inventé. */}
      {vue === 'stats' && <StatsRecrutement stats={stats} postes={postes} loading={loading} />}
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
            rowActions={campagneActions}
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
      {internesFor && (
        <CandidatsInternesDialog
          ouverture={internesFor}
          onClose={() => setInternesFor(null)}
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
      {feedbackFor && (
        <FeedbackDialog
          evaluation={feedbackFor}
          onClose={() => setFeedbackFor(null)}
        />
      )}
      {activiteFor && (
        <ActiviteCandidatureDialog
          candidature={activiteFor}
          onClose={() => setActiviteFor(null)}
        />
      )}
      {ouvertureOpen && (
        <OuverturePosteDialog
          onClose={() => setOuvertureOpen(false)}
          onSaved={() => { setOuvertureOpen(false); recharger() }}
        />
      )}
      {refusFor && (
        <RefusOuvertureDialog
          ouverture={refusFor}
          onClose={() => setRefusFor(null)}
          onSaved={() => { setRefusFor(null); recharger() }}
        />
      )}
      {dotationOpen && (
        <DotationEpiDialog
          employes={employes}
          catalogue={epiCat}
          onClose={() => setDotationOpen(false)}
          onSaved={() => { setDotationOpen(false); recharger() }}
        />
      )}
      {emargerFor && (
        <EmargerDotationDialog
          dotation={emargerFor}
          onClose={() => setEmargerFor(null)}
          onSaved={() => { setEmargerFor(null); recharger() }}
        />
      )}
      {emargementsFor && (
        <EmargementsDialog
          dotation={emargementsFor}
          onClose={() => setEmargementsFor(null)}
        />
      )}
    </div>
  )
}

/* ── WIR240 (XRH17/XRH18) — Activité d'une candidature : chatter + notation ───
   Deux trous fermés d'un coup :
     * le chatter (`historique`/`noter`) journalisait les transitions d'étape
       côté serveur sans qu'aucun écran ne les lise, et aucune note manuelle
       n'était possible ;
     * la grille d'entretien (`noterEntretienRecrutement`) n'avait aucun
       appelant, donc la colonne « Note » et le comparatif des candidats
       restaient vides QUOI QU'ON FASSE.
   L'auteur, la société et l'horodatage sont posés côté serveur ; la note
   publiée est RELUE du serveur, jamais ajoutée optimistement au fil. */
const AVIS_ENTRETIEN = [
  { value: 'favorable', label: 'Favorable' },
  { value: 'reserve', label: 'Réservé' },
  { value: 'defavorable', label: 'Défavorable' },
]

// Critères de la grille — miroir des clés libres de `notes_criteres` (JSON
// serveur). Un critère = une note 1–5 ; la moyenne est calculée par le serveur
// (`moyenne_criteres`), jamais ici.
const CRITERES_ENTRETIEN = ['Technique', 'Communication', 'Motivation']

function ActiviteCandidatureDialog({ candidature, onClose }) {
  const [entrees, setEntrees] = useState([])
  const [entretiens, setEntretiens] = useState([])
  const [loading, setLoading] = useState(true)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)

  useEffect(() => {
    let vivant = true
    Promise.allSettled([
      rhApi.getHistoriqueCandidature(candidature.id),
      rhApi.getEntretiensRecrutement({ candidature: candidature.id }),
    ]).then(([hist, ent]) => {
      if (!vivant) return
      if (hist.status === 'fulfilled') setEntrees(unwrap(hist.value.data))
      if (ent.status === 'fulfilled') setEntretiens(unwrap(ent.value.data))
      setLoading(false)
    })
    return () => { vivant = false }
  }, [candidature.id, reloadTick])

  const publier = async (e) => {
    e.preventDefault()
    if (!note.trim()) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.noterCandidature(candidature.id, { message: note.trim() })
      setNote('')
      setReloadTick((t) => t + 1)
      toast.success('Note ajoutée au fil.')
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.message || data?.detail || 'Ajout de la note impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Activité — {candidature.nom}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <form onSubmit={publier} className="flex flex-col gap-2">
            <Label htmlFor="ac-note">Ajouter une note</Label>
            <Textarea id="ac-note" rows={2} value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Note libre — visible dans le fil de la candidature" />
            <div className="flex justify-end">
              <Button type="submit" size="sm" disabled={!note.trim() || saving}>
                {saving ? 'Envoi…' : 'Publier la note'}
              </Button>
            </div>
          </form>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}

          {loading
            ? <p className="text-sm text-muted-foreground">Chargement…</p>
            : (
              <ChatterTimeline
                entries={entrees.map(versEntreeChatter)}
                emptyLabel="Aucune activité sur cette candidature."
              />
            )}

          {entretiens.length > 0 && (
            <div className="flex flex-col gap-3">
              <h3 className="text-sm font-medium">Entretiens — grille de notation</h3>
              {entretiens.map((en) => (
                <GrilleEntretien
                  key={en.id}
                  entretien={en}
                  onSaved={() => setReloadTick((t) => t + 1)}
                />
              ))}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* Adapte la forme RH (`CandidatureActivity` : type/message/field/date_creation)
   à celle attendue par `ChatterTimeline` (kind/body/user_nom/created_at). Aucun
   champ n'est inventé : `log` porte un couple old→new, `note` un message. */
function versEntreeChatter(a) {
  return {
    id: a.id,
    kind: a.type === 'note' ? 'note' : 'modification',
    body: a.message || '',
    field_label: a.field || 'Étape',
    old_value: a.old_value ?? '—',
    new_value: a.new_value ?? '—',
    user_nom: a.auteur_nom || '',
    created_at: a.date_creation,
  }
}

function GrilleEntretien({ entretien, onSaved }) {
  const maNote = Array.isArray(entretien.notes) && entretien.notes.length > 0
    ? entretien.notes[entretien.notes.length - 1] : null
  const [criteres, setCriteres] = useState(
    () => ({ ...(maNote?.notes_criteres || {}) }))
  const [commentaire, setCommentaire] = useState(maNote?.commentaire || '')
  const [avis, setAvis] = useState(maNote?.avis || 'reserve')
  const [saving, setSaving] = useState(false)
  const [erreur, setErreur] = useState(null)

  const soumettre = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErreur(null)
    try {
      // Seuls les critères réellement saisis partent : un champ vide ne doit
      // pas devenir un 0 qui fausserait la moyenne serveur.
      const notes = {}
      CRITERES_ENTRETIEN.forEach((c) => {
        const v = criteres[c]
        if (v !== undefined && v !== '') notes[c] = Number(v)
      })
      await rhApi.noterEntretienRecrutement(entretien.id, {
        notes_criteres: notes,
        commentaire: commentaire || '',
        avis,
      })
      toast.success('Entretien noté.')
      onSaved?.()
    } catch (err) {
      setErreur(err?.response?.data?.detail ?? 'Notation impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={soumettre} className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3">
      <p className="text-sm font-medium">
        {entretien.type_display || entretien.type_entretien || 'Entretien'}
        {entretien.date_heure ? ` — ${formatDate(entretien.date_heure)}` : ''}
      </p>
      <div className="grid grid-cols-3 gap-3">
        {CRITERES_ENTRETIEN.map((c) => (
          <div key={c} className="flex flex-col gap-1.5">
            <Label htmlFor={`gr-${entretien.id}-${c}`}>{c} (1–5)</Label>
            <Input id={`gr-${entretien.id}-${c}`} type="number" step="any"
              value={criteres[c] ?? ''}
              onChange={(e) => setCriteres((p) => ({ ...p, [c]: e.target.value }))} />
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`gr-${entretien.id}-avis`}>Avis</Label>
        <select id={`gr-${entretien.id}-avis`} value={avis}
          onChange={(e) => setAvis(e.target.value)}
          className="h-9 rounded-md border border-border bg-card px-3 text-sm">
          {AVIS_ENTRETIEN.map((a) => (
            <option key={a.value} value={a.value}>{a.label}</option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`gr-${entretien.id}-com`}>Commentaire</Label>
        <Input id={`gr-${entretien.id}-com`} value={commentaire}
          onChange={(e) => setCommentaire(e.target.value)} />
      </div>
      {erreur && <p className="text-sm text-destructive" role="alert">{erreur}</p>}
      <div className="flex justify-end">
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? 'Enregistrement…' : 'Enregistrer la notation'}
        </Button>
      </div>
    </form>
  )
}

/* ── WIR196 (FG189/YHIRE14) — Créer une ouverture de poste ────────────────────
   L'ouverture naît BROUILLON côté serveur (défaut du modèle) : le formulaire
   n'envoie donc AUCUN statut — le cycle appartient aux @actions. `company` est
   posée dans `perform_create`. */
function OuverturePosteDialog({ onClose, onSaved }) {
  const [intitule, setIntitule] = useState('')
  const [nombrePostes, setNombrePostes] = useState('1')
  const [ville, setVille] = useState('')
  const [dateCible, setDateCible] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(intitule || ville || dateCible || description)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(intitule.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createOuverturePoste({
        intitule: intitule.trim(),
        nombre_postes: Number(nombrePostes) || 1,
        ville: ville || '',
        date_cible: dateCible || null,
        description: description || '',
      })
      toast.success('Ouverture créée (brouillon).')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.intitule
        || 'Création de l’ouverture impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvelle ouverture de poste</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="op-intitule">Intitulé</Label>
            <Input id="op-intitule" autoFocus value={intitule} onChange={(e) => setIntitule(e.target.value)}
              placeholder="Ex. Technicien photovoltaïque" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="op-nb">Postes à pourvoir</Label>
              <Input id="op-nb" type="number" step="any" value={nombrePostes} onChange={(e) => setNombrePostes(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="op-ville">Ville</Label>
              <Input id="op-ville" value={ville} onChange={(e) => setVille(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="op-cible">Date cible</Label>
              <Input id="op-cible" type="date" value={dateCible} onChange={(e) => setDateCible(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="op-desc">Profil recherché</Label>
            <Textarea id="op-desc" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>
              {saving ? 'Création…' : 'Créer l’ouverture'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR196 (YHIRE14) — Refuser une ouverture soumise (motif) ─────────────────
   Le 400 { detail } du serveur — notamment le refus d'auto-approbation
   (séparation des tâches) — est affiché TEL QUEL dans le dialogue. */
function RefusOuvertureDialog({ ouverture, onClose, onSaved }) {
  const [motif, setMotif] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.refuserOuverturePoste(ouverture.id, { motif_refus: motif })
      toast.success('Ouverture refusée.')
      onSaved?.()
    } catch (err) {
      setServerError(err?.response?.data?.detail ?? 'Refus impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Refuser l’ouverture — {ouverture.intitule}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ro-motif">Motif du refus</Label>
            <Input id="ro-motif" autoFocus value={motif} onChange={(e) => setMotif(e.target.value)}
              placeholder="Ex. Budget non validé" />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Refus…' : 'Refuser'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR194 (FG178) — Remettre un EPI à un employé (nouvelle dotation) ────────
   `company` n'est JAMAIS envoyée : le serveur la pose dans `perform_create`.
   Les échéances dérivées (péremption, prochain contrôle) sont calculées côté
   serveur à partir du catalogue — le formulaire ne les propose pas. */
function DotationEpiDialog({ employes, catalogue, onClose, onSaved }) {
  const [employe, setEmploye] = useState('')
  const [epi, setEpi] = useState('')
  const [taille, setTaille] = useState('')
  const [dateDotation, setDateDotation] = useState('')
  const [quantite, setQuantite] = useState('1')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || epi || taille || dateDotation)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe && epi)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createDotationEpi({
        employe,
        epi,
        taille: taille || '',
        date_dotation: dateDotation || undefined,
        quantite: Number(quantite) || 1,
      })
      toast.success('Dotation EPI enregistrée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.employe || data?.epi
        || 'Création de la dotation impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvelle dotation EPI</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="do-employe">Employé</Label>
            <select id="do-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              <option value="">— Choisir —</option>
              {employes.map((em) => (
                <option key={em.id} value={em.id}>{em.nom} {em.prenom}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="do-epi">EPI (catalogue)</Label>
            <select id="do-epi" value={epi} onChange={(e) => setEpi(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              <option value="">— Choisir —</option>
              {catalogue.map((c) => (
                <option key={c.id} value={c.id}>{c.designation}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="do-taille">Taille</Label>
              <Input id="do-taille" value={taille} onChange={(e) => setTaille(e.target.value)} placeholder="Ex. 42, L" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="do-date">Remis le</Label>
              <Input id="do-date" type="date" value={dateDotation} onChange={(e) => setDateDotation(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="do-qte">Quantité</Label>
              <Input id="do-qte" type="number" step="any" value={quantite} onChange={(e) => setQuantite(e.target.value)} />
            </div>
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer la dotation'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR194 (FG180) — Émarger la remise : accusé de réception signé ───────────
   Le nom dactylographié fait foi (loi 53-05) et est OBLIGATOIRE côté client
   comme côté serveur. L'utilisateur agissant, la société, l'IP et le user
   agent sont posés par le serveur — jamais envoyés d'ici. */
const ROLES_EMARGEMENT = [
  { value: 'employe', label: 'Employé (bénéficiaire)' },
  { value: 'remettant', label: 'Remettant' },
  { value: 'temoin', label: 'Témoin' },
]

function EmargerDotationDialog({ dotation, onClose, onSaved }) {
  const [nom, setNom] = useState('')
  const [role, setRole] = useState('employe')
  const [mention, setMention] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(nom || mention)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(nom.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.emargerDotationEpi(dotation.id, {
        signataire_nom: nom.trim(),
        role_signataire: role,
        methode: 'typed',
        mention: mention || '',
      })
      toast.success('Émargement enregistré — remise accusée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.signataire_nom
        || 'Émargement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            Émarger la remise — {dotation.epi_designation || `Dotation #${dotation.id}`}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="em-nom">Nom du signataire</Label>
            <Input id="em-nom" autoFocus value={nom} onChange={(e) => setNom(e.target.value)}
              placeholder="Nom dactylographié — fait foi (loi 53-05)" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="em-role">Rôle du signataire</Label>
            <select id="em-role" value={role} onChange={(e) => setRole(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              {ROLES_EMARGEMENT.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="em-mention">Mention (optionnelle)</Label>
            <Input id="em-mention" value={mention} onChange={(e) => setMention(e.target.value)}
              placeholder="Ex. Reçu en bon état" />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>
              {saving ? 'Enregistrement…' : 'Émarger'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR194 (FG180) — Historique des émargements d'une dotation (lecture) ── */
function EmargementsDialog({ dotation, onClose }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let vivant = true
    rhApi.getEmargementsDotationEpi(dotation.id)
      .then((res) => { if (vivant) setRows(unwrap(res.data)) })
      .catch(() => { if (vivant) setError('Historique indisponible.') })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [dotation.id])

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Émargements — {dotation.epi_designation || `Dotation #${dotation.id}`}</DialogTitle>
        </DialogHeader>
        {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && (
          rows.length === 0
            ? <p className="text-sm text-muted-foreground">Aucun émargement enregistré pour cette dotation.</p>
            : (
              <ul className="flex flex-col gap-2">
                {rows.map((r) => (
                  <li key={r.id} className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-sm">
                    <span className="font-medium">{r.signataire_nom}</span>
                    <span className="flex items-center gap-2 text-xs text-muted-foreground">
                      {r.role_signataire_display || r.role_signataire}
                      <Badge tone="info">{formatDate(r.date_signature)}</Badge>
                    </span>
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

/* ── XRH22 — Statistiques de recrutement ──────────────────────────────────────
   PACT20 — les 4 tuiles affichaient « — » POUR TOUJOURS, sans aucune erreur ni
   alerte : elles lisaient `delai_embauche_moyen`, `total_candidatures`,
   `total_embauches` et `ouvertures_actives`, quatre clés que
   `selectors.stats_recrutement` (apps/rh/selectors.py) ne renvoie PAS. Il
   renvoie `delai_embauche_moyen_jours`, `entonnoir`,
   `candidatures_par_ouverture` et `sources`.

   Un seul défaut était un simple désaccord de nom (le suffixe `_jours`, type
   b). Les trois autres étaient de type (a') : la donnée EXISTE mais sous une
   autre forme — un entonnoir, pas des totaux. Les tuiles sont donc DÉRIVÉES de
   ce que le serveur sait dire, jamais forcées à afficher un chiffre qu'il n'a
   pas :
     * Candidatures reçues = `entonnoir.recu` + `entonnoir.rejete` — le
       sélecteur compte les rejetées HORS entonnoir (elles n'ont pas franchi
       les étapes), la somme est donc le total exact de la période ;
     * Embauches = `entonnoir.embauche`, le dernier étage de l'entonnoir ;
     * Ouvertures actives = les ouvertures au statut `ouvert`, comptées sur la
       liste que l'écran charge DÉJÀ (`getOuverturesPoste`) — le serveur le
       sait, simplement par un autre endpoint ; rien n'est inventé côté client.
   Une tuile sans donnée dit « — » : ça n'arrive plus que si le serveur n'a
   vraiment rien renvoyé. */

const ETAPES_ENTONNOIR = [
  ['recu', 'Reçues'],
  ['preselection', 'Présélection'],
  ['entretien', 'Entretien'],
  ['offre', 'Offre'],
  ['embauche', 'Embauchées'],
  ['rejete', 'Rejetées'],
]

function StatsRecrutement({ stats, postes = [], loading }) {
  if (loading) {
    return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_u, i) => <Card key={i} className="h-24 animate-pulse" />)}
    </div>
  }
  if (!stats) {
    return <p className="text-sm text-muted-foreground">Aucune statistique disponible.</p>
  }
  const entonnoir = stats.entonnoir || {}
  const nombre = (cle) => (typeof entonnoir[cle] === 'number' ? entonnoir[cle] : null)
  const recues = nombre('recu')
  const rejetees = nombre('rejete')
  const totalCandidatures = recues == null && rejetees == null
    ? null : (recues ?? 0) + (rejetees ?? 0)
  const embauches = nombre('embauche')
  const delai = stats.delai_embauche_moyen_jours
  const ouverturesActives = postes.filter((p) => p.statut === 'ouvert').length
  const parOuverture = Array.isArray(stats.candidatures_par_ouverture)
    ? stats.candidatures_par_ouverture : []
  const sources = Array.isArray(stats.sources) ? stats.sources : []

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4">
          <Stat label="Délai d’embauche moyen"
                value={delai != null ? `${delai} j` : '—'} icon={CalendarClock} />
        </Card>
        <Card className="p-4">
          <Stat label="Candidatures reçues"
                value={totalCandidatures ?? '—'} icon={UserPlus} />
        </Card>
        <Card className="p-4">
          <Stat label="Embauches" value={embauches ?? '—'} icon={UserPlus} />
        </Card>
        <Card className="p-4">
          <Stat label="Ouvertures actives" value={ouverturesActives} icon={BarChart3} />
        </Card>
      </div>
      {Object.keys(entonnoir).length > 0 && (
        <Card className="p-4">
          <h3 className="mb-3 text-sm font-medium">Entonnoir par étape</h3>
          <ul className="flex flex-col gap-2">
            {ETAPES_ENTONNOIR
              .filter(([cle]) => entonnoir[cle] !== undefined)
              .map(([cle, libelle]) => (
                <li key={cle} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{libelle}</span>
                  <Badge tone="info">{entonnoir[cle]}</Badge>
                </li>
              ))}
          </ul>
        </Card>
      )}
      {parOuverture.length > 0 && (
        <Card className="p-4">
          <h3 className="mb-3 text-sm font-medium">Candidatures par ouverture</h3>
          <ul className="flex flex-col gap-2">
            {parOuverture.map((o) => (
              <li key={o.ouverture_id ?? o.intitule} className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{o.intitule || '— (sans ouverture)'}</span>
                <Badge tone="info">{o.nb}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {sources.length > 0 && (
        <Card className="p-4">
          <h3 className="mb-3 text-sm font-medium">Efficacité par source</h3>
          <ul className="flex flex-col gap-2">
            {sources.map((s) => (
              <li key={s.source || '(sans source)'} className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{s.source || '(sans source)'}</span>
                <span className="flex items-center gap-2">
                  <span className="text-muted-foreground">
                    {s.embauches}/{s.candidatures}
                  </span>
                  <Badge tone="info">
                    {formatNumber(s.taux_embauche_pct ?? 0, { decimals: 1 })} %
                  </Badge>
                </span>
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

/* ── XRH15 — Candidats INTERNES d'une ouverture (mobilité interne) ── */
function CandidatsInternesDialog({ ouverture, onClose }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let vivant = true
    rhApi.getCandidatsInternes(ouverture.poste_ref)
      .then((res) => { if (vivant) setRows(unwrap(res.data)) })
      .catch(() => { if (vivant) setError('Classement indisponible.') })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [ouverture.poste_ref])

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Candidats internes — {ouverture.intitule}</DialogTitle>
        </DialogHeader>
        {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && (
          rows.length === 0
            ? <p className="text-sm text-muted-foreground">Aucun profil requis défini sur ce poste.</p>
            : (
              <ul className="flex flex-col gap-2">
                {rows.map((r) => (
                  <li key={r.employe_id} className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-sm">
                    <span className="font-medium">{r.employe_nom}</span>
                    <Badge tone={r.couverture_pct >= 100 ? 'success' : 'info'}>
                      {formatNumber(r.couverture_pct ?? 0, { decimals: 1 })} %
                    </Badge>
                  </li>
                ))}
              </ul>
            )
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
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

/* ── WIR131 (ZRH9) — Feedback 360° d'une évaluation : invitations + synthèse ── */
const RELATIONS_FEEDBACK360 = [
  { value: 'pair', label: 'Pair' },
  { value: 'subordonne', label: 'Subordonné' },
  { value: 'manager_transversal', label: 'Manager transversal' },
]

function FeedbackDialog({ evaluation, onClose }) {
  const [retours, setRetours] = useState([])
  const [synthese, setSynthese] = useState(null)
  const [employes, setEmployes] = useState([])
  const [loading, setLoading] = useState(true)
  const [repondant, setRepondant] = useState('')
  const [relation, setRelation] = useState('pair')
  const [inviting, setInviting] = useState(false)
  const [serverError, setServerError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)

  useEffect(() => {
    let vivant = true
    // Différé d'un microtask : pas de setState synchrone dans le corps d'un
    // effet (react-hooks/set-state-in-effect).
    Promise.resolve().then(() => { if (vivant) setLoading(true) })
    Promise.allSettled([
      rhApi.getRetoursFeedback360({ evaluation: evaluation.id }),
      rhApi.getSyntheseFeedback360({ evaluation: evaluation.id }),
      rhApi.getEmployes(),
    ]).then(([r, s, emp]) => {
      if (!vivant) return
      if (r.status === 'fulfilled') setRetours(unwrap(r.value.data))
      if (s.status === 'fulfilled') setSynthese(s.value.data)
      if (emp.status === 'fulfilled') setEmployes(unwrap(emp.value.data))
      setLoading(false)
    })
    return () => { vivant = false }
  }, [evaluation.id, reloadTick])

  const inviter = async (e) => {
    e.preventDefault()
    if (!repondant) return
    setInviting(true)
    setServerError(null)
    try {
      await rhApi.createRetourFeedback360({
        evaluation: evaluation.id,
        repondant: Number(repondant),
        relation,
      })
      toast.success('Répondant invité.')
      setRepondant('')
      setReloadTick((t) => t + 1)
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.repondant || 'Invitation impossible.')
    } finally {
      setInviting(false)
    }
  }

  const moyennes = Object.entries(synthese?.moyennes_par_critere || {})

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Feedback 360° — {evaluation.employe_nom || `Évaluation #${evaluation.id}`}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          {synthese && (
            <div className="rounded-lg border border-border bg-card px-3 py-2 text-sm">
              <p className="font-medium">
                {synthese.nb_soumis ?? 0}/{synthese.nb_invites ?? 0} retour(s) soumis
              </p>
              {synthese.anonymise ? (
                <p className="text-xs text-muted-foreground">
                  Synthèse anonymisée sous le seuil de répondants — moyenne agrégée uniquement.
                </p>
              ) : moyennes.length > 0 ? (
                <ul className="mt-1 flex flex-col gap-0.5 text-xs text-muted-foreground">
                  {moyennes.map(([critere, note]) => (
                    <li key={critere}>{critere} : {note}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          )}

          <form onSubmit={inviter} className="flex flex-wrap items-end gap-3">
            <div className="min-w-[10rem] flex-1 flex flex-col gap-1.5">
              <Label htmlFor="fb-repondant">Répondant</Label>
              <select
                id="fb-repondant"
                value={repondant}
                onChange={(e) => setRepondant(e.target.value)}
                className="h-9 w-full rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Choisir —</option>
                {employes.map((emp) => (
                  <option key={emp.id} value={emp.id}>{emp.nom} {emp.prenom}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fb-relation">Relation</Label>
              <select
                id="fb-relation"
                value={relation}
                onChange={(e) => setRelation(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {RELATIONS_FEEDBACK360.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <Button type="submit" size="sm" disabled={!repondant || inviting}>
              {inviting ? 'Invitation…' : 'Inviter'}
            </Button>
          </form>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}

          {!loading && (
            retours.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun répondant invité pour l’instant.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {retours.map((r) => (
                  <li key={r.id} className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-sm">
                    <span>{r.repondant_nom || `Répondant #${r.repondant}`}</span>
                    <Badge tone={r.soumis ? 'success' : 'neutral'}>{r.soumis ? 'Soumis' : 'En attente'}</Badge>
                  </li>
                ))}
              </ul>
            )
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
