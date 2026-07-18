import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { Badge } from '../../ui'
import santeApi from '../../api/santeApi'
import { formatDate } from '../../lib/format'

/* ============================================================================
   WIR53(b) — Liste + fiche des prises en charge / entente préalable
   (NTSAN12). La tâche beat quotidienne `sante.alertes_prise_en_charge_
   expirant` (apps/sante/tasks.py) notifie le secrétariat via un lien
   `/sante/prises-en-charge?id=<pk>` — cet écran est la destination RÉELLE de
   ce lien (jusque-là jamais enregistrée, donc systématiquement un 404).
   ----------------------------------------------------------------------------
   `?id=` (lu via useSearchParams) ouvre la fiche détaillée en tête de page ;
   la liste complète reste toujours affichée en dessous. Noms patient/
   convention résolus côté client (jointure sur les listes déjà exposées) —
   aucun changement backend nécessaire (PriseEnChargeSerializer expose déjà
   tout le reste).
   ========================================================================== */

const STATUT_TONE = {
  demandee: 'neutral',
  accordee: 'success',
  refusee: 'danger',
  expiree: 'warning',
}

export default function PrisesEnChargePage() {
  const [searchParams] = useSearchParams()
  const ficheId = searchParams.get('id')

  const [pecs, setPecs] = useState([])
  const [patients, setPatients] = useState([])
  const [conventions, setConventions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    setLoading(true)
    setError(false)
    Promise.all([
      santeApi.prisesEnCharge.list(),
      santeApi.patients.list(),
      santeApi.conventions.list(),
    ])
      .then(([pecRes, patRes, convRes]) => {
        setPecs(pecRes.data?.results ?? pecRes.data ?? [])
        setPatients(patRes.data?.results ?? patRes.data ?? [])
        setConventions(convRes.data?.results ?? convRes.data ?? [])
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  const patientNom = (id) => {
    const p = patients.find((x) => x.id === id)
    return p ? `${p.nom} ${p.prenom || ''}`.trim() : `Patient #${id}`
  }
  const conventionNom = (id) => {
    const c = conventions.find((x) => x.id === id)
    return c ? c.nom : `Convention #${id}`
  }

  const fiche = useMemo(() => {
    if (!ficheId) return null
    return pecs.find((p) => String(p.id) === String(ficheId)) || null
  }, [ficheId, pecs])

  if (loading) return <p>Chargement…</p>
  if (error) return <p role="alert">Impossible de charger les prises en charge.</p>

  return (
    <div className="sante-prises-en-charge">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <ShieldCheck size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Prises en charge</h1>
      </div>

      {ficheId && (
        <div
          data-testid="pec-fiche"
          style={{
            border: '1px solid var(--border, #e5e7eb)', borderRadius: 8,
            padding: 12, marginBottom: 20,
          }}
        >
          {fiche ? (
            <>
              <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>
                Fiche — {patientNom(fiche.patient)}
              </h2>
              <p>Convention : {conventionNom(fiche.convention)}</p>
              <p>
                Statut :{' '}
                <Badge tone={STATUT_TONE[fiche.statut] || 'neutral'}>
                  {fiche.statut_display || fiche.statut}
                </Badge>
              </p>
              <p>Demandée le : {formatDate(fiche.date_demande)}</p>
              {fiche.date_expiration && (
                <p>Expire le : {formatDate(fiche.date_expiration)}</p>
              )}
              {fiche.montant_accorde != null && (
                <p>Montant accordé : {fiche.montant_accorde}</p>
              )}
              {fiche.motif_refus && <p>Motif de refus : {fiche.motif_refus}</p>}
            </>
          ) : (
            <p>Prise en charge introuvable (id {ficheId}).</p>
          )}
        </div>
      )}

      <table className="data-table" data-testid="pec-table">
        <thead>
          <tr>
            <th>Patient</th><th>Convention</th><th>Statut</th>
            <th>Demandée le</th><th>Expire le</th>
          </tr>
        </thead>
        <tbody>
          {pecs.map((p) => (
            <tr key={p.id} data-testid={`pec-row-${p.id}`}>
              <td>{patientNom(p.patient)}</td>
              <td>{conventionNom(p.convention)}</td>
              <td>
                <Badge tone={STATUT_TONE[p.statut] || 'neutral'}>
                  {p.statut_display || p.statut}
                </Badge>
              </td>
              <td>{formatDate(p.date_demande)}</td>
              <td>{p.date_expiration ? formatDate(p.date_expiration) : '—'}</td>
            </tr>
          ))}
          {pecs.length === 0 && (
            <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>
              Aucune prise en charge
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
