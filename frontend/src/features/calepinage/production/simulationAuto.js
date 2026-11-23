/* ACAL398 / ACAL1987 — la simulation d'une pose COMPLÈTE part TOUTE SEULE, mais un seul déclencheur la lance : le
   SERVEUR (`services/layout.py::simuler_apres_enregistrement`, à la validation de l'enregistrement). Le navigateur ne
   poste plus `simuler/` : après un enregistrement il LIT l'état servi (`simulation_automatique` de `GET resultat/` :
   `en_cours`, `job_id`, `manquants`) et retient le job du serveur, s'il y en a un, dans une table EN MÉMOIRE de la
   page, relue par l'onglet Production (« Simulation en cours… » puis le résultat). Pose incomplète : aucun job, rien
   n'est retenu — l'écran Résultats dit ce qui manque avec les phrases servies. Aucun calcul ici. */
import calepinageApi from '../../../api/calepinageApi'

const table = new Map() // calepinageId -> { jobId }

/** Lit l'état servi après un enregistrement. `en_cours` + `job_id` → job retenu ; sinon rien. N'échoue jamais. */
export function suivreSimulationDuServeur(calepinageId) {
  const id = String(calepinageId)
  table.delete(id)
  return Promise.resolve(calepinageApi.calepinages.resultat(calepinageId))
    .then((res) => {
      const auto = res?.data?.simulation_automatique
      if (auto?.en_cours === true && auto.job_id) table.set(id, { jobId: auto.job_id })
    })
    .catch(() => null) // lecture refusée ou réseau coupé : l'onglet Production relira de lui-même
}

/** Ce que l'écran Production doit reprendre : `{jobId}` | null. La lecture le consomme (une seule reprise). */
export function reprendreSimulationAuto(calepinageId) {
  const id = String(calepinageId)
  const v = table.get(id) || null
  table.delete(id)
  return v
}

export function viderSimulationsAuto() { table.clear() }
