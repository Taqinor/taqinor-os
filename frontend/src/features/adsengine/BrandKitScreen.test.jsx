import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB83 — Éditeur singleton du kit de marque : charge / crée / met à jour. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(), create: vi.fn(), update: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    brandKit: { list: mocks.list, create: mocks.create, update: mocks.update },
  },
}))

import BrandKitScreen from './BrandKitScreen'

const renderScreen = () => render(<MemoryRouter><BrandKitScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [] })
  mocks.create.mockResolvedValue({ data: { id: 9 } })
  mocks.update.mockResolvedValue({ data: {} })
})

describe('BrandKitScreen', () => {
  it('crée un kit au premier enregistrement', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-brandkit-form')).toBeTruthy())
    fireEvent.change(screen.getByTestId('ae-brandkit-name'), { target: { value: 'Taqinor' } })
    fireEvent.change(screen.getByTestId('ae-brandkit-primary'), { target: { value: '#0A6' } })
    fireEvent.change(screen.getByTestId('ae-brandkit-fonts'), { target: { value: 'Inter, Cairo' } })
    fireEvent.click(screen.getByTestId('ae-brandkit-save'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    const payload = mocks.create.mock.calls[0][0]
    expect(payload.colors.primary).toBe('#0A6')
    expect(payload.fonts).toEqual(['Inter', 'Cairo'])
  })

  it('charge et met à jour un kit existant', async () => {
    mocks.list.mockResolvedValue({ data: [{
      id: 3, name: 'Existant', logo_key: 'k', colors: { primary: '#111' },
      fonts: ['Roboto'],
    }] })
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-brandkit-name')).toBeTruthy())
    expect(screen.getByTestId('ae-brandkit-name').value).toBe('Existant')
    expect(screen.getByTestId('ae-brandkit-fonts').value).toBe('Roboto')
    fireEvent.click(screen.getByTestId('ae-brandkit-save'))
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(3, expect.any(Object)))
  })
})
