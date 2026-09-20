import { useParams } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis, Tooltip,
} from 'recharts'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatPercent } from '../../../lib/format'
import { Card, Spinner } from '../../../ui'
import { ChartFrame, ChartTooltip, ChartEmpty } from '../../../ui/charts'
import {
  CHART_TOKENS, CHART_GRID_STYLE, BAR_RADIUS, animationDuration, CHART_ANIM_EASING,
} from '../../../ui/charts/chart-theme.js'

/* ============================================================================
   CAL143 — LE DIAGRAMME DE PERTES (Sankey/cascade) DU MODULE.
   ----------------------------------------------------------------------------
   `grep -rni "sankey|diagramme de pertes" backend frontend` valait 0 : aucune
   visualisation de pertes n'existait, alors que ce diagramme figure dans
   CHAQUE rapport PVsyst
   (https://www.pvsyst.com/help/project-design/results/loss-diagram.html).

   ZÉRO CALCUL DE PERTE CÔTÉ ÉCRAN. Les postes viennent tels quels de
   `production.pertes` (contrat partagé `calepinage_resultat.json`, CAL139/
   CAL244) : `poste`, `libelle`, `pct`, `source`. La SEULE chose calculée ici
   est la position CUMULÉE des barres en cascade (`haut`/`bas` d'un même
   poste) — un pur positionnement visuel, jamais une perte recalculée : la
   somme des `pct` affichés reste EXACTEMENT celle des postes servis.

   UN POSTE NON SOURCÉ (`source: null`) est rendu HACHURÉ et NOMMÉ, jamais
   dissimulé : le remplissage bascule sur le motif `url(#cal143-hachure)`
   plutôt que sur un ton plein, et la table équivalente (`ChartFrame`) écrit
   « — » à la colonne Source plutôt que d'inventer une provenance.

   La cascade est un BarChart empilé recharts (déjà présent au dépôt,
   `frontend/package.json`) : une série `base` invisible (offset) + une série
   `perte` visible, tokens de couleur du kit graphique — donc lisible en clair
   ET en sombre sans une seule couleur en dur.
   ========================================================================== */

const CASCADE_DEPART = 'Irradiance incidente'
const CASCADE_ARRIVEE = 'Énergie livrée'

/** Construit la cascade : chaque poste consomme le `pct` servi, en cumul, sans
    recalculer aucune perte — juste la position visuelle des barres. */
function construireCascade(pertes) {
  let courant = 100
  const etapes = [{ nom: CASCADE_DEPART, base: 0, valeur: 100, total: true }]
  for (const poste of pertes) {
    const pct = Number(poste.pct) || 0
    const bas = courant - pct
    etapes.push({
      nom: poste.libelle || poste.poste,
      base: Math.max(bas, 0),
      valeur: pct,
      total: false,
      source: poste.source ?? null,
      poste: poste.poste,
    })
    courant = bas
  }
  etapes.push({ nom: CASCADE_ARRIVEE, base: 0, valeur: Math.max(courant, 0), total: true })
  return etapes
}

const SOURCE_LABELS = {
  fiche: 'Fiche technique',
  saisie: 'Saisie',
  pvgis: 'PVGIS',
  mesure: 'Mesure',
  hypothese: 'Hypothèse',
}

const libelleSource = (source) => (source ? (SOURCE_LABELS[source] || source) : '—')

export default function DiagrammePertes({ calepinageId }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.resultat(id), id,
    { select: (r) => r.data, errorMessage: 'Diagramme de pertes indisponible.' },
  )

  if (loading) return <Spinner />
  if (error) {
    return <p className="text-sm text-destructive" data-testid="cal143-erreur">{error}</p>
  }

  const pertes = data?.production?.pertes ?? data?.pertes ?? []

  return (
    <Card className="flex flex-col gap-3 p-4" data-testid="cal143-panneau">
      <h2 className="text-base font-semibold">Diagramme de pertes</h2>
      {pertes.length === 0 ? (
        <ChartEmpty
          title="Pertes non calculées"
          description={data?.avertissements?.[0]
            || 'Aucune simulation lancée : la chaîne de pertes n\'a pas été produite.'}
        />
      ) : (
        <DiagrammePertesCascade pertes={pertes} />
      )}
    </Card>
  )
}

function DiagrammePertesCascade({ pertes }) {
  const etapes = construireCascade(pertes)
  const dur = animationDuration()

  const colonnes = [
    { key: 'nom', header: 'Poste' },
    {
      key: 'valeur',
      header: 'Perte',
      align: 'right',
      format: (v, row) => (row.total ? `${formatPercent(v, { decimals: 1 })} (cumulé)` : formatPercent(v, { decimals: 1 })),
    },
    { key: 'source', header: 'Source', format: (v, row) => (row.total ? '—' : libelleSource(v)) },
  ]

  return (
    <div className="flex flex-col gap-2" data-testid="cal143-cascade">
      <svg width={0} height={0} aria-hidden="true">
        <defs>
          {/* Poste non sourcé : hachure plutôt qu'un ton plein — jamais dissimulé. */}
          <pattern
            id="cal143-hachure" patternUnits="userSpaceOnUse" width={6} height={6}
            patternTransform="rotate(45)"
          >
            <rect width={6} height={6} fill={CHART_TOKENS.muted} fillOpacity={0.15} />
            <line x1={0} y1={0} x2={0} y2={6} stroke={CHART_TOKENS.muted} strokeWidth={2} />
          </pattern>
        </defs>
      </svg>

      <ChartFrame
        label="Diagramme de pertes en cascade, de l'irradiance incidente à l'énergie livrée"
        columns={colonnes}
        rows={etapes}
        getRowKey={(row) => row.nom}
      >
        <BarChart
          width={640}
          height={280}
          data={etapes}
          margin={{ top: 8, right: 8, bottom: 24, left: 0 }}
        >
          <CartesianGrid {...CHART_GRID_STYLE} />
          <XAxis
            dataKey="nom"
            tick={{ fontSize: 10, fill: CHART_TOKENS.axis }}
            tickLine={false}
            interval={0}
            angle={-20}
            textAnchor="end"
            height={50}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
            tickLine={false}
            axisLine={false}
            unit="%"
          />
          <Tooltip
            content={(
              <ChartTooltip
                format={(v, name, entry) => (entry?.payload?.total
                  ? formatPercent(v, { decimals: 1 })
                  : `${formatPercent(v, { decimals: 1 })} · ${libelleSource(entry?.payload?.source)}`)}
              />
            )}
          />
          <Bar dataKey="base" stackId="cascade" fill="transparent" isAnimationActive={false} />
          <Bar
            dataKey="valeur"
            name="Poste"
            stackId="cascade"
            radius={BAR_RADIUS}
            isAnimationActive={dur > 0}
            animationDuration={dur}
            animationEasing={CHART_ANIM_EASING}
          >
            {etapes.map((etape) => (
              <Cell
                key={etape.nom}
                fill={etape.total
                  ? CHART_TOKENS.primary
                  : (etape.source ? CHART_TOKENS.warning : 'url(#cal143-hachure)')}
              />
            ))}
          </Bar>
        </BarChart>
      </ChartFrame>
    </div>
  )
}
