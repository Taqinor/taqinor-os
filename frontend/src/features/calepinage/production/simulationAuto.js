/* ACAL398 — la simulation repart TOUTE SEULE après un enregistrement qui crée
   une nouvelle version : un seul POST `simuler/` (sans `forcer`), l'issue est
   gardée dans une table EN MÉMOIRE de la page, relue par l'onglet Production.
   Aucun calcul ici ; le résultat reste écrit par la tâche serveur existante. */
import calepinageApi from '../../../api/calepinageApi'
import { refusDepuisErreur } from './suiviSimulation'

const PREFIXE_REFUS = 'La simulation automatique n’a pas démarré : '
const table = new Map() // calepinageId -> { jobId } | { refus }

/** Lance la simulation (jamais forcée). 202 → job retenu ; 200 → rien ;
    refus → phrase du serveur retenue, AUCUN toast. N'échoue jamais. */
export function lancerSimulationAuto(calepinageId) {
  const id = String(calepinageId)
  table.delete(id)
  return Promise.resolve(calepinageApi.calepinages.simuler(calepinageId))
    .then((res) => {
      const jobId = res?.data?.job_id
      if (jobId) table.set(id, { jobId })
    })
    .catch((e) => {
      const refus = refusDepuisErreur(e)
      table.set(id, { refus: { ...refus, motif: PREFIXE_REFUS + refus.motif } })
    })
}

/** Ce que l'écran Production doit reprendre : `{jobId}` | `{refus}` | null.
    La lecture le consomme (une seule reprise). */
export function reprendreSimulationAuto(calepinageId) {
  const id = String(calepinageId)
  const v = table.get(id) || null
  table.delete(id)
  return v
}

export function viderSimulationsAuto() { table.clear() }
