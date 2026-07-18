import { useEffect, useMemo, useState } from 'react'
import { Power, Trash2, Plus } from 'lucide-react'
import { ListShell, EcheanceCenter } from '../../ui/module'
import {
  Segmented, Badge, toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'

/* ============================================================================
   UX25 — Compétences, habilitations & formation.
   ----------------------------------------------------------------------------
   Matrice des compétences par employé, suivi de validité (habilitations,
   certifications, visites médicales) via un centre d'échéances, et sessions /
   besoins de formation. Les titres expirés/à expirer alimentent le centre
   d'échéances (couleur + pastille jamais seul signal). WIR36 — saisie
   manuelle (évaluation de compétence, habilitation, certification, visite
   médicale, quiz) câblée sur les wrappers d'écriture de `rhApi.js` ajoutés
   pour l'occasion (ViewSets full CRUD jusqu'ici sans appelant côté écriture).
   ========================================================================== */

const VUES = [
  { value: 'matrice', label: 'Matrice compétences' },
  { value: 'habilitations', label: 'Habilitations' },
  { value: 'certifications', label: 'Certifications' },
  { value: 'visites', label: 'Visites médicales' },
  { value: 'formation', label: 'Formation' },
  { value: 'quiz', label: 'Quiz' },
  { value: 'organigramme', label: 'Organigramme' },
]

// Habilitation.TypeHabilitation.choices (NF C 18-510) — côté serveur.
const TYPE_HABILITATION_OPTIONS = [
  { value: 'b0', label: "B0 — Non-électricien (travaux d'ordre non électrique BT)" },
  { value: 'h0', label: 'H0 — Non-électricien (zone HT)' },
  { value: 'h0v', label: 'H0V — Non-électricien (voisinage HT)' },
  { value: 'b1', label: 'B1 — Exécutant électricien BT' },
  { value: 'b1v', label: 'B1V — Exécutant électricien BT (voisinage)' },
  { value: 'b2', label: 'B2 — Chargé de travaux BT' },
  { value: 'b2v', label: 'B2V — Chargé de travaux BT (voisinage)' },
  { value: 'br', label: "BR — Chargé d'intervention générale BT" },
  { value: 'bc', label: 'BC — Chargé de consignation BT' },
  { value: 'be', label: "BE — Chargé d'opérations spécifiques BT" },
  { value: 'h1', label: 'H1 — Exécutant électricien HT' },
  { value: 'h1v', label: 'H1V — Exécutant électricien HT (voisinage)' },
  { value: 'h2', label: 'H2 — Chargé de travaux HT' },
  { value: 'h2v', label: 'H2V — Chargé de travaux HT (voisinage)' },
  { value: 'hc', label: 'HC — Chargé de consignation HT' },
  { value: 'bp', label: 'BP — Photovoltaïque (opérations sur installation PV)' },
  { value: 'autre', label: 'Autre' },
]

// Certification.TypeCertification.choices — côté serveur.
const TYPE_CERTIFICATION_OPTIONS = [
  { value: 'travail_hauteur', label: 'Travail en hauteur' },
  { value: 'harnais', label: 'Port du harnais / EPI antichute' },
  { value: 'caces_nacelle', label: 'CACES / nacelle (PEMP)' },
  { value: 'secourisme_sst', label: 'Secourisme du travail (SST)' },
  { value: 'conduite', label: 'Conduite (permis / engins)' },
  { value: 'autre', label: 'Autre' },
]

// CompetenceEmploye.Niveau.choices — côté serveur.
const NIVEAU_OPTIONS = [
  { value: '0', label: 'Non acquis' },
  { value: '1', label: 'Débutant' },
  { value: '2', label: 'Intermédiaire' },
  { value: '3', label: 'Confirmé' },
  { value: '4', label: 'Expert' },
]

// VisiteMedicale.Aptitude.choices — côté serveur.
const APTITUDE_OPTIONS = [
  { value: 'apte', label: 'Apte' },
  { value: 'apte_avec_restrictions', label: 'Apte avec restrictions' },
  { value: 'inapte', label: 'Inapte' },
]

export default function Competences() {
  const { confirmDelete } = useConfirmDialog()
  const [vue, setVue] = useState('matrice')
  const [competencesEmp, setCompetencesEmp] = useState([])
  const [habilitations, setHabilitations] = useState([])
  const [certifications, setCertifications] = useState([])
  const [visites, setVisites] = useState([])
  const [sessions, setSessions] = useState([])
  const [besoins, setBesoins] = useState([])
  const [quiz, setQuiz] = useState([])
  const [arbre, setArbre] = useState([])
  const [employes, setEmployes] = useState([])
  const [catalogue, setCatalogue] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)

  // WIR36 — dialogues de création.
  const [evalOpen, setEvalOpen] = useState(false)
  const [habOpen, setHabOpen] = useState(false)
  const [certOpen, setCertOpen] = useState(false)
  const [visiteOpen, setVisiteOpen] = useState(false)
  const [quizOpen, setQuizOpen] = useState(false)

  const recharger = () => setReloadTick((t) => t + 1)

  useEffect(() => {
    let vivant = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    setLoading(true)
    setError(null)
    Promise.all([
      rhApi.getCompetencesEmploye(),
      rhApi.getHabilitations(),
      rhApi.getCertifications(),
      rhApi.getVisitesMedicales(),
      rhApi.getSessionsFormation(),
      rhApi.getBesoinsFormation(),
      rhApi.getQuizFormation(),
      rhApi.getArbreDepartements(),
      rhApi.getEmployes(),
      rhApi.getCompetences(),
    ])
      .then(([ce, hab, cert, vm, ses, bes, qz, ar, emp, cat]) => {
        if (!vivant) return
        setCompetencesEmp(unwrap(ce.data))
        setHabilitations(unwrap(hab.data))
        setCertifications(unwrap(cert.data))
        setVisites(unwrap(vm.data))
        setSessions(unwrap(ses.data))
        setBesoins(unwrap(bes.data))
        setQuiz(unwrap(qz.data))
        setArbre(unwrap(ar.data))
        setEmployes(unwrap(emp.data))
        setCatalogue(unwrap(cat.data))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les compétences.')
        toast.error('Impossible de charger les compétences.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const basculerQuiz = async (q) => {
    try {
      await rhApi.updateQuizFormation(q.id, { actif: !q.actif })
      toast.success(q.actif ? 'Quiz désactivé.' : 'Quiz activé.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Modification impossible.')
    }
  }

  const supprimerQuiz = async (q) => {
    const ok = await confirmDelete({
      title: 'Supprimer ce quiz ?',
      description: `« ${q.intitule} » sera supprimé.`,
      confirmLabel: 'Supprimer',
    })
    if (!ok) return
    try {
      await rhApi.deleteQuizFormation(q.id)
      toast.success('Quiz supprimé.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Suppression impossible.')
    }
  }

  // Centre d'échéances : titres réglementaires + visites à expirer.
  const echeanceItems = useMemo(() => {
    const items = []
    const jours = (d) => (d ? Math.round((new Date(d) - new Date()) / 86400000) : null)
    habilitations.forEach((h) => h.date_validite && items.push({
      id: `hab-${h.id}`, label: `Habilitation — ${h.type_habilitation_display || h.type_habilitation}`,
      date: h.date_validite, daysLeft: jours(h.date_validite),
      meta: h.employe_nom || `Employé ${h.employe}`,
    }))
    certifications.forEach((c) => c.date_validite && items.push({
      id: `cert-${c.id}`, label: `Certification — ${c.type_certification_display || c.type_certification}`,
      date: c.date_validite, daysLeft: jours(c.date_validite),
      meta: c.employe_nom || `Employé ${c.employe}`,
    }))
    visites.forEach((v) => v.prochaine_visite && items.push({
      id: `vm-${v.id}`, label: 'Visite médicale',
      date: v.prochaine_visite, daysLeft: jours(v.prochaine_visite),
      meta: v.employe_nom || `Employé ${v.employe}`,
    }))
    return items
  }, [habilitations, certifications, visites])

  const matriceColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (c) => c.employe_nom || String(c.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'competence', header: 'Compétence', width: 200, accessor: (c) => c.competence_libelle || c.competence_code || '', cell: (v) => v || '—' },
    { id: 'niveau', header: 'Niveau', width: 130, accessor: (c) => c.niveau_display || String(c.niveau ?? ''), cell: (v) => v || '—' },
    { id: 'evalue', header: 'Évalué le', width: 120, searchable: false, accessor: (c) => c.evalue_le || '', cell: (v) => (v ? formatDate(v) : '—') },
  ], [])

  const titreColumns = (typeKey, displayKey) => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (t) => t.employe_nom || String(t.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'type', header: 'Type', width: 180, accessor: (t) => t[displayKey] || t[typeKey] || '', cell: (v) => v || '—' },
    { id: 'organisme', header: 'Organisme', width: 160, accessor: (t) => t.organisme || '', cell: (v) => v || '—' },
    { id: 'validite', header: 'Validité', width: 120, searchable: false, accessor: (t) => t.date_validite || '', cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'etat', header: 'État', width: 100, accessor: (t) => (t.valide ? 'valide' : 'expiree'), cell: (_v, t) => <Badge tone={t.valide ? 'success' : 'danger'}>{t.valide ? 'Valide' : 'Expirée'}</Badge> },
  ]

  // WIR36 — visites médicales : pas de liste dédiée jusqu'ici (uniquement le
  // centre d'échéances) ; colonnes propres (aptitude, distinct de valide/expirée).
  const visiteColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (v) => v.employe_nom || String(v.employe || ''), cell: (val) => <span className="font-medium">{val || '—'}</span> },
    { id: 'date_visite', header: 'Visite du', width: 120, searchable: false, accessor: (v) => v.date_visite || '', cell: (val) => (val ? formatDate(val) : '—') },
    { id: 'prochaine', header: 'Prochaine échéance', width: 150, searchable: false, accessor: (v) => v.prochaine_visite || '', cell: (val) => (val ? formatDate(val) : '—') },
    { id: 'aptitude', header: 'Aptitude', width: 160, accessor: (v) => v.aptitude_display || v.aptitude || '', cell: (val, v) => <Badge tone={v.aptitude === 'inapte' ? 'danger' : v.aptitude === 'apte_avec_restrictions' ? 'warning' : 'success'}>{val || '—'}</Badge> },
  ], [])

  const sessionColumns = useMemo(() => [
    { id: 'intitule', header: 'Intitulé', width: 220, accessor: (s) => s.intitule || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'organisme', header: 'Organisme', width: 160, accessor: (s) => s.organisme || '', cell: (v) => v || '—' },
    { id: 'debut', header: 'Début', width: 120, searchable: false, accessor: (s) => s.date_debut || '', cell: (v) => formatDate(v) },
    { id: 'statut', header: 'Statut', width: 120, accessor: (s) => s.statut_display || s.statut || '', cell: (v) => v || '—' },
  ], [])

  const quizColumns = useMemo(() => [
    { id: 'intitule', header: 'Quiz', width: 240, accessor: (q) => q.intitule || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'questions', header: 'Questions', width: 110, align: 'right', searchable: false, accessor: (q) => (Array.isArray(q.questions) ? q.questions.length : (q.questions_count ?? '')), cell: (v) => (v === '' ? '—' : v) },
    { id: 'seuil', header: 'Seuil', width: 90, align: 'right', searchable: false, accessor: (q) => q.seuil_reussite ?? '', cell: (v) => (v === '' ? '—' : `${v}%`) },
    { id: 'actif', header: 'Actif', width: 100, accessor: (q) => (q.actif ? 'oui' : 'non'), cell: (_v, q) => <Badge tone={q.actif ? 'success' : 'neutral'}>{q.actif ? 'Actif' : 'Inactif'}</Badge> },
  ], [])

  const quizActions = (q) => [
    { id: 'toggle', label: q.actif ? 'Désactiver' : 'Activer', icon: Power, onClick: () => basculerQuiz(q) },
    { id: 'suppr', label: 'Supprimer', icon: Trash2, destructive: true, onClick: () => supprimerQuiz(q) },
  ]

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Compétences & habilitations</h2>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="flex flex-col gap-4">
          <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue compétences" />

          {vue === 'matrice' && (
            <ListShell title="Matrice des compétences" columns={matriceColumns} rows={competencesEmp}
              loading={loading} error={error} searchable exportName="matrice-competences"
              actions={<Button onClick={() => setEvalOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle évaluation</Button>}
              emptyTitle="Aucune compétence" emptyDescription="Aucune compétence évaluée." />
          )}
          {vue === 'habilitations' && (
            <ListShell title="Habilitations" columns={titreColumns('type_habilitation', 'type_habilitation_display')}
              rows={habilitations} loading={loading} error={error} searchable exportName="habilitations"
              actions={<Button onClick={() => setHabOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle habilitation</Button>}
              emptyTitle="Aucune habilitation" emptyDescription="Aucune habilitation enregistrée." />
          )}
          {vue === 'certifications' && (
            <ListShell title="Certifications" columns={titreColumns('type_certification', 'type_certification_display')}
              rows={certifications} loading={loading} error={error} searchable exportName="certifications"
              actions={<Button onClick={() => setCertOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle certification</Button>}
              emptyTitle="Aucune certification" emptyDescription="Aucune certification enregistrée." />
          )}
          {/* WIR36 — visites médicales (jusqu'ici affichées uniquement dans le
              centre d'échéances, sans écran de liste/saisie dédié). */}
          {vue === 'visites' && (
            <ListShell title="Visites médicales" columns={visiteColumns} rows={visites}
              loading={loading} error={error} searchable exportName="visites-medicales"
              actions={<Button onClick={() => setVisiteOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle visite</Button>}
              emptyTitle="Aucune visite" emptyDescription="Aucune visite médicale enregistrée." />
          )}
          {vue === 'formation' && (
            <>
              <ListShell title="Sessions de formation" columns={sessionColumns} rows={sessions}
                loading={loading} error={error} searchable exportName="sessions-formation"
                emptyTitle="Aucune session" emptyDescription="Aucune session planifiée." />
              <ListShell title="Besoins de formation"
                columns={[
                  { id: 'employe', header: 'Employé', width: 180, accessor: (b) => b.employe_nom || String(b.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
                  { id: 'theme', header: 'Thème', width: 200, accessor: (b) => b.theme || '', cell: (v) => v || '—' },
                  { id: 'priorite', header: 'Priorité', width: 120, accessor: (b) => b.priorite_display || b.priorite || '', cell: (v) => v || '—' },
                  { id: 'statut', header: 'Statut', width: 120, accessor: (b) => b.statut_display || b.statut || '', cell: (v) => v || '—' },
                ]}
                rows={besoins} loading={loading} error={error} searchable exportName="besoins-formation"
                emptyTitle="Aucun besoin" emptyDescription="Aucun besoin de formation." />
            </>
          )}
          {vue === 'quiz' && (
            <ListShell title="Quiz de formation" columns={quizColumns} rows={quiz}
              loading={loading} error={error} searchable rowActions={quizActions} exportName="quiz-formation"
              actions={<Button onClick={() => setQuizOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouveau quiz</Button>}
              emptyTitle="Aucun quiz" emptyDescription="Aucun quiz d’évaluation configuré." />
          )}
          {vue === 'organigramme' && (
            <div className="rounded-lg border border-border bg-card p-4">
              {arbre.length === 0
                ? <p className="text-sm text-muted-foreground">Aucun département.</p>
                : <ArbreDepartements noeuds={arbre} />}
            </div>
          )}
        </div>

        <EcheanceCenter
          title="Titres à échéance"
          items={echeanceItems}
          loading={loading}
          error={error}
          emptyText="Aucun titre réglementaire à échéance."
          max={12}
        />
      </div>
      {evalOpen && (
        <CompetenceEmployeDialog
          employes={employes}
          catalogue={catalogue}
          onClose={() => setEvalOpen(false)}
          onSaved={() => { setEvalOpen(false); recharger() }}
        />
      )}
      {habOpen && (
        <HabilitationDialog
          employes={employes}
          onClose={() => setHabOpen(false)}
          onSaved={() => { setHabOpen(false); recharger() }}
        />
      )}
      {certOpen && (
        <CertificationDialog
          employes={employes}
          onClose={() => setCertOpen(false)}
          onSaved={() => { setCertOpen(false); recharger() }}
        />
      )}
      {visiteOpen && (
        <VisiteMedicaleDialog
          employes={employes}
          onClose={() => setVisiteOpen(false)}
          onSaved={() => { setVisiteOpen(false); recharger() }}
        />
      )}
      {quizOpen && (
        <QuizFormationDialog
          onClose={() => setQuizOpen(false)}
          onSaved={() => { setQuizOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

/* ── WIR36 — Évaluer une compétence (matrice) ── */
function CompetenceEmployeDialog({ employes, catalogue, onClose, onSaved }) {
  const [employe, setEmploye] = useState('')
  const [competence, setCompetence] = useState('')
  const [niveau, setNiveau] = useState('2')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || competence || note)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe && competence)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createCompetenceEmploye({ employe, competence, niveau: Number(niveau), note: note || '' })
      toast.success('Évaluation de compétence enregistrée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.non_field_errors?.[0] || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvelle évaluation de compétence</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ce-employe">Employé</Label>
              <select id="ce-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ce-competence">Compétence</Label>
              <select id="ce-competence" value={competence} onChange={(e) => setCompetence(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {catalogue.map((c) => <option key={c.id} value={c.id}>{c.libelle || c.code}</option>)}
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ce-niveau">Niveau</Label>
            <select id="ce-niveau" value={niveau} onChange={(e) => setNiveau(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              {NIVEAU_OPTIONS.map((n) => <option key={n.value} value={n.value}>{n.label}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ce-note">Note (optionnel)</Label>
            <Textarea id="ce-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR36 — Nouvelle habilitation électrique ── */
function HabilitationDialog({ employes, onClose, onSaved }) {
  const [employe, setEmploye] = useState('')
  const [type, setType] = useState('b1v')
  const [organisme, setOrganisme] = useState('')
  const [dateObtention, setDateObtention] = useState('')
  const [dateValidite, setDateValidite] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || organisme || dateObtention || dateValidite || note)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createHabilitation({
        employe, type_habilitation: type, organisme: organisme || '',
        date_obtention: dateObtention || null, date_validite: dateValidite || null,
        note: note || '',
      })
      toast.success('Habilitation enregistrée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvelle habilitation</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ha-employe">Employé</Label>
            <select id="ha-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              <option value="">— Choisir —</option>
              {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ha-type">Titre d’habilitation</Label>
            <select id="ha-type" value={type} onChange={(e) => setType(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              {TYPE_HABILITATION_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ha-organisme">Organisme délivrant</Label>
            <Input id="ha-organisme" value={organisme} onChange={(e) => setOrganisme(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ha-obtention">Date d’obtention</Label>
              <Input id="ha-obtention" type="date" value={dateObtention} onChange={(e) => setDateObtention(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ha-validite">Validité jusqu’au</Label>
              <Input id="ha-validite" type="date" value={dateValidite} onChange={(e) => setDateValidite(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ha-note">Note (optionnel)</Label>
            <Textarea id="ha-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR36 — Nouvelle certification ── */
function CertificationDialog({ employes, onClose, onSaved }) {
  const [employe, setEmploye] = useState('')
  const [type, setType] = useState('travail_hauteur')
  const [organisme, setOrganisme] = useState('')
  const [dateObtention, setDateObtention] = useState('')
  const [dateValidite, setDateValidite] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || organisme || dateObtention || dateValidite || note)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createCertification({
        employe, type_certification: type, organisme: organisme || '',
        date_obtention: dateObtention || null, date_validite: dateValidite || null,
        note: note || '',
      })
      toast.success('Certification enregistrée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvelle certification</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ct-employe">Employé</Label>
            <select id="ct-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              <option value="">— Choisir —</option>
              {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ct-type">Type de certification</Label>
            <select id="ct-type" value={type} onChange={(e) => setType(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              {TYPE_CERTIFICATION_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ct-organisme">Organisme délivrant</Label>
            <Input id="ct-organisme" value={organisme} onChange={(e) => setOrganisme(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ct-obtention">Date d’obtention</Label>
              <Input id="ct-obtention" type="date" value={dateObtention} onChange={(e) => setDateObtention(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ct-validite">Validité jusqu’au</Label>
              <Input id="ct-validite" type="date" value={dateValidite} onChange={(e) => setDateValidite(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ct-note">Note (optionnel)</Label>
            <Textarea id="ct-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR36 — Nouvelle visite médicale du travail ── */
function VisiteMedicaleDialog({ employes, onClose, onSaved }) {
  const [employe, setEmploye] = useState('')
  const [dateVisite, setDateVisite] = useState('')
  const [prochaineVisite, setProchaineVisite] = useState('')
  const [aptitude, setAptitude] = useState('apte')
  const [medecin, setMedecin] = useState('')
  const [organisme, setOrganisme] = useState('')
  const [restrictions, setRestrictions] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || dateVisite || prochaineVisite || medecin || organisme || restrictions)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createVisiteMedicale({
        employe, date_visite: dateVisite || null, prochaine_visite: prochaineVisite || null,
        aptitude, medecin: medecin || '', organisme: organisme || '',
        restrictions: restrictions || '',
      })
      toast.success('Visite médicale enregistrée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvelle visite médicale</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="vm-employe">Employé</Label>
            <select id="vm-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              <option value="">— Choisir —</option>
              {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="vm-date">Date de la visite</Label>
              <Input id="vm-date" type="date" value={dateVisite} onChange={(e) => setDateVisite(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="vm-prochaine">Prochaine visite</Label>
              <Input id="vm-prochaine" type="date" value={prochaineVisite} onChange={(e) => setProchaineVisite(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="vm-aptitude">Verdict d’aptitude</Label>
            <select id="vm-aptitude" value={aptitude} onChange={(e) => setAptitude(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              {APTITUDE_OPTIONS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="vm-medecin">Médecin du travail</Label>
              <Input id="vm-medecin" value={medecin} onChange={(e) => setMedecin(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="vm-organisme">Organisme / service santé</Label>
              <Input id="vm-organisme" value={organisme} onChange={(e) => setOrganisme(e.target.value)} />
            </div>
          </div>
          {aptitude === 'apte_avec_restrictions' && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="vm-restrictions">Restrictions de poste</Label>
              <Textarea id="vm-restrictions" value={restrictions} onChange={(e) => setRestrictions(e.target.value)} rows={2} />
            </div>
          )}
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR36 (XRH34) — Nouveau quiz de formation ── */
function QuizFormationDialog({ onClose, onSaved }) {
  const [intitule, setIntitule] = useState('')
  const [scoreReussite, setScoreReussite] = useState('80')
  const [question, setQuestion] = useState('')
  const [choixTexte, setChoixTexte] = useState('')
  const [bonnesReponses, setBonnesReponses] = useState('0')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(intitule || question || choixTexte)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(intitule.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      // Une question minimale (texte + choix + bonne(s) réponse(s), index dans
      // `choix`) — le format JSON exact attendu par `QuizFormation.questions`.
      const choix = choixTexte.split('\n').map((l) => l.trim()).filter(Boolean)
      const bonnes = bonnesReponses.split(',').map((s) => Number(s.trim())).filter((n) => Number.isInteger(n) && n >= 0)
      const questions = (question.trim() && choix.length > 0)
        ? [{
          question: question.trim(),
          type: bonnes.length > 1 ? 'multiple' : 'unique',
          choix,
          bonnes_reponses: bonnes,
        }]
        : []
      await rhApi.createQuizFormation({
        intitule: intitule.trim(),
        score_reussite: Number(scoreReussite) || 80,
        questions,
      })
      toast.success('Quiz créé.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.intitule || 'Création du quiz impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouveau quiz</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-[1fr_140px] gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="qz-intitule">Intitulé</Label>
              <Input id="qz-intitule" autoFocus value={intitule} onChange={(e) => setIntitule(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="qz-seuil">Seuil de réussite (%)</Label>
              <Input id="qz-seuil" type="number" step="any" min="0" max="100" value={scoreReussite} onChange={(e) => setScoreReussite(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="qz-question">Question (optionnel)</Label>
            <Input id="qz-question" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ex. Quelle est la tension d’une installation BT ?" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="qz-choix">Choix (un par ligne)</Label>
            <Textarea id="qz-choix" value={choixTexte} onChange={(e) => setChoixTexte(e.target.value)} rows={3} placeholder={'Ex.\n≤ 50 V\n50 à 1000 V\n> 1000 V'} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="qz-bonnes">Index de(s) bonne(s) réponse(s) (séparés par virgule, 0 = premier choix)</Label>
            <Input id="qz-bonnes" value={bonnesReponses} onChange={(e) => setBonnesReponses(e.target.value)} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Création…' : 'Créer le quiz'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* XRH27 — arbre des départements (effectif propre + cumulé). */
function ArbreDepartements({ noeuds, niveau = 0 }) {
  return (
    <ul className={niveau === 0 ? 'flex flex-col gap-1' : 'ml-4 flex flex-col gap-1 border-l border-border pl-3'}>
      {noeuds.map((n) => (
        <li key={n.id ?? n.nom} className="flex flex-col gap-1">
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className="font-medium">{n.nom || '—'}</span>
            <span className="text-xs text-muted-foreground">
              {n.effectif_propre ?? n.effectif ?? 0}
              {n.effectif_cumule != null && n.effectif_cumule !== (n.effectif_propre ?? n.effectif)
                ? ` (${n.effectif_cumule} avec sous-dép.)` : ''}
            </span>
          </div>
          {Array.isArray(n.enfants) && n.enfants.length > 0 && (
            <ArbreDepartements noeuds={n.enfants} niveau={niveau + 1} />
          )}
        </li>
      ))}
    </ul>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
