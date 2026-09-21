import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber, formatPercent } from '../../../lib/format'
import { Button, Card, Spinner, Stat } from '../../../ui'
import { PARAM_ONGLET } from '../atelier/onglets'
import RetourAtelier from '../atelier/RetourAtelier'
import TapisHoraire from './TapisHoraire'

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

/** Une grandeur absente du serveur s'écrit « non calculée », jamais « — » nu
    ni `0` : c'est le vocabulaire que CAL236 impose (Done, PLAN2.md). */
function nonCalculee(valeur, rendu) {
  return valeur === null || valeur === undefined ? 'non calculée' : rendu(valeur)
}

const kwh = (v) => nonCalculee(v, (x) => `${formatNumber(x, { decimals: 0 })} kWh`)
const pourcentagePerf = (v) => nonCalculee(v, (x) => formatPercent(x * 100, { decimals: 1 }))
const kwhParKwc = (v) => nonCalculee(v, (x) => `${formatNumber(x, { decimals: 1 })} kWh/kWc`)

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
    || 'Simulation périmée : le document a changé depuis le dernier calcul.'
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

const JOB_EN_ATTENTE = new Set(['PENDING', 'STARTED', 'RETRY'])

/** Le refus 400 de `POST simuler/` : `{champ: [motif]}` (règle fondateur —
    jamais un refus générique, le champ fautif est toujours nommé). */
function refusDepuisErreur(erreur) {
  const corps = erreur?.response?.data
  if (!corps || typeof corps !== 'object') {
    return { champ: '', motif: 'Simulation refusée par le serveur.' }
  }
  const [champ, valeur] = Object.entries(corps)[0] || []
  const motif = Array.isArray(valeur) ? valeur[0] : valeur
  return {
    champ: champ || '',
    motif: (typeof motif === 'string' && motif) || 'Simulation refusée par le serveur.',
  }
}

/* ============================================================================
   CALX48 — LE REFUS ACTIONNABLE : PARTAGÉ PAR LES DEUX PANNEAUX.
   ----------------------------------------------------------------------------
   Un bouton « Lancer la simulation » (`POST simuler/`, CALX5), le suivi du
   travail de fond par `moteur/resultat/<job_id>/` (MÊME patron que
   `RemplissageProuve.jsx`, CAL79 — un seul kind, D-CALX 12) et la liste
   NOMMÉE de ce qui manque, publiée par le serveur (`avertissements`) — jamais
   devinée ici. `DiagrammePertes.jsx` (même tâche) importe ce composant plutôt
   que de dupliquer le suivi de job.
   ========================================================================== */
export function BoutonLancerSimulation({
  calepinageId, avertissements = [], desactive = false, intervalleMs = 2000, onTermine,
}) {
  const [enCours, setEnCours] = useState(false)
  const [job, setJob] = useState(null)
  const [refus, setRefus] = useState(null)
  const minuterie = useRef(null)

  // Un suivi de travail de fond ne doit jamais survivre au démontage.
  useEffect(() => () => {
    if (minuterie.current) clearTimeout(minuterie.current)
  }, [])

  const suivre = (jobId) => {
    Promise.resolve(calepinageApi.moteur.resultat(jobId))
      .then((res) => {
        const suivi = res?.data ?? null
        setJob(suivi)
        if (JOB_EN_ATTENTE.has(String(suivi?.statut || '').toUpperCase())) {
          minuterie.current = setTimeout(() => suivre(jobId), intervalleMs)
          return
        }
        setEnCours(false)
        if (suivi?.resultat) {
          // Les chiffres arrivent SANS rechargement complet : un simple
          // `refetch()` du panneau appelant.
          onTermine?.()
        } else {
          setRefus({ champ: '', motif: suivi?.message_erreur || 'La simulation a échoué.' })
        }
      })
      .catch(() => {
        setEnCours(false)
        setRefus({ champ: '', motif: 'Le suivi du calcul de fond a été interrompu.' })
      })
  }

  const lancer = () => {
    if (!calepinageId) return
    setRefus(null)
    setEnCours(true)
    Promise.resolve(calepinageApi.calepinages.simuler(calepinageId))
      .then((res) => {
        const donnees = res?.data ?? null
        if (donnees?.job_id) {
          setJob(donnees)
          suivre(donnees.job_id)
          return
        }
        // 200 « déjà calculé » (hash inchangé) : rien à recalculer, mais
        // l'écran se rafraîchit quand même (course possible avec un calcul
        // qui vient de finir ailleurs).
        setEnCours(false)
        onTermine?.()
      })
      .catch((e) => {
        setEnCours(false)
        setRefus(refusDepuisErreur(e))
      })
  }

  // CALX69 — un refus sur un réglage de simulation renvoie vers son écran.
  const versReglages = typeof refus?.champ === 'string'
    && refus.champ.startsWith('parametres.simulation')

  return (
    <div className="flex flex-col gap-2" data-testid="calx48-lancer">
      <Button
        type="button"
        size="sm"
        onClick={lancer}
        disabled={enCours || desactive}
        data-testid="calx48-lancer-bouton"
        className="w-fit"
      >
        {enCours ? 'Simulation en cours…' : 'Lancer la simulation'}
      </Button>

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

      {avertissements.length > 0 && (
        <div data-testid="calx48-manques">
          <p className="text-xs font-medium text-muted-foreground">Ce qui manque encore :</p>
          <ul className="list-disc pl-5 text-xs text-muted-foreground">
            {avertissements.map((a) => <li key={a}>{a}</li>)}
          </ul>
          <Link
            to={`/calepinage/${calepinageId}?${PARAM_ONGLET}=pertes`}
            className="text-xs font-medium text-primary underline"
            data-testid="calx48-lien-pertes"
          >
            Ouvrir l’onglet Pertes
          </Link>
        </div>
      )}

      {refus && (
        <p className="text-sm text-destructive" role="alert" data-testid="calx48-refus">
          {refus.motif}
          {versReglages && (
            <>
              {' '}
              <Link to="/calepinage/reglages" className="underline" data-testid="calx48-lien-reglages">
                Ouvrir les réglages de simulation
              </Link>
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

function TotalKpis({ total }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="cal236-total">
      <Stat label="P50 (annuel)" value={kwh(total?.p50_kwh)} />
      <Stat label="P75 (annuel)" value={kwh(total?.p75_kwh)} />
      <Stat label="P90 (annuel)" value={kwh(total?.p90_kwh)} />
      <Stat
        label="Variabilité annuelle (σ)"
        value={nonCalculee(total?.annual_variability,
          (x) => formatPercent(x * 100, { decimals: 1 }))}
      />
      <Stat label="Ratio de performance (PR)" value={pourcentagePerf(total?.performance_ratio)} />
      <Stat label="Productible" value={kwhParKwc(total?.specific_yield_kwh_kwc)} />
      <Stat label="Puissance installée" value={nonCalculee(total?.kwc,
        (x) => `${formatNumber(x, { decimals: 2 })} kWc`)}
      />
      <Stat label="Pertes totales" value={nonCalculee(total?.total_loss_pct,
        (x) => formatPercent(x, { decimals: 1 }))}
      />
    </div>
  )
}

function TableauMensuel({ mensuel }) {
  if (!mensuel?.length) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="cal236-mensuel-vide">
        Production mensuelle non calculée.
      </p>
    )
  }
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
            <td className="py-1">{MOIS[(point.mois || 1) - 1] || point.mois}</td>
            <td className="py-1 text-right tabular-nums">{kwh(point.p50_kwh)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function TableauParPan({ parPan }) {
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
          <th className="py-1 font-normal">Pan</th>
          <th className="py-1 text-right font-normal">Modules</th>
          <th className="py-1 text-right font-normal">kWc</th>
          <th className="py-1 text-right font-normal">P50</th>
          <th className="py-1 text-right font-normal">P75</th>
          <th className="py-1 text-right font-normal">P90</th>
          <th className="py-1 text-right font-normal">PR</th>
          <th className="py-1 text-right font-normal">kWh/kWc</th>
        </tr>
      </thead>
      <tbody>
        {parPan.map((pan) => (
          <tr key={pan.pan} className="border-t border-border/60">
            <td className="py-1">{pan.pan}</td>
            {/* Un pan sans module reste un vrai `0`, jamais « non calculée » :
                `formatNumber(0)` rend « 0 », distinct de `null`. */}
            <td className="py-1 text-right tabular-nums">{formatNumber(pan.modules, { decimals: 0 })}</td>
            <td className="py-1 text-right tabular-nums">
              {nonCalculee(pan.kwc, (x) => formatNumber(x, { decimals: 2 }))}
            </td>
            <td className="py-1 text-right tabular-nums">{kwh(pan.p50_kwh)}</td>
            <td className="py-1 text-right tabular-nums">{kwh(pan.p75_kwh)}</td>
            <td className="py-1 text-right tabular-nums">{kwh(pan.p90_kwh)}</td>
            <td className="py-1 text-right tabular-nums">{pourcentagePerf(pan.performance_ratio)}</td>
            <td className="py-1 text-right tabular-nums">{kwhParKwc(pan.specific_yield_kwh_kwc)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function PanneauProduction({ calepinageId }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error, refetch } = useResource(
    () => calepinageApi.calepinages.resultat(id), id,
    { select: (r) => r.data, errorMessage: 'Production indisponible.' },
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
        <p className="text-sm text-destructive" data-testid="cal236-erreur">{error}</p>
      </>
    )
  }

  const production = data?.production || null
  // CALX70 : un document qui a changé depuis le dernier calcul reste `simule:
  // false`, mais le motif « périmé » remplace celui de « jamais lancé ».
  const perime = data?.simulation_perimee === true
  // CALX48 — Done : « sans poste de perte, le bouton est inactif ». `pertes`
  // (liste plate) ET `cascade.etapes` valent tous deux « rien à simuler ».
  const pertesVides = !(data?.pertes?.length) && !(data?.cascade?.etapes?.length)

  return (
    <>
      <RetourAtelier calepinageId={id} />
      <Card className="flex flex-col gap-4 p-4" data-testid="cal236-panneau">
      <h2 className="text-base font-semibold">Production</h2>
      {perime
        ? <BandeauPerime motif={data?.motif} />
        : (!data?.simule && <BandeauNonSimule avertissements={data?.avertissements} />)}
      {!data?.simule && (
        <BoutonLancerSimulation
          calepinageId={id}
          avertissements={data?.avertissements ?? []}
          desactive={pertesVides}
          onTermine={refetch}
        />
      )}
      <BlocBase base={production?.base} />
      <TotalKpis total={production?.total} />
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Production mensuelle</p>
          <TableauMensuel mensuel={production?.mensuel} />
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Par pan</p>
          <TableauParPan parPan={production?.par_pan} />
        </div>
      </div>
    </Card>
    {/* CALX64 — le tapis jour × heure de la série persistée (CALX193). La
        série n'est PAS recopiée par `GET resultat/` (D-CALX 14, volume) :
        la propriété est passée pour le jour où elle y sera, et le composant
        retombe sinon sur la porte d'export (CALX6, CAL144). */}
    <TapisHoraire calepinageId={id} serie={data?.serie_horaire} />
    </>
  )
}
