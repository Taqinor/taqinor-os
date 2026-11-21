/* ACAL488 — l'onglet « Détection du toit » : le bouton n'existe que si le
   serveur dit la détection disponible ; la PROPOSITION n'est posée que sur
   « Utiliser ce contour » ; un 503 ou une annulation laisse le tracé intact.

   Charges servies : contrat `calepinage_detection_toit.json` (ACAL391), jamais
   écrites à la main. Mutant visé : afficher le bouton quand `disponible` est
   faux ⇒ échec. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { detectionToitDisponible: vi.fn(), detectionToit: vi.fn() } },
}))
vi.mock('../../../hooks/useHasPermission', () => ({ useHasPermission: () => true }))

import calepinageApi from '../../../api/calepinageApi'
import PanneauDetectionToit from './PanneauDetectionToit'

const contrat = (cle) => exempleContrat('calepinage', 'calepinage_detection_toit', cle)
const api = calepinageApi.calepinages

const disponible = (cle = 'exemple_disponibilite') => api.detectionToitDisponible.mockResolvedValue({ data: contrat(cle) })

const envoyerImage = async (builderApi) => {
  render(<PanneauDetectionToit calepinageId={7} builderApi={builderApi} />)
  await screen.findByTestId('cal-detection-panneau')
  const emprise = contrat('exemple_corps').emprise
  for (const [coin, valeur] of Object.entries(emprise)) {
    fireEvent.change(screen.getByLabelText(`${coin} (°)`), { target: { value: String(valeur) } })
  }
  const image = new File(['x'], 'toit.png', { type: 'image/png' })
  fireEvent.change(screen.getByTestId('cal-detection-fichier'), { target: { files: [image] } })
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('PanneauDetectionToit (ACAL488)', () => {
  it('détection indisponible : une phrase, AUCUN bouton', async () => {
    disponible('exemple_disponibilite_indisponible')
    render(<PanneauDetectionToit calepinageId={7} builderApi={{}} />)
    expect(await screen.findByTestId('cal-detection-indisponible')).toHaveTextContent('tracez le toit à la main')
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('sans origine carte (cas par défaut) : seul « Choisir une photo ou un plan » ; la proposition n’est posée que sur « Utiliser ce contour »', async () => {
    api.detectionToitDisponible.mockResolvedValue({ data: { ...contrat('exemple_disponibilite'), origines_acceptees: ['importee'] } })
    api.detectionToit.mockResolvedValue({ data: contrat('exemple') })
    const ajouterPanDepuisContour = vi.fn(() => ({ ok: true, id: 'pan-2' }))
    await envoyerImage({ ajouterPanDepuisContour, capturerCarte: vi.fn() })
    expect(screen.queryByTestId('cal-detection-carte')).toBeNull()
    await screen.findByTestId('cal-detection-proposition')
    const [id, corps, config] = api.detectionToit.mock.calls[0]
    expect(id).toBe(7)
    expect(corps.get('origine')).toBe('importee')
    expect(JSON.parse(corps.get('emprise'))).toEqual(contrat('exemple_corps').emprise)
    expect(config.signal).toBeInstanceOf(AbortSignal)
    expect(ajouterPanDepuisContour).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId('cal-detection-utiliser'))
    expect(ajouterPanDepuisContour).toHaveBeenCalledTimes(contrat('exemple').propositions.pans.length)
    expect(ajouterPanDepuisContour.mock.calls[0][0]).toEqual(contrat('exemple').propositions.pans[0].contour_lnglat)
  })

  it('un refus de croisement est affiché avec son motif', async () => {
    disponible()
    api.detectionToit.mockResolvedValue({ data: contrat('exemple') })
    await envoyerImage({ ajouterPanDepuisContour: () => ({ ok: false, motif: 'Le contour se croise.' }) })
    fireEvent.click(await screen.findByTestId('cal-detection-utiliser'))
    expect(screen.getAllByTestId('cal-detection-refus')[0]).toHaveTextContent('Le contour se croise.')
  })

  it('un 503 affiche le message du serveur et ne pose rien', async () => {
    disponible()
    api.detectionToit.mockRejectedValue({ response: { status: 503, data: contrat('exemple_indisponible_503') } })
    const ajouterPanDepuisContour = vi.fn()
    await envoyerImage({ ajouterPanDepuisContour })
    expect(await screen.findByTestId('cal-detection-message')).toHaveTextContent(contrat('exemple_indisponible_503').detail)
    expect(screen.queryByTestId('cal-detection-proposition')).toBeNull()
    expect(ajouterPanDepuisContour).not.toHaveBeenCalled()
  })

  it('« Annuler » coupe l’appel (AbortController) et laisse le tracé intact', async () => {
    disponible()
    api.detectionToit.mockImplementation((_id, _corps, { signal }) => new Promise((_ok, ko) => {
      signal.addEventListener('abort', () => ko({ code: 'ERR_CANCELED' }))
    }))
    await envoyerImage({ ajouterPanDepuisContour: vi.fn() })
    fireEvent.click(await screen.findByTestId('cal-detection-annuler'))
    await waitFor(() => expect(screen.getByTestId('cal-detection-message')).toHaveTextContent('annulée'))
    expect(screen.queryByTestId('cal-detection-annuler')).toBeNull()
  })

  it('origine carte acceptée mais capture impossible : message nommé, rien envoyé', async () => {
    disponible()
    render(<PanneauDetectionToit calepinageId={7} builderApi={{ capturerCarte: () => Promise.resolve(null) }} />)
    fireEvent.click(await screen.findByTestId('cal-detection-carte'))
    expect(await screen.findByTestId('cal-detection-message')).toHaveTextContent('La capture de la carte n’est pas possible ici')
    expect(api.detectionToit).not.toHaveBeenCalled()
  })
})
