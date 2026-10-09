import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   APRF34 — export des mouvements au-delà du seuil NTPLT30 : le serveur répond
   202 (job de fond) → l'écran affiche « export en préparation » et ne
   télécharge rien ; sur 200 il télécharge le fichier comme avant. Faux
   serveur HTTP : le client axios est remplacé, le VRAI stockApi est utilisé.
   ========================================================================== */

vi.mock('../../lib/monitoring', () => ({
  captureException: () => {},
  initMonitoring: () => {},
}))

const post = vi.fn()
vi.mock('../../api/axios', () => ({
  default: {
    post: (...args) => post(...args),
    get: vi.fn(() => Promise.resolve({ status: 200, data: [] })),
    patch: vi.fn(), put: vi.fn(), delete: vi.fn(),
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
  },
}))

vi.mock('../../utils/downloadBlob', () => ({
  downloadBlob: vi.fn(),
  stampedFilename: (base, ext) => `${base}.${ext}`,
}))

vi.mock('../../features/stock/store/stockSlice', () => ({
  fetchMouvements: () => ({ type: 'stock/fetchMouvements/noop' }),
  fetchProduits: () => ({ type: 'stock/fetchProduits/noop' }),
  createMouvement: vi.fn((payload) => ({ type: 'stock/createMouvement/noop', payload })),
}))

import { downloadBlob } from '../../utils/downloadBlob'
import MouvementsPage from './MouvementsPage.jsx'
import { installJsdomPolyfills } from './__testutils__/jsdomPolyfills.js'

beforeEach(() => {
  vi.clearAllMocks()
  installJsdomPolyfills()
})

function renderPage() {
  const store = configureStore({
    reducer: {
      auth: (s = { role: 'admin', permissions: [] }) => s,
      stock: (s = { mouvements: [], produits: [], loading: false, error: null }) => s,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><MouvementsPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('APRF34 — export des mouvements : 202 = en préparation', () => {
  it('sur 202 affiche « export en préparation » et ne télécharge rien', async () => {
    post.mockResolvedValue({
      status: 202,
      data: new Blob([JSON.stringify({ job_id: 7, statut: 'queued' })],
        { type: 'application/json' }),
    })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Exporter Excel/ }))
    expect(await screen.findByText(/Export en préparation/)).toBeInTheDocument()
    expect(post).toHaveBeenCalledWith('/stock/mouvements/export-xlsx/', null,
      expect.objectContaining({ responseType: 'blob' }))
    expect(downloadBlob).not.toHaveBeenCalled()
  })

  it('sur 200 télécharge le fichier comme avant, sans message d’attente', async () => {
    const blob = new Blob(['xlsx'])
    post.mockResolvedValue({ status: 200, data: blob })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Exporter Excel/ }))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalledWith(blob, 'mouvements-stock.xlsx'))
    expect(screen.queryByText(/Export en préparation/)).toBeNull()
  })
})
