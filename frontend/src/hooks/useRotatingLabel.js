import { useEffect, useState } from 'react'

/**
 * VX132 — useRotatingLabel(labels, options)
 *
 * Chargement long CONSCIENT : au lieu d'un spinner muet pendant une attente
 * connue-longue (ex. génération du devis PDF premium — la latence la plus
 * longue de l'app), fait tourner 3-4 libellés honnêtes toutes les ~2.5 s
 * (« Mise en page des schémas… », « Calcul du système… »). AUCUNE fausse
 * barre de progression — juste un rappel que ça travaille, pas un mensonge
 * sur le temps restant.
 *
 * @param {string[]} labels        — libellés à faire tourner (≥ 1).
 * @param {object}   [options]
 * @param {boolean}  [options.active=true]     — l'opération est-elle en cours ?
 * @param {number}   [options.intervalMs=2500] — délai entre deux libellés (ms).
 * @returns {string} le libellé courant (revient au premier quand `active`
 *          redevient faux, pour repartir proprement à la prochaine attente).
 */
export function useRotatingLabel(labels, options = {}) {
  const { active = true, intervalMs = 2500 } = options
  const [index, setIndex] = useState(0)

  // Repart du premier libellé à chaque nouveau cycle d'attente (motif React
  // officiel « ajuster l'état en réponse à un changement de prop »).
  const [prevActive, setPrevActive] = useState(active)
  if (active !== prevActive) {
    setPrevActive(active)
    setIndex(0)
  }

  useEffect(() => {
    if (!active || !labels || labels.length <= 1) return undefined
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % labels.length)
    }, intervalMs)
    return () => clearInterval(timer)
  }, [active, labels, intervalMs])

  return labels?.[index] ?? labels?.[0] ?? ''
}

export default useRotatingLabel
