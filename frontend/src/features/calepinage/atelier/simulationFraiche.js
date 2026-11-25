import { useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'

/* T4-X2-006 — LA production SIMULÉE de la pose, quand elle est fraîche, pour la vue Expert de l'atelier : la ligne de
   résumé (`ResumeAtelier`) et la case « Production » du Total (relayée au constructeur par `chiffrageAvecSimulation`).
   Une seule règle de fraîcheur — celle que `ResumeAtelier` appliquait déjà : `simule` vrai, `simulation_perimee` faux,
   un P50 servi. La simulation automatique part APRÈS l'enregistrement : tant que le serveur la dit en cours
   (`simulation_automatique.en_cours`), la lecture est refaite, un nombre borné de fois. Aucun calcul ici. */

export const RELECTURES_SIMULATION = 12
export const INTERVALLE_SIMULATION_MS = 5000

const nombre = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

/** Le P50 servi d'une simulation FRAÎCHE, sinon `null`. */
export function p50Frais(resultat) {
  return resultat?.simule === true && resultat?.simulation_perimee === false
    ? nombre(resultat?.production?.total?.p50_kwh) : null
}

/** Le bloc `chiffrage` servi, complété de la simulation fraîche de la pose (`simulation: {p50_kwh, a_jour: true}`,
    lue par `affichageErp.ts::texteTotalProduction`) ; sans simulation fraîche : le bloc tel quel. */
export function chiffrageAvecSimulation(chiffrage, p50) {
  if (p50 == null) return chiffrage ?? null
  return { ...(chiffrage ?? {}), simulation: { p50_kwh: p50, a_jour: true } }
}

/** Le P50 frais du calepinage, relu à chaque `rechargerLe` (enregistrement) et tant que la simulation tourne. */
export function useSimulationFraiche(calepinageId, rechargerLe) {
  const [etat, setEtat] = useState({ p50: null, cle: null })
  // Le compteur de relectures appartient à UNE source (calepinage + enregistrement) : une autre source repart de zéro.
  const source = `${calepinageId ?? ''}|${rechargerLe ?? ''}`
  const [relectures, setRelectures] = useState({ source, n: 0 })
  const relecture = relectures.source === source ? relectures.n : 0
  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    let minuteur = null
    Promise.resolve().then(() => calepinageApi.calepinages.resultat(calepinageId)).then((rep) => {
      if (annule) return
      const d = rep?.data
      setEtat({ p50: p50Frais(d), cle: calepinageId })
      if (p50Frais(d) == null && d?.simulation_automatique?.en_cours === true && relecture < RELECTURES_SIMULATION) {
        minuteur = window.setTimeout(() => setRelectures({ source, n: relecture + 1 }), INTERVALLE_SIMULATION_MS)
      }
    }).catch(() => { if (!annule) setEtat({ p50: null, cle: calepinageId }) })
    return () => { annule = true; if (minuteur != null) window.clearTimeout(minuteur) }
  }, [calepinageId, rechargerLe, relecture, source])
  return etat.cle === calepinageId ? etat.p50 : null
}
