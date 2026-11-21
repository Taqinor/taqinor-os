import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, ReferenceLine, Tooltip, XAxis, YAxis,
} from 'recharts'
import calepinageApi from '../../../api/calepinageApi'
import { formatNumber, formatPercent } from '../../../lib/format'
import { ChartFrame, ChartTooltip } from '../../../ui/charts'
import { CHART_GRID_STYLE, CHART_TOKENS, animationDuration } from '../../../ui/charts/chart-theme.js'
import { useModeExpert } from '../atelier/modeExpert'

/* ACAL737 — L'ÉCRÊTAGE EN CLAIR : énergie par classe de puissance (ACAL736),
   ligne verticale à la borne de l'onduleur, phrase « x % … plafonne à y kW ».
   Lecture seule de `cascade.etapes[etape=ecretage].entree` ; aucune valeur
   recalculée. Simulation périmée ou jamais lancée ⇒ rien ; guidé ⇒ rien.
   « Au-dessus de la borne » est dit en MOTS dans la table (jamais une couleur seule). */

const kwhTexte = (v) => `${formatNumber(v, { decimals: 1 })} kWh`

function etapeEcretage(data) {
  return (data?.cascade?.etapes ?? []).find((e) => e?.etape === 'ecretage') ?? null
}

export function HistogrammeEcretageVue({ etape }) {
  const entree = etape?.entree && typeof etape.entree === 'object' ? etape.entree : null
  if (!entree) {
    return (
      <p className="text-sm" data-testid="acal737-omise">
        Écrêtage non calculé : {etape?.motif_omission || 'aucun motif servi.'}
      </p>
    )
  }
  const dist = entree.distribution
  if (!dist || !Array.isArray(dist.classes)) {
    return (
      <p className="text-sm" data-testid="acal737-sans-distribution">
        {entree.motif_distribution || 'Aucune distribution de puissance servie.'}
      </p>
    )
  }
  const borne = dist.borne_kw
  const lignes = dist.classes.map((c) => ({
    classe: `${formatNumber(c.de_kw)} – ${formatNumber(c.a_kw)} kW`,
    energie: c.energie_kwh,
    position: c.de_kw >= borne ? 'au-dessus de la borne' : '',
  }))
  const surBorne = lignes[dist.classes.findIndex((c) => c.de_kw >= borne)]?.classe
  const dur = animationDuration()
  return (
    <div className="flex flex-col gap-2" data-testid="acal737-histogramme">
      <p className="text-sm" data-testid="acal737-phrase">
        {formatPercent(dist.part_ecretee_pct, { decimals: 1 })} de l'énergie des panneaux est perdue :
        {' '}l'onduleur plafonne à {formatNumber(borne)} kW
      </p>
      <ChartFrame
        label="Énergie des panneaux par classe de puissance"
        columns={[
          { key: 'classe', header: 'Classe de puissance' },
          { key: 'energie', header: 'Énergie', align: 'right', format: kwhTexte },
          { key: 'position', header: 'Position' },
        ]}
        rows={lignes}
        getRowKey={(r) => r.classe}
      >
        <BarChart width={640} height={220} data={lignes} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
          <CartesianGrid {...CHART_GRID_STYLE} />
          <XAxis dataKey="classe" tick={{ fontSize: 12, fill: CHART_TOKENS.axis }} tickLine={false} />
          <YAxis tick={{ fontSize: 12, fill: CHART_TOKENS.axis }} tickLine={false} axisLine={false} unit=" kWh" />
          <Tooltip content={<ChartTooltip format={kwhTexte} />} />
          <Bar dataKey="energie" name="Énergie" fill={CHART_TOKENS.primary}
            isAnimationActive={dur > 0} animationDuration={dur} />
          {surBorne && <ReferenceLine x={surBorne} stroke={CHART_TOKENS.warning} strokeDasharray="4 3"
            label={{ value: 'Borne', fontSize: 12, fill: CHART_TOKENS.axis }} />}
        </BarChart>
      </ChartFrame>
      <p className="text-xs text-muted-foreground">
        La comparaison est approchée : le rendement de conversion n'est pas retiré.
      </p>
    </div>
  )
}

export default function HistogrammeEcretage({ calepinageId }) {
  const [expert] = useModeExpert()
  const [data, setData] = useState(null)
  useEffect(() => {
    if (!calepinageId || !expert) return undefined
    let actif = true
    Promise.resolve()
      .then(() => calepinageApi.calepinages.resultat(calepinageId))
      .then((res) => { if (actif) setData(res?.data ?? null) })
      .catch(() => {})
    return () => { actif = false }
  }, [calepinageId, expert])
  const etape = etapeEcretage(data)
  if (!expert || !etape || data?.simule !== true || data?.simulation_perimee === true) return null
  return (
    <section className="flex flex-col gap-2 border-t border-border/60 pt-3" data-testid="acal737-carte">
      <h3 className="text-sm font-semibold">Écrêtage de l'onduleur</h3>
      <HistogrammeEcretageVue etape={etape} />
    </section>
  )
}
