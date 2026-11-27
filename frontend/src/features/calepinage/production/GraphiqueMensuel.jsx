import { useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis,
} from 'recharts'
import { formatNumber } from '../../../lib/format'
import { ChartEmpty, ChartFrame, ChartTooltip } from '../../../ui/charts'
import {
  CHART_GRID_STYLE, CHART_TOKENS, animationDuration,
} from '../../../ui/charts/chart-theme.js'
import { echelle, lectureMensuelle } from './GraphiqueMensuel.helpers'

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

/* « MOIS PAR MOIS » de l'étape Résultats (maquette v2 Resultats.dc.html) : douze colonnes — barres dorées de
   production, points et courbe bleus de consommation, initiales J à D dessous, repères 500 / 1 000 / 1 500 à gauche,
   le mois choisi (le plus fort par défaut, ou celui qu'on touche) entouré, et sa pastille « Juillet · 1 332 kWh
   produits · 1 400 kWh consommés ». Mêmes sources que ci-dessus (production : `production.mensuel` P50, sinon
   `autoconsommation.par_mois` ; consommation : `par_mois[].consommation_kwh`), aucune valeur calculée : un mois sans
   valeur servie n'a PAS de barre (jamais 0), pas de consommation servie = ni point, ni courbe, ni légende. Les
   hauteurs ne sont qu'un rapport à l'échelle des repères (arrondie au-dessus du plus grand mois servi). La bascule
   « Année / Journée type » n'existe pas : aucune série horaire n'est servie (un bloc sans donnée est absent). Les
   valeurs exactes sont en infobulle et dans un tableau lisible par les lecteurs d'écran. */
const INITIALES = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
const MOIS_LONG = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre',
  'Novembre', 'Décembre']
export function MoisParMois({ data, nomProduction = null }) {
  const { prod, conso } = lectureMensuelle(data)
  const [touche, setTouche] = useState(null)
  const avecProd = prod.some((v) => v !== null)
  const avecConso = conso.some((v) => v !== null)
  if (!avecProd && !avecConso) return null
  const servis = [...prod, ...conso].filter((v) => v !== null)
  const { pas, haut } = echelle(Math.max(...servis))
  const h = (v) => (v === null || !(haut > 0) ? null : Math.max(0, Math.min(100, (v / haut) * 100)))
  const reference = avecProd ? prod : conso
  const fort = reference.indexOf(Math.max(...reference.filter((v) => v !== null)))
  const choisi = touche ?? fort
  const points = conso.map((v, i) => (v === null ? null : [((i + 0.5) / 12) * 100, 100 - h(v)])).filter(Boolean)
  return (
    <section className="cal-res-carte cal-res-carte-mois" data-testid="cal-resultats-mois">
      <div className="cal-res-entete">
        <h2 className="cal-res-titre">{nomProduction ? `Mois par mois · ${nomProduction}` : 'Mois par mois'}</h2>
        <div className="cal-res-legende" data-testid="cal-res-mois-choisi">
          <strong>{MOIS_LONG[choisi]}</strong>
          {avecProd && prod[choisi] !== null && (
            <span><i className="cal-res-pastille" /><b>{kwhOuNonCalcule(prod[choisi])}</b>{' '}produits</span>
          )}
          {avecConso && conso[choisi] !== null && (
            <span><i className="cal-res-pastille cal-res-pastille-conso" /><b>{kwhOuNonCalcule(conso[choisi])}</b>{' '}consommés</span>
          )}
        </div>
      </div>
      {/* ACAL1631 — la consommation n'est pas servie : une ligne le dit (le motif servi), jamais un graphe muet. */}
      {avecProd && !avecConso && (
        <p className="cal-res-sourdine" data-testid="cal-res-mois-sans-conso">
          {`Consommation non tracée : ${typeof data?.autoconsommation?.motif_absence === 'string' && data.autoconsommation.motif_absence
            ? data.autoconsommation.motif_absence : 'aucune consommation connue pour ce calepinage.'}`}
        </p>
      )}
      <div className="cal-res-graphe">
        <div className="cal-res-axe" aria-hidden="true">
          {/* T4-X7-005 — le repère 0 est dit : une courbe nulle se lit sur la ligne du bas, jamais « sous 400 kWh ». */}
          {[0, 1, 2, 3].map((k) => <span key={k} style={{ bottom: `${(k / 3) * 100}%` }}>{formatNumber(pas * k, { decimals: 0 })}</span>)}
        </div>
        <div role="img" className="cal-res-mois"
          aria-label={`Histogramme mensuel de ${[avecProd && 'la production', avecConso && 'la consommation'].filter(Boolean).join(' et de ')}`}>
          {[0, 1, 2, 3].map((k) => <span key={k} className="cal-res-grille" aria-hidden="true" style={{ bottom: `${(k / 3) * 100}%` }} />)}
          {INITIALES.map((_, i) => (
            <button key={MOIS_COURT[i]} type="button" className="cal-res-mois-paire" aria-pressed={i === choisi}
              aria-label={`${MOIS_LONG[i]}`}
              onClick={() => setTouche(i)}
              title={[prod[i] !== null && `${MOIS_COURT[i]} · production ${kwhOuNonCalcule(prod[i])}`,
                conso[i] !== null && `consommation ${kwhOuNonCalcule(conso[i])}`].filter(Boolean).join(' · ') || undefined}>
              {h(prod[i]) !== null && <div className="cal-res-barre" style={{ height: `${h(prod[i])}%` }} />}
              {h(conso[i]) !== null && <span className="cal-res-point" style={{ bottom: `${h(conso[i])}%` }} />}
            </button>
          ))}
          {points.length > 1 && (
            <svg className="cal-res-courbe" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <polyline points={points.map((p) => p.join(',')).join(' ')} className="cal-res-courbe-halo" />
              <polyline points={points.map((p) => p.join(',')).join(' ')} className="cal-res-courbe-trait" />
            </svg>
          )}
        </div>
      </div>
      <div className="cal-res-mois-noms" aria-hidden="true">
        {INITIALES.map((l, i) => <span key={MOIS_COURT[i]} data-choisi={i === choisi ? 'oui' : undefined}>{l}</span>)}
      </div>
      <table className="sr-only">
        <caption>Valeurs mensuelles</caption>
        <thead><tr><th>Mois</th>{avecProd && <th>{nomProduction ?? 'Production'}</th>}{avecConso && <th>Consommation</th>}</tr></thead>
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
