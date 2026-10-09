import { beforeEach, afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

import { installerShimsJsdom, preparerEcranFige } from './shimsEcran'

/* Cycle de vie PARTAGÉ des tests qui montent l'écran générateur de devis.

   Chaque test recopiait ses `beforeEach` / `afterEach` (horloge figée, stockage
   vidé, shims jsdom, nettoyage du DOM) : ACAL345
   (`scripts/check_duplicats_litteraux.py`) refuse tout bloc de >= 6 lignes
   significatives copié dans deux fichiers. Un seul appel, en tête du fichier :

     cycleEcran({ date: DATE_FIGEE })

   - `date`            : fige `Date` (golden) et la libère ensuite ;
   - `pointerCapture`  : shims `hasPointerCapture` / `releasePointerCapture` ;
   - `confirmer`       : `window.confirm` répond « oui » ;
   - `restaurer`       : `vi.restoreAllMocks()` après chaque test. */
export function cycleEcran({
  date = null, pointerCapture = false, confirmer = false, restaurer = false,
} = {}) {
  beforeEach(() => {
    if (date) {
      preparerEcranFige(date, { pointerCapture })
    } else {
      try { window.localStorage.clear() } catch { /* stockage indisponible */ }
      installerShimsJsdom({ pointerCapture })
    }
    if (confirmer) vi.spyOn(window, 'confirm').mockReturnValue(true)
  })
  afterEach(() => {
    cleanup()
    if (restaurer || confirmer) vi.restoreAllMocks()
    if (date) vi.useRealTimers()
  })
}
