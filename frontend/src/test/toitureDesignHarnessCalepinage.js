/* Double PARTAGÉ de `calepinageApi` pour les tests de l'écran ToitureDesign.

   Il SUIT la surface RÉELLE du module : chaque méthode devient un espion qui
   résout `{ data: null }`. Une liste écrite à la main laissait des groupes
   indéfinis (`calepinageApi.parametres`, lu par `PanneauAllees`) et faisait
   planter tout l'écran au lieu de montrer l'assertion. Se charge par
   `import '../../test/toitureDesignHarnessCalepinage'` avant l'écran. */
import { vi } from 'vitest'

vi.mock('../api/calepinageApi', async (importOriginal) => {
  const actual = await importOriginal()
  const espionner = (groupe) => Object.fromEntries(
    Object.entries(groupe).map(([cle, valeur]) => [
      cle,
      typeof valeur === 'function'
        ? vi.fn(() => Promise.resolve({ data: null }))
        : valeur,
    ]),
  )
  return {
    default: Object.fromEntries(
      Object.entries(actual.default).map(([nom, groupe]) => [
        nom,
        (groupe && typeof groupe === 'object') ? espionner(groupe) : groupe,
      ]),
    ),
  }
})
