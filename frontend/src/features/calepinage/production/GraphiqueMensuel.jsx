import {
  Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis,
} from 'recharts'
import { formatNumber } from '../../../lib/format'
import { ChartEmpty, ChartFrame, ChartTooltip } from '../../../ui/charts'
import {
  CHART_GRID_STYLE, CHART_TOKENS, animationDuration,
} from '../../../ui/charts/chart-theme.js'

/* ACAL453 — GRAPHIQUE MENSUEL Production / Consommation / Autoconsommée.
   Données SERVIES : `autoconsommation.par_mois` (ACAL445), sinon `production.mensuel` (R3-08). Aucun
   calcul ; un mois `null` n'a pas de barre (jamais 0). Bloc ou `par_mois`
   absent : `ChartEmpty` qui nomme le `motif_absence` servi. */

const MOIS_COURT = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
  'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']

const kwhOuNonCalcule = (v) => (v === null || v === undefined
  ? 'non calculée' : `${formatNumber(v, { decimals: 0 })} kWh`)

export default function GraphiqueMensuel({ autoconsommation, production = null }) {
  const parMois = autoconsommation?.par_mois
  const avecCharge = Array.isArray(parMois) && parMois.length > 0
  const mensuel = Array.isArray(production?.mensuel) ? production.mensuel : []
  if (!avecCharge && !mensuel.length) {
    return (
      <div data-testid="acal453-vide">
        <ChartEmpty
          title="Graphique mensuel indisponible"
          description={autoconsommation?.motif_absence
            || 'Production, consommation et autoconsommation non calculées.'}
        />
      </div>
    )
  }
  /* R3-08 — la production mensuelle SERVIE se trace même sans consommation :
     le motif ne vaut que pour la consommation et l'autoconsommation. */
  const donnees = avecCharge ? parMois.map((m) => ({
    mois: MOIS_COURT[(m.mois || 1) - 1] || m.mois,
    production: m.production_kwh ?? null,
    consommation: m.consommation_kwh ?? null,
    autoconsommee: m.autoconsomme_kwh ?? null,
  })) : mensuel.map((m) => ({
    mois: MOIS_COURT[(m.mois || 1) - 1] || m.mois,
    production: m.p50_kwh ?? null,
  }))
  const dur = animationDuration()
  const nomProduction = avecCharge ? 'Production (au compteur)' : 'Production (P50)'
  return (
    <div data-testid="acal453-graphique">
      {!avecCharge && (
        <p className="mb-1 text-xs text-muted-foreground" data-testid="acal453-motif">
          {`Consommation et énergie autoconsommée non tracées : ${autoconsommation?.motif_absence
            || 'aucune consommation connue pour ce calepinage.'}`}
        </p>
      )}
      <ChartFrame
        label={avecCharge ? 'Production, consommation et énergie autoconsommée par mois'
          : 'Production par mois'}
        columns={[
          { key: 'mois', header: 'Mois' },
          { key: 'production', header: nomProduction, align: 'right', format: kwhOuNonCalcule },
          ...(avecCharge ? [
            { key: 'consommation', header: 'Consommation', align: 'right', format: kwhOuNonCalcule },
            { key: 'autoconsommee', header: 'Autoconsommée', align: 'right', format: kwhOuNonCalcule },
          ] : []),
        ]}
        rows={donnees}
        getRowKey={(row) => row.mois}
      >
        <BarChart
          width={640}
          height={240}
          data={donnees}
          margin={{ top: 8, right: 8, bottom: 8, left: 0 }}
        >
          <CartesianGrid {...CHART_GRID_STYLE} />
          <XAxis dataKey="mois" tick={{ fontSize: 11, fill: CHART_TOKENS.axis }} tickLine={false} />
          <YAxis
            tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
            tickLine={false}
            axisLine={false}
            unit=" kWh"
          />
          <Tooltip content={<ChartTooltip format={(v) => kwhOuNonCalcule(v)} />} />
          <Legend />
          <Bar dataKey="production" name={nomProduction}
            fill={CHART_TOKENS.primary} isAnimationActive={dur > 0} animationDuration={dur} />
          {avecCharge && (
            <Bar dataKey="consommation" name="Consommation"
              fill={CHART_TOKENS.warning} isAnimationActive={dur > 0} animationDuration={dur} />
          )}
          {avecCharge && (
            <Bar dataKey="autoconsommee" name="Autoconsommée"
              fill={CHART_TOKENS.success} isAnimationActive={dur > 0} animationDuration={dur} />
          )}
        </BarChart>
      </ChartFrame>
    </div>
  )
}

/* « MOIS PAR MOIS » de l'étape Résultats (maquette Resultats.dc.html) : douze paires de
   barres Production / Consommation, initiales J à D dessous. Mêmes sources que ci-dessus
   (production : `production.mensuel` P50, sinon `autoconsommation.par_mois` ; consommation :
   `par_mois[].consommation_kwh`), aucune valeur calculée : un mois sans valeur servie n'a PAS
   de barre (jamais 0), pas de consommation servie = pas de barre consommation ni de légende.
   Les hauteurs ne sont qu'un rapport au plus grand mois affiché. Les valeurs exactes sont en
   infobulle et dans un tableau lisible par les lecteurs d'écran. */
const INITIALES = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
const nombreServi = (v) => typeof v === 'number' && Number.isFinite(v)

export function MoisParMois({ data }) {
  const mensuel = Array.isArray(data?.production?.mensuel) ? data.production.mensuel : []
  const parMois = Array.isArray(data?.autoconsommation?.par_mois) ? data.autoconsommation.par_mois : []
  const prod = Array(12).fill(null)
  const conso = Array(12).fill(null)
  if (mensuel.length) {
    mensuel.forEach((m) => { if (m?.mois >= 1 && m.mois <= 12 && nombreServi(m.p50_kwh)) prod[m.mois - 1] = m.p50_kwh })
  } else {
    parMois.forEach((m) => { if (m?.mois >= 1 && m.mois <= 12 && nombreServi(m.production_kwh)) prod[m.mois - 1] = m.production_kwh })
  }
  parMois.forEach((m) => { if (m?.mois >= 1 && m.mois <= 12 && nombreServi(m.consommation_kwh)) conso[m.mois - 1] = m.consommation_kwh })
  const avecProd = prod.some((v) => v !== null)
  const avecConso = conso.some((v) => v !== null)
  if (!avecProd && !avecConso) return null
  const max = Math.max(...prod.filter((v) => v !== null), ...conso.filter((v) => v !== null))
  const h = (v) => (v === null || !(max > 0) ? null : `${Math.max(0, (v / max) * 100)}%`)
  return (
    <section className="cal-res-carte" data-testid="cal-resultats-mois">
      <div className="cal-res-entete">
        <h2 className="cal-res-titre">Mois par mois</h2>
        <div className="cal-res-legende">
          {avecProd && <span><span className="cal-res-pastille" />Production</span>}
          {avecConso && <span><span className="cal-res-pastille cal-res-pastille-conso" />Consommation</span>}
        </div>
      </div>
      <div role="img" className="cal-res-mois"
        aria-label={`Histogramme mensuel de ${[avecProd && 'la production', avecConso && 'la consommation'].filter(Boolean).join(' et de ')}`}>
        {INITIALES.map((_, i) => (
          <div key={MOIS_COURT[i]} className="cal-res-mois-paire"
            title={[prod[i] !== null && `${MOIS_COURT[i]} · production ${kwhOuNonCalcule(prod[i])}`,
              conso[i] !== null && `consommation ${kwhOuNonCalcule(conso[i])}`].filter(Boolean).join(' · ') || undefined}>
            {h(prod[i]) && <div className="cal-res-barre" style={{ height: h(prod[i]) }} />}
            {h(conso[i]) && <div className="cal-res-barre cal-res-barre-conso" style={{ height: h(conso[i]) }} />}
          </div>
        ))}
      </div>
      <div className="cal-res-mois-noms" aria-hidden="true">
        {INITIALES.map((l, i) => <span key={MOIS_COURT[i]}>{l}</span>)}
      </div>
      <table className="sr-only">
        <caption>Valeurs mensuelles</caption>
        <thead><tr><th>Mois</th>{avecProd && <th>Production</th>}{avecConso && <th>Consommation</th>}</tr></thead>
        <tbody>
          {MOIS_COURT.map((nom, i) => (prod[i] !== null || conso[i] !== null) && (
            <tr key={nom}><td>{nom}</td>
              {avecProd && <td>{prod[i] === null ? '' : kwhOuNonCalcule(prod[i])}</td>}
              {avecConso && <td>{conso[i] === null ? '' : kwhOuNonCalcule(conso[i])}</td>}</tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
