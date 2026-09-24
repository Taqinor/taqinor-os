import { useParams } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import ventesApi from '../../../api/ventesApi'
import useResource from '../../../hooks/useResource'
import { formatDate, formatMAD, formatNumber, formatPercent } from '../../../lib/format'
import { Card, Spinner, Stat } from '../../../ui'

/* ============================================================================
   CALX289 — L'ONGLET « ÉCONOMIE », EN LECTURE SEULE.
   ----------------------------------------------------------------------------
   Constat : le module ne montrait aucune donnée économique — `apps/calepinage`
   n'a ni fichier ni répertoire d'économie, et la règle du module INTERDIT au
   calepinage de calculer de l'argent (`apps/calepinage/services/note_calcul.py`
   CLES_INTERDITES/CLES_INTERDITES_EXACTES, D5). Parité Aurora : le calcul
   financier vit dans l'outil de VENTE, pas dans la conception
   (https://aurorasolar.com/sales-mode/).

   AUCUN CALCUL CÔTÉ ÉCRAN. Ce panneau LIT le bloc économie servi par
   `apps/ventes` (`GET /api/django/ventes/devis/<pk>/economie/`, CALX288,
   contrat `apps/ventes/contract_samples/ventes_economie.json`, CALX280) via
   `ventesApi.getEconomieDevis` — il ne recalcule ni ne devine jamais un
   montant. Le devis lu est celui rattaché au calepinage (`Calepinage.devis`,
   `apps/calepinage/models.py:66`), résolu depuis l'agrégat de détail déjà
   servi (`calepinageApi.calepinages.get`, CAL17,
   `contract_samples/calepinage_detail.json` — clé `devis` nullable, jamais
   omise).

   DEUX ABSENCES DISTINCTES, jamais confondues :
     1. Aucun devis lié (`calepinage.devis === null`) — le bloc économie
        n'existe pour AUCUN devis : le panneau affiche le motif et AUCUN
        nombre, jamais un tiret (Done).
     2. Un devis est lié mais un réglage société manque (indexation,
        actualisation, horizon…) — le SERVEUR publie alors `null` pour
        l'indicateur concerné avec son entrée dans `omissions[]` (jamais un
        zéro) : ce panneau affiche « non publié : <motif> » EXACTEMENT tel que
        servi, jamais reformulé.

   SANS AUCUN CHAMP DE SAISIE (règle du Done : `queryAllByRole('textbox')`
   vide) — ce panneau ne PEUT PAS écrire un réglage société ; l'écran de
   saisie est `Paramètres › Tarification & ROI` (CALX72), hors de ce périmètre.
   ========================================================================== */

const INDICATEURS = [
  { cle: 'van_mad', label: 'VAN', formatter: (v) => formatMAD(v, { decimals: 0 }) },
  { cle: 'tri_pct', label: 'TRI', formatter: (v) => formatPercent(v, { decimals: 2 }) },
  {
    cle: 'lcoe_mad_kwh',
    label: 'LCOE',
    formatter: (v) => `${formatNumber(v, { decimals: 2 })} MAD/kWh`,
  },
  {
    cle: 'retour_ans',
    label: 'Retour',
    formatter: (v) => `${formatNumber(v, { decimals: 0 })} ans`,
  },
  {
    cle: 'retour_actualise_ans',
    label: 'Retour actualisé',
    formatter: (v) => `${formatNumber(v, { decimals: 0 })} ans`,
  },
]

const LIBELLES_HYPOTHESES = {
  option_devis: 'Option retenue',
  investissement_mad: 'Investissement',
  economie_annee1_mad: 'Économie année 1',
  production_annee1_kwh: 'Production année 1',
  horizon_ans: 'Horizon',
  taux_actualisation_pct: "Taux d'actualisation",
  indexation_pct: 'Indexation tarifaire',
  degradation_pct: 'Dégradation annuelle',
}

// Libellé lisible d'une grandeur d'hypothèse — la clé brute sert de repli :
// jamais un libellé inventé pour une clé que ce panneau ne connaît pas encore.
const libelleHypothese = (cle) => LIBELLES_HYPOTHESES[cle] || cle

// Formatage de la VALEUR d'une hypothèse, dérivé du SUFFIXE de sa clé (mêmes
// conventions que le reste du dépôt : `_mad`, `_pct`, `_kwh`, `_ans`) — jamais
// une unité devinée hors de ce que la clé nomme déjà.
function formatValeurHypothese(cle, valeur) {
  if (valeur === null || valeur === undefined) return 'non publié'
  if (typeof valeur !== 'number') return String(valeur)
  if (cle.endsWith('_mad')) return formatMAD(valeur, { decimals: 0 })
  if (cle.endsWith('_pct')) return formatPercent(valeur, { decimals: 2 })
  if (cle.endsWith('_kwh')) return `${formatNumber(valeur, { decimals: 0 })} kWh`
  if (cle.endsWith('_ans')) return `${formatNumber(valeur, { decimals: 0 })} ans`
  return formatNumber(valeur)
}

function omissionMotif(omissions, cle) {
  return omissions?.find((o) => o.cle === cle)?.motif ?? null
}

// Le motif d'UNE omission, préfixé « non publié : » — SAUF s'il le porte déjà
// (le serveur préfixe lui-même le motif des CINQ indicateurs dérivés, jamais
// celui d'une grandeur d'entrée simple : `ventes_economie.json`, exemple_vide).
// Ne JAMAIS doubler le préfixe plutôt que de le supposer absent.
function libelleOmission(motif) {
  const texte = motif || 'aucun motif publié par le serveur'
  return /^non publié\s*:/i.test(texte) ? texte : `non publié : ${texte}`
}

/** Un devis (ou aucun) : AUCUN chiffre, seulement le motif du serveur (ou,
    à défaut, un motif générique — jamais un panneau muet). */
function MotifAbsence({ motif, testId }) {
  return (
    <p
      className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-sm text-muted-foreground"
      data-testid={testId}
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>{motif}</span>
    </p>
  )
}

/** UN indicateur : la valeur servie si publiée, sinon « non publié : <motif> »
    — jamais un zéro, jamais un tiret muet. */
function IndicateurCarte({ cle, label, valeur, formatter, omissions }) {
  if (valeur === null || valeur === undefined) {
    const motif = omissionMotif(omissions, cle)
    return (
      <div
        className="flex flex-col gap-1 rounded-md border border-border bg-muted/40 p-3"
        data-testid={`calx289-indicateur-${cle}`}
      >
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        <span className="text-sm text-muted-foreground">
          {libelleOmission(motif)}
        </span>
      </div>
    )
  }
  return (
    <Stat
      label={label}
      value={formatter(valeur)}
      data-testid={`calx289-indicateur-${cle}`}
    />
  )
}

function cellule(valeur, formatter) {
  return valeur === null || valeur === undefined ? 'non publié' : formatter(valeur)
}

/** Le flux de trésorerie année par année, EXACTEMENT tel que servi — aucune
    ligne recalculée. Un flux vide (aucun horizon saisi) ne rend aucun
    tableau : `omissions[]` porte déjà le motif. */
function TableauFlux({ flux }) {
  if (!flux?.length) return null
  return (
    <table className="w-full text-sm" data-testid="calx289-flux">
      <thead>
        <tr className="text-left text-xs text-muted-foreground">
          <th className="py-1 font-normal">Année</th>
          <th className="py-1 text-right font-normal">Économie</th>
          <th className="py-1 text-right font-normal">Flux</th>
          <th className="py-1 text-right font-normal">Cumul</th>
          <th className="py-1 text-right font-normal">Flux actualisé</th>
        </tr>
      </thead>
      <tbody>
        {flux.map((ligne) => (
          <tr key={ligne.annee} className="border-t border-border/60" data-testid="calx289-flux-ligne">
            <td className="py-1">{ligne.annee}</td>
            <td className="py-1 text-right tabular-nums">
              {cellule(ligne.economie_mad, (v) => formatMAD(v, { decimals: 0 }))}
            </td>
            <td className="py-1 text-right tabular-nums">
              {cellule(ligne.flux_mad, (v) => formatMAD(v, { decimals: 0 }))}
            </td>
            <td className="py-1 text-right tabular-nums">
              {cellule(ligne.cumul_mad, (v) => formatMAD(v, { decimals: 0 }))}
            </td>
            <td className="py-1 text-right tabular-nums">
              {cellule(ligne.flux_actualise_mad, (v) => formatMAD(v, { decimals: 0 }))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Chaque grandeur ENTRÉE dans le calcul, avec sa PROVENANCE (`source`) et sa
    date de saisie — une valeur tirée du devis lui-même (`saisie_le: null`)
    n'est pas une saisie, elle est ANNOTÉE comme telle plutôt que laissée nue. */
function TableauHypotheses({ hypotheses }) {
  if (!hypotheses?.length) return null
  return (
    <table className="w-full text-sm" data-testid="calx289-hypotheses">
      <thead>
        <tr className="text-left text-xs text-muted-foreground">
          <th className="py-1 font-normal">Grandeur</th>
          <th className="py-1 text-right font-normal">Valeur</th>
          <th className="py-1 font-normal">Source</th>
          <th className="py-1 font-normal">Saisie le</th>
        </tr>
      </thead>
      <tbody>
        {hypotheses.map((h) => (
          <tr key={h.cle} className="border-t border-border/60" data-testid="calx289-hypothese">
            <td className="py-1">{libelleHypothese(h.cle)}</td>
            <td className="py-1 text-right tabular-nums">{formatValeurHypothese(h.cle, h.valeur)}</td>
            <td className="py-1 text-xs text-muted-foreground">{h.source}</td>
            <td className="py-1 text-xs text-muted-foreground">
              {h.saisie_le ? formatDate(h.saisie_le) : 'issue du devis'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Chaque grandeur NON saisie et chaque indicateur NON publié, en clair —
    LISTE COMPLÈTE (au-delà des cinq indicateurs ci-dessus : charges,
    remplacements, taux non fournis…), jamais tue. */
function ListeOmissions({ omissions }) {
  if (!omissions?.length) return null
  return (
    <ul className="list-disc pl-5 text-xs text-muted-foreground" data-testid="calx289-omissions">
      {omissions.map((o) => (
        <li key={o.cle} data-testid="calx289-omission">{libelleOmission(o.motif)}</li>
      ))}
    </ul>
  )
}

function BlocEconomie({ economie }) {
  const { horizon_ans: horizonAns, flux, hypotheses, omissions } = economie
  return (
    <div className="flex flex-col gap-4" data-testid="calx289-bloc">
      {horizonAns !== null && horizonAns !== undefined && (
        <p className="text-xs text-muted-foreground" data-testid="calx289-horizon">
          {`Horizon retenu : ${formatNumber(horizonAns, { decimals: 0 })} ans`}
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5" data-testid="calx289-indicateurs">
        {INDICATEURS.map(({ cle, label, formatter }) => (
          <IndicateurCarte
            key={cle}
            cle={cle}
            label={label}
            valeur={economie[cle]}
            formatter={formatter}
            omissions={omissions}
          />
        ))}
      </div>
      <TableauFlux flux={flux} />
      <TableauHypotheses hypotheses={hypotheses} />
      <ListeOmissions omissions={omissions} />
    </div>
  )
}

export default function PanneauEconomie({ calepinageId }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const {
    data: calepinage,
    loading: loadingCalepinage,
    error: errorCalepinage,
  } = useResource(
    () => calepinageApi.calepinages.get(id), id,
    { select: (r) => r.data, errorMessage: 'Calepinage indisponible.' },
  )

  const devisId = calepinage?.devis?.id ?? null

  const {
    data: economie,
    loading: loadingEconomie,
    error: errorEconomie,
  } = useResource(
    () => ventesApi.getEconomieDevis(devisId), devisId,
    {
      enabled: Boolean(devisId),
      select: (r) => r.data,
      errorMessage: (e) => e?.response?.data?.detail || 'Bloc économie indisponible.',
    },
  )

  if (loadingCalepinage) return <Spinner />
  if (errorCalepinage) {
    return <p className="text-sm text-destructive" data-testid="calx289-erreur">{errorCalepinage}</p>
  }

  return (
    <Card className="flex flex-col gap-4 p-4" data-testid="calx289-panneau">
      <h2 className="text-base font-semibold">Économie</h2>
      {!devisId && (
        <MotifAbsence
          testId="calx289-sans-devis"
          motif="Aucun devis lié à ce calepinage : le bloc économie n'est publié que pour un calepinage rattaché à un devis."
        />
      )}
      {devisId && loadingEconomie && <Spinner />}
      {devisId && errorEconomie && (
        <p className="text-sm text-destructive" data-testid="calx289-erreur-economie">{errorEconomie}</p>
      )}
      {devisId && !loadingEconomie && !errorEconomie && economie && (
        <BlocEconomie economie={economie} />
      )}
    </Card>
  )
}
