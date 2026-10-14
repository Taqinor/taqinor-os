import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { espions } from '../../test/fixtures/calepinageApiMock'
import { MESSAGE_ILLISIBLE } from './useDocumentCalepinage'

/* ENF15 — l'onglet « Horizon lointain » (CALX1) est MONTÉ : lecture du document,
   un profil incomplet n'est pas enregistrable, un document illisible le dit. */

vi.mock('../../api/calepinageApi', async () => (await import('../../test/fixtures/calepinageApiMock')).apiDocument({ horizon: true }))

const { default: HorizonPanel } = await import('./HorizonPanel')

const rendre = () => render(<MemoryRouter><HorizonPanel calepinageId={7} /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('HorizonPanel — onglet monté', () => {
  it('3 points relevés : listés, mais « Enregistrer » refusé (tour incomplet)', async () => {
    const points = [0, 120, 240].map((azimuthDeg) => ({ azimuthDeg, heightDeg: 10 }))
    espions.layout.mockResolvedValue({ data: { roof_layout: { pin: { lat: 33.5, lng: -7.6 }, horizonProfile: { source: 'saisie', points } } } })
    rendre()
    const liste = await screen.findByTestId('cal-horizon-points')
    await vi.waitFor(() => expect(liste.querySelectorAll('li')).toHaveLength(3))
    expect(screen.getByRole('button', { name: 'Enregistrer le profil' })).toBeDisabled()
    expect(screen.getByText(/au moins 8 directions \(3 relevée/)).toBeInTheDocument()
  })

  it('ajouter un point à la saisie le met dans la liste', async () => {
    espions.layout.mockResolvedValue({ data: { roof_layout: {} } })
    rendre()
    await screen.findByTestId('cal-horizon')
    fireEvent.change(screen.getByTestId('cal-horizon-champ-azimut').querySelector('input'), { target: { value: '90' } })
    fireEvent.change(screen.getByTestId('cal-horizon-champ-hauteur').querySelector('input'), { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter le point' }))
    expect(screen.getByTestId('cal-horizon-hauteur-max')).toHaveTextContent('12.0°')
  })

  it('lecture du document en échec : message d’illisibilité, rien d’enregistrable', async () => {
    espions.layout.mockRejectedValue(new Error('500'))
    rendre()
    expect(await screen.findByText(MESSAGE_ILLISIBLE)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enregistrer le profil' })).toBeDisabled()
  })
})
