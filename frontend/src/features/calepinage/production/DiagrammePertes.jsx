import { useParams } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis, Tooltip,
} from 'recharts'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber, formatPercent } from '../../../lib/format'
import { Card, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'
import { BandeauPerime, BoutonLancerSimulation } from './PanneauProduction'
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

   CALX48 — LA CASCADE SÉQUENTIELLE (`resultat['cascade']`, CALX141) PRIME SUR
   LA LISTE PLATE QUAND ELLE EXISTE. `resultat['cascade'].etapes` porte le
   rang, l'énergie avant/après CHAQUE étape et, pour une étape OMISE
   (`motif_omission` non vide, D-CALX 16 — spectral/diodes TOUJOURS omis,
   jamais forfaitisés), `perte_pct: null` — rendu VIDE, jamais un zéro qui
   laisserait croire à une étape sans effet. Cascade absente (calepinage posé
   mais la chaîne séquentielle n'a jamais tourné) : repli sur la liste plate
   ACTUELLE (D-CALX 11, forme inchangée) avec une mention qui dit laquelle des
   deux est affichée — jamais un panneau muet sur sa propre provenance.
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
  societe: 'Réglage société',
}

const libelleSource = (source) => (source ? (SOURCE_LABELS[source] || source) : '—')

/**
 * CALX48 — la cascade construite depuis `resultat['cascade'].etapes` (CALX141),
 * PAS depuis la liste plate : chaque étape porte déjà son `perte_pct` (négatif
 * pour un GAIN, ex. bifacial), donc aucune conversion — une étape OMISE
 * (`perte_pct: null`) traverse à hauteur nulle, hachurée, JAMAIS un zéro qui
 * prétendrait qu'elle n'a rien coûté.
 */
function construireCascadeDetaillee(etapes) {
  let courant = 100
  const lignes = [{ nom: CASCADE_DEPART, base: 0, valeur: 100, total: true }]
  for (const etape of etapes) {
    const omise = etape.perte_pct === null || etape.perte_pct === undefined
    const delta = omise ? 0 : (Number(etape.perte_pct) || 0)
    const bas = courant - delta
    lignes.push({
      nom: etape.libelle || etape.etape,
      base: Math.max(Math.min(bas, courant), 0),
      valeur: Math.abs(delta),
      total: false,
      source: etape.source ?? null,
      poste: etape.etape,
      rang: etape.rang,
      omise,
      motif: etape.motif_omission || '',
      pertePct: etape.perte_pct,
      kwhAvant: etape.kwh_avant ?? null,
      kwhApres: etape.kwh_apres ?? null,
      gain: Boolean(etape.gain),
    })
    courant = bas
  }
  lignes.push({ nom: CASCADE_ARRIVEE, base: 0, valeur: Math.max(courant, 0), total: true })
  return lignes
}

/** `perte_pct` d'une étape omise s'affiche VIDE (Done CALX48), jamais « — »
    ni `0 %` : une cellule vide qui appelle l'œil vers la colonne Motif. */
const pctCascadeDetaillee = (v) => (v === null || v === undefined
  ? '' : formatPercent(v, { decimals: 1 }))

const kwhCascadeDetaillee = (v) => (v === null || v === undefined
  ? 'non calculée' : `${formatNumber(v, { decimals: 0 })} kWh`)

/** La couleur d'une barre de la cascade détaillée : total (cumulé), étape
    OMISE (hachure — jamais dissimulée), GAIN (bifacial…) ou perte ordinaire. */
function couleurCascadeDetaillee(ligne) {
  if (ligne.total) return CHART_TOKENS.primary
  if (ligne.omise) return 'url(#calx48-hachure)'
  if (ligne.gain) return CHART_TOKENS.success
  return CHART_TOKENS.warning
}

/** CALX48 — dit laquelle des deux sources est affichée, jamais un panneau
    muet sur sa propre provenance (D-CALX 11 : la liste plate n'est QUE
    saisie, jamais calculée par la chaîne séquentielle). */
function MentionSourceCascade({ cascadeServie }) {
  return (
    <p className="text-xs text-muted-foreground" data-testid="calx48-mention-source">
      {cascadeServie
        ? 'Chaîne de pertes séquentielle calculée, étape par étape (CALX141).'
        : "Postes saisis, non calculés : la chaîne de pertes séquentielle n'a "
          + 'pas encore été produite pour ce calepinage.'}
    </p>
  )
}

export default function DiagrammePertes({ calepinageId }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error, refetch } = useResource(
    () => calepinageApi.calepinages.resultat(id), id,
    { select: (r) => r.data, errorMessage: 'Diagramme de pertes indisponible.' },
  )

  if (loading) {
    return (
      <>
        <RetourAtelier calepinageId={id} />
        <Spinner />
      </>
    )
  }
  if (error) {
    return (
      <>
        <RetourAtelier calepinageId={id} />
        <p className="text-sm text-destructive" data-testid="cal143-erreur">{error}</p>
      </>
    )
  }

  const pertes = data?.production?.pertes ?? data?.pertes ?? []
  const etapesCascade = Array.isArray(data?.cascade?.etapes) ? data.cascade.etapes : []
  const perime = data?.simulation_perimee === true
  const pertesVides = !(pertes.length) && !(etapesCascade.length)

  return (
    <>
      <RetourAtelier calepinageId={id} />
      <Card className="flex flex-col gap-3 p-4" data-testid="cal143-panneau">
      <h2 className="text-base font-semibold">Diagramme de pertes</h2>
      {perime && <BandeauPerime motif={data?.motif} />}
      {!data?.simule && (
        /* CALX48 — les manques restent affichés par le panneau Production
           (qui, lui, pointe VERS cet onglet Pertes) : les redire ICI créerait
           un lien qui pointe sur l'onglet où l'on est déjà. */
        <BoutonLancerSimulation
          calepinageId={id}
          avertissements={[]}
          desactive={pertesVides}
          onTermine={refetch}
        />
      )}
      {etapesCascade.length > 0 ? (
        <>
          <MentionSourceCascade cascadeServie />
          <DiagrammePertesCascadeDetaillee etapes={etapesCascade} />
        </>
      ) : pertes.length === 0 ? (
        <ChartEmpty
          title="Pertes non calculées"
          description={data?.avertissements?.[0]
            || 'Aucune simulation lancée : la chaîne de pertes n\'a pas été produite.'}
        />
      ) : (
        <>
          <MentionSourceCascade cascadeServie={false} />
          <DiagrammePertesCascade pertes={pertes} />
        </>
      )}
    </Card>
    </>
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

/**
 * CALX48 — la cascade SÉQUENTIELLE (`resultat['cascade'].etapes`, CALX141),
 * rang par rang, énergie avant/après. Une étape OMISE (`motif_omission` non
 * vide) traverse le graphique à hauteur nulle et hachurée — SON motif reste
 * lisible dans la table (colonne dédiée, jamais fondu dans le libellé) et sa
 * colonne « Perte » reste VIDE (Done CALX48), jamais un zéro trompeur.
 */
function DiagrammePertesCascadeDetaillee({ etapes }) {
  const lignes = construireCascadeDetaillee(etapes)
  const dur = animationDuration()

  const colonnes = [
    { key: 'rang', header: 'Rang', format: (v, row) => (row.total ? '—' : v) },
    { key: 'nom', header: 'Étape' },
    { key: 'kwhAvant', header: 'Énergie avant', align: 'right', format: (v, row) => (row.total ? '—' : kwhCascadeDetaillee(v)) },
    { key: 'kwhApres', header: 'Énergie après', align: 'right', format: (v, row) => (row.total ? '—' : kwhCascadeDetaillee(v)) },
    {
      key: 'pertePct',
      header: 'Perte',
      align: 'right',
      format: (v, row) => (row.total
        ? `${formatPercent(row.valeur, { decimals: 1 })} (cumulé)`
        : pctCascadeDetaillee(v)),
    },
    { key: 'source', header: 'Source', format: (v, row) => (row.total ? '—' : libelleSource(v)) },
    // Étape omise : le motif publié par le serveur, jamais reconstruit.
    { key: 'motif', header: 'Motif', format: (v, row) => (row.omise ? v : '') },
  ]

  return (
    <div className="flex flex-col gap-2" data-testid="calx48-cascade-detaillee">
      <svg width={0} height={0} aria-hidden="true">
        <defs>
          {/* Étape omise : même hachure que le poste non sourcé — jamais dissimulée. */}
          <pattern
            id="calx48-hachure" patternUnits="userSpaceOnUse" width={6} height={6}
            patternTransform="rotate(45)"
          >
            <rect width={6} height={6} fill={CHART_TOKENS.muted} fillOpacity={0.15} />
            <line x1={0} y1={0} x2={0} y2={6} stroke={CHART_TOKENS.muted} strokeWidth={2} />
          </pattern>
        </defs>
      </svg>

      <ChartFrame
        label="Chaîne de pertes séquentielle, rang par rang, de l'irradiance incidente à l'énergie livrée"
        columns={colonnes}
        rows={lignes}
        getRowKey={(row) => row.nom}
      >
        <BarChart
          width={640}
          height={280}
          data={lignes}
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
                format={(v, name, entry) => {
                  const row = entry?.payload
                  if (row?.total) return formatPercent(v, { decimals: 1 })
                  if (row?.omise) return row.motif || 'Étape omise, sans motif publié.'
                  return `${formatPercent(v, { decimals: 1 })} · ${libelleSource(row?.source)}`
                }}
              />
            )}
          />
          <Bar dataKey="base" stackId="cascade" fill="transparent" isAnimationActive={false} />
          <Bar
            dataKey="valeur"
            name="Étape"
            stackId="cascade"
            radius={BAR_RADIUS}
            isAnimationActive={dur > 0}
            animationDuration={dur}
            animationEasing={CHART_ANIM_EASING}
          >
            {lignes.map((ligne) => (
              <Cell key={ligne.nom} fill={couleurCascadeDetaillee(ligne)} />
            ))}
          </Bar>
        </BarChart>
      </ChartFrame>
    </div>
  )
}
