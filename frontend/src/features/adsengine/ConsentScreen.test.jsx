import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB75 — Écran de collecte des consentements (CNDP) : enregistrer, lister avec
   statut (actif/révoqué/expiré), révoquer (retrait de rotation côté serveur). */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  revoke: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    consents: {
      list: mocks.list, create: mocks.create, revoke: mocks.revoke,
    },
  },
}))

import ConsentScreen from './ConsentScreen'

const renderScreen = () => render(<MemoryRouter><ConsentScreen /></MemoryRouter>)

const RECORDS = [
  {
    id: 1, client_nom: 'M. Actif', reference: 'ref-1',
    scopes: ['photo', 'temoignage'], is_active: true, revoked_at: null,
  },
  {
    id: 2, client_nom: 'M. Révoqué', reference: 'ref-2',
    scopes: ['photo'], is_active: false, revoked_at: '2026-07-10T10:00:00Z',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: RECORDS })
  mocks.create.mockResolvedValue({ data: { id: 3 } })
  mocks.revoke.mockResolvedValue({ data: { assets_retires: 2 } })
})

describe('ConsentScreen', () => {
  it('liste les consentements avec leur statut', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-consent-table')).toBeTruthy())
    expect(screen.getByTestId('ae-consent-status-1').textContent).toContain('Actif')
    expect(screen.getByTestId('ae-consent-status-2').textContent).toContain('Révoqué')
  })

  it('n\'affiche le bouton révoquer que pour un consentement actif', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-consent-table')).toBeTruthy())
    expect(screen.queryByTestId('ae-consent-revoke-1')).toBeTruthy()
    expect(screen.queryByTestId('ae-consent-revoke-2')).toBeNull()
  })

  it('enregistre un nouveau consentement', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-consent-form')).toBeTruthy())
    fireEvent.change(screen.getByTestId('ae-consent-nom'), { target: { value: 'Mme Neuve' } })
    fireEvent.change(screen.getByTestId('ae-consent-date'), { target: { value: '2026-02-01' } })
    fireEvent.click(screen.getByTestId('ae-consent-portee_photo'))
    fireEvent.click(screen.getByTestId('ae-consent-submit'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    const payload = mocks.create.mock.calls[0][0]
    expect(payload.client_nom).toBe('Mme Neuve')
    expect(payload.portee_photo).toBe(true)
    expect(payload.expiration).toBeUndefined()
  })

  it('révoque un consentement et recharge', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-consent-revoke-1')).toBeTruthy())
    fireEvent.click(screen.getByTestId('ae-consent-revoke-1'))
    await waitFor(() => expect(mocks.revoke).toHaveBeenCalledWith(1))
    expect(screen.getByTestId('ae-consent-msg').textContent).toContain('révoqué')
  })

  it('construit un lien WhatsApp signable', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-consent-wa-1')).toBeTruthy())
    const href = screen.getByTestId('ae-consent-wa-1').getAttribute('href')
    expect(href).toContain('https://wa.me/?text=')
  })
})
