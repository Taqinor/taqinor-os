import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* Fondateur 18/08 — entrée standalone du layouteur 3D (`/ventes/conception-3d`,
   ouverte depuis le nav Ventes, SANS contexte de devis/lead). Mêmes règles que
   PV22 (le geste lancé depuis une fiche lead) : seuls les devis BROUILLON sont
   proposés, via le MÊME chooser `ChoisirDevisPourDesign` — jamais dupliqué. */

vi.mock('../../api/ventesApi', () => ({
  default: { getDevis: vi.fn() },
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import ventesApi from '../../api/ventesApi'
import Conception3DPage from './Conception3DPage'

function mockMatchMedia(mobile) {
  window.matchMedia = (query) => ({
    matches: mobile, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}

function rendre() {
  return render(
    <MemoryRouter initialEntries={['/ventes/conception-3d']}>
      <Routes>
        <Route path="/ventes/conception-3d" element={<Conception3DPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => { mockMatchMedia(false) })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Conception3DPage — /ventes/conception-3d (fondateur 18/08)', () => {
  it('rend la route et propose les devis BROUILLON via ChoisirDevisPourDesign', async () => {
    ventesApi.getDevis.mockResolvedValue({
      data: [
        { id: 412, reference: 'DEV-2026-412', statut: 'brouillon' },
        // Un devis déjà accepté n'est jamais calepinable depuis cet écran.
        { id: 300, reference: 'DEV-2026-300', statut: 'accepte' },
      ],
    })

    rendre()

    expect(await screen.findByTestId('conception-3d-page')).toBeTruthy()
    expect(ventesApi.getDevis).toHaveBeenCalled()

    const liste = await screen.findByTestId('pv22-choix-devis')
    expect(liste).toHaveTextContent('DEV-2026-412')
    expect(liste).not.toHaveTextContent('DEV-2026-300')

    fireEvent.click(screen.getByText('DEV-2026-412'))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/412/design')
  })

  it('aucun brouillon : état vide avec un lien vers le générateur de devis', async () => {
    ventesApi.getDevis.mockResolvedValue({ data: [] })

    rendre()

    await waitFor(() => expect(ventesApi.getDevis).toHaveBeenCalled())
    expect(await screen.findByText('Aucun devis brouillon')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Créer un devis' }))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/nouveau')
  })
})
