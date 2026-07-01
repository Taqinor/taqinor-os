import { useEffect, useMemo, useState } from 'react'
import { ListShell, EcheanceCenter } from '../../ui/module'
import { Segmented, Badge, toast } from '../../ui'
import { formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'

/* ============================================================================
   UX25 — Compétences, habilitations & formation.
   ----------------------------------------------------------------------------
   Matrice des compétences par employé, suivi de validité (habilitations,
   certifications, visites médicales) via un centre d'échéances, et sessions /
   besoins de formation. Les titres expirés/à expirer alimentent le centre
   d'échéances (couleur + pastille jamais seul signal).
   ========================================================================== */

const VUES = [
  { value: 'matrice', label: 'Matrice compétences' },
  { value: 'habilitations', label: 'Habilitations' },
  { value: 'certifications', label: 'Certifications' },
  { value: 'formation', label: 'Formation' },
]

export default function Competences() {
  const [vue, setVue] = useState('matrice')
  const [competencesEmp, setCompetencesEmp] = useState([])
  const [habilitations, setHabilitations] = useState([])
  const [certifications, setCertifications] = useState([])
  const [visites, setVisites] = useState([])
  const [sessions, setSessions] = useState([])
  const [besoins, setBesoins] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

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
    ])
      .then(([ce, hab, cert, vm, ses, bes]) => {
        if (!vivant) return
        setCompetencesEmp(unwrap(ce.data))
        setHabilitations(unwrap(hab.data))
        setCertifications(unwrap(cert.data))
        setVisites(unwrap(vm.data))
        setSessions(unwrap(ses.data))
        setBesoins(unwrap(bes.data))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les compétences.')
        toast.error('Impossible de charger les compétences.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [])

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

  const sessionColumns = useMemo(() => [
    { id: 'intitule', header: 'Intitulé', width: 220, accessor: (s) => s.intitule || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'organisme', header: 'Organisme', width: 160, accessor: (s) => s.organisme || '', cell: (v) => v || '—' },
    { id: 'debut', header: 'Début', width: 120, searchable: false, accessor: (s) => s.date_debut || '', cell: (v) => formatDate(v) },
    { id: 'statut', header: 'Statut', width: 120, accessor: (s) => s.statut_display || s.statut || '', cell: (v) => v || '—' },
  ], [])

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
              emptyTitle="Aucune compétence" emptyDescription="Aucune compétence évaluée." />
          )}
          {vue === 'habilitations' && (
            <ListShell title="Habilitations" columns={titreColumns('type_habilitation', 'type_habilitation_display')}
              rows={habilitations} loading={loading} error={error} searchable exportName="habilitations"
              emptyTitle="Aucune habilitation" emptyDescription="Aucune habilitation enregistrée." />
          )}
          {vue === 'certifications' && (
            <ListShell title="Certifications" columns={titreColumns('type_certification', 'type_certification_display')}
              rows={certifications} loading={loading} error={error} searchable exportName="certifications"
              emptyTitle="Aucune certification" emptyDescription="Aucune certification enregistrée." />
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
    </div>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
