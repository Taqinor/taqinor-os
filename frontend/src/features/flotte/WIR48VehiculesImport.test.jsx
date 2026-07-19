import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR48 — bouton « Importer » de VehiculesList ouvre le modal d'import (cible
   `vehicules`). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../api/flotteApi', () => ({
  default: {
    vehicules: { list: () => Promise.resolve({ data: [] }) },
    engins: { list: () => Promise.resolve({ data: [] }) },
    modelesVehicule: { list: () => Promise.resolve({ data: [] }) },
  },
}))
const getSavedMappings = vi.fn(() => Promise.resolve({ data: [] }))
vi.mock('../../api/importApi', () => ({
  default: { getSavedMappings: (...a) => getSavedMappings(...a), dryRun: vi.fn(), commit: vi.fn() },
  downloadBlob: vi.fn(),
  filenameFromResponse: vi.fn(),
}))

import VehiculesList from './VehiculesList'

beforeEach(() => { vi.clearAllMocks() })

describe('WIR48 — import véhicules depuis VehiculesList', () => {
  it('le bouton « Importer » ouvre le modal d\'import véhicules', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter><ThemeProvider><VehiculesList /></ThemeProvider></MemoryRouter>,
    )

    await user.click(await screen.findByRole('button', { name: /Importer/ }))

    expect(await screen.findByText(/Importer des véhicules/)).toBeInTheDocument()
    await waitFor(() => expect(getSavedMappings).toHaveBeenCalledWith('vehicules'))
  })
})
