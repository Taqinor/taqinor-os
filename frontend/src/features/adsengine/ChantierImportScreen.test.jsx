import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB73 — Import photo chantier : succès + refus expliqué (consentement). */

const mocks = vi.hoisted(() => ({ importPhoto: vi.fn() }))

vi.mock('./adsengineApi', () => ({
  default: { chantierImport: { importPhoto: mocks.importPhoto } },
}))

import ChantierImportScreen from './ChantierImportScreen'

const renderScreen = () => render(<MemoryRouter><ChantierImportScreen /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks() })

function fill() {
  fireEvent.change(screen.getByTestId('ae-chantier-import-chantier'), { target: { value: '7' } })
  fireEvent.change(screen.getByTestId('ae-chantier-import-attachment'), { target: { value: '99' } })
  fireEvent.change(screen.getByTestId('ae-chantier-import-client'), { target: { value: '42' } })
}

describe('ChantierImportScreen', () => {
  it('importe une photo de chantier', async () => {
    mocks.importPhoto.mockResolvedValue({ data: { imported: true, message: 'Photo importée dans la créathèque.' } })
    renderScreen()
    fill()
    fireEvent.click(screen.getByTestId('ae-chantier-import-submit'))
    await waitFor(() => expect(mocks.importPhoto).toHaveBeenCalled())
    expect(screen.getByTestId('ae-chantier-import-msg').textContent).toContain('créathèque')
  })

  it('affiche le refus expliqué sans consentement', async () => {
    mocks.importPhoto.mockRejectedValue({
      response: { data: { detail: 'Consentement photo client manquant (CNDP).', blocked_reason: 'consentement_manquant' } },
    })
    renderScreen()
    fill()
    fireEvent.click(screen.getByTestId('ae-chantier-import-submit'))
    await waitFor(() => expect(screen.getByTestId('ae-chantier-import-err')).toBeTruthy())
    expect(screen.getByTestId('ae-chantier-import-err').textContent).toContain('CNDP')
  })
})
