import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { DetailShell } from '../../ui/module'
import { DefinitionList, EmptyState, Skeleton, Badge, toast } from '../../ui'
import { formatMAD, formatDate, formatPhoneMA } from '../../lib/format'
import { useSelector } from 'react-redux'
import rhApi from '../../api/rhApi'
import { peutVoirSalaires } from './permissions.js'
import { StatutEmploye, TYPE_CONTRAT_LABELS } from './constants.jsx'

/* ============================================================================
   UX22 — Dossier employé (détail multi-onglets).
   ----------------------------------------------------------------------------
   Onglets : Identité, Contrat, Documents, Rémunération (masqué sans la
   permission `salaires_voir`), Habilitations, Formations. Les rémunérations
   sont chargées uniquement si l'utilisateur peut les voir (le serveur renvoie
   403 sinon). Jamais de prix d'achat ni de marge — montants paie légitimes,
   gatés par permission.
   ========================================================================== */

function Liste({ rows, loading, empty, renderRow }) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }).map((unused, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }
  if (!rows.length) {
    return <EmptyState title="Rien à afficher" description={empty} />
  }
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((r, i) => (
        <li key={r.id ?? i} className="rounded-lg border border-border bg-card px-3 py-2 text-sm">
          {renderRow(r)}
        </li>
      ))}
    </ul>
  )
}

export default function EmployeDetail() {
  const { id } = useParams()
  const permissions = useSelector((s) => s.auth.permissions)
  const canSalaires = peutVoirSalaires(permissions)

  const [emp, setEmp] = useState(null)
  const [documents, setDocuments] = useState([])
  const [remunerations, setRemunerations] = useState([])
  const [habilitations, setHabilitations] = useState([])
  const [formation, setFormation] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [subLoading, setSubLoading] = useState(true)

  useEffect(() => {
    let vivant = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    setLoading(true)
    setError(null)
    rhApi.getEmploye(id)
      .then((res) => { if (vivant) setEmp(res.data) })
      .catch(() => {
        if (!vivant) return
        setError('Employé introuvable.')
        toast.error('Employé introuvable.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [id])

  useEffect(() => {
    let vivant = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    setSubLoading(true)
    const calls = [
      rhApi.getDocuments({ employe: id }),
      rhApi.getHabilitations({ employe: id }),
      rhApi.getRegistreFormation(id),
    ]
    if (canSalaires) calls.push(rhApi.getRemunerations({ employe: id }))
    Promise.allSettled(calls).then((results) => {
      if (!vivant) return
      const [docRes, habRes, formRes, remRes] = results
      if (docRes.status === 'fulfilled') setDocuments(unwrap(docRes.value.data))
      if (habRes.status === 'fulfilled') setHabilitations(unwrap(habRes.value.data))
      if (formRes.status === 'fulfilled') setFormation(formRes.value.data)
      if (canSalaires && remRes?.status === 'fulfilled') {
        setRemunerations(unwrap(remRes.value.data))
      }
      setSubLoading(false)
    })
    return () => { vivant = false }
  }, [id, canSalaires])

  if (loading) {
    return (
      <div className="page flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (error || !emp) {
    return (
      <div className="page">
        <EmptyState title="Employé introuvable" description="Ce dossier n'existe pas ou n'est pas accessible." />
      </div>
    )
  }

  const nomComplet = `${emp.nom} ${emp.prenom}`.trim()

  const identiteTab = (
    <DefinitionList
      items={[
        { term: 'Matricule', description: emp.matricule || '—' },
        { term: 'Nom complet', description: nomComplet || '—' },
        { term: 'CIN', description: emp.cin || '—' },
        { term: 'CNSS', description: emp.cnss || '—' },
        { term: 'Situation familiale', description: emp.situation_familiale_display || '—' },
        { term: 'Enfants', description: emp.nombre_enfants ?? '—' },
        { term: 'Téléphone', description: emp.telephone ? formatPhoneMA(emp.telephone) : '—' },
        { term: 'Email', description: emp.email || '—' },
        { term: 'Contact d’urgence', description: emp.urgence_nom
          ? `${emp.urgence_nom}${emp.urgence_lien ? ` (${emp.urgence_lien})` : ''}${emp.urgence_telephone ? ` — ${formatPhoneMA(emp.urgence_telephone)}` : ''}`
          : '—' },
      ]}
    />
  )

  const contratTab = (
    <DefinitionList
      items={[
        { term: 'Poste', description: emp.poste || '—' },
        { term: 'Département', description: emp.departement ? String(emp.departement) : '—' },
        { term: 'Type de contrat', description: emp.type_contrat_display || TYPE_CONTRAT_LABELS[emp.type_contrat] || '—' },
        { term: 'Date d’embauche', description: formatDate(emp.date_embauche) },
        { term: 'Début de contrat', description: formatDate(emp.contrat_date_debut) },
        { term: 'Fin de contrat', description: emp.contrat_date_fin ? formatDate(emp.contrat_date_fin) : '—' },
        { term: 'Statut', description: emp.statut_display || emp.statut || '—' },
        { term: 'Date de sortie', description: emp.date_sortie ? formatDate(emp.date_sortie) : '—' },
      ]}
    />
  )

  const documentsTab = (
    <Liste
      rows={documents}
      loading={subLoading}
      empty="Aucune pièce au dossier."
      renderRow={(d) => (
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-medium">{d.type_document_display || d.type_document}</p>
            <p className="truncate text-xs text-muted-foreground">
              {d.filename || '—'}
              {d.date_expiration ? ` · expire le ${formatDate(d.date_expiration)}` : ''}
            </p>
          </div>
          {d.url && (
            <a className="link-blue text-xs" href={d.url} target="_blank" rel="noreferrer">
              Ouvrir
            </a>
          )}
        </div>
      )}
    />
  )

  const habilitationsTab = (
    <Liste
      rows={habilitations}
      loading={subLoading}
      empty="Aucune habilitation enregistrée."
      renderRow={(h) => (
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-medium">{h.type_habilitation_display || h.type_habilitation}</p>
            <p className="truncate text-xs text-muted-foreground">
              {h.organisme || '—'}
              {h.date_validite ? ` · valide jusqu’au ${formatDate(h.date_validite)}` : ''}
            </p>
          </div>
          <Badge tone={h.valide ? 'success' : 'danger'}>
            {h.valide ? 'Valide' : 'Expirée'}
          </Badge>
        </div>
      )}
    />
  )

  const formationsRows = formation?.lignes ?? []
  const formationsTab = (
    <Liste
      rows={formationsRows}
      loading={subLoading}
      empty="Aucune formation au registre."
      renderRow={(f) => (
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-medium">{f.intitule || f.session_intitule || '—'}</p>
            <p className="truncate text-xs text-muted-foreground">
              {f.organisme || '—'}
              {f.date_debut ? ` · ${formatDate(f.date_debut)}` : ''}
            </p>
          </div>
          {f.statut_display && <Badge tone="neutral">{f.statut_display}</Badge>}
        </div>
      )}
    />
  )

  const remunerationTab = (
    <Liste
      rows={remunerations}
      loading={subLoading}
      empty="Aucune rémunération enregistrée."
      renderRow={(r) => (
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-medium">{formatMAD(r.montant)}</p>
            <p className="truncate text-xs text-muted-foreground">
              {r.periodicite_display || r.periodicite || ''}
              {r.date_effet ? ` · effet le ${formatDate(r.date_effet)}` : ''}
              {r.motif ? ` · ${r.motif}` : ''}
            </p>
          </div>
        </div>
      )}
    />
  )

  const tabs = [
    { value: 'identite', label: 'Identité', content: identiteTab },
    { value: 'contrat', label: 'Contrat', content: contratTab },
    { value: 'documents', label: 'Documents', content: documentsTab, count: documents.length },
    // Rémunération masquée sans la permission salaires_voir (UX22).
    ...(canSalaires
      ? [{ value: 'remuneration', label: 'Rémunération', content: remunerationTab, count: remunerations.length }]
      : []),
    { value: 'habilitations', label: 'Habilitations', content: habilitationsTab, count: habilitations.length },
    { value: 'formations', label: 'Formations', content: formationsTab, count: formationsRows.length },
  ]

  return (
    <div className="page">
      <DetailShell
        title={nomComplet || 'Employé'}
        subtitle={emp.matricule ? `Matricule ${emp.matricule}` : undefined}
        status={emp.statut}
        statusPill={StatutEmploye}
        backTo="/rh/employes"
        backLabel="Retour aux employés"
        tabs={tabs}
      />
    </div>
  )
}

// Les listes DRF peuvent être paginées ({results:[…]}) ou brutes ([…]).
function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
