import { useEffect, useState } from 'react'
import { ShieldCheck, AlertTriangle } from 'lucide-react'
import assurancesApi from './assurancesApi'
import { Card, CardContent, CardHeader, CardTitle, Stat, Badge, Spinner, EmptyState } from '../../ui'
import { PageHeader } from '../../ui/PageHeader'
import { formatMAD, formatNumber } from '../../lib/format'

/* ============================================================================
   WIR145 (NTASS21) — Tableau de bord Assurances : les 10 indicateurs de
   `tableau_bord_assurances` (prime totale, polices actives par type, sinistres
   ouverts/clos, réclamé vs indemnisé 12 mois, expirations 30 j, sinistralité).
   Lecture seule ; primes en formatMAD (jamais de marge/prix d'achat).
   ========================================================================== */

const mad = (v) => formatMAD(v, { decimals: 0 })

export default function TableauBordAssurances() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    assurancesApi.getTableauBord()
      .then((r) => { setData(r.data); setError(false) })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="ui-root page">
      <PageHeader title="Tableau de bord Assurances" icon={ShieldCheck} />
      {loading ? (
        <Spinner />
      ) : error || !data ? (
        <EmptyState icon={AlertTriangle} title="Données indisponibles"
                    description="Impossible de charger le tableau de bord assurances." />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat label="Prime annuelle totale" value={mad(data.prime_annuelle_totale)} tone="impact" />
            <Stat label="Polices actives" value={formatNumber(data.nb_polices_actives)} />
            <Stat label="Sinistres ouverts" value={formatNumber(data.sinistres_ouverts)} />
            <Stat label="Sinistres clos" value={formatNumber(data.sinistres_clos)} />
            <Stat label="Réclamé (12 mois)" value={mad(data.montant_reclame_12m)} />
            <Stat label="Indemnisé (12 mois)" value={mad(data.montant_indemnise_12m)} />
            <Stat label="Taux de sinistralité" value={`${Math.round((data.taux_sinistralite || 0) * 100)} %`} />
            <Stat label="Expirations ≤ 30 j" value={formatNumber(data.polices_expirant_30j)} />
          </div>

          <Card>
            <CardHeader><CardTitle>Attestations expirant ≤ 30 j</CardTitle></CardHeader>
            <CardContent>
              <Badge tone={data.attestations_expirant_30j > 0 ? 'warning' : 'success'}>
                {formatNumber(data.attestations_expirant_30j)} attestation(s)
              </Badge>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Polices actives par type</CardTitle></CardHeader>
            <CardContent>
              {Object.keys(data.polices_actives_par_type || {}).length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune police active.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(data.polices_actives_par_type).map(([type, n]) => (
                    <Badge key={type} tone="info">{type} : {formatNumber(n)}</Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
