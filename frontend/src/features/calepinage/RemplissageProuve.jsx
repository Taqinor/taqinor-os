/* eslint-disable react-refresh/only-export-components --
   `regimeDePreuve` est une fonction PURE (un bloc `preuve` → la phrase à
   afficher) : le test jumeau l'exerce sans monter l'écran, parce que c'est ELLE
   qui garantit qu'on n'écrit jamais « prouvé » sur une heuristique. Même
   dérogation que `module.config.jsx` du même module. */
import { useEffect, useRef, useState } from 'react'
import calepinageApi from '../../api/calepinageApi'

/* ============================================================================
   CAL79 — LE REMPLISSAGE, ET L'HONNÊTETÉ SUR SON RÉGIME DE PREUVE.
   ----------------------------------------------------------------------------
   Constat : l'atelier affiche déjà une note « calepinage automatique » (AP-F2)
   mais AUCUN régime de preuve, et aucun écran ne consomme le moteur prouvé. Un
   plan heuristique et un optimum démontré s'affichaient donc à l'identique —
   c'est-à-dire que le commercial ne pouvait pas savoir lequel des deux il
   promettait au client.

   LES DEUX PHRASES, ET JAMAIS L'UNE POUR L'AUTRE :
     * « Optimum prouvé (N) » — UNIQUEMENT quand le moteur le démontre
       (`preuve.optimal` ET `preuve.methode_exacte`) ;
     * « Meilleur plan trouvé (N) — borne supérieure B » sinon, avec la borne
       que le moteur publie. Sans borne publiée, on le DIT plutôt que d'en
       inventer une.
   C'est la règle fondateur « zéro chiffre inventé » appliquée à un mot : le
   mot « prouvé » est un chiffre comme un autre.

   L'ÉDITION MANUELLE RESTE PRIORITAIRE : ce panneau ne pose JAMAIS le plan
   tout seul. Il propose ; c'est un geste explicite (« Appliquer ce plan ») qui
   écrase le travail en cours, et en lecture seule il ne le propose même pas.

   LA PORTE MOTEUR EST CELLE DE CAL22/CAL23, sans seconde forme d'URL :
   `POST /calepinage/moteur/calculer/` rend soit le résultat, soit un 202
   `{job_id}` au-delà du budget de calcul synchrone ; on suit alors
   `GET /calepinage/moteur/resultat/<job_id>/` et on AFFICHE l'avancement
   publié (`progress_pct`), jamais une barre qui avance toute seule.
   ========================================================================== */

/**
 * CAL79 — le RÉGIME de preuve d'un résultat du moteur.
 * Rend `{ prouve, total, borne, phrase, methode }`, ou `null` si le moteur
 * n'a publié aucun bloc `preuve` (on n'affirme alors rien du tout).
 */
export function regimeDePreuve(resultat) {
  const preuve = resultat?.preuve
  if (!preuve || typeof preuve !== 'object') return null

  const total = preuve.total_retenu ?? resultat?.total_modules ?? null
  const prouve = Boolean(preuve.optimal) && Boolean(preuve.methode_exacte)
  const borne = preuve.borne_superieure ?? null

  if (prouve) {
    return {
      prouve: true,
      total,
      borne,
      methode: preuve.methode ?? null,
      phrase: `Optimum prouvé (${total ?? '—'})`,
    }
  }
  return {
    prouve: false,
    total,
    borne,
    methode: preuve.methode ?? null,
    phrase: borne === null || borne === undefined
      // Aucune borne publiée : on ne la fabrique pas.
      ? `Meilleur plan trouvé (${total ?? '—'}) — aucune borne supérieure publiée`
      : `Meilleur plan trouvé (${total ?? '—'}) — borne supérieure ${borne}`,
  }
}

/** Un travail de fond encore en cours ? Les statuts du job partagé (CAL23). */
function enAttente(job) {
  const statut = String(job?.statut || '').toUpperCase()
  return statut === 'PENDING' || statut === 'STARTED' || statut === 'RETRY'
}

export default function RemplissageProuve({
  entree = null, onAppliquer = null, lectureSeule = false, intervalleMs = 2000,
}) {
  const [resultat, setResultat] = useState(null)
  const [job, setJob] = useState(null)
  const [enCours, setEnCours] = useState(false)
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
        if (enAttente(suivi)) {
          minuterie.current = setTimeout(() => suivre(jobId), intervalleMs)
          return
        }
        setEnCours(false)
        if (suivi?.resultat) {
          setResultat(suivi.resultat)
        } else if (suivi?.message_erreur) {
          setRefus(suivi.message_erreur)
        }
      })
      .catch(() => {
        setEnCours(false)
        setRefus('Le suivi du calcul de fond a été interrompu.')
      })
  }

  const remplir = () => {
    if (!entree) {
      setRefus('Aucune surface à remplir : dessinez d’abord un pan de toit.')
      return
    }
    setRefus(null)
    setResultat(null)
    setJob(null)
    setEnCours(true)
    Promise.resolve(calepinageApi.moteur.calculer(entree))
      .then((res) => {
        const donnees = res?.data ?? null
        // 202 au-delà du budget synchrone : le moteur rend un job, pas un plan.
        if (donnees?.job_id) {
          setJob(donnees)
          suivre(donnees.job_id)
          return
        }
        setEnCours(false)
        setResultat(donnees)
      })
      .catch((e) => {
        setEnCours(false)
        setRefus(e?.response?.data?.detail
          || 'Le moteur n’a pas pu calculer ce remplissage.')
      })
  }

  const regime = regimeDePreuve(resultat)

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-remplissage">
      <p className="tech-label rule-brass text-brass-300">Remplissage automatique</p>

      {!lectureSeule && (
        <button
          type="button"
          onClick={remplir}
          disabled={enCours}
          data-testid="cal-remplissage-lancer"
          className="mt-3 rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200"
        >
          {enCours ? 'Calcul en cours…' : 'Remplir automatiquement'}
        </button>
      )}

      {/* L'AVANCEMENT PUBLIÉ par la tâche de fond — jamais une barre qui
          avance toute seule pour faire patienter. */}
      {enCours && job?.job_id && (
        <p className="mt-3 text-sm text-lune-soft" role="status"
          data-testid="cal-remplissage-avancement">
          Calcul de fond n°{job.job_id} —{' '}
          {job.progress_pct === null || job.progress_pct === undefined
            ? 'avancement non publié'
            : `${job.progress_pct} %`}{' '}
          ({job.statut ?? '—'})
        </p>
      )}

      {refus && (
        <p className="mt-3 text-sm text-red-300" role="alert"
          data-testid="cal-remplissage-refus">{refus}</p>
      )}

      {regime && (
        <div className="mt-4 border-t border-white/10 pt-4">
          <p
            className={`text-sm font-semibold ${regime.prouve ? 'text-emerald-300' : 'text-amber-200'}`}
            data-testid="cal-remplissage-regime"
            data-regime={regime.prouve ? 'prouve' : 'heuristique'}
          >
            {regime.phrase}
          </p>
          <p className="mt-1 text-xs text-lune-faint" data-testid="cal-remplissage-methode">
            Méthode : {regime.methode ?? 'non publiée'}
          </p>

          {/* L'ÉDITION MANUELLE RESTE PRIORITAIRE : le plan proposé n'écrase
              rien tant que ce geste n'est pas fait. */}
          {!lectureSeule && (
            <button
              type="button"
              onClick={() => onAppliquer && onAppliquer(resultat)}
              data-testid="cal-remplissage-appliquer"
              className="mt-3 rounded border border-white/15 px-4 py-2 text-sm font-semibold text-white"
            >
              Appliquer ce plan (remplace la disposition en cours)
            </button>
          )}
          <p className="mt-2 text-xs text-lune-faint">
            Tant que vous ne l’appliquez pas, votre disposition manuelle reste
            celle du calepinage.
          </p>
        </div>
      )}

      {resultat && !regime && (
        <p className="mt-3 text-sm text-lune-soft" data-testid="cal-remplissage-sans-preuve">
          Le moteur n’a publié aucun régime de preuve pour ce plan : rien n’est
          affirmé — ni « prouvé », ni borne supérieure.
        </p>
      )}
    </div>
  )
}
