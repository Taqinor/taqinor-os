import { useEffect, useState } from 'react'

/**
 * L153 — useDelayedLoading(isLoading, options)
 *
 * Chargement différé anti-scintillement : on n'affiche RIEN tant que l'attente
 * est imperceptible, un spinner discret si elle se prolonge, puis un squelette
 * si elle dure vraiment. Les trois états sont mutuellement exclusifs — on ne
 * montre JAMAIS un spinner ET un squelette en même temps.
 *
 * Frise temporelle (par défaut) :
 *   0 → 300 ms   : rien                (phase 'pending')   — évite le clignotement
 *   300 → 500 ms : spinner seul        (phase 'spinner')
 *   ≥ 500 ms     : squelette seul      (phase 'skeleton')  — le spinner s'éteint
 *
 * Un chargement qui se termine sous 300 ms ne fait donc jamais clignoter
 * l'écran : les timers sont annulés avant de déclencher quoi que ce soit.
 *
 * @param {boolean} isLoading            — l'opération est-elle en cours ?
 * @param {object}  [options]
 * @param {number}  [options.spinnerDelay=300] — délai avant le spinner (ms).
 * @param {number}  [options.skeletonDelay=500] — délai avant le squelette (ms).
 * @returns {{ phase: 'idle'|'pending'|'spinner'|'skeleton',
 *             showSpinner: boolean, showSkeleton: boolean }}
 */
export function useDelayedLoading(isLoading, options = {}) {
  const { spinnerDelay = 300, skeletonDelay = 500 } = options

  // `step` n'avance que via les timers : 'none' (rien), 'spinner', 'skeleton'.
  // Quand isLoading est faux on dérive 'idle' au rendu sans setState d'effet ;
  // tant qu'aucun seuil n'est franchi, on dérive 'pending'.
  const [step, setStep] = useState('none')

  // Réinitialise au changement de prop pendant le rendu (motif React officiel
  // « ajuster l'état en réponse à un changement de prop » : setState rendu, pas
  // d'effet ni de ref). Un nouveau cycle false → true repart donc de 'none'.
  const [prevLoading, setPrevLoading] = useState(isLoading)
  if (isLoading !== prevLoading) {
    setPrevLoading(isLoading)
    setStep('none')
  }

  useEffect(() => {
    if (!isLoading) return

    const spinnerTimer = setTimeout(() => setStep('spinner'), spinnerDelay)
    const skeletonTimer = setTimeout(() => setStep('skeleton'), skeletonDelay)

    // Annulation dès que le chargement s'arrête (ou que les seuils changent) :
    // un chargement rapide ne déclenche donc aucun affichage.
    return () => {
      clearTimeout(spinnerTimer)
      clearTimeout(skeletonTimer)
    }
  }, [isLoading, spinnerDelay, skeletonDelay])

  let phase
  if (!isLoading) phase = 'idle'
  else if (step === 'none') phase = 'pending'
  else phase = step

  return {
    phase,
    showSpinner: phase === 'spinner',
    showSkeleton: phase === 'skeleton',
  }
}

export default useDelayedLoading
