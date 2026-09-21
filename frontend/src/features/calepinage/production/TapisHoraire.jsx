import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  CartesianGrid, Legend, Line, LineChart, Tooltip, XAxis, YAxis,
} from 'recharts'
import calepinageApi from '../../../api/calepinageApi'
import { formatNumber } from '../../../lib/format'
import { Button, Card, Spinner } from '../../../ui'
import { ChartEmpty, ChartFrame, ChartTooltip } from '../../../ui/charts'
import {
  CHART_GRID_STYLE, CHART_TOKENS, animationDuration,
} from '../../../ui/charts/chart-theme.js'

/* ============================================================================
   CALX64 — LE TAPIS DE CHALEUR JOUR × HEURE, ET LA JOURNÉE TYPE PAR MOIS.
   ----------------------------------------------------------------------------
   CONSTAT. `PanneauProduction.jsx` n'affiche que des indicateurs et deux
   tables mensuelles ; la série horaire est persistée (CALX193) et exportable
   (CALX6), mais AUCUN composant ne la dessine. PV*SOL publie ce tapis
   (https://help.valentin-software.com/pvsol/en/pages/results/diagram-editor/)
   et PVsyst ses graphes au pas de simulation
   (https://www.pvsyst.com/help/project-design/results/index.html).

   D'OÙ VIENNENT LES CHIFFRES — AUCUN RECALCUL. Deux entrées, dans cet ordre :
     1. la série PASSÉE EN PROPRIÉTÉ (le bloc CALX142 `{points, colonnes,
        tronquee, …}`), quand l'écran l'a déjà en main ;
     2. à défaut, LA MÊME PORTE que le panneau « Séries » (CALX6) :
        `GET export-csv/?quoi=horaire`, dont le fichier porte les colonnes du
        serveur (`production_kw` = `p_ac_kw`, `irradiance_plan_w_m2` =
        `gi_w_m2`). La série n'est PAS recopiée par `GET resultat/` (D-CALX 14,
        volume) : cette porte est la seule qui la sert.
   Le composant ne modélise rien : il met en forme des valeurs publiées. Les
   moyennes de la journée type sont des moyennes de CES valeurs-là, jamais une
   production ré-estimée.

   SÉRIE ABSENTE ⇒ ÉTAT VIDE QUI LE DIT. Le motif affiché est celui que le
   serveur a écrit (il NOMME le champ manquant) ; le titre dit le geste à
   faire — « Lancer la simulation ». Jamais un tapis de zéros : un zéro se
   lirait « mesuré à zéro » (contrat CALX142).

   SÉRIE TRONQUÉE (CALX193). Au-delà du plafond de points, la chaîne AGRÈGE la
   série AU JOUR (`tronquee: true`, `heure: null`, `motif_troncature`). Le
   tapis n'invente alors aucune heure : il affiche UNE seule ligne — la
   journée entière — et publie le motif de troncature au-dessus.
   ========================================================================== */

const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]
const MOIS_COURT = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
  'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']

/** Les deux grandeurs que le tapis sait peindre, et RIEN d'autre. */
const GRANDEURS = [
  {
    cle: 'p_ac_kw',
    colonneCsv: 'production_kw',
    libelle: 'Production',
    unite: 'kW',
    decimales: 2,
  },
  {
    cle: 'gi_w_m2',
    colonneCsv: 'irradiance_plan_w_m2',
    libelle: 'Irradiance sur le plan',
    unite: 'W/m²',
    decimales: 0,
  },
]

const LIGNE_JOUR = 'jour'

const SANS_SERIE = (
  "La série horaire n'est pas encore enregistrée pour ce calepinage : le "
  + 'tapis reste vide plutôt que de peindre des zéros.'
)

/** Un nombre, ou `null` — jamais `0` par défaut. */
function nombre(valeur) {
  if (valeur === null || valeur === undefined || valeur === '') return null
  const lu = Number(valeur)
  return Number.isFinite(lu) ? lu : null
}

/** Un nombre écrit à la française par le serveur (`1,25`), ou `null`. */
function nombreFrancais(cellule) {
  const texte = String(cellule ?? '').trim()
  if (!texte) return null
  // `\s` en JS couvre DEJA l'espace insecable (U+00A0) et l'espace fin
  // insecable (U+202F) qu'un serveur peut emettre : aucun caractere
  // invisible n'entre dans ce fichier.
  const lu = Number(texte.replace(/\s/g, '').replace(',', '.'))
  return Number.isFinite(lu) ? lu : null
}

/** Le texte d'un fichier servi en blob (navigateur) ou déjà en chaîne. */
async function texteDuFichier(donnees) {
  if (typeof donnees === 'string') return donnees
  if (donnees && typeof donnees.text === 'function') return donnees.text()
  return ''
}

/**
 * Les points de la série, lus dans le CSV que le serveur produit (CAL144).
 *
 * L'en-tête de provenance précède le tableau : on repère la ligne de titres
 * (`annee;mois;…`) et on ne lit que ce qui suit. Une cellule vide reste
 * `null` — le serveur l'a laissée vide parce que l'heure n'a pas de mesure.
 */
function lireCsvHoraire(texte) {
  const brut = String(texte || '')
  // Le serveur prefixe le fichier du BOM qu'Excel attend (CAL144) : on le
  // retire par son POINT DE CODE, jamais par un caractere colle dans la
  // source.
  const sansBom = brut.charCodeAt(0) === 0xFEFF ? brut.slice(1) : brut
  const lignes = sansBom.split('\n').map((ligne) => ligne.replace('\r', ''))
  const depart = lignes.findIndex((ligne) => ligne.split(';')[0] === 'annee')
  if (depart < 0) return null
  const titres = lignes[depart].split(';').map((titre) => titre.trim())
  const points = []
  for (const ligne of lignes.slice(depart + 1)) {
    if (!ligne.trim()) continue
    const cellules = ligne.split(';')
    const point = {}
    titres.forEach((titre, rang) => { point[titre] = cellules[rang] })
    const annee = nombreFrancais(point.annee)
    if (annee === null) continue
    points.push({
      annee,
      mois: nombreFrancais(point.mois),
      jour: nombreFrancais(point.jour),
      heure: nombreFrancais(point.heure),
      p_ac_kw: nombreFrancais(point.production_kw),
      gi_w_m2: nombreFrancais(point.irradiance_plan_w_m2),
      // La courbe de charge ne figure pas dans ce fichier (sept colonnes
      // historiques, CAL144) : elle reste absente, jamais inventée.
      charge_kwh: null,
    })
  }
  return { points, colonnes: titres, tronquee: null, motif_troncature: '' }
}

/** Le refus du serveur, tel qu'il l'a écrit — ou `null`. */
async function motifDuRefus(erreur) {
  let corps = erreur?.response?.data
  if (corps && typeof corps.text === 'function') {
    try { corps = JSON.parse(await corps.text()) } catch { return null }
  }
  if (!corps || typeof corps !== 'object') return null
  for (const [champ, valeur] of Object.entries(corps)) {
    if (champ === 'exports_disponibles') continue
    const motif = Array.isArray(valeur) ? valeur[0] : valeur
    if (typeof motif === 'string' && motif.trim()) return motif
  }
  return null
}

/**
 * Le tapis : une COLONNE par jour du calendrier, une LIGNE par heure.
 *
 * Une série agrégée au jour (CALX193) n'a pas d'heure : elle rend alors UNE
 * seule ligne, nommée, au lieu de vingt-quatre lignes dont vingt-trois
 * seraient vides.
 */
function construireTapis(points, grandeur) {
  const parJour = new Map()
  let horaire = false
  for (const point of points) {
    const cle = `${point.annee}-${point.mois}-${point.jour}`
    if (!parJour.has(cle)) {
      parJour.set(cle, {
        cle,
        annee: nombre(point.annee),
        mois: nombre(point.mois),
        jour: nombre(point.jour),
        cellules: new Map(),
      })
    }
    const heure = nombre(point.heure)
    if (heure !== null) horaire = true
    parJour.get(cle).cellules.set(heure === null ? LIGNE_JOUR : heure,
      nombre(point[grandeur.cle]))
  }
  const jours = [...parJour.values()].sort((a, b) => (
    (a.annee - b.annee) || (a.mois - b.mois) || (a.jour - b.jour)))
  const lignes = horaire
    ? Array.from({ length: 24 }, (_, heure) => heure)
    : [LIGNE_JOUR]

  let mini = null
  let maxi = null
  for (const jourCourant of jours) {
    for (const valeur of jourCourant.cellules.values()) {
      if (valeur === null) continue
      mini = mini === null ? valeur : Math.min(mini, valeur)
      maxi = maxi === null ? valeur : Math.max(maxi, valeur)
    }
  }
  return { jours, lignes, mini, maxi, horaire }
}

/**
 * La journée TYPE de chaque mois : la moyenne, heure par heure, des valeurs
 * publiées de ce mois. Une heure sans aucune mesure reste `null`.
 */
function journeesTypes(points, cle) {
  const parMois = new Map()
  for (const point of points) {
    const mois = nombre(point.mois)
    const heure = nombre(point.heure)
    if (mois === null || heure === null) continue
    const valeur = nombre(point[cle])
    if (valeur === null) continue
    if (!parMois.has(mois)) {
      parMois.set(mois, Array.from({ length: 24 }, () => ({ somme: 0, n: 0 })))
    }
    const case24 = parMois.get(mois)[heure]
    if (!case24) continue
    case24.somme += valeur
    case24.n += 1
  }
  return [...parMois.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([mois, heures]) => {
      const moyennes = heures.map(
        (c) => (c.n ? c.somme / c.n : null))
      const connues = moyennes.filter((v) => v !== null)
      return {
        mois,
        heures: moyennes,
        pic: connues.length ? Math.max(...connues) : null,
      }
    })
}

export default function TapisHoraire({ calepinageId, serie: serieProposee }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const fournie = (serieProposee && Array.isArray(serieProposee.points)
    && serieProposee.points.length) ? serieProposee : null

  const [chargee, setChargee] = useState(null)
  const [refus, setRefus] = useState(null)
  const [enCours, setEnCours] = useState(!fournie)
  const [cleGrandeur, setCleGrandeur] = useState(GRANDEURS[0].cle)
  const [moisChoisi, setMoisChoisi] = useState(null)

  const charger = useCallback(() => {
    if (fournie || !id) return Promise.resolve()
    return Promise.resolve(calepinageApi.calepinages.exportCsv(id, 'horaire'))
      .then(async (res) => setChargee(lireCsvHoraire(await texteDuFichier(res?.data))))
      .catch(async (erreur) => setRefus(await motifDuRefus(erreur) || SANS_SERIE))
      .finally(() => setEnCours(false))
  }, [fournie, id])

  useEffect(() => { charger() }, [charger])

  const serie = fournie || chargee
  const points = useMemo(
    () => (Array.isArray(serie?.points) ? serie.points : []), [serie])
  const grandeur = GRANDEURS.find((g) => g.cle === cleGrandeur) || GRANDEURS[0]

  const disponibles = useMemo(() => GRANDEURS.filter(
    (g) => points.some((point) => nombre(point[g.cle]) !== null)), [points])
  const tapis = useMemo(
    () => construireTapis(points, grandeur), [points, grandeur])
  const journees = useMemo(
    () => journeesTypes(points, grandeur.cle), [points, grandeur])
  const charges = useMemo(
    () => journeesTypes(points, 'charge_kwh'), [points])

  if (enCours) return <Spinner />

  if (!points.length) {
    return (
      <Card className="p-4" data-testid="cal-tapis-vide">
        <ChartEmpty
          title="Lancer la simulation"
          description={refus || SANS_SERIE}
        />
      </Card>
    )
  }

  const moisActif = moisChoisi
    ?? (journees.length ? journees[journees.length - 1].mois : null)
  const journeeActive = journees.find((j) => j.mois === moisActif) || null
  const chargeActive = charges.find((c) => c.mois === moisActif) || null
  const dur = animationDuration()

  const donneesJournee = Array.from({ length: 24 }, (_, heure) => ({
    heure,
    production: journeeActive ? journeeActive.heures[heure] : null,
    charge: chargeActive ? chargeActive.heures[heure] : null,
  }))

  const valeur = (v) => (v === null
    ? 'non calculée'
    : `${formatNumber(v, { decimals: grandeur.decimales })} ${grandeur.unite}`)

  return (
    <Card className="flex flex-col gap-3 p-4" data-testid="cal-tapis">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold">Série horaire</h3>
        <div className="flex gap-1">
          {disponibles.map((g) => (
            <Button
              key={g.cle}
              size="sm"
              variant={g.cle === grandeur.cle ? 'default' : 'outline'}
              onClick={() => setCleGrandeur(g.cle)}
              data-testid={`cal-tapis-grandeur-${g.cle}`}
            >
              {g.libelle}
            </Button>
          ))}
        </div>
      </div>

      {serie?.tronquee && (
        <p className="text-xs text-warning" data-testid="cal-tapis-tronquee">
          {serie.motif_troncature
            || "Série agrégée au jour : le tapis n'affiche qu'une ligne par "
              + "journée, aucune heure n'est reconstituée."}
        </p>
      )}

      {/* ── Le tapis : une colonne par jour, une ligne par heure ─────────── */}
      <div>
        <svg
          viewBox={`0 0 ${tapis.jours.length} ${tapis.lignes.length}`}
          preserveAspectRatio="none"
          className="h-36 w-full"
          role="img"
          aria-label={`Tapis de chaleur ${grandeur.libelle.toLowerCase()}, `
            + `${tapis.jours.length} jour(s) × ${tapis.lignes.length} ligne(s)`}
          data-testid="cal-tapis-grille"
        >
          {tapis.jours.map((jour, x) => (
            <g key={jour.cle} data-testid="cal-tapis-jour">
              {tapis.lignes.map((ligne, y) => {
                const v = jour.cellules.has(ligne)
                  ? jour.cellules.get(ligne) : null
                const etendue = (tapis.maxi ?? 0) - (tapis.mini ?? 0)
                const ratio = (v === null || etendue <= 0)
                  ? 0 : (v - tapis.mini) / etendue
                return (
                  <rect
                    key={`${jour.cle}-${ligne}`}
                    x={x} y={y} width={1} height={1}
                    fill={v === null ? CHART_TOKENS.grid : CHART_TOKENS.primary}
                    fillOpacity={v === null ? 0.25 : 0.08 + 0.92 * ratio}
                  />
                )
              })}
            </g>
          ))}
        </svg>
        <div
          className="mt-1 flex items-center justify-between text-xs text-muted-foreground"
          data-testid="cal-tapis-legende"
        >
          <span>{valeur(tapis.mini)}</span>
          <span>
            {tapis.jours.length} jour(s) ·{' '}
            {tapis.horaire ? '24 heures' : 'journée entière'}
          </span>
          <span>{valeur(tapis.maxi)}</span>
        </div>
      </div>

      {/* ── La journée type du mois choisi, et le pic de chaque mois ─────── */}
      {journees.length > 0 && (
        <div className="flex flex-col gap-2" data-testid="cal-tapis-journee-type">
          <div className="flex flex-wrap gap-1">
            {journees.map((j) => (
              <Button
                key={j.mois}
                size="sm"
                variant={j.mois === moisActif ? 'default' : 'ghost'}
                onClick={() => setMoisChoisi(j.mois)}
                data-testid={`cal-tapis-mois-${j.mois}`}
              >
                {MOIS_COURT[j.mois - 1] || j.mois}
              </Button>
            ))}
          </div>

          <ChartFrame
            label={`Journée type de ${MOIS[(moisActif || 1) - 1]} : moyenne `
              + `de ${grandeur.libelle.toLowerCase()} par heure`}
            columns={[
              { key: 'heure', header: 'Heure' },
              {
                key: 'production',
                header: grandeur.libelle,
                align: 'right',
                format: (v) => valeur(v),
              },
            ]}
            rows={donneesJournee}
            getRowKey={(row) => row.heure}
          >
            <LineChart
              width={640}
              height={220}
              data={donneesJournee}
              margin={{ top: 8, right: 8, bottom: 8, left: 0 }}
            >
              <CartesianGrid {...CHART_GRID_STYLE} />
              <XAxis
                dataKey="heure"
                tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<ChartTooltip />} />
              <Legend />
              <Line
                type="monotone"
                dataKey="production"
                name={`${grandeur.libelle} (${grandeur.unite})`}
                stroke={CHART_TOKENS.primary}
                dot={false}
                connectNulls={false}
                isAnimationActive={dur > 0}
                animationDuration={dur}
              />
              {chargeActive && (
                <Line
                  type="monotone"
                  dataKey="charge"
                  name="Consommation (kWh)"
                  stroke={CHART_TOKENS.warning}
                  dot={false}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              )}
            </LineChart>
          </ChartFrame>

          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {journees.map((j) => (
              <li key={j.mois} data-testid={`cal-tapis-pic-${j.mois}`} data-pic={j.pic ?? ''}>
                {MOIS_COURT[j.mois - 1] || j.mois} : {valeur(j.pic)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}
