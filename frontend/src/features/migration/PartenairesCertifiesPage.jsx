import { useCallback, useEffect, useState } from 'react'

import { ListShell } from '../../ui/module'
import { Badge } from '../../ui'
import migrationApi from '../../api/migrationApi'
import { NIVEAUX_CERTIFICATION, SPECIALITES_PARTENAIRE, errMessage } from './constants'

/* Sélecteur natif léger pour les filtres inline de cet écran — même patron
   que `kb/FilterSelect.jsx`, gardé LOCAL pour ne pas coupler le module
   migration au module kb pour un simple `<select>`. */
function FiltreSelect({ value, onChange, options, ...props }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-[var(--control-h)] rounded-md border border-input bg-card px-2 text-sm text-foreground shadow-ui-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      {...props}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

/* ============================================================================
   NTMIG29 — Annuaire interne des partenaires certifiés (Administrateur/
   Directeur). Distinct du portail partenaire lui-même (owned NTPRT) : cet
   écran est réservé à l'équipe interne, filtre par niveau/spécialité/zone, et
   affiche le score PROPOSÉ (NTMIG27) + l'historique des déploiements
   (NTMIG28). LECTURE SEULE — le niveau de certification reste un PATCH
   explicite sur la fiche partenaire (`crm/partenaires/<id>/`).
   ========================================================================== */

const NIVEAU_TONE = {
  aucun: 'neutral',
  enregistre: 'info',
  certifie: 'success',
  or: 'warning',
  platine: 'primary',
}

const COLUMNS = [
  { id: 'nom', header: 'Partenaire', accessor: (r) => r.nom, sortable: true },
  {
    id: 'niveau',
    header: 'Certification',
    accessor: (r) => r.niveau_certification_display,
    cell: (value, r) => (
      <Badge tone={NIVEAU_TONE[r.niveau_certification] || 'neutral'}>{value}</Badge>
    ),
    sortable: true,
  },
  {
    id: 'specialites',
    header: 'Spécialités',
    accessor: (r) => (r.specialites || []).join(', ') || '—',
  },
  { id: 'zone', header: 'Zone', accessor: (r) => r.zone || '—', sortable: true },
  { id: 'score', header: 'Score', accessor: (r) => r.score, sortable: true },
  {
    id: 'deploiements',
    header: 'Déploiements réussis',
    accessor: (r) => r.nb_deploiements_reussis,
  },
  {
    id: 'expiration',
    header: 'Échéance certification',
    accessor: (r) => r.date_expiration_certification || '—',
    cell: (value, r) => (
      r.certification_expiree
        ? <Badge tone="danger">Expirée ({value})</Badge>
        : value
    ),
  },
]

export default function PartenairesCertifiesPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [niveauMin, setNiveauMin] = useState('')
  const [specialite, setSpecialite] = useState('')
  const [zone, setZone] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {}
      if (niveauMin) params.niveau_min = niveauMin
      if (specialite) params.specialite = specialite
      if (zone) params.zone = zone
      const res = await migrationApi.listPartenairesCertifies(params)
      setRows(Array.isArray(res?.data) ? res.data : [])
    } catch (err) {
      setError(errMessage(err, "Impossible de charger l'annuaire des partenaires."))
    } finally {
      setLoading(false)
    }
  }, [niveauMin, specialite, zone])

  useEffect(() => {
    let alive = true
    ;(async () => {
      if (alive) await load()
    })()
    return () => {
      alive = false
    }
  }, [load])

  const filters = (
    <>
      <FiltreSelect
        value={niveauMin}
        onChange={setNiveauMin}
        options={NIVEAUX_CERTIFICATION}
        aria-label="Niveau de certification minimum"
      />
      <FiltreSelect
        value={specialite}
        onChange={setSpecialite}
        options={SPECIALITES_PARTENAIRE}
        aria-label="Spécialité"
      />
      <input
        type="text"
        value={zone}
        onChange={(e) => setZone(e.target.value)}
        placeholder="Zone…"
        aria-label="Zone géographique"
        className="h-[var(--control-h)] rounded-md border border-input bg-card px-2 text-sm text-foreground shadow-ui-xs"
      />
    </>
  )

  return (
    <ListShell
      title="Partenaires certifiés"
      subtitle="Annuaire interne des partenaires intégrateurs : niveau, spécialités,
        score proposé et historique de déploiements."
      filters={filters}
      columns={COLUMNS}
      rows={rows}
      loading={loading}
      error={error}
      searchPlaceholder="Rechercher un partenaire…"
      exportName="partenaires-certifies"
      emptyTitle="Aucun partenaire qualifié"
      emptyDescription="Aucun partenaire ne correspond à ces filtres."
    />
  )
}
