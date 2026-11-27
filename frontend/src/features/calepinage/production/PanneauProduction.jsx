import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { formatNumber, formatPercent } from '../../../lib/format'
import { Button, Card } from '../../../ui'
import ListeManques from './ListeManques'
import RetourAtelier from '../atelier/RetourAtelier'
import {
  libelleBouton, cibleDuManque, etatCalcul, lienReglage, refusDepuisErreur, refusRenvoieAuxReglages,
} from './suiviSimulation'
import { premierOngletEtape } from '../atelier/parcoursGuide' // ACAL1639 — l'onglet qui ouvre une étape
import { lienManque } from './lienManque'
import { EcartPvgis, IncertitudeSigma, ReglagesUtilises, SourceMeteo } from './BandeauProvenanceProduction'
import { estIncomplet } from './BandeauProvenanceProduction.helpers'
import TapisHoraire from './TapisHoraire'
import GraphiqueMensuel from './GraphiqueMensuel'
import ResultatHeros from './ResultatHeros'
import PartiesProduction from './PartiesProduction'
import PourquoiProduction from './PourquoiProduction'
import LigneSurLaDuree from './LigneSurLaDuree'
import CartePostesPertes from './CartePostesPertes'
import LigneValeursPubliees from './LigneValeursPubliees'
import ResultatIncomplet from './ResultatIncomplet'
import {
  kwh, kwhParKwc, nonPublie, pourcentagePerf,
} from './ResultatHeros.helpers'
import useSuiviJob from './useSuiviJob'
import { reprendreSimulationAuto } from './simulationAuto'
import EtatEcranAtelier from '../atelier/EtatEcranAtelier'
import { estDelaiDepasse, MESSAGE_CALCUL_LENT } from '../delaiReseau'
import { useModeExpert } from '../atelier/modeExpert'
import useExpertParUrl from './useExpertParUrl'
import CarteFluxEnergie from './CarteFluxEnergie'
import ChargesAjoutees from './ChargesAjoutees'
import Pourquoi from '../commun/Pourquoi'

/* ============================================================================
   CAL236 — LE PANNEAU « PRODUCTION » DU MODULE.
   ----------------------------------------------------------------------------
   Constat (PACT11) : toute la chaîne de simulation est déjà backend (CAL138
   par pan, CAL139 pertes, CAL142 P50/P90) mais aucun écran ne montre le
   RÉSULTAT — ce panneau comble ce trou, alimenté PAR le contrat partagé
   `apps/calepinage/contract_samples/calepinage_resultat.json` (CAL244,
   `resultat_calepinage`) via `calepinageApi.calepinages.resultat(id)`.

   AUCUN CALCUL CÔTÉ ÉCRAN. Chaque grandeur affichée est EXACTEMENT celle que
   le serveur renvoie sous `production` ; ce panneau ne fait que la mettre en
   forme (`formatNumber`/`formatPercent`, jamais `toLocaleString`).

   LA DISCIPLINE DU NULL (même que `VariantesCompare.jsx`, CAL42) : le contrat
   distingue un calepinage POSÉ-mais-NON-SIMULÉ (`simule: false`, toutes les
   grandeurs de `production` valent `null`) d'un calepinage simulé. `null`
   s'affiche « non calculée », JAMAIS `0` — un `0 kWh` se lirait « cette
   toiture ne produit rien » là où personne n'a lancé de simulation. Un pan
   SANS module affiche en revanche un vrai `0` (`modules: 0`, une mesure), pas
   « non calculée » : `formatNumber` ne confond jamais les deux, il ne rend
   « — » QUE sur `null`/`undefined`.
   ========================================================================== */

const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

function BandeauNonSimule({ avertissements }) {
  const raison = avertissements?.[0]
    || 'Calepinage non simulé : aucune valeur de production n\'a encore été calculée.'
  return (
    <div
      className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm"
      data-testid="cal236-non-simule"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
      <span>{raison}</span>
    </div>
  )
}

/* ============================================================================
   CALX48 — LE BANDEAU DE PÉREMPTION (CALX70), JAMAIS UN CHIFFRE TROMPEUR.
   ----------------------------------------------------------------------------
   `simulation_perimee: true` veut dire que le document a changé DEPUIS le
   dernier calcul : les blocs sont déjà tous à `null` côté serveur (CALX70,
   D-CALX 14), donc l'état vide existant affiche déjà « non calculée » partout
   — ce bandeau ajoute seulement le MOT JUSTE (« périmé », pas « jamais
   lancé ») et la date du calcul devenu obsolète, EXACTEMENT le `motif` publié.
   ========================================================================== */
export function BandeauPerime({ motif }) {
  const texte = motif
    || 'Simulation périmée : le document ou un réglage de la société a changé depuis le dernier calcul.'
  return (
    <div
      className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm"
      data-testid="calx48-perime"
      role="status"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
      <span>{texte}</span>
    </div>
  )
}

/* ============================================================================
   ACAL125 — LE BOUTON DE CALCUL UNIQUE, PARTAGÉ PAR LES QUATRE ÉCRANS.
   ----------------------------------------------------------------------------
   Un seul bouton, toujours visible pour qui peut gérer (`calepinage_gerer`),
   dont le libellé dit l'état RÉEL du résultat servi : « Lancer » (jamais
   simulé), « Relancer la simulation » (périmé ; « Relancer (réglages modifiés) » quand le serveur prouve la cause), « Recalculer »
   (frais → `forcer: true`). Il suit le travail de fond par
   `moteur/resultat/<job_id>/` avec les statuts réels du serveur
   (`suiviSimulation.js` : queued/running = attente, done = succès, failed =
   refus structuré nommant le champ) et la liste NOMMÉE de ce qui manque,
   publiée par le serveur (`avertissements`) — jamais devinée ici. Il n'est
   PAS désactivé quand aucun poste de perte n'est saisi : le service
   n'en exige aucun.
   ========================================================================== */
// ACAL774 — le lien d'un refus qui ne se corrige pas dans les réglages (`plans`, `site.pin`).
// ACAL1639 — la cible SERVIE qui nomme une étape (Toit, Panneaux) ouvre CETTE étape (son écran, jamais la feuille
// « Avancé » : `state.etapeChoisie`, comme le clic sur l'étape) ; cible nulle ou absente : la table par champ.
function LienHorsReglages({ calepinageId, champ, cible = null }) {
  const ou = cibleDuManque(champ, cible)
  if (!ou) return null
  const vers = ou.etape ? lienManque(calepinageId, { onglet: premierOngletEtape(ou.etape) }) : lienManque(calepinageId, ou.cible)
  return (
    <>
      {' '}
      <Link to={vers} state={ou.etape ? { etapeChoisie: true } : undefined}
        className="inline-flex min-h-11 items-center underline" data-testid="acal774-lien">{ou.libelle}</Link>
    </>
  )
}

export function BoutonCalculer({
  calepinageId, data = null, avertissements = [], manque = [], intervalleMs = 2000, onTermine,
  declenchement = 0, variante = 'defaut',
}) {
  const peutGerer = useHasPermission('calepinage_gerer')
  const [refus, setRefus] = useState(null)
  // ACAL345 — le suivi du job de fond est l'UNIQUE copie partagée avec le
  // remplissage automatique (`useSuiviJob`).
  const suiviJob = useSuiviJob({
    intervalleMs,
    surIssue: (issue) => {
      if (issue.etat === 'succes') {
        // Le résultat est RELU du serveur (aucun calcul ni recopie ici).
        onTermine?.()
      } else {
        setRefus(issue.refus)
      }
    },
    surInterruption: () => setRefus({ champ: '', motif: 'Le suivi du calcul de fond a été interrompu.' }),
  })
  const { enCours, job } = suiviJob

  const etat = etatCalcul(data)

  const lancer = (forcerDemande = false) => {
    if (!calepinageId) return
    setRefus(null)
    const forcer = forcerDemande || etat === 'frais'
    const appel = forcer
      ? calepinageApi.calepinages.simuler(calepinageId, { forcer: true })
      : calepinageApi.calepinages.simuler(calepinageId)
    suiviJob.lancer(appel, {
      // 200 « déjà calculé » (hash inchangé) : rien à recalculer, mais
      // l'écran se rafraîchit quand même.
      surSynchrone: () => onTermine?.(),
      surErreur: (e) => setRefus(refusDepuisErreur(e)),
    })
  }

  // ACAL1987 — la simulation partie toute seule, lancée par le SERVEUR à l'enregistrement : on reprend son job
  // (« Simulation en cours… » puis le résultat). Pose incomplète : aucun job, rien à reprendre.
  const reprisAuto = useRef(false)
  useEffect(() => {
    if (reprisAuto.current || !calepinageId) return
    reprisAuto.current = true
    const auto = reprendreSimulationAuto(calepinageId)
    if (auto?.jobId) suiviJob.reprendre(auto.jobId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calepinageId])

  // ACAL167 — « Enregistrer et relancer » : le parent incrémente `declenchement`,
  // le bouton lance alors LA MÊME relance forcée (une seule logique de suivi).
  const dernierDeclenchement = useRef(declenchement)
  const relancerForce = useEffectEvent(() => lancer(true))
  useEffect(() => {
    if (declenchement !== dernierDeclenchement.current) {
      dernierDeclenchement.current = declenchement
      relancerForce()
    }
  }, [declenchement])

  if (!peutGerer) return null

  return (
    <div className="flex flex-col gap-2" data-testid="calx48-lancer">
      {variante === 'carte' ? (
        <button type="button" onClick={() => lancer()} disabled={enCours || !calepinageId}
          data-testid="calx48-lancer-bouton" data-etat={etat} className="cal-res-cta w-fit disabled:opacity-60">
          {enCours ? 'Simulation en cours…' : libelleBouton(etat, data?.motif)}
        </button>
      ) : (
        <Button
          type="button"
          size="sm"
          onClick={() => lancer()}
          disabled={enCours || !calepinageId}
          data-testid="calx48-lancer-bouton"
          data-etat={etat}
          className="w-fit"
        >
          {enCours ? 'Simulation en cours…' : libelleBouton(etat, data?.motif)}
        </Button>
      )}

      {/* L'AVANCEMENT PUBLIÉ par la tâche de fond — jamais une barre qui
          avance toute seule pour faire patienter (CAL79). */}
      {enCours && job?.job_id && (
        <p className="text-xs text-muted-foreground" role="status" data-testid="calx48-avancement">
          Calcul de fond n°{job.job_id} —{' '}
          {job.progress_pct === null || job.progress_pct === undefined
            ? 'avancement non publié'
            : `${job.progress_pct} %`}
        </p>
      )}

      {variante !== 'carte' && (manque.length > 0 || avertissements.length > 0) && (
        <div data-testid="calx48-manques">
          <p className="text-xs font-medium text-muted-foreground">Ce qui manque encore :</p>
          {manque.length > 0
            ? <ListeManques calepinageId={calepinageId} manque={manque} />
            : (
              <ul className="list-disc pl-5 text-xs text-muted-foreground">
                {avertissements.map((a) => <li key={a}>{a}</li>)}
              </ul>
            )}
        </div>
      )}

      {refus && refus.manquants?.length > 1 ? (
        <div className={variante === 'carte' ? 'rounded-md bg-card p-3 text-sm text-destructive' : 'text-sm text-destructive'}
          role="alert" data-testid="calx48-refus">
          <p>La simulation ne peut pas démarrer :</p>
          <ul className="list-disc pl-5" data-testid="acal940-manquants">
            {refus.manquants.map((ligne) => (
              <li key={ligne.champ} data-testid="acal940-manquant">
                {ligne.motif}
                {ligne.cible?.onglet === 'reglages' && ligne.cible.champ && (
                  <>
                    {' '}
                    <Link to={`/calepinage/reglages#${ligne.cible.champ}`} className="inline-flex min-h-11 items-center underline"
                      data-testid="acal940-lien-reglage">Ouvrir ce réglage</Link>
                  </>
                )}
                {(!ligne.cible || ligne.cible.etape) && (
                  <LienHorsReglages calepinageId={calepinageId} champ={ligne.champ} cible={ligne.cible} />
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : refus && (
        <p className={variante === 'carte' ? 'rounded-md bg-card p-3 text-sm text-destructive' : 'text-sm text-destructive'}
          role="alert" data-testid="calx48-refus">
          {refus.motif}
          <LienHorsReglages calepinageId={calepinageId} champ={refus.champ} cible={refus.cible} />
          {refusRenvoieAuxReglages(refus) && (
            <>
              {' '}
              <Link to={lienReglage(refus.champ)} className="underline" data-testid="calx48-lien-reglages">
                Ouvrir les réglages de simulation
              </Link>
            </>
          )}
          {/* T4-V1-012 — une erreur du serveur (temps dépassé, erreur inattendue) se relance d'ici. */}
          {refus.relancable && (
            <>
              {' '}
              <button type="button" onClick={() => lancer(true)} disabled={enCours}
                className="inline-flex min-h-11 items-center font-semibold underline" data-testid="calx48-reessayer">
                Réessayer
              </button>
            </>
          )}
        </p>
      )}
    </div>
  )
}

function BlocBase({ base }) {
  if (!base) return null
  return (
    <p className="text-xs text-muted-foreground" data-testid="cal236-base">
      Base {base.source || 'non calculée'}
      {base.fenetre_annees ? ` · fenêtre ${base.fenetre_annees}` : ''}
      {base.loss_passee_pct != null
        ? ` · pertes passées à PVGIS : ${formatPercent(base.loss_passee_pct, { decimals: 1 })}`
        : ''}
    </p>
  )
}

/* ACAL707 — niveau EXPERT : le tableau mensuel complet (irradiation horizontale,
   irradiation du plan, température, production, PR), chaque colonne lue par mois
   dans son bloc servi ; `null` = « non calculée » (jamais 0) ; bloc absent =
   colonne absente. En guidé : « Mois / P50 » d'origine. */
const parMois = (liste, cle) => (Array.isArray(liste) && liste.length
  ? Object.fromEntries(liste.map((e) => [e.mois, e[cle]])) : null)

function TableauMensuelComplet({ mensuel, production }) {
  const pr = parMois(production?.bilan_mensuel, 'pr')
  const motifsPr = parMois(production?.bilan_mensuel, 'pr_motif')
  const colonnes = [
    ['horizontale', 'Irradiation horizontale', parMois(production?.gain_inclinaison?.ghi_mensuel, 'ghi_kwh_m2'),
      (v) => `${formatNumber(v, { decimals: 1 })} kWh/m²`],
    ['plan', 'Irradiation du plan', parMois(production?.irradiation_mensuelle, 'irradiation_plan_kwh_m2'),
      (v) => `${formatNumber(v, { decimals: 1 })} kWh/m²`],
    ['temperature', 'Température', parMois(production?.bilan_mensuel, 'temperature_ambiante_c'),
      (v) => `${formatNumber(v, { decimals: 1 })} °C`],
    ['production', 'Production', Object.fromEntries(mensuel.map((m) => [m.mois, m.p50_kwh])), kwh],
    ['pr', 'PR', pr, pourcentagePerf],
  ].filter(([, , valeurs]) => valeurs !== null)
  const motifOmission = production?.gain_inclinaison?.motif_omission
  return (
    <>
      <table className="w-full text-sm" data-testid="acal707-mensuel">
        <thead>
          <tr className="text-left text-xs text-muted-foreground">
            <th className="py-1 font-normal">Mois</th>
            {colonnes.map(([cle, titre]) => (
              <th key={cle} className="py-1 text-right font-normal">{titre}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {mensuel.map((point) => (
            <tr key={point.mois} className="border-t border-border/60">
              <td className="py-1">{MOIS[(point.mois || 1) - 1] || point.mois}
                <Pourquoi cle="production.mensuel" valeurs={{ production }} /></td>
              {colonnes.map(([cle, , valeurs, rendu]) => (
                <td key={cle} className="py-1 text-right tabular-nums" data-testid={`acal707-${cle}-${point.mois}`}>
                  {valeurs[point.mois] === null || valeurs[point.mois] === undefined
                    ? <span title={(cle === 'pr' && motifsPr?.[point.mois]) || undefined}>non calculée</span>
                    : rendu(valeurs[point.mois])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {motifOmission && (
        <p className="mt-1 text-xs text-muted-foreground" data-testid="acal707-motif-horizontale">
          {`Irradiation horizontale non publiée : ${motifOmission}`}
        </p>
      )}
    </>
  )
}

function TableauMensuel({ mensuel, production = null }) {
  const [expert] = useModeExpert()
  if (!mensuel?.length) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="cal236-mensuel-vide">
        Production mensuelle non calculée.
      </p>
    )
  }
  if (expert) return <TableauMensuelComplet mensuel={mensuel} production={production} />
  return (
    <table className="w-full text-sm" data-testid="cal236-mensuel">
      <thead>
        <tr className="text-left text-xs text-muted-foreground">
          <th className="py-1 font-normal">Mois</th>
          <th className="py-1 text-right font-normal">P50</th>
        </tr>
      </thead>
      <tbody>
        {mensuel.map((point) => (
          <tr key={point.mois} className="border-t border-border/60">
            <td className="py-1">{MOIS[(point.mois || 1) - 1] || point.mois}
              <Pourquoi cle="production.mensuel" valeurs={{ production }} /></td>{/* ACAL873 */}
            <td className="py-1 text-right tabular-nums">{kwh(point.p50_kwh)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/* ACAL970 — une grandeur absente du tableau par pan s'écrit « — », « non calculée » en infobulle. */
const tiret = (v, rendu) => (v === null || v === undefined ? <span title="non calculée">—</span> : rendu(v))

function TableauParPan({ parPan, total = null }) {
  const incomplet = estIncomplet(total)
  if (!parPan?.length) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="cal236-par-pan-vide">
        Aucun pan.
      </p>
    )
  }
  return (
    <table className="w-full text-sm" data-testid="cal236-par-pan">
      <thead>
        <tr className="text-left text-xs text-muted-foreground">
          <th className="px-3 py-1 font-normal">Pan</th>
          {['Modules', 'kWc', 'P50', 'P75', 'P90', 'PR', 'kWh/kWc'].map((t) => (
            <th key={t} className="px-3 py-1 text-right font-normal">{t}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {parPan.map((pan) => (
          <tr key={pan.pan} className="border-t border-border/60">
            <td className="px-3 py-1">{pan.pan}</td>
            {/* Un pan sans module reste un vrai `0`, jamais « non calculée » :
                `formatNumber(0)` rend « 0 », distinct de `null`. */}
            <td className="px-3 py-1 text-right tabular-nums">{formatNumber(pan.modules, { decimals: 0 })}</td>
            <td className="px-3 py-1 text-right tabular-nums">
              {tiret(pan.kwc, (x) => formatNumber(x, { decimals: 2 }))}
            </td>
            <td className="px-3 py-1 text-right tabular-nums">{tiret(pan.p50_kwh, kwh)}</td>
            <td className="px-3 py-1 text-right tabular-nums">
              {incomplet ? nonPublie(total?.p75_kwh_motif) : tiret(pan.p75_kwh, kwh)}
            </td>
            <td className="px-3 py-1 text-right tabular-nums">
              {incomplet ? nonPublie(total?.p90_kwh_motif) : tiret(pan.p90_kwh, kwh)}
            </td>
            <td className="px-3 py-1 text-right tabular-nums">
              {incomplet ? nonPublie(total?.performance_ratio_motif) : tiret(pan.performance_ratio, pourcentagePerf)}
            </td>
            <td className="px-3 py-1 text-right tabular-nums">{tiret(pan.specific_yield_kwh_kwc, kwhParKwc)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function PanneauProduction({ calepinageId, intervalleMs = 2000, parcours = null }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute
  const expert = useExpertParUrl()

  const { data, loading, error, refetch } = useResource(
    () => calepinageApi.calepinages.resultat(id), id,
    // ACAL1905 — un délai dépassé se dit « Calcul en cours… » (avec « Réessayer »), pas « Production indisponible ».
    { select: (r) => r.data, errorMessage: (e) => (estDelaiDepasse(e) ? MESSAGE_CALCUL_LENT : 'Production indisponible.') },
  )
  // ACAL698 — « Voir les sources » ouvre le <details> « Réglages utilisés ».
  const [sourcesOuvertes, setSourcesOuvertes] = useState(false)

  if (loading || error) {
    return <EtatEcranAtelier id={id} loading={loading} error={error} testIdErreur="cal236-erreur" onRetry={refetch} />
  }

  const production = data?.production || null
  // CALX70 : un document qui a changé depuis le dernier calcul reste `simule:
  // false`, mais le motif « périmé » remplace celui de « jamais lancé ».
  const perime = data?.simulation_perimee === true
  // ERR-QAH-CALEPINAGE-EXPORT-CSV-400-PRODUCTION — `pose` est TOUJOURS
  // chiffrée (contrat CAL244 : « la pose est un fait », jamais `null`, même
  // non simulée/périmée) : `pose.total_modules === 0` dit sans détour qu'
  // AUCUN panneau n'est posé sur ce document — le MÊME fait que la porte
  // d'export refuse en 400 (`views/export_csv.py`, "Aucune géométrie
  // enregistrée"). On le lit ici, sur la réponse `resultat()` déjà en main
  // (AUCUNE requête de plus), pour que `TapisHoraire` ne l'ouvre même pas.
  // Acceptation ACAL490 — jamais simulé (ou calcul en cours) : aucune série
  // horaire n'existe, la porte d'export refuserait (400 « points ») : non ouverte.
  // ACAL990 — un avertissement ne s'écrit qu'une fois : celui du bandeau n'est pas redit dans la liste.
  const dejaDit = perime ? data?.motif : data?.avertissements?.[0]
  const autresAvertissements = [...new Set(data?.avertissements ?? [])].filter((a) => a !== dejaDit)
  const geometriePresente = (data?.pose?.total_modules ?? 0) > 0 && data?.simule === true

  return (
    <>
      <RetourAtelier calepinageId={id} />
      <Card className="flex flex-col gap-4 p-4" data-testid="cal236-panneau">
      {/* ACAL872 — le « ? » de la production annuelle, phrase du registre. */}
      <h2 className="flex items-center gap-1 text-base font-semibold">
        Production
        {data?.simule === true && !perime && <Pourquoi cle="production.p50_kwh" valeurs={data} />}
      </h2>
      {perime
        ? <BandeauPerime motif={data?.motif} />
        : (!data?.simule && <BandeauNonSimule avertissements={data?.avertissements} />)}
      <BoutonCalculer
        calepinageId={id}
        data={data}
        avertissements={data?.simule ? [] : autresAvertissements}
        manque={parcours?.manque ?? []}
        intervalleMs={intervalleMs}
        onTermine={refetch}
      />
      <BlocBase base={production?.base} />
      <ResultatHeros total={production?.total} simule={data?.simule === true && !perime}
        plages={data?.cascade?.plages}
        autoconsommation={data?.autoconsommation} />
      {data?.simule === true && !perime && <PartiesProduction parties={production?.parties} />}
      {data?.simule === true && !perime && <EcartPvgis validation={data?.validation} />}
      {data?.simule === true && !perime && <PourquoiProduction cascade={data?.cascade} />}
      {data?.simule === true && !perime && <LigneSurLaDuree production={production} incertitude={data?.incertitude} />}
      {data?.simule === true && !perime && <ResultatIncomplet calepinageId={id} data={data} parcours={parcours} />}
      {data?.simule === true && !perime && <GraphiqueMensuel autoconsommation={data?.autoconsommation} production={data?.production} />}
      <ReglagesUtilises simulation={data?.simulation} ouvert={sourcesOuvertes} onBascule={setSourcesOuvertes} />
      {/* ENF15 — `meteo` / `incertitude` servis par `GET resultat/` (CALX143/144). */}
      {data?.simule && <SourceMeteo meteo={data?.meteo} />}
      {data?.simule && <IncertitudeSigma incertitude={data?.incertitude} />}
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Production mensuelle</p>
          <TableauMensuel mensuel={production?.mensuel} production={production} />
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Par pan</p>
          <TableauParPan parPan={production?.par_pan} total={production?.total} />
        </div>
      </div>
      <CartePostesPertes cascade={data?.cascade} />
      {expert && <CarteFluxEnergie calepinageId={id} data={data} />}
      <ChargesAjoutees consommation={data?.consommation} />
      <LigneValeursPubliees simulation={data?.simulation} onVoirSources={() => setSourcesOuvertes(true)} />
    </Card>
    {/* CALX64 — le tapis jour × heure de la série persistée (CALX193). La
        série n'est PAS recopiée par `GET resultat/` (D-CALX 14, volume) :
        la propriété est passée pour le jour où elle y sera, et le composant
        retombe sinon sur la porte d'export (CALX6, CAL144) — SAUF quand
        `geometriePresente` est faux (ERR-QAH-CALEPINAGE-EXPORT-CSV-400-
        PRODUCTION) : la porte d'export refuserait de toute façon, pour un
        geste que personne n'a demandé en ouvrant simplement l'onglet. */}
    <TapisHoraire calepinageId={id} serie={data?.serie_horaire}
      geometriePresente={geometriePresente}
      perime={perime} cascade={data?.cascade}
      motifConsommation={data?.autoconsommation?.motif_absence} />
    </>
  )
}
