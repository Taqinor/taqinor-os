import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CALX8 — REMETTRE AU PANNEAU DE L'ATELIER L'API DU CONSTRUCTEUR, ET NON LA
   RÉFÉRENCE QUI LA CONTIENT.
   ----------------------------------------------------------------------------
   Constat : `ToitureDesign.jsx` crée `builderApi = useRef(null)` (O3) et
   passait la RÉF NUE à `AtelierPanneaux` (`builderApi={builderApi}`) — donc
   `builderApi?.entreeMoteur` valait TOUJOURS `undefined`, même une fois
   `onApiReady` posé (CALX3), puisque l'objet vit sur `.current` et que la ref
   elle-même ne change jamais d'identité. Ce fichier prouve : (1) le panneau
   reçoit désormais l'OBJET (`.current`), avec `entreeMoteur` dessus ; (2) le
   moteur reçoit un DOCUMENT (pas la fonction `entreeMoteur` elle-même,
   AtelierPanneaux.jsx l'appelant à son rendu) ; (3) « Remplir automatiquement »
   ne montre plus le refus « dessinez d'abord un pan de toit ».

   MÊME HARNAIS que `ToitureDesign.calepinage.test.jsx` (mode calepinage,
   design-context, double espion de `calepinageApi`) — voir ce fichier pour le
   détail de chaque garde ; celui-ci n'ajoute que les quatre clés CALX3 de
   l'API du constructeur (`entreeMoteur`, `appliquerPlan`, `raccourcis`,
   `calquesDisponibles`), absentes de ce harnais-là.
   ========================================================================== */

// CALX3 — le document d'entrée du moteur (`entreeMoteur()`), forme minimale
// exploitable par `RemplissageProuve`/`PanneauAllees` (elles ne font que le
// reposter tel quel à `calepinageApi.moteur.calculer`).
const DOCUMENT_MOTEUR = {
  schema_version: 2,
  repere: { lat: 33.5731, lng: -7.5898 },
  contour: [[33.5731, -7.5898], [33.5732, -7.5898], [33.5732, -7.5897]],
  surfaces: [], kits: [], parametres: {}, obstacles: [], zones: [], engagements: [],
}
const entreeMoteur = vi.fn(() => DOCUMENT_MOTEUR)
const appliquerPlan = vi.fn(() => true)
const raccourcis = {
  outilTrace: vi.fn(), outilObstacle: vi.fn(), outilZone: vi.fn(), outilMesure: vi.fn(),
  aimantation: vi.fn(), supprimer: vi.fn(), dupliquer: vi.fn(), pleinEcran: vi.fn(),
}
const calquesDisponibles = vi.fn(() => [])

import '../../test/toitureDesignHarnessCalepinage'
import {
  initRoofToolPro8, rendreCalepinage, reinitialiserBoot,
} from '../../test/toitureDesignHarness'
import calepinageApi from '../../api/calepinageApi'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')

beforeEach(() => {
  vi.clearAllMocks()
  entreeMoteur.mockReturnValue(DOCUMENT_MOTEUR)
  appliquerPlan.mockReturnValue(true)
  calquesDisponibles.mockReturnValue([])
  reinitialiserBoot({ entreeMoteur, appliquerPlan, raccourcis, calquesDisponibles })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ToitureDesign — CALX8 : builderApi.current voyage jusqu’au panneau', () => {
  it('« Remplir automatiquement » poste le DOCUMENT du moteur, plus le refus « dessinez d’abord »', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))

    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())

    const bouton = await screen.findByTestId('cal-remplissage-lancer')
    await userEvent.click(bouton)

    // AVANT CALX8 : `entree` valait la ref `useRef` (jamais l'objet posé par
    // `onApiReady`), donc `entreeMoteur` était `undefined` et le moteur
    // n'était JAMAIS appelé — le clic échouait en silence sur le refus. La
    // preuve qui compte : le moteur reçoit maintenant le DOCUMENT exact rendu
    // par `entreeMoteur()`, jamais la fonction elle-même.
    await waitFor(() => expect(calepinageApi.moteur.calculer)
      .toHaveBeenCalledWith(DOCUMENT_MOTEUR))
    expect(screen.queryByTestId('cal-remplissage-refus')).toBeNull()
    expect(screen.queryByText(/dessinez d.abord un pan de toit/i)).toBeNull()
  })

  it('le rail de raccourcis (CALX3) reçoit les huit actions, pas un objet vide', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))

    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    await screen.findByTestId('cal-atelier-panneaux')

    // `RaccourcisAtelier` lit `builderApi?.raccourcis ?? {}` : avec la ref
    // nue, c'était toujours `{}`, donc AUCUNE frappe ne déclenchait jamais de
    // geste. La preuve qui compte : la touche « O » (`outilObstacle`) atteint
    // maintenant le gestionnaire posé par `onApiReady`.
    await userEvent.keyboard('o')
    await waitFor(() => expect(raccourcis.outilObstacle).toHaveBeenCalledTimes(1))
  })
})
