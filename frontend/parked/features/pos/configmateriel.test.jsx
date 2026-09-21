import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XPOS18 — smoke de l'écran de configuration matériel POS (API mockée). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('../../api/posApi', () => ({
  default: {
    getConfigMateriel: () => Promise.resolve({
      data: { results: [{ id: 3, imprimante_ip: '192.168.1.50', imprimante_port: 9100, imprimante_active: true }] },
    }),
    createConfigMateriel: () => Promise.resolve({ data: { id: 3 } }),
    updateConfigMateriel: () => Promise.resolve({ data: {} }),
  },
}))

import ConfigMaterielScreen from './ConfigMaterielScreen'

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('rendu smoke de ConfigMaterielScreen', () => {
  it('charge la config existante dans le formulaire', async () => {
    withProviders(<ConfigMaterielScreen />)
    await waitFor(() => expect(screen.getByLabelText(/Adresse IP/)).toBeInTheDocument())
    expect(screen.getByLabelText(/Adresse IP/)).toHaveValue('192.168.1.50')
    expect(screen.getByRole('button', { name: /Enregistrer/ })).toBeInTheDocument()
  })
})
