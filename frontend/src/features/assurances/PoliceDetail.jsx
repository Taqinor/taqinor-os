import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import assurancesApi from './assurancesApi'
import { Badge, Button } from '../../ui'
import { RecordShell } from '../../ui/module'
import { formatMAD, formatDate, formatDateTime } from '../../lib/format'
import { POLICE_STATUS, toneEcheance } from './status'

/* ============================================================================
   NTASS26 — Fiche police détail (onglets).
   ----------------------------------------------------------------------------
   RecordShell UX1 : onglets Garanties (NTASS4), Actifs couverts (NTASS7),
   Échéancier de primes (NTASS5, bouton « Proposer écriture » NTASS6),
   Historique (chatter NTASS3), Attestations (NTASS17). Lecture des montants
   client-safe (formatMAD — jamais de prix d'achat/marge).
   ========================================================================== */

function useLoader(fn, deps) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const reload = () => {
    setLoading(true)
    fn()
      .then((res) => setData(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setData([]))
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { reload() }, deps)
  return { data, loading, reload }
}

function Empty({ label }) {
  return <p className="py-6 text-center text-sm text-muted-foreground">{label}</p>
}

export default function PoliceDetail() {
  const { id } = useParams()
  const [police, setPolice] = useState(null)
  const [error, setError] = useState(null)

  const loadPolice = () => {
    assurancesApi.getPolice(id)
      .then((res) => setPolice(res.data))
      .catch(() => setError('Police introuvable.'))
  }
  useEffect(() => { loadPolice() /* eslint-disable-line */ }, [id])

  const garanties = useLoader(() => assurancesApi.getGaranties(id), [id])
  const actifs = useLoader(() => assurancesApi.getActifsCouverts(id), [id])
  const echeances = useLoader(() => assurancesApi.getEcheancesPrime(id), [id])
  const historique = useLoader(() => assurancesApi.getPoliceHistorique(id), [id])
  const attestations = useLoader(() => assurancesApi.getAttestations(id), [id])

  const proposerEcriture = (echeanceId) => {
    assurancesApi.proposerEcriturePrime(echeanceId)
      .then(() => echeances.reload())
      .catch(() => { /* affiché via rechargement */ })
  }

  const tabs = useMemo(() => [
    {
      value: 'garanties',
      label: 'Garanties',
      count: garanties.data.length,
      content: garanties.data.length === 0
        ? <Empty label="Aucune garantie enregistrée." />
        : (
          <ul className="divide-y">
            {garanties.data.map((g) => (
              <li key={g.id} className="flex items-center justify-between py-2 text-sm">
                <span className="font-medium">{g.libelle_garantie}</span>
                <span className="text-muted-foreground">
                  Plafond {formatMAD(g.plafond_indemnisation)} · Franchise{' '}
                  {formatMAD(g.franchise_montant)}
                </span>
              </li>
            ))}
          </ul>
        ),
    },
    {
      value: 'actifs',
      label: 'Actifs couverts',
      count: actifs.data.length,
      content: actifs.data.length === 0
        ? <Empty label="Aucun actif couvert." />
        : (
          <ul className="divide-y">
            {actifs.data.map((a) => (
              <li key={a.id} className="flex items-center justify-between py-2 text-sm">
                <span className="font-medium">{a.actif_libelle || '—'}</span>
                <Badge tone="slate">{a.type_actif}</Badge>
              </li>
            ))}
          </ul>
        ),
    },
    {
      value: 'echeancier',
      label: 'Échéancier de primes',
      count: echeances.data.length,
      content: echeances.data.length === 0
        ? <Empty label="Aucune échéance de prime générée." />
        : (
          <ul className="divide-y">
            {echeances.data.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span>{formatDate(e.date_echeance_paiement)}</span>
                <span className="font-medium tabular-nums">{formatMAD(e.montant)}</span>
                <Badge tone={e.statut === 'payee' ? 'green' : 'amber'}>{e.statut}</Badge>
                {e.statut === 'a_payer' && (
                  <Button size="sm" variant="outline" onClick={() => proposerEcriture(e.id)}>
                    Proposer écriture
                  </Button>
                )}
              </li>
            ))}
          </ul>
        ),
    },
    {
      value: 'attestations',
      label: 'Attestations',
      count: attestations.data.length,
      content: attestations.data.length === 0
        ? <Empty label="Aucune attestation." />
        : (
          <ul className="divide-y">
            {attestations.data.map((att) => (
              <li key={att.id} className="flex items-center justify-between py-2 text-sm">
                <span className="font-medium">{att.emise_pour || 'Attestation'}</span>
                <Badge tone={toneEcheance(att.date_validite)}>
                  Valide jusqu'au {formatDate(att.date_validite)}
                </Badge>
              </li>
            ))}
          </ul>
        ),
    },
  ], [garanties.data, actifs.data, echeances.data, attestations.data])

  const activity = (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">Historique</h3>
      {historique.data.length === 0
        ? <Empty label="Aucune activité." />
        : (
          <ul className="flex flex-col gap-2">
            {historique.data.map((h) => (
              <li key={h.id} className="rounded-md border p-2 text-xs">
                <div className="flex items-center justify-between text-muted-foreground">
                  <span>{h.kind}</span>
                  <span>{formatDateTime(h.created_at)}</span>
                </div>
                {h.field
                  ? <p>{h.field_label || h.field} : {h.old_value} → {h.new_value}</p>
                  : <p>{h.body}</p>}
              </li>
            ))}
          </ul>
        )}
    </div>
  )

  if (error) {
    return <p className="p-6 text-sm text-destructive">{error}</p>
  }

  const statut = police?.statut
  const statutInfo = statut ? POLICE_STATUS[statut] : null

  return (
    <RecordShell
      title={police ? `${police.numero_police}` : 'Police'}
      subtitle={police
        ? `${police.type_police_display || police.type_police} · ${police.assureur_nom || ''}`
        : ''}
      backTo="/assurances"
      backLabel="Retour aux polices"
      status={statutInfo ? statutInfo.label : null}
      actions={police && (
        <Button variant="outline" onClick={() => assurancesApi.renouvelerPolice(id).then(loadPolice)}>
          Renouveler
        </Button>
      )}
      tabs={tabs}
      activity={activity}
    />
  )
}
