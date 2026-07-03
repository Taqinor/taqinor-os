import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

// QG12 — page autonome plein écran : mocke le GET du devis par id.
vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getDevisById: vi.fn(() => Promise.resolve({
        data: {
          id: 55, reference: 'DEV-3D', roof_layout: {
            version: 1, zones: [{
              id: 'z1', label: 'Toit', roofType: 'flat', pitchDeg: 15,
              facingAzimuthDeg: 180, neededPanels: 8,
              vertices: [[-7.60, 33.50], [-7.599, 33.50], [-7.599, 33.501], [-7.60, 33.501]],
              obstacles: [],
            }],
          },
        },
      })),
    },
  }
})

import RoofViewerPage from './RoofViewerPage'
import ventesApi from '../../api/ventesApi'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderAt(id = '55') {
  return render(
    <MemoryRouter initialEntries={[`/ventes/devis/${id}/3d`]}>
      <Routes>
        <Route path="/ventes/devis/:id/3d" element={<RoofViewerPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RoofViewerPage — QG12 : route /ventes/devis/:id/3d', () => {
  it('charge le devis par id et monte RoofViewer plein écran', async () => {
    renderAt('55')
    await waitFor(() => {
      expect(ventesApi.getDevisById).toHaveBeenCalledWith('55')
    })
    // Le titre référence le devis et le plan (RoofViewer) est monté.
    expect(await screen.findByText(/Design 3D — DEV-3D/)).toBeTruthy()
    expect(screen.getByTestId('roof-viewer-page')).toBeTruthy()
    await waitFor(() => {
      expect(screen.getByTestId('roofviewer-svg')).toBeTruthy()
    })
  })

  it('affiche un état d\'erreur si le devis est introuvable', async () => {
    ventesApi.getDevisById.mockImplementationOnce(() => Promise.reject(new Error('404')))
    renderAt('999')
    expect(await screen.findByText(/Design 3D indisponible/)).toBeTruthy()
  })
})
