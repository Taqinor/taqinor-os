import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* Fondateur 18/08 — entrée standalone du layouteur 3D (`/ventes/conception-3d`,
   ouverte depuis le nav Ventes, SANS contexte de devis/lead). QJR636 — la
   liste vient du serveur (`?concevable=1`, toutes les pages : brouillon ET
   envoyé), via le MÊME chooser `ChoisirDevisPourDesign` — jamais dupliqué. */

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
  it('demande ?concevable=1 et liste brouillon ET envoyé, sans phrase « Ce lead »', async () => {
    ventesApi.getDevis.mockResolvedValue({
      data: {
        count: 2,
        results: [
          { id: 412, reference: 'DEV-2026-412', statut: 'brouillon' },
          { id: 413, reference: 'DEV-2026-413', statut: 'envoye' },
        ],
      },
    })

    rendre()

    expect(await screen.findByTestId('conception-3d-page')).toBeTruthy()
    await waitFor(() => expect(ventesApi.getDevis)
      .toHaveBeenCalledWith(expect.objectContaining({ concevable: 1, page: 1 })))

    const liste = await screen.findByTestId('pv22-choix-devis')
    expect(liste).toHaveTextContent('DEV-2026-412')
    expect(liste).toHaveTextContent('DEV-2026-413')
    expect(screen.queryByText(/Ce lead/)).toBeNull()

    fireEvent.click(screen.getByText('DEV-2026-412'))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/412/design')
  })

  it('aucun devis concevable : état vide avec un lien vers le générateur de devis', async () => {
    ventesApi.getDevis.mockResolvedValue({ data: { count: 0, results: [] } })

    rendre()

    await waitFor(() => expect(ventesApi.getDevis).toHaveBeenCalled())
    expect(await screen.findByText('Aucun devis à calepiner')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Créer un devis' }))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/nouveau')
  })
})
