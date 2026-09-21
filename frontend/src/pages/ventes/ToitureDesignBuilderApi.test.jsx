import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
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

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisDesignContext: vi.fn(),
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    syncDevisLayout: vi.fn(),
    shareLinkDevis: vi.fn(),
    whatsappPreviewDevis: vi.fn(),
    reviserDevis: vi.fn(),
  },
}))
// Même double que `ToitureDesign.calepinage.test.jsx` : chaque méthode de
// `calepinageApi` devient un espion `{ data: null }` — sans quoi
// `calepinageApi.parametres` (lu par `PanneauAllees`) est `undefined` et
// fait planter tout l'écran.
vi.mock('../../api/calepinageApi', async (importOriginal) => {
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
vi.mock('../../api/crmApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getLeadPhotoToit: vi.fn(() => Promise.resolve({
        data: { visite_id: null, url: null, texture_calage: null },
      })),
    },
  }
})
vi.mock('../../lib/toast', () => ({ toastInfo: vi.fn() }))

const LAYOUT = { version: 2, zones: [{ id: 'z1' }] }
// CALX3 — le document d'entrée du moteur (`entreeMoteur()`), forme minimale
// exploitable par `RemplissageProuve`/`PanneauAllees` (elles ne font que le
// reposter tel quel à `calepinageApi.moteur.calculer`).
const DOCUMENT_MOTEUR = {
  schema_version: 2,
  repere: { lat: 33.5731, lng: -7.5898 },
  contour: [[33.5731, -7.5898], [33.5732, -7.5898], [33.5732, -7.5897]],
  surfaces: [], kits: [], parametres: {}, obstacles: [], zones: [], engagements: [],
}
const serializeLayout = vi.fn(() => LAYOUT)
const snapshot = vi.fn(() => null)
const setReferenceContourVisible = vi.fn()
const recommencerDepuisTraceClient = vi.fn(() => true)
const entreeMoteur = vi.fn(() => DOCUMENT_MOTEUR)
const appliquerPlan = vi.fn(() => true)
const raccourcis = {
  outilTrace: vi.fn(), outilObstacle: vi.fn(), outilZone: vi.fn(), outilMesure: vi.fn(),
  aimantation: vi.fn(), supprimer: vi.fn(), dupliquer: vi.fn(), pleinEcran: vi.fn(),
}
const calquesDisponibles = vi.fn(() => [])
const initRoofToolPro8 = vi.fn((options) => {
  options?.onApiReady?.({
    serializeLayout, snapshot, setReferenceContourVisible,
    recommencerDepuisTraceClient, entreeMoteur, appliquerPlan, raccourcis,
    calquesDisponibles,
  })
})
vi.mock('@roofbuilder', () => ({ initRoofToolPro8: (...a) => initRoofToolPro8(...a) }))

import calepinageApi from '../../api/calepinageApi'
import ToitureDesign from './ToitureDesign'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')

function rendreCalepinage(id) {
  return render(
    <MemoryRouter initialEntries={[`/calepinage/${id}`]}>
      <Routes>
        <Route path="/calepinage/:id"
          element={<ToitureDesign mode="calepinage" />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  delete window.__taqinorRoofBooted
  serializeLayout.mockReturnValue(LAYOUT)
  snapshot.mockReturnValue(null)
  entreeMoteur.mockReturnValue(DOCUMENT_MOTEUR)
  appliquerPlan.mockReturnValue(true)
  calquesDisponibles.mockReturnValue([])
  initRoofToolPro8.mockImplementation((options) => {
    options?.onApiReady?.({
      serializeLayout, snapshot, setReferenceContourVisible,
      recommencerDepuisTraceClient, entreeMoteur, appliquerPlan, raccourcis,
      calquesDisponibles,
    })
  })
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
