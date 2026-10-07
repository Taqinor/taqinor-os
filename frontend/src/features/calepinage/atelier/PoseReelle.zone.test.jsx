/* ACAL268 — l'écran Pose réelle est indexé par `zone_id`.

   Deux pans de même libellé (« Pan A ») sont deux lignes INDÉPENDANTES (clé
   React et état des saisies par identifiant stable du pan, plus par
   `ligne.pan`), et une ligne ORPHELINE (pan supprimé du document) est montrée
   hors totaux avec « Retirer » (DELETE pose-reelle/<zone_id>/).

   Réponses au format COMMITTÉ `calepinage_asbuilt_ecarts.json` : l'exemple du
   contrat, dont deux lignes reçoivent le même libellé. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      poseReelle: vi.fn(),
      enregistrerPoseReelle: vi.fn(),
      creerVersionPoseReelle: vi.fn(),
      supprimerPoseReelle: vi.fn(),
    },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import PoseReelle from './PoseReelle'

/** L'exemple du contrat, où les pans z1 et z2 portent le libellé « Pan A ». */
const avecLibellesDupliques = () => {
  const reponse = reponseContrat('calepinage', 'calepinage_asbuilt_ecarts', 'exemple')
  const donnees = JSON.parse(JSON.stringify(reponse.data))
  donnees.lignes = donnees.lignes.map((ligne) => (
    ['z1', 'z2'].includes(ligne.zone_id)
      ? { ...ligne, pan: 'Pan A', libelle: 'Pan A' }
      : ligne
  ))
  return { data: donnees }
}

const rendre = () => render(
  <MemoryRouter><PoseReelle calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  calepinageApi.calepinages.poseReelle.mockResolvedValue(avecLibellesDupliques())
  calepinageApi.calepinages.enregistrerPoseReelle.mockResolvedValue(avecLibellesDupliques())
  calepinageApi.calepinages.supprimerPoseReelle.mockResolvedValue({ status: 204 })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PoseReelle — indexée par zone_id (ACAL268)', () => {
  it('libellés dupliqués indépendants et orphelin retirable', async () => {
    rendre()
    await screen.findByTestId('cal-pose-grille')

    // Deux « Pan A » : deux lignes, deux saisies indépendantes.
    expect(screen.getByTestId('cal-pose-ligne-z1')).toHaveTextContent('Pan A')
    expect(screen.getByTestId('cal-pose-ligne-z2')).toHaveTextContent('Pan A')
    fireEvent.change(screen.getByTestId('cal-pose-modules-z1'), { target: { value: '7' } })
    expect(screen.getByTestId('cal-pose-modules-z1')).toHaveValue(7)
    expect(screen.getByTestId('cal-pose-modules-z2')).toHaveValue(3)

    fireEvent.click(screen.getByTestId('cal-pose-enregistrer-z1'))
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerPoseReelle).toHaveBeenCalled())
    const [, corps] = calepinageApi.calepinages.enregistrerPoseReelle.mock.calls[0]
    expect(corps.pan).toBe('z1')
    expect(corps.modules_poses).toBe('7')

    // L'orphelin (z9) est signalé hors totaux et se RETIRE par DELETE.
    expect(screen.getByTestId('cal-pose-orphelin-z9')).toHaveTextContent('hors totaux')
    expect(screen.queryByTestId('cal-pose-enregistrer-z9')).toBeNull()
    fireEvent.click(screen.getByTestId('cal-pose-retirer-z9'))
    await waitFor(() => expect(calepinageApi.calepinages.supprimerPoseReelle)
      .toHaveBeenCalledWith(1, 'z9'))
    await waitFor(() => expect(calepinageApi.calepinages.poseReelle).toHaveBeenCalledTimes(2))
  })
})
