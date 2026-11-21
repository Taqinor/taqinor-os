import { useEffect, useMemo, useState } from 'react'
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import calepinageApi from '../../../api/calepinageApi'
import { lireCsvHoraire, texteDuFichier } from '../production/serieHoraire'
import { Spinner } from '../../../ui'
import { ChartFrame, ChartTooltip } from '../../../ui/charts'
import { CHART_GRID_STYLE, CHART_TOKENS } from '../../../ui/charts/chart-theme.js'

/* ACAL447 — l'état de charge d'UNE semaine réelle de la série simulée (jours 8 à 14),
   lu dans le CSV horaire (`batterie_soc_pct`). Aucun lissage, aucune moyenne : une
   heure sans valeur est un TROU, jamais 0. Pas de fragment autour des axes recharts. */

const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
const JOURS = [8, 9, 10, 11, 12, 13, 14]
const COLONNES = 'annee,mois,jour,heure,batterie_soc_pct'
const AGREGEE = 'courbe horaire indisponible : série agrégée au jour'
const SANS_COLONNE = 'la série servie ne porte pas la colonne batterie_soc_pct'

export default function SemaineBatterie({ calepinageId }) {
  const [mois, setMois] = useState(3)
  const [serie, setSerie] = useState(null)
  const [motif, setMotif] = useState('')
  const [enCours, setEnCours] = useState(true)

  useEffect(() => {
    let vivant = true
    Promise.resolve(calepinageApi.calepinages.exportCsv(calepinageId, 'horaire', COLONNES))
      .then(async (res) => {
        const lue = lireCsvHoraire(await texteDuFichier(res?.data))
        if (vivant) setSerie(lue)
      })
      .catch(() => { if (vivant) setMotif('série horaire indisponible') })
      .finally(() => { if (vivant) setEnCours(false) })
    return () => { vivant = false }
  }, [calepinageId])

  const points = useMemo(() => (serie?.points || []), [serie])
  const agregee = points.some((p) => p.heure === null)
  const annee = useMemo(() => {
    const annees = points.filter((p) => p.mois === mois).map((p) => p.annee)
    return annees.length ? Math.min(...annees) : null
  }, [points, mois])

  const donnees = useMemo(() => {
    if (annee === null) return []
    const parCle = new Map()
    for (const p of points) {
      if (p.annee === annee && p.mois === mois) parCle.set(`${p.jour}-${p.heure}`, p.batterie_soc_pct)
    }
    return JOURS.flatMap((jour) => Array.from({ length: 24 }, (_, heure) => ({
      rang: `${jour}/${mois} ${heure} h`,
      soc: parCle.has(`${jour}-${heure}`) ? parCle.get(`${jour}-${heure}`) : null,
    })))
  }, [points, annee, mois])

  if (enCours) return <Spinner />

  let raison = motif
  if (!raison && !points.length) raison = 'série horaire indisponible'
  else if (!raison && agregee) raison = serie?.motif_troncature || AGREGEE
  else if (!raison && !(serie?.colonnes || []).includes('batterie_soc_pct')) raison = SANS_COLONNE
  else if (!raison && !donnees.some((d) => d.soc !== null)) raison = `aucun état de charge servi pour ${MOIS[mois - 1]}`

  const titre = annee === null
    ? `Semaine du 8 au 14 ${MOIS[mois - 1]}`
    : `du 8 au 14 ${MOIS[mois - 1]} ${annee} (année météo de la série, pas une moyenne)`

  return (
    <div className="flex flex-col gap-2" data-testid="acal447-semaine">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">État de charge de la batterie</h3>
        <select
          className="rounded-md border border-border bg-background px-2 py-1 text-sm"
          aria-label="Mois de la semaine tracée"
          value={mois}
          onChange={(e) => setMois(Number(e.target.value))}
          data-testid="acal447-mois"
        >
          {MOIS.map((nom, i) => <option key={nom} value={i + 1}>{nom.charAt(0).toUpperCase() + nom.slice(1)}</option>)}
        </select>
      </div>
      {raison ? (
        <p className="text-xs text-muted-foreground" data-testid="acal447-motif">{raison}</p>
      ) : (
        <ChartFrame
          label={titre}
          columns={[
            { key: 'rang', header: 'Heure' },
            { key: 'soc', header: 'État de charge (%)', align: 'right', format: (v) => (v === null ? 'non calculé' : `${v} %`) },
          ]}
          rows={donnees}
          getRowKey={(row) => row.rang}
        >
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={donnees} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
              <CartesianGrid {...CHART_GRID_STYLE} />
              <XAxis dataKey="rang" tick={{ fontSize: 11, fill: CHART_TOKENS.axis }} tickLine={false} interval={23} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: CHART_TOKENS.axis }} tickLine={false} axisLine={false} unit=" %" />
              <Tooltip content={<ChartTooltip />} />
              <Area
                type="linear"
                dataKey="soc"
                name="État de charge (%)"
                stroke={CHART_TOKENS.primary}
                fill={CHART_TOKENS.primary}
                fillOpacity={0.15}
                connectNulls={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartFrame>
      )}
      {!raison && <p className="text-xs text-muted-foreground" data-testid="acal447-titre">{titre}</p>}
    </div>
  )
}
