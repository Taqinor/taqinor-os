import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CAL37 — l'emplacement des panneaux de l'atelier en mode calepinage.

   Ce que ce fichier prouve :
   1. le panneau affiche la CIBLE servie par le serveur, et « non renseignée »
      quand elle vaut `null` — jamais une puissance inventée ;
   2. une conception en LECTURE SEULE ne propose aucune écriture ;
   3. CALX27 — le bandeau de lecture seule porte enfin une SORTIE
      (« Déverrouiller », action `deverrouiller/` de CAL207 qui n'avait aucun
      consommateur) : elle n'apparaît qu'en lecture seule ET avec
      `calepinage_gerer`, elle nomme sa conséquence avant d'agir, et après elle
      les gestes d'écriture reviennent sans rechargement complet.

   SOLMVP15 — les deux essais du bouton « Reprendre le contour de l'affaire »
   (CAL242, sens CAL240) sont partis avec lui : son endpoint n'existe plus,
   l'app d'appels d'offres sortant du produit.
   ========================================================================== */

/* CALX27 — le droit est PILOTÉ par le test : `AtelierPanneaux` lit désormais
   `calepinage_gerer` (le code EXACT de la garde serveur). Sans ce double, le
   hook irait chercher le store redux, qu'aucun de ces rendus ne monte. */
const mocks = vi.hoisted(() => ({ hasPermission: vi.fn(() => false) }))
vi.mock('../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => mocks.hasPermission(code),
}))

vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      get: vi.fn(),
      genererDevis: vi.fn(),
      syncDevis: vi.fn(),
      // CALX27 — l'action de levée du verrou (CAL207, `views/verrou.py`).
      deverrouiller: vi.fn(),
    },
    // CAL70 — PanneauAllees (monté ici, emplacement CAL37) lit les réglages
    // société et interroge le moteur ; sans double par défaut, la promesse
    // non résolue laisse `.get`/`.calculer` undefined et casse CE fichier.
    parametres: { get: vi.fn().mockResolvedValue({ data: { degagements: {} } }) },
    moteur: { calculer: vi.fn() },
  },
}))
vi.mock('../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))

import calepinageApi from '../../api/calepinageApi'
import AtelierPanneaux from './AtelierPanneaux'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CTX_VIDE = exempleContrat('calepinage', 'calepinage_design_context',
  'exemple_vide')
const DETAIL = exempleContrat('calepinage', 'calepinage_detail')

const rendre = (props = {}) => render(
  <MemoryRouter>
    <AtelierPanneaux calepinageId={CTX.calepinage.id} contexte={CTX} {...props} />
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  calepinageApi.calepinages.get.mockResolvedValue({ data: DETAIL })
  // Par défaut : SANS le droit de gérer — l'affordance d'écriture est l'exception.
  mocks.hasPermission.mockReturnValue(false)
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AtelierPanneaux (CAL37)', () => {
  it('affiche la cible SERVIE et le lien contextuel vers le comparatif', async () => {
    rendre()

    expect(screen.getByTestId('cal-cible-panneaux'))
      .toHaveTextContent(String(CTX.cible.panneaux))
    expect(screen.getByTestId('cal-lien-variantes'))
      .toHaveAttribute('href', `/calepinage/${CTX.calepinage.id}/variantes`)
  })

  it('cible nulle : « non renseignée », et l’écran le DIT', async () => {
    rendre({ contexte: CTX_VIDE, calepinageId: CTX_VIDE.calepinage.id })

    expect(screen.getByTestId('cal-cible-panneaux'))
      .toHaveTextContent('non renseignée')
    expect(screen.getByRole('status'))
      .toHaveTextContent('Aucune cible de puissance connue')
  })

  it('lecture seule : aucune écriture proposée', async () => {
    rendre({ lectureSeule: true })

    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-bouton-devis')).toBeNull()
    // Le panneau LUI-MÊME reste : consulter une conception figée est le but.
    expect(screen.getByTestId('cal-lien-variantes')).toBeTruthy()
  })
})

/* ============================================================================
   CALX27 — LE DÉVERROUILLAGE, ET SES DEUX GARDES.
   ========================================================================== */
describe('CALX27 — deverrouiller une conception figee', () => {
  it('le bandeau et son bouton n’existent QUE en lecture seule', async () => {
    mocks.hasPermission.mockReturnValue(true)
    rendre()

    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-bandeau-lecture-seule')).toBeNull()
    expect(screen.queryByTestId('cal-deverrouiller')).toBeNull()
  })

  it('sans `calepinage_gerer`, le bandeau reste mais n’offre AUCUNE sortie', async () => {
    mocks.hasPermission.mockReturnValue(false)
    rendre({ lectureSeule: true })

    expect(screen.getByTestId('cal-bandeau-lecture-seule')).toBeTruthy()
    expect(screen.queryByTestId('cal-deverrouiller')).toBeNull()
    expect(mocks.hasPermission).toHaveBeenCalledWith('calepinage_gerer')
  })

  it('la confirmation NOMME la conséquence, et rien n’est appelé avant elle', async () => {
    mocks.hasPermission.mockReturnValue(true)
    rendre({ lectureSeule: true })

    await userEvent.click(screen.getByTestId('cal-deverrouiller'))

    expect(screen.getByTestId('cal-deverrouiller-confirmation'))
      .toHaveTextContent('le devis lié')
    expect(screen.getByTestId('cal-deverrouiller-confirmation'))
      .toHaveTextContent('rejouer')
    expect(calepinageApi.calepinages.deverrouiller).not.toHaveBeenCalled()

    // Annuler ne déverrouille rien : l'atelier reste figé.
    await userEvent.click(screen.getByTestId('cal-deverrouiller-annuler'))
    expect(screen.queryByTestId('cal-deverrouiller-confirmation')).toBeNull()
    expect(calepinageApi.calepinages.deverrouiller).not.toHaveBeenCalled()
  })

  it('après déverrouillage, les gestes d’écriture reviennent SANS rechargement', async () => {
    mocks.hasPermission.mockReturnValue(true)
    calepinageApi.calepinages.deverrouiller.mockResolvedValue({
      data: { calepinage: CTX.calepinage.id, verrouille: false, deverrouille: true },
    })
    rendre({ lectureSeule: true })

    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-bouton-devis')).toBeNull()

    await userEvent.click(screen.getByTestId('cal-deverrouiller'))
    await userEvent.click(screen.getByTestId('cal-deverrouiller-confirmer'))

    expect(calepinageApi.calepinages.deverrouiller)
      .toHaveBeenCalledWith(CTX.calepinage.id)
    // Le bandeau s'efface et la sortie devis REVIENT : aucun rechargement de page.
    await waitFor(() => expect(screen.queryByTestId('cal-bandeau-lecture-seule')).toBeNull())
    expect(await screen.findByTestId('cal-bouton-devis')).toBeTruthy()
  })

  it('un refus serveur est rendu MOT POUR MOT, et l’atelier reste figé', async () => {
    mocks.hasPermission.mockReturnValue(true)
    calepinageApi.calepinages.deverrouiller.mockRejectedValue({
      response: { status: 403, data: { detail: 'Droit insuffisant sur ce calepinage.' } },
    })
    rendre({ lectureSeule: true })

    await userEvent.click(screen.getByTestId('cal-deverrouiller'))
    await userEvent.click(screen.getByTestId('cal-deverrouiller-confirmer'))

    expect(await screen.findByTestId('cal-deverrouiller-refus'))
      .toHaveTextContent('Droit insuffisant sur ce calepinage.')
    expect(screen.getByTestId('cal-bandeau-lecture-seule')).toBeTruthy()
    expect(screen.queryByTestId('cal-bouton-devis')).toBeNull()
  })
})
