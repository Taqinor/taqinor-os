import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { toast } from '../../ui'
import { formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'
import { StatutEmploye, TYPE_CONTRAT_LABELS } from './constants.jsx'

/* ============================================================================
   UX22 — Liste des dossiers employés.
   ----------------------------------------------------------------------------
   Tableau maître (matricule, nom, poste, contrat, embauche, statut) → clic
   ouvre le dossier détaillé (`/rh/employes/:id`). Lecture seule ici ; la
   création/édition d'un dossier reste au périmètre paramètres RH.
   ========================================================================== */

export default function EmployeList() {
  const navigate = useNavigate()
  const [rows, setRows] = useState([])
  const [alertesSecurite, setAlertesSecurite] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let vivant = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    setLoading(true)
    setError(null)
    rhApi.getEmployes()
      .then((res) => {
        if (!vivant) return
        const data = Array.isArray(res.data) ? res.data : res.data?.results ?? []
        setRows(data)
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les employés.')
        toast.error('Impossible de charger les employés.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    // YHIRE2 — rapport de sécurité : comptes restés actifs alors que le dossier
    // est sorti (doit rester vide en fonctionnement normal).
    rhApi.getComptesActifsSortis()
      .then((res) => { if (vivant) setAlertesSecurite(unwrap(res.data)) })
      .catch(() => { /* non bloquant */ })
    return () => { vivant = false }
  }, [])

  const columns = useMemo(() => [
    {
      id: 'matricule',
      header: 'Matricule',
      width: 120,
      accessor: (e) => e.matricule || '',
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span>,
    },
    {
      id: 'nom',
      header: 'Employé',
      width: 220,
      accessor: (e) => `${e.nom || ''} ${e.prenom || ''}`.trim(),
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'poste',
      header: 'Poste',
      width: 180,
      accessor: (e) => e.poste || '',
      cell: (v) => v || '—',
    },
    {
      id: 'type_contrat',
      header: 'Contrat',
      width: 120,
      accessor: (e) => e.type_contrat_display || TYPE_CONTRAT_LABELS[e.type_contrat] || e.type_contrat || '',
      cell: (v) => v || '—',
    },
    {
      id: 'date_embauche',
      header: 'Embauche',
      width: 120,
      align: 'right',
      searchable: false,
      accessor: (e) => e.date_embauche || '',
      cell: (v) => (v ? formatDate(v) : '—'),
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 120,
      accessor: (e) => e.statut || '',
      cell: (_v, e) => <StatutEmploye status={e.statut} label={e.statut_display} />,
    },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      {alertesSecurite.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div>
            <p className="font-medium">
              {alertesSecurite.length} compte(s) actif(s) alors que le dossier est sorti
            </p>
            <p className="text-xs">
              {alertesSecurite.map((a) => a.nom || a.matricule || `#${a.id}`).join(', ')}
              {' '}— à désactiver (sortie faite hors du chemin standard).
            </p>
          </div>
        </div>
      )}
      <ListShell
        title="Employés"
        columns={columns}
        rows={rows}
        loading={loading}
        error={error}
        searchable
        searchPlaceholder="Rechercher matricule, nom, poste…"
        exportName="employes"
        onRowClick={(e) => navigate(`/rh/employes/${e.id}`)}
        emptyTitle="Aucun employé"
        emptyDescription="Aucun dossier employé pour le moment."
      />
    </div>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
