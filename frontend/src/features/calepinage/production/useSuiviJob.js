/* ACAL345 — l'UNIQUE suivi d'un calcul moteur qui peut passer en tâche de fond
   (CAL23 / ACAL125). `RemplissageProuve.jsx` et `PanneauProduction.jsx`
   portaient deux copies du même cycle : lancer l'appel, reconnaître un 202
   (`job_id`) et suivre `moteur.resultat(jobId)` jusqu'à une issue RÉELLE
   (`issueDuJob` : queued/running/done/failed), sans qu'un minuteur survive au
   démontage. Seul ce que chaque écran fait de l'issue reste chez lui. */
import { useEffect, useRef, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { issueDuJob } from './suiviSimulation'

/**
 * @param {object} o
 * @param {number} o.intervalleMs           pas de relecture du job
 * @param {Function} o.surIssue             (issue, suivi) — job terminé (succès ou refus)
 * @param {Function} o.surInterruption      le suivi lui-même a échoué
 */
export default function useSuiviJob({ intervalleMs, surIssue, surInterruption }) {
  const [enCours, setEnCours] = useState(false)
  const [job, setJob] = useState(null)
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
        // ACAL125 — statuts RÉELS du job partagé (queued/running/done/failed).
        const issue = issueDuJob(suivi)
        if (issue.etat === 'attente') {
          minuterie.current = setTimeout(() => suivre(jobId), intervalleMs)
          return
        }
        setEnCours(false)
        surIssue(issue, suivi)
      })
      .catch(() => {
        setEnCours(false)
        surInterruption()
      })
  }

  /**
   * Lance `appel` (une promesse axios). 202 au-delà du budget synchrone : le
   * moteur rend un job, suivi ici ; sinon `surSynchrone(donnees)`.
   */
  const lancer = (appel, { surSynchrone, surErreur }) => {
    setJob(null)
    setEnCours(true)
    Promise.resolve(appel)
      .then((res) => {
        const donnees = res?.data ?? null
        if (donnees?.job_id) {
          setJob(donnees)
          suivre(donnees.job_id)
          return
        }
        setEnCours(false)
        surSynchrone(donnees)
      })
      .catch((e) => {
        setEnCours(false)
        surErreur(e)
      })
  }

  return { enCours, job, lancer }
}
